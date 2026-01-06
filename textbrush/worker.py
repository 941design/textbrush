"""Background worker for continuous image generation."""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import replace

from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.inference.base import GenerationOptions, InferenceEngine

logger = logging.getLogger(__name__)


class GenerationWorker:
    """Background worker that continuously fills buffer with generated images.

    Runs in daemon thread until stopped.
    """

    def __init__(
        self,
        engine: InferenceEngine,
        buffer: ImageBuffer,
        prompt: str,
        options: GenerationOptions,
    ):
        """Initialize worker with engine, buffer, and generation parameters.

        CONTRACT:
          Inputs:
            - engine: InferenceEngine, must be loaded (is_loaded() = True)
            - buffer: ImageBuffer to fill with images
            - prompt: non-empty string, text description for generation
            - options: GenerationOptions with seed, dimensions, steps, aspect_ratio

          Outputs: none (constructs instance)

          Invariants:
            - Worker starts in stopped state
            - Thread is not started until start() is called

          Properties:
            - Non-blocking: constructor returns immediately
            - Lazy: thread is created in start(), not __init__
        """
        self.engine = engine
        self.buffer = buffer
        self.prompt = prompt
        self.options = options
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._error_queue: queue.Queue[Exception] = queue.Queue(maxsize=1)

    def start(self) -> None:
        """Start background generation thread.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Creates and starts daemon thread
            - Thread begins generating images immediately
            - After start(), is_alive() returns True

          Properties:
            - Non-blocking: returns immediately, thread runs in background
            - Daemon thread: won't block process exit
            - Idempotent-ish: calling multiple times creates new threads (caller should not do this)

          Algorithm:
            1. Clear stop_event
            2. Create daemon thread targeting _run()
            3. Start thread
        """
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal worker to stop gracefully.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Sets stop_event to signal thread to exit
            - Calls buffer.shutdown() to unblock waiting put()
            - After stop(), thread will exit its loop

          Properties:
            - Non-blocking: returns immediately, thread stops asynchronously
            - Graceful: allows current generation to complete
            - Idempotent: calling multiple times is safe

          Algorithm:
            1. Set stop_event
            2. Call buffer.shutdown() to wake thread if blocked
        """
        self._stop_event.set()
        self.buffer.shutdown()

    def join(self, timeout: float | None = None) -> None:
        """Wait for worker thread to finish.

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely)

          Outputs: none

          Invariants:
            - Blocks until thread exits or timeout expires
            - If no thread exists, returns immediately

          Properties:
            - Blocking: waits for thread to finish
            - Timeout respected: returns after timeout even if thread still running
        """
        if self._thread:
            self._thread.join(timeout)

    def get_error(self) -> Exception | None:
        """Get error from worker if one occurred.

        CONTRACT:
          Inputs: none

          Outputs:
            - Exception if error occurred, None otherwise

          Invariants:
            - Non-destructive: error remains in queue for future checks
            - Thread-safe: can be called while worker is running

          Properties:
            - Non-blocking: returns immediately
            - Persistent: same error returned on repeated calls until cleared
            - FIFO semantics: returns oldest error if multiple occurred

          Algorithm:
            1. Try to get error from queue without blocking
            2. If error exists, put it back in queue
            3. Return error (or None if queue empty)
        """
        try:
            error = self._error_queue.get_nowait()
            self._error_queue.put_nowait(error)
            return error
        except queue.Empty:
            return None

    def clear_error(self) -> None:
        """Clear error state.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After clear_error(), get_error() returns None
            - Thread-safe: can be called while worker is running

          Properties:
            - Non-blocking: returns immediately
            - Idempotent: safe to call multiple times

          Algorithm:
            1. Try to get error from queue without blocking
            2. Discard error if exists
            3. Return without putting back
        """
        try:
            self._error_queue.get_nowait()
        except queue.Empty:
            pass

    def _run(self) -> None:
        """Worker loop - generate images until stopped.

        CONTRACT:
          Inputs: none (internal method, called by thread)

          Outputs: none (loop until stopped)

          Invariants:
            - Continuously generates images and adds to buffer
            - Increments seed after each successful generation
            - Stops when stop_event is set
            - Logs generation events and errors

          Properties:
            - Loop: runs until stop_event or unrecoverable error
            - Seed progression: seed increments by 1 for each image
            - Error resilient: catches exceptions, logs, continues (unless stopped)
            - Blocking: respects buffer.put() blocking when buffer full

          Algorithm:
            1. Log worker start
            2. Loop while not stopped:
               a. Generate image using engine.generate(prompt, options)
               b. Create BufferedImage with result.image and result.seed
               c. Put image in buffer with timeout (blocks if full)
               d. If put fails and stopped: break loop
               e. Log debug message with seed
               f. Increment seed in options for next generation
            3. Catch exceptions: log error, continue if not stopped
            4. Log worker stop
        """
        logger.info("Worker started")

        try:
            while not self._stop_event.is_set():
                try:
                    result = self.engine.generate(self.prompt, self.options)

                    buffered_image = BufferedImage(image=result.image, seed=result.seed)

                    put_success = self.buffer.put(buffered_image, timeout=1.0)

                    if not put_success and self._stop_event.is_set():
                        break

                    logger.debug(f"Generated image with seed {result.seed}")

                    next_seed = (self.options.seed or result.seed) + 1
                    self.options = replace(self.options, seed=next_seed)

                except Exception as e:
                    logger.error(f"Error during generation: {e}", exc_info=True)

                    if self._error_queue.full():
                        try:
                            self._error_queue.get_nowait()
                        except queue.Empty:
                            pass

                    try:
                        self._error_queue.put_nowait(e)
                    except queue.Full:
                        pass

                    if self._stop_event.is_set():
                        break
        finally:
            logger.info("Worker stopped")

"""Message handler integrating IPC server with TextbrushBackend.

Implements business logic for each IPC command, managing backend lifecycle and
coordinating image delivery to UI.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from textbrush.backend import TextbrushBackend
from textbrush.config import Config
from textbrush.ipc.protocol import (
    BufferStatusEvent,
    Message,
    MessageType,
    PausedEvent,
    dataclass_to_dict,
)

logger = logging.getLogger(__name__)


class MessageHandler:
    """Handler for IPC messages, integrating with TextbrushBackend.

    Manages backend lifecycle (init, generation, accept, abort) and coordinates
    image delivery via background threads.
    """

    def __init__(self, config: Config):
        """Initialize message handler.

        CONTRACT:
          Inputs:
            - config: Config instance for backend initialization

          Outputs: none (constructs instance)

          Invariants:
            - Backend is not created until handle_init()
            - No generation is running
            - No images are ready

          Properties:
            - Lazy initialization: backend created on first INIT command
            - Configuration stored: config is saved for later backend creation
        """
        self.config = config
        self.backend: TextbrushBackend | None = None
        self._current_image = None
        self._output_path: Path | None = None
        self._action_event = threading.Event()
        self._state_lock = threading.Lock()  # Protects _current_image access

    def handle_init(self, payload: dict, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle INIT command: load model and start generation.

        CONTRACT:
          Inputs:
            - payload: dict with keys: prompt (str), output_path (str|None),
                       seed (int|None), aspect_ratio (str), format (str),
                       width (int|None), height (int|None)
            - server: IPCServer instance for sending events

          Outputs: none (starts background processes, sends events)

          Invariants:
            - Creates TextbrushBackend instance
            - Loads model in background thread
            - After model loads: sends READY event
            - After READY: starts generation via backend.start_generation()
            - Starts image delivery thread to send IMAGE_READY events

          Properties:
            - Non-blocking: returns immediately, model loading happens in background
            - Error handling: sends fatal ERROR event if backend init fails
            - Sequential: READY event sent before generation starts
            - Thread coordination: image delivery waits for model load to complete

          Algorithm:
            1. Parse payload into InitCommand dataclass
            2. Create TextbrushBackend instance with stored config
            3. Define on_ready callback:
               a. Send READY event
               b. Call backend.start_generation() with prompt, seed, aspect_ratio, width, height
               c. Start image delivery thread
            4. Start background thread to:
               a. Call backend.initialize() (blocks until model loaded)
               b. Call on_ready callback
               c. If exception: log error, send fatal ERROR event
            5. Return immediately (model loading continues in background)

        Image Delivery Thread:
            Runs concurrently after model loads:
            1. Loop:
               a. Call backend.get_next_image() (blocks)
               b. If None: break (shutdown)
               c. Store as current_image
               d. Encode image as base64 PNG
               e. Send IMAGE_READY event with base64 data, seed, buffer stats
               f. Wait for skip/accept action before delivering next
            2. Exit on shutdown or error
        """
        from textbrush.ipc.protocol import InitCommand

        cmd = InitCommand(**payload)
        logger.info(
            f"INIT received: prompt='{cmd.prompt[:50]}...', "
            f"seed={cmd.seed}, width={cmd.width}, height={cmd.height}"
        )
        self.backend = TextbrushBackend(self.config)
        logger.info("Backend created, starting init thread")

        def on_ready():
            logger.info("Backend ready, sending READY event")
            server.send(Message(MessageType.READY))
            logger.info(
                f"Starting generation: prompt='{cmd.prompt[:50]}...', "
                f"seed={cmd.seed}, width={cmd.width}, height={cmd.height}"
            )
            self.backend.start_generation(
                prompt=cmd.prompt,
                seed=cmd.seed,
                aspect_ratio=cmd.aspect_ratio,
                width=cmd.width,
                height=cmd.height,
            )
            logger.info("Starting image delivery")
            self._start_image_delivery(server, cmd.output_path)

        threading.Thread(target=self._init_backend, args=(on_ready, server), daemon=True).start()

    def handle_skip(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle SKIP command: delete preview and continue to next image.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (deletes preview, clears current image, sends status)

          Invariants:
            - Preview file for current image is deleted
            - Current image reference is cleared
            - Image delivery thread is signaled to continue
            - BUFFER_STATUS event is sent with updated buffer info

          Properties:
            - Non-blocking: returns immediately after file deletion
            - Thread coordination: signals waiting delivery thread
            - Status reporting: sends buffer status after skip

          Algorithm:
            1. Delete preview file for current image
            2. Clear current_image reference (set to None)
            3. Signal image delivery thread to continue (unblock wait)
            4. If backend exists: send BUFFER_STATUS event
        """
        with self._state_lock:
            if self._current_image is not None and self.backend:
                self.backend.delete_preview(self._current_image)
            self._current_image = None
        self._signal_action()

        if self.backend:
            server.send(
                Message(
                    MessageType.BUFFER_STATUS,
                    dataclass_to_dict(
                        BufferStatusEvent(
                            count=len(self.backend.buffer),
                            max=self.backend.buffer.max_size,
                            generating=True,
                        )
                    ),
                )
            )

    def handle_accept(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle ACCEPT command: move preview to output and report path.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (moves preview file, sends event)

          Invariants:
            - If no current image: sends non-fatal ERROR event
            - If current image exists: moves from preview to output directory
            - ACCEPTED event sent with absolute path where image was moved
            - Image delivery thread is signaled to continue

          Properties:
            - Blocking: waits for file move to complete
            - Error handling: sends non-fatal ERROR if no image or move fails
            - Path reporting: sends absolute path in ACCEPTED event
            - Uses stored output_path or auto-generates via backend

          Algorithm:
            1. Check if current_image exists
            2. If not: send non-fatal ERROR event, return
            3. Try:
               a. Call backend.accept_from_preview(current_image, output_path)
               b. Get absolute path returned
               c. Send ACCEPTED event with path
            4. Catch exceptions:
               a. Log error
               b. Send non-fatal ERROR event
            5. Signal image delivery thread to continue
        """
        from textbrush.ipc.protocol import AcceptedEvent, ErrorEvent

        with self._state_lock:
            if not self._current_image or not self.backend:
                server.send(
                    Message(
                        MessageType.ERROR,
                        dataclass_to_dict(ErrorEvent(message="No image to accept", fatal=False)),
                    )
                )
                return

        try:
            path = self.backend.accept_from_preview(self._current_image, self._output_path)
            logger.info(f"Image moved to: {path.absolute()}")
            server.send(
                Message(
                    MessageType.ACCEPTED,
                    dataclass_to_dict(AcceptedEvent(path=str(path.absolute()))),
                )
            )
        except Exception as e:
            logger.error(f"Failed to accept image: {e}")
            server.send(
                Message(
                    MessageType.ERROR, dataclass_to_dict(ErrorEvent(message=str(e), fatal=False))
                )
            )

        self._signal_action()

    def handle_abort(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle ABORT command: stop generation and cleanup.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (stops backend, sends event)

          Invariants:
            - If backend exists: backend.abort() is called
            - All generation stops
            - Buffer is cleared
            - ABORTED event is sent
            - Server shutdown is triggered

          Properties:
            - Blocking: waits for backend.abort() to complete
            - Cleanup: releases all resources
            - Terminal: server will exit after this command
            - Idempotent: safe to call even if no backend exists

          Algorithm:
            1. If backend exists: call backend.abort() (blocks)
            2. Send ABORTED event
            3. Trigger server shutdown (server.shutdown())
        """
        if self.backend:
            self.backend.abort()
        server.send(Message(MessageType.ABORTED))
        server.shutdown()

    def handle_status(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle STATUS command: report current buffer status.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (sends status event)

          Invariants:
            - If backend exists: sends BUFFER_STATUS event with current stats
            - If no backend: no event sent (or could send error)

          Properties:
            - Non-blocking: returns immediately
            - Read-only: does not modify state
            - Optional: mostly for debugging/UI updates

          Algorithm:
            1. If backend exists:
               a. Send BUFFER_STATUS event with:
                  - count: len(backend.buffer)
                  - max: backend.buffer.max_size
                  - generating: backend._worker is not None
        """
        if self.backend:
            server.send(
                Message(
                    MessageType.BUFFER_STATUS,
                    dataclass_to_dict(
                        BufferStatusEvent(
                            count=len(self.backend.buffer),
                            max=self.backend.buffer.max_size,
                            generating=self.backend._worker is not None,
                        )
                    ),
                )
            )

    def handle_update_config(self, payload: dict, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle UPDATE_CONFIG command: restart generation with new configuration.

        CONTRACT:
          Inputs:
            - payload: dict with keys: prompt (str), aspect_ratio (str),
                       width (int|None), height (int|None)
            - server: IPCServer instance for sending events

          Outputs: none (modifies backend state, sends events)

          Invariants:
            - If backend not initialized: sends non-fatal ERROR event
            - If backend exists:
              * Calls backend.abort() to stop current worker and clear buffer
              * Calls backend.start_generation() with new prompt, aspect_ratio, dimensions
              * Sends BUFFER_STATUS event showing reset buffer (count=0)
              * Image delivery thread continues, will deliver new images

          Properties:
            - Thread-safe: uses backend's thread-safe abort() and start_generation()
            - Non-blocking: returns quickly after starting restart sequence
            - Continuous delivery: image delivery thread not restarted, continues running
            - Seed handling: new generation uses auto-generated seeds (seed=None)
            - Buffer cleared: all pending images from old generation are purged
            - Error handling: sends non-fatal ERROR if backend not initialized
            - Dimension priority: explicit width/height override aspect_ratio

          Algorithm:
            1. Parse payload into UpdateConfigCommand dataclass
            2. If backend is None:
               a. Send non-fatal ERROR event ("Backend not initialized")
               b. Return
            3. Validate aspect_ratio only if no explicit dimensions provided
            4. Log config update with truncated prompt
            5. Call backend.abort():
               - Stops current GenerationWorker thread
               - Clears buffer via buffer.clear()
               - Waits for worker to finish
            6. Call backend.start_generation():
               - Creates new GenerationWorker with updated config
               - Seed is None (auto-generate)
               - Starts new worker thread
            7. Send BUFFER_STATUS event:
               - count: 0 (buffer was just cleared)
               - max: backend.buffer.max_size
               - generating: True (new worker started)
            8. Return (image delivery thread will deliver new images automatically)

        Thread Safety:
          - backend.abort() is thread-safe: stops worker, waits for completion
          - backend.start_generation() is thread-safe: creates new worker
          - buffer.clear() is atomic (called by abort())
          - Image delivery thread continues running, will automatically:
            * Wait on empty buffer after clear
            * Receive new images when new worker produces them
            * No race conditions: buffer operations are thread-safe
        """
        from textbrush.ipc.protocol import ErrorEvent, UpdateConfigCommand

        cmd = UpdateConfigCommand(**payload)

        if not self.backend:
            server.send(
                Message(
                    MessageType.ERROR,
                    dataclass_to_dict(ErrorEvent(message="Backend not initialized", fatal=False)),
                )
            )
            return

        # Only validate aspect_ratio if using preset (not "custom") and no explicit dimensions
        if cmd.aspect_ratio != "custom" and cmd.width is None and cmd.height is None:
            valid_aspect_ratios = {"1:1", "16:9", "9:16"}
            if cmd.aspect_ratio not in valid_aspect_ratios:
                valid_values = ", ".join(sorted(valid_aspect_ratios))
                error_msg = (
                    f"Invalid aspect_ratio: {cmd.aspect_ratio}. "
                    f"Must be one of: {valid_values}, or 'custom' with dimensions"
                )
                server.send(
                    Message(
                        MessageType.ERROR,
                        dataclass_to_dict(ErrorEvent(message=error_msg, fatal=False)),
                    )
                )
                return

        if not cmd.prompt or not cmd.prompt.strip():
            server.send(
                Message(
                    MessageType.ERROR,
                    dataclass_to_dict(ErrorEvent(message="Prompt cannot be empty", fatal=False)),
                )
            )
            return

        if cmd.width and cmd.height:
            dims_info = f"width={cmd.width}, height={cmd.height}"
        else:
            dims_info = f"aspect_ratio={cmd.aspect_ratio}"
        logger.info(f"UPDATE_CONFIG: prompt='{cmd.prompt[:50]}...', {dims_info}")
        self.backend.abort()
        self.backend.start_generation(
            prompt=cmd.prompt,
            seed=None,
            aspect_ratio=cmd.aspect_ratio,
            width=cmd.width,
            height=cmd.height,
        )

        server.send(
            Message(
                MessageType.BUFFER_STATUS,
                dataclass_to_dict(
                    BufferStatusEvent(
                        count=0,
                        max=self.backend.buffer.max_size,
                        generating=True,
                    )
                ),
            )
        )

    def handle_pause(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle PAUSE command: toggle pause/resume generation.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (modifies backend state, sends event)

          Invariants:
            - If backend not initialized: sends non-fatal ERROR event
            - If backend exists:
              * If currently running: pauses generation
              * If currently paused: resumes generation
            - PAUSED event sent with new pause state

          Properties:
            - Toggle behavior: alternates between paused and running
            - Non-blocking: returns immediately
            - Thread-safe: uses backend's thread-safe pause/resume

          Algorithm:
            1. If backend is None:
               a. Send non-fatal ERROR event ("Backend not initialized")
               b. Return
            2. Check current pause state via backend.is_paused()
            3. If paused: call backend.resume_generation()
            4. If running: call backend.pause_generation()
            5. Send PAUSED event with new state
            6. Send BUFFER_STATUS event with updated generating flag
        """
        from textbrush.ipc.protocol import ErrorEvent

        if not self.backend:
            server.send(
                Message(
                    MessageType.ERROR,
                    dataclass_to_dict(ErrorEvent(message="Backend not initialized", fatal=False)),
                )
            )
            return

        is_paused = self.backend.is_paused()

        if is_paused:
            self.backend.resume_generation()
            new_paused = False
        else:
            self.backend.pause_generation()
            new_paused = True

        logger.info(f"Generation {'paused' if new_paused else 'resumed'}")

        server.send(
            Message(
                MessageType.PAUSED,
                dataclass_to_dict(PausedEvent(paused=new_paused)),
            )
        )

        server.send(
            Message(
                MessageType.BUFFER_STATUS,
                dataclass_to_dict(
                    BufferStatusEvent(
                        count=len(self.backend.buffer),
                        max=self.backend.buffer.max_size,
                        generating=not new_paused,
                    )
                ),
            )
        )

    def _start_image_delivery(self, server: "IPCServer", output_path: str | None) -> None:  # type: ignore  # noqa: F821
        """Start background thread delivering images to UI.

        Helper method for handle_init. Runs image delivery loop in daemon thread.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events
            - output_path: Optional path for saving accepted images

          Outputs: none (starts background thread)

          Invariants:
            - Thread runs until backend.get_next_image() returns None
            - Each image is encoded as base64 PNG
            - IMAGE_READY events sent for each image
            - Thread blocks waiting for skip/accept between images

          Properties:
            - Daemon thread: exits when main thread exits
            - Error handling: logs errors but continues
            - Thread coordination: uses threading primitives to wait for actions

          Algorithm:
            1. Store output_path for later use in accept
            2. Define deliver_loop function:
               a. Loop:
                  - Call backend.get_next_image() (blocks)
                  - If None: break
                  - Store as self._current_image
                  - Encode image as base64 PNG:
                    * Create BytesIO buffer
                    * Save image to buffer as PNG
                    * Base64 encode buffer contents
                  - Send IMAGE_READY event with:
                    * image_data: base64 string
                    * seed: buffered.seed
                    * buffer_count: len(backend.buffer)
                    * buffer_max: backend.buffer.max_size
                  - Wait for skip/accept action (block on threading.Event or similar)
               b. Exit loop on shutdown
            3. Start daemon thread running deliver_loop
        """
        from textbrush.ipc.protocol import ErrorEvent, ImageReadyEvent

        self._output_path = Path(output_path) if output_path else None

        def deliver_loop():
            logger.info("Image delivery loop started")
            while True:
                try:
                    logger.debug("Waiting for next image from buffer...")
                    # Use None timeout to wait indefinitely - FLUX can take 60+ seconds per image
                    buffered = self.backend.get_next_image(timeout=None)
                    if buffered is None:
                        logger.info("No more images, delivery loop ending")
                        break

                    # Check for worker errors during generation
                    worker_error = self.backend.check_worker_error()
                    if worker_error:
                        logger.error(f"Worker error detected: {worker_error}")
                        server.send(
                            Message(
                                MessageType.ERROR,
                                dataclass_to_dict(
                                    ErrorEvent(message=str(worker_error), fatal=True)
                                ),
                            )
                        )
                        break

                    with self._state_lock:
                        self._current_image = buffered

                    logger.info(f"Image ready: seed={buffered.seed}")

                    # Save to preview directory with full metadata in PNG tEXt chunks
                    preview_path = self.backend.save_to_preview(buffered)
                    logger.info(f"Saved preview: {preview_path}")

                    server.send(
                        Message(
                            MessageType.IMAGE_READY,
                            dataclass_to_dict(
                                ImageReadyEvent(
                                    path=str(preview_path.absolute()),
                                    buffer_count=len(self.backend.buffer),
                                    buffer_max=self.backend.buffer.max_size,
                                )
                            ),
                        )
                    )

                    self._wait_for_action()

                except Exception as e:
                    logger.error(f"Image delivery error: {e}")
                    break

        threading.Thread(target=deliver_loop, daemon=True).start()

    def _wait_for_action(self) -> None:
        """Block until skip or accept action is taken.

        Helper for image delivery thread. Implements synchronization primitive
        that blocks delivery thread until UI responds with skip/accept.

        CONTRACT:
          Inputs: none

          Outputs: none (blocks until signaled)

          Invariants:
            - Blocks current thread
            - Unblocks when _signal_action() is called

          Properties:
            - Thread synchronization: uses threading primitives
            - One-time use per image: reset for each new image

          Algorithm:
            Use threading.Event or threading.Condition to block:
            1. Wait on event/condition
            2. Return when signaled
        """
        self._action_event.wait()
        self._action_event.clear()

    def _signal_action(self) -> None:
        """Signal image delivery thread to continue.

        Helper for skip/accept handlers. Unblocks waiting delivery thread.

        CONTRACT:
          Inputs: none

          Outputs: none (signals waiting thread)

          Invariants:
            - Wakes waiting delivery thread
            - Safe to call even if no thread waiting

          Properties:
            - Thread synchronization: uses same primitive as _wait_for_action()
            - Non-blocking: returns immediately

          Algorithm:
            Use threading.Event or threading.Condition to signal:
            1. Set event or notify condition
            2. Return
        """
        self._action_event.set()

    def _init_backend(self, on_ready, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Load model in background and call ready callback.

        Helper for handle_init. Runs in background thread.

        CONTRACT:
          Inputs:
            - on_ready: callback function to call after model loads
            - server: IPCServer instance for sending error events

          Outputs: none (calls callback or sends error)

          Invariants:
            - Calls backend.initialize() (blocks for model loading)
            - If successful: calls on_ready()
            - If exception: logs error, sends fatal ERROR event

          Properties:
            - Blocking: waits for model to load
            - Error handling: sends fatal error if init fails
            - Callback: on_ready() called only after successful init

          Algorithm:
            1. Try:
               a. Call self.backend.initialize() (blocks)
               b. Call on_ready()
            2. Catch Exception as e:
               a. Log error
               b. Send fatal ERROR event with exception message
        """
        from textbrush.ipc.protocol import ErrorEvent

        try:
            logger.info("Initializing backend (loading model)...")
            self.backend.initialize()
            logger.info("Backend initialized successfully")
            on_ready()
        except Exception as e:
            logger.error(f"Backend init failed: {e}", exc_info=True)
            server.send(
                Message(
                    MessageType.ERROR, dataclass_to_dict(ErrorEvent(message=str(e), fatal=True))
                )
            )

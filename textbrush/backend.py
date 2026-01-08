"""Backend coordinator for textbrush image generation.

Orchestrates model loading, generation workflow, and image buffer management.
"""

from __future__ import annotations

from pathlib import Path

from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.config import Config
from textbrush.inference.base import GenerationOptions
from textbrush.inference.factory import create_engine
from textbrush.worker import GenerationWorker


class TextbrushBackend:
    """High-level coordinator for inference backend.

    Manages model lifecycle, worker threads, and image buffer.
    """

    def __init__(self, config: Config):
        """Initialize backend with configuration.

        CONTRACT:
          Inputs:
            - config: Config object with inference and model settings

          Outputs: none (constructs instance)

          Invariants:
            - Engine is created but not loaded
            - Buffer is created with config.model.buffer_size
            - Worker is not started

          Properties:
            - Lazy loading: model is not loaded until initialize()
            - Configuration immutable: config is stored, not modified
        """
        self.config = config
        self.engine = create_engine(config.inference.backend)
        self.buffer = ImageBuffer(max_size=config.model.buffer_size)
        self._worker: GenerationWorker | None = None

    def initialize(self) -> None:
        """Load model - call before starting generation.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After initialize(), engine.is_loaded() = True
            - Model is ready for inference

          Properties:
            - Blocking: waits for model to load completely
            - Idempotent: safe to call multiple times (engine handles it)
            - Must be called before start_generation()

          Algorithm:
            1. Call engine.load()
        """
        self.engine.load()

    def start_generation(
        self,
        prompt: str,
        seed: int | None = None,
        aspect_ratio: str = "1:1",
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        """Begin background image generation.

        CONTRACT:
          Inputs:
            - prompt: non-empty string, text description
            - seed: optional integer seed (None = auto-generate)
            - aspect_ratio: string, one of "1:1", "16:9", "9:16", or "custom"
            - width: optional int, image width in pixels (overrides aspect_ratio)
            - height: optional int, image height in pixels (overrides aspect_ratio)

          Outputs: none (modifies internal state)

          Invariants:
            - Engine must be loaded (initialize() called) before start_generation()
            - Creates GenerationWorker with prompt and options
            - Starts worker thread
            - After start_generation(), worker is filling buffer
            - If both width and height are provided, they override aspect_ratio

          Properties:
            - Non-blocking: returns immediately, generation runs in background
            - Prerequisites: initialize() must be called first (raises RuntimeError if not)
            - Worker lifecycle: creates new worker (any existing worker should be stopped first)
            - Buffer reset: resets shutdown state to allow new images to be delivered

          Algorithm:
            1. Check engine.is_loaded(), raise RuntimeError if not loaded
            2. Reset buffer shutdown state to allow put/get operations
            3. Create GenerationOptions with seed, aspect_ratio, and optional dimensions
            4. Create GenerationWorker with engine, buffer, prompt, options
            5. Start worker thread
        """
        if not self.engine.is_loaded():
            raise RuntimeError("Engine not loaded. Call initialize() before start_generation().")

        self.buffer.reset_shutdown()

        options = GenerationOptions(
            seed=seed,
            steps=4,
            aspect_ratio=aspect_ratio,
            width=width if width is not None else 512,
            height=height if height is not None else 512,
        )
        self._worker = GenerationWorker(
            engine=self.engine,
            buffer=self.buffer,
            prompt=prompt,
            options=options,
        )
        self._worker.start()

    def get_next_image(self, timeout: float | None = 30.0) -> BufferedImage | None:
        """Get next generated image (blocks if buffer empty).

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely, default 30.0)

          Outputs:
            - BufferedImage if available, None if buffer shutdown or timeout

          Invariants:
            - Removes and returns oldest image from buffer
            - Blocks until image available, buffer shutdown, or timeout

          Properties:
            - Blocking: waits for image if buffer empty
            - FIFO: returns images in generation order
            - Thread-safe: can be called while worker is generating
            - Timeout protection: returns None if timeout expires

          Algorithm:
            1. Call buffer.get(timeout) and return result
        """
        return self.buffer.get(timeout=timeout)

    def skip_current(self, timeout: float | None = 30.0) -> BufferedImage | None:
        """Skip current image and get next.

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely, default 30.0)

          Outputs:
            - BufferedImage (next image), or None if buffer shutdown or timeout

          Invariants:
            - Discards current image (calls buffer.get())
            - Returns next image in queue

          Properties:
            - Blocking: waits for image if buffer empty
            - Discard: current image is removed and not saved
            - Timeout protection: returns None if timeout expires

          Algorithm:
            1. Delegate to get_next_image(timeout) for implementation
        """
        return self.get_next_image(timeout=timeout)

    def accept_current(self, output_path: Path | None = None) -> Path:
        """Save current image and return path.

        CONTRACT:
          Inputs:
            - output_path: optional Path to save image (None = auto-generate)

          Outputs:
            - Path: absolute path where image was saved

          Invariants:
            - Current image (from buffer.peek()) is saved to disk
            - Image remains in buffer (use get_next_image() to advance)
            - If output_path is None, generates path based on seed or timestamp

          Properties:
            - Non-blocking: returns after save completes
            - Side effect: writes file to disk
            - Error: raises RuntimeError if no image to accept

          Algorithm:
            1. Peek at current image
            2. If no image: raise RuntimeError
            3. If output_path is None: generate path using _generate_output_path()
            4. Save image to output_path
            5. Return output_path
        """
        current = self.buffer.peek()
        if not current:
            raise RuntimeError("No image to accept")

        if output_path is None:
            output_path = self._generate_output_path()

        current.image.save(output_path)
        return output_path

    def abort(self) -> None:
        """Stop generation and discard all images.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Worker is stopped
            - Buffer is cleared
            - After abort(), no generation is happening
            - All temp files from discarded images are deleted

          Properties:
            - Blocking: waits for worker to stop (with timeout)
            - Cleanup: discards all buffered images and deletes temp files
            - Idempotent: safe to call multiple times

          Algorithm:
            1. If worker exists: stop worker and join with timeout
            2. Clear buffer (which calls cleanup() on all items)
        """
        if self._worker:
            self._worker.stop()
            self._worker.join(timeout=5.0)
        self.buffer.clear()

    def shutdown(self) -> None:
        """Clean shutdown of backend.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Worker is stopped
            - Buffer is cleared
            - Model is unloaded

          Properties:
            - Blocking: waits for worker and unload to complete
            - Cleanup: releases all resources
            - Idempotent: safe to call multiple times

          Algorithm:
            1. Call abort() to stop worker and clear buffer
            2. Call engine.unload()
        """
        self.abort()
        self.engine.unload()

    def check_worker_error(self) -> Exception | None:
        """Check if worker has encountered an error.

        CONTRACT:
          Inputs: none

          Outputs:
            - Exception if worker encountered an error, None otherwise

          Invariants:
            - Non-destructive: error state persists in worker
            - Returns None if no worker exists

          Properties:
            - Non-blocking: returns immediately
            - Delegates to worker.get_error()
            - Thread-safe: can be called while worker is running

          Algorithm:
            1. If worker exists: return worker.get_error()
            2. Otherwise: return None
        """
        if self._worker:
            return self._worker.get_error()
        return None

    def pause_generation(self) -> None:
        """Pause image generation without stopping.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - If worker exists: worker.pause() is called
            - Current generation completes before pause takes effect
            - is_paused() returns True after this call (if worker exists)

          Properties:
            - Non-blocking: returns immediately
            - Graceful: current generation completes
            - Idempotent: safe to call multiple times
            - No-op if no worker exists
        """
        if self._worker:
            self._worker.pause()

    def resume_generation(self) -> None:
        """Resume paused image generation.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - If worker exists: worker.resume() is called
            - is_paused() returns False after this call (if worker exists)

          Properties:
            - Non-blocking: returns immediately
            - Idempotent: safe to call multiple times
            - No-op if no worker exists
        """
        if self._worker:
            self._worker.resume()

    def is_paused(self) -> bool:
        """Check if generation is paused.

        CONTRACT:
          Inputs: none

          Outputs:
            - True if paused, False if running or no worker

          Properties:
            - Thread-safe: can be called from any thread
            - Non-blocking: returns immediately
        """
        if self._worker:
            return self._worker.is_paused()
        return False

    def _generate_output_path(self) -> Path:
        """Generate output path for accepted image.

        CONTRACT:
          Inputs: none

          Outputs:
            - Path: absolute path in config.output.directory with generated filename

          Invariants:
            - Path is in config.output.directory
            - Filename includes timestamp or seed
            - Extension matches config.output.format

          Properties:
            - Unique: generates unique filename for each call
            - Deterministic structure: uses config settings

          Algorithm:
            1. Get config.output.directory
            2. Generate filename based on timestamp and/or seed
            3. Add extension from config.output.format
            4. Return Path object
        """
        from datetime import datetime

        output_dir = self.config.output.directory
        output_dir.mkdir(parents=True, exist_ok=True)

        current_image = self.buffer.peek()
        if current_image is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_seed{current_image.seed}.{self.config.output.format}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}.{self.config.output.format}"

        return output_dir / filename

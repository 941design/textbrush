"""Message handler integrating IPC server with TextbrushBackend.

Implements business logic for each IPC command, managing backend lifecycle and
coordinating image delivery to UI.
"""

from __future__ import annotations

import logging
import threading

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.config import Config
from textbrush.ipc.protocol import (
    Message,
    MessageType,
    dataclass_to_dict,
)
from textbrush.model.weights import download_flux_weights, is_flux_available
from textbrush.paths import display_path

_MISSING_MODEL_MESSAGE = """\
FLUX.1 schnell model not found. To set up the model:

1. Get a HuggingFace token from https://huggingface.co/settings/tokens
2. Accept the license at https://huggingface.co/black-forest-labs/FLUX.1-schnell
3. Run: HUGGINGFACE_HUB_TOKEN=hf_xxx textbrush --download-model

Or manually place model files in the HuggingFace cache directory."""

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
            - delivered_images list is empty

          Properties:
            - Lazy initialization: backend created on first INIT command
            - Configuration stored: config is saved for later backend creation
            - delivered_images: backend owns authoritative list of delivered images
        """
        self.config = config
        self.backend: TextbrushBackend | None = None
        self._current_image = None
        self._action_event = threading.Event()
        self._state_lock = threading.Lock()  # Protects _current_image and _delivered_images access
        self._delivered_images: list[BufferedImage] = []  # Backend-owned list of delivered images
        self._next_index = 0  # Monotonic counter for image indices
        self._image_index_map: dict[int, BufferedImage] = {}  # Maps index → BufferedImage
        self._deleted_indices: set[int] = set()  # Tracks soft-deleted indices
        self._delivery_order: list[int] = []  # Records order images were delivered to frontend
        self._current_state: str | None = None  # Tracks current backend state
        self._current_prompt: str = ""  # Tracks current generation prompt for state_changed events
        self._generation_started = False  # True after backend.start_generation() succeeds
        self._pending_startup_config: dict | None = None  # Latest UPDATE_CONFIG before start
        self._pending_start_paused = False  # Pause intent before worker starts

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
        self._current_prompt = cmd.prompt  # Store prompt for state_changed events
        self._emit_state_changed(server, "loading")
        self.backend = TextbrushBackend(self.config)
        self._generation_started = False
        self._pending_startup_config = None
        self._pending_start_paused = False
        logger.info("Backend created, starting init thread")

        def on_ready():
            pending_config = self._pending_startup_config
            start_paused = self._pending_start_paused
            start_prompt = cmd.prompt
            start_aspect_ratio = cmd.aspect_ratio
            start_width = cmd.width
            start_height = cmd.height
            if pending_config is not None:
                start_prompt = pending_config["prompt"]
                start_aspect_ratio = pending_config["aspect_ratio"]
                start_width = pending_config["width"]
                start_height = pending_config["height"]
                logger.info(
                    "Applying queued UPDATE_CONFIG before initial generation: "
                    f"prompt='{start_prompt[:50]}...', "
                    f"aspect_ratio={start_aspect_ratio}, width={start_width}, height={start_height}"
                )
                self._pending_startup_config = None

            # Capture prompt at registration time to avoid races with later updates.
            generation_prompt = start_prompt

            def on_generation_start(seed: int, queue_position: int) -> None:
                logger.debug(f"Generation started: seed={seed}, queue_position={queue_position}")
                self._emit_state_changed(server, "generating", prompt=generation_prompt)

            logger.info(
                f"Starting generation: prompt='{start_prompt[:50]}...', "
                f"seed={cmd.seed}, width={start_width}, height={start_height}"
            )
            self.backend.start_generation(
                prompt=start_prompt,
                seed=cmd.seed,
                aspect_ratio=start_aspect_ratio,
                width=start_width,
                height=start_height,
                on_generation_start=on_generation_start,
                start_paused=start_paused,
            )
            self._generation_started = True
            self._current_prompt = start_prompt
            if start_paused:
                logger.info("Backend ready, emitting state_changed(paused)")
                self._emit_state_changed(server, "paused")
            else:
                logger.info("Backend ready, emitting state_changed(idle)")
                self._emit_state_changed(server, "idle")
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
        """
        with self._state_lock:
            if self._current_image is not None and self.backend:
                self.backend.delete_preview(self._current_image)
            self._current_image = None
        self._signal_action()

    def handle_accept(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle ACCEPT command: move all delivered images to output and report paths.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (moves all preview files, sends event, exits process)

          Invariants:
            - If no delivered images: sends non-fatal ERROR event
            - If delivered_images non-empty: moves all from preview to output directory
            - ACCEPTED event sent with all absolute paths where images were moved
            - delivered_images list is cleared after successful save
            - Image delivery thread is NOT signaled (process will exit)

          Properties:
            - Blocking: waits for all file moves to complete
            - Error handling: sends non-fatal ERROR if no images or move fails
            - Batch operation: all delivered images saved in one operation
            - Order preservation: paths in ACCEPTED event match delivery order
            - Terminal: process exits after this (no need to signal delivery thread)

          Algorithm:
            1. Acquire state lock
            2. Check if delivered_images is empty or backend is None
            3. If empty: send non-fatal ERROR event "No images to accept", return
            4. Copy delivered_images to local variable
            5. Clear delivered_images list
            6. Release lock
            7. Try:
               a. Call backend.accept_all(images)
               b. Get list of absolute paths returned
               c. Create display_paths list using display_path() for each
               d. Send ACCEPTED event with paths and display_paths
               e. Log success
            8. Catch exceptions:
               a. Log error
               b. Send non-fatal ERROR event
            9. Do NOT signal delivery thread (process will exit via Rust handler)
        """
        from textbrush.ipc.protocol import AcceptedEvent, ErrorEvent

        with self._state_lock:
            # Build list of non-deleted images in delivery order (viewing order)
            images_to_accept = [
                self._image_index_map[idx]
                for idx in self._delivery_order
                if idx in self._image_index_map and idx not in self._deleted_indices
            ]

            if not images_to_accept or not self.backend:
                server.send(
                    Message(
                        MessageType.ERROR,
                        dataclass_to_dict(ErrorEvent(message="No images to accept", fatal=False)),
                    )
                )
                return

            # Clear state after successful collection (backend no longer owns these)
            self._image_index_map.clear()
            self._deleted_indices.clear()
            self._delivery_order.clear()
            self._delivered_images.clear()  # Keep for compatibility

        try:
            # Batch save all delivered images
            paths = self.backend.accept_all(images_to_accept)
            display_paths = [display_path(p) for p in paths]

            logger.info(f"Accepted {len(paths)} images")
            for p in display_paths:
                logger.info(f"  - {p}")

            server.send(
                Message(
                    MessageType.ACCEPTED,
                    dataclass_to_dict(
                        AcceptedEvent(
                            paths=[str(p.absolute()) for p in paths],
                            display_paths=display_paths,
                        )
                    ),
                )
            )
        except Exception as e:
            logger.error(f"Failed to accept images: {e}")
            server.send(
                Message(
                    MessageType.ERROR, dataclass_to_dict(ErrorEvent(message=str(e), fatal=False))
                )
            )

        # Do NOT signal action - process will exit after ACCEPTED event

    def handle_abort(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle ABORT command: stop generation, delete all delivered images, cleanup.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (stops backend, deletes temp files, sends event)

          Invariants:
            - If backend exists: backend.abort() is called
            - All delivered_images temp files are deleted
            - delivered_images list is cleared
            - All generation stops
            - Buffer is cleared
            - ABORTED event is sent
            - Server shutdown is triggered

          Properties:
            - Blocking: waits for backend.abort() and file deletions to complete
            - Comprehensive cleanup: deletes all delivered_images temp files
            - Terminal: server will exit after this command
            - Idempotent: safe to call even if no backend exists

          Algorithm:
            1. Acquire state lock
            2. Copy delivered_images to local variable
            3. Clear delivered_images list
            4. Release lock
            5. For each buffered_image in copied list:
               a. Call buffered_image.cleanup() to delete temp file
            6. If backend exists: call backend.abort() (blocks - clears buffer)
            7. Send ABORTED event
            8. Trigger server shutdown (server.shutdown())
        """
        with self._state_lock:
            # Get all images for cleanup (including deleted ones that still have temp files)
            images_to_cleanup = list(self._image_index_map.values())
            self._image_index_map.clear()
            self._deleted_indices.clear()
            self._delivered_images.clear()  # Keep for compatibility
            self._generation_started = False
            self._pending_startup_config = None

        # Delete all delivered images temp files
        for buffered_image in images_to_cleanup:
            buffered_image.cleanup()

        if self.backend:
            self.backend.abort()

        server.send(Message(MessageType.ABORTED))
        server.shutdown()

    def handle_status(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle STATUS command: deprecated (buffer status removed).

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (no-op, buffer status is deprecated)

          Invariants:
            - DEPRECATED: Buffer status concept removed from state sync protocol
            - This handler remains for backwards compatibility but does nothing

          Properties:
            - Non-blocking: returns immediately
            - No-op: does not send any event
        """
        logger.debug("STATUS command received (deprecated, no-op)")

    def handle_update_config(self, payload: dict, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle UPDATE_CONFIG command: update generation configuration.

        CONTRACT:
          Inputs:
            - payload: dict with keys: prompt (str), aspect_ratio (str),
                       width (int|None), height (int|None)
            - server: IPCServer instance for sending events

          Outputs: none (modifies backend state, sends events)

          Invariants:
            - If backend not initialized: sends non-fatal ERROR event
            - If backend exists:
              * Calls backend.update_config() to update worker settings
              * Buffer is cleared (old images are stale)
              * Sends BUFFER_STATUS event showing reset buffer (count=0)
              * Image delivery thread continues, will deliver new images
            - Pause state is preserved: worker thread stays alive, not restarted

          Properties:
            - Thread-safe: uses backend's thread-safe update_config()
            - Non-blocking: returns quickly after updating configuration
            - Continuous delivery: image delivery thread not restarted, continues running
            - Seed handling: new generation uses auto-generated seeds (seed=None)
            - Buffer cleared: all pending images from old generation are purged
            - Error handling: sends non-fatal ERROR if backend not initialized
            - Dimension priority: explicit width/height override aspect_ratio
            - Pause preservation: worker thread stays alive, pause state unchanged

          Algorithm:
            1. Parse payload into UpdateConfigCommand dataclass
            2. If backend is None:
               a. Send non-fatal ERROR event ("Backend not initialized")
               b. Return
            3. Validate aspect_ratio only if no explicit dimensions provided
            4. Log config update with truncated prompt
            5. Get current pause state via backend.is_paused()
            6. Call backend.update_config():
               - Updates worker's prompt and options in-place
               - Clears buffer (old images are stale)
               - Worker thread stays alive (not stopped/restarted)
            7. Send BUFFER_STATUS event:
               - count: 0 (buffer was just cleared)
               - max: backend.buffer.max_size
               - generating: True only if not paused
            8. Clear current_image (now stale) and signal delivery thread to continue
            9. Return (image delivery thread will deliver new images automatically)

        Thread Safety:
          - backend.update_config() is thread-safe: updates worker config
          - buffer.clear() is atomic (called by update_config())
          - Image delivery thread continues running, will automatically:
            * Wait on empty buffer after clear
            * Receive new images when worker produces them
            * No race conditions: buffer operations are thread-safe
        """
        from textbrush.ipc.protocol import BufferStatusEvent, ErrorEvent, UpdateConfigCommand

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

        # Store new prompt for state_changed events
        self._current_prompt = cmd.prompt

        # Capture prompt at registration time to avoid race conditions with subsequent
        # UPDATE_CONFIG calls. The callback may fire after _current_prompt has been
        # changed by another UPDATE_CONFIG, so we need to use the prompt value that
        # was active when this update_config was called.
        generation_prompt = cmd.prompt

        def on_generation_start(seed: int, queue_position: int) -> None:
            """Callback invoked when worker starts generating an image."""
            logger.debug(f"Generation started: seed={seed}, queue_position={queue_position}")
            self._emit_state_changed(server, "generating", prompt=generation_prompt)

        try:
            self.backend.update_config(
                prompt=cmd.prompt,
                aspect_ratio=cmd.aspect_ratio,
                width=cmd.width,
                height=cmd.height,
                on_generation_start=on_generation_start,
            )
            self._generation_started = True
        except RuntimeError as e:
            # During model loading the backend exists but worker is not started yet.
            # Queue latest config instead of surfacing an error to the server loop.
            if "No worker to update" in str(e):
                self._pending_startup_config = {
                    "prompt": cmd.prompt,
                    "aspect_ratio": cmd.aspect_ratio,
                    "width": cmd.width,
                    "height": cmd.height,
                }
                logger.info(
                    "Queued UPDATE_CONFIG while backend is loading; "
                    "will apply before initial generation starts"
                )
                return
            raise

        # Send BUFFER_STATUS event showing reset buffer
        is_generating = not self.backend.is_paused()
        server.send(
            Message(
                MessageType.BUFFER_STATUS,
                dataclass_to_dict(
                    BufferStatusEvent(
                        count=0,
                        max=self.backend.buffer.max_size,
                        generating=is_generating,
                    )
                ),
            )
        )

        # Signal delivery thread to continue - it may be waiting for action after
        # delivering the previous image. Clear current image since it's now stale.
        with self._state_lock:
            self._current_image = None
        self._signal_action()

    def handle_pause(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle PAUSE command: toggle pause/resume generation.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (modifies backend state, sends state_changed event)

          Invariants:
            - If backend not initialized: sends non-fatal ERROR event
            - If backend exists:
              * If currently running: pauses generation
              * If currently paused: resumes generation
            - state_changed event sent with new state ("paused" or "generating")

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
            5. Send state_changed event with appropriate state
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

        # During startup/loading, preserve pause intent and reflect it in state.
        # This avoids emitting paused while silently dropping the request.
        if not self._generation_started:
            self._pending_start_paused = not self._pending_start_paused
            if self._pending_start_paused:
                self._emit_state_changed(server, "paused")
            else:
                if self._current_state == "loading":
                    self._emit_state_changed(server, "loading")
                else:
                    self._emit_state_changed(server, "idle")
            return

        is_paused = self.backend.is_paused()

        if is_paused:
            self.backend.resume_generation()
            new_paused = False
        else:
            self.backend.pause_generation()
            new_paused = True

        logger.info(f"Generation {'paused' if new_paused else 'resumed'}")

        if new_paused:
            self._emit_state_changed(server, "paused")
        else:
            self._emit_state_changed(server, "generating", prompt=self._current_prompt)

    def handle_delete(self, payload: dict, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle DELETE command: soft-delete image by index.

        CONTRACT:
          Inputs:
            - payload: dict with key "index" (int, backend index)
            - server: IPCServer instance for sending events

          Outputs: none (modifies state, deletes file, sends event)

          Invariants:
            - If index found in image_index_map:
              * Image marked as deleted (added to deleted_indices)
              * Temp file is deleted
              * Image remains in index map (soft-delete)
              * DELETE_ACK event is sent
            - If index not found or already deleted:
              * No state change (idempotent)
              * DELETE_ACK event still sent (no-op)

          Properties:
            - Thread-safe: uses state lock for index map access
            - Idempotent: deleting already-deleted index is no-op, sends DELETE_ACK
            - Non-blocking: returns quickly after deletion
            - Soft-delete: image stays in index map for recovery

          Algorithm:
            1. Parse payload to extract index integer
            2. Acquire state lock
            3. Check if index exists in image_index_map
            4. If found:
               a. Add index to deleted_indices set
               b. Get BufferedImage reference
               c. Release lock
               d. Call buffered_image.cleanup() to delete temp file
               e. Send DELETE_ACK event with index
               f. Log deletion
            5. If not found or already deleted:
               a. Release lock
               b. Send DELETE_ACK event with index (idempotent)
               c. Log no-op
        """
        from textbrush.ipc.protocol import DeleteAckEvent, DeleteCommand

        cmd = DeleteCommand(**payload)
        logger.info(f"DELETE received: index={cmd.index}")

        with self._state_lock:
            if cmd.index in self._image_index_map:
                if cmd.index not in self._deleted_indices:
                    # First deletion - mark as deleted
                    self._deleted_indices.add(cmd.index)
                    buffered_image = self._image_index_map[cmd.index]
                    needs_cleanup = True
                else:
                    # Already deleted - idempotent no-op
                    buffered_image = None
                    needs_cleanup = False
            else:
                # Index doesn't exist - idempotent no-op
                buffered_image = None
                needs_cleanup = False

        # Cleanup temp file outside lock
        if needs_cleanup and buffered_image:
            buffered_image.cleanup()
            logger.info(f"Deleted image at index {cmd.index}")
        else:
            logger.info(f"DELETE no-op for index {cmd.index} (already deleted or not found)")

        # Always send DELETE_ACK (idempotent)
        server.send(
            Message(
                MessageType.DELETE_ACK,
                dataclass_to_dict(DeleteAckEvent(index=cmd.index)),
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
            - Each image assigned unique stable index via _assign_image_index
            - IMAGE_READY events sent for each image with index
            - STATE_CHANGED(IDLE) emitted after each image ready
            - Thread blocks waiting for skip/accept between images

          Properties:
            - Daemon thread: exits when main thread exits
            - Error handling: logs errors but continues
            - Thread coordination: uses threading primitives to wait for actions
            - Index assignment: monotonic, thread-safe, permanent

          Algorithm:
            1. Store output_path for later use in accept
            2. Define deliver_loop function:
               a. Loop:
                  - Call backend.get_next_image() (blocks)
                  - If None: break
                  - Assign index via _assign_image_index(buffered)
                  - Store as self._current_image
                  - Save to preview directory
                  - Send IMAGE_READY event with:
                    * index: stable backend index
                    * path: absolute path to PNG file
                    * display_path: path with ~ for home
                  - Emit STATE_CHANGED(state=IDLE)
                  - Wait for skip/accept action (block on threading.Event or similar)
               b. Exit loop on shutdown
            3. Start daemon thread running deliver_loop
        """
        from textbrush.ipc.protocol import ImageReadyEvent

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
                        self._emit_state_changed(
                            server, "error", message=str(worker_error), fatal=True
                        )
                        break

                    index = self._assign_image_index(buffered)

                    with self._state_lock:
                        self._current_image = buffered

                    logger.info(f"Image ready: index={index}, seed={buffered.seed}")

                    # Save to preview directory with full metadata in PNG tEXt chunks
                    preview_path = self.backend.save_to_preview(buffered)
                    logger.info(f"Saved preview: {display_path(preview_path)}")

                    server.send(
                        Message(
                            MessageType.IMAGE_READY,
                            dataclass_to_dict(
                                ImageReadyEvent(
                                    index=index,
                                    path=str(preview_path.absolute()),
                                    display_path=display_path(preview_path),
                                )
                            ),
                        )
                    )

                    if self.backend.is_paused():
                        self._emit_state_changed(server, "paused")
                    else:
                        self._emit_state_changed(server, "idle")

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

    def _detect_hf_credentials(self) -> str | None:
        """Detect available HuggingFace credentials from multiple sources.

        Checks in priority order:
          1. HUGGINGFACE_HUB_TOKEN environment variable
          2. config.huggingface.token from config file
          3. HuggingFace CLI login cache (~/.cache/huggingface/token)

        Returns:
            Token string if found, None otherwise.
        """
        import os
        from pathlib import Path

        # 1. HUGGINGFACE_HUB_TOKEN env var
        token = os.environ.get("HUGGINGFACE_HUB_TOKEN")
        if token:
            return token

        # 2. config.huggingface.token
        if self.config.huggingface.token:
            return self.config.huggingface.token

        # 3. HuggingFace CLI login cache
        hf_token_file = Path.home() / ".cache" / "huggingface" / "token"
        if hf_token_file.exists():
            try:
                content = hf_token_file.read_text().strip()
                if content:
                    return content
            except OSError:
                pass

        return None

    def _init_backend(self, on_ready, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Load model in background and call ready callback.

        Helper for handle_init. Runs in background thread.

        CONTRACT:
          Inputs:
            - on_ready: callback function to call after model loads
            - server: IPCServer instance for sending error events

          Outputs: none (calls callback or sends error)

          Invariants:
            - Checks model availability before backend.initialize()
            - If model available: calls backend.initialize() directly
            - If model missing with credentials: emits loading state, downloads,
              then calls backend.initialize()
            - If model missing without credentials: emits fatal error and returns
            - If discovery logic fails unexpectedly: falls back to direct
              backend.initialize() call (graceful degradation)
            - If backend.initialize() fails: logs error, sends fatal ERROR event

          Properties:
            - Blocking: waits for model to load
            - Error handling: sends fatal error if init fails
            - Callback: on_ready() called only after successful init
            - Graceful degradation: unexpected discovery errors fall back to
              original behavior

          Algorithm:
            1. Try model discovery:
               a. Call is_flux_available(custom_dirs=config.model.directories)
               b. If not available: check credentials
                  - If credentials found: emit loading state, call download_flux_weights()
                    - If download fails: emit fatal error, return
                  - If no credentials: emit fatal error with instructions, return
               c. If unexpected error: log warning, fall through to backend.initialize()
            2. Try:
               a. Call self.backend.initialize() (blocks)
               b. Call on_ready()
            3. Catch Exception as e:
               a. Log error
               b. Send fatal ERROR event with exception message
        """
        import os

        # Model discovery step — graceful degradation on unexpected errors
        proceed_to_init = True
        try:
            custom_dirs = self.config.model.directories
            model_available = is_flux_available(custom_dirs=custom_dirs)

            if not model_available:
                token = self._detect_hf_credentials()

                if token:
                    # Credentials found — attempt auto-download
                    logger.info("Model not found, credentials available — starting auto-download")
                    self._emit_state_changed(server, "loading")

                    try:
                        # Set HF_TOKEN so download_flux_weights can find it
                        old_hf_token = os.environ.get("HF_TOKEN")
                        os.environ["HF_TOKEN"] = token
                        try:
                            download_flux_weights()
                        finally:
                            if old_hf_token is None:
                                os.environ.pop("HF_TOKEN", None)
                            else:
                                os.environ["HF_TOKEN"] = old_hf_token

                        logger.info("Model download succeeded, proceeding to initialize")
                    except Exception as download_err:
                        logger.error(f"Model download failed: {download_err}", exc_info=True)
                        self._emit_state_changed(
                            server,
                            "error",
                            message=f"Model download failed: {download_err}",
                            fatal=True,
                        )
                        proceed_to_init = False
                else:
                    # No credentials — emit actionable error
                    logger.warning("Model not found and no HuggingFace credentials available")
                    self._emit_state_changed(
                        server,
                        "error",
                        message=_MISSING_MODEL_MESSAGE,
                        fatal=True,
                    )
                    proceed_to_init = False

        except Exception as discovery_err:
            # Unexpected error in discovery logic — fall back to original behavior
            logger.warning(
                f"Model discovery failed unexpectedly ({discovery_err}); "
                "falling back to direct backend init",
                exc_info=True,
            )

        if not proceed_to_init:
            return

        try:
            logger.info("Initializing backend (loading model)...")
            self.backend.initialize()
            logger.info("Backend initialized successfully")
            on_ready()
        except Exception as e:
            logger.error(f"Backend init failed: {e}", exc_info=True)
            self._emit_state_changed(server, "error", message=str(e), fatal=True)

    def handle_get_image_list(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle GET_IMAGE_LIST command: send full image list to frontend.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (sends IMAGE_LIST event)

          Invariants:
            - Sends IMAGE_LIST event containing all images (including soft-deleted)
            - Images ordered by index (ascending)
            - Each entry has: index, path, display_path, deleted flag

          Properties:
            - Thread-safe: uses state lock for accessing image data
            - Complete state: includes all images, even deleted ones
            - Synchronous: sends response immediately
            - Recovery mechanism: allows frontend to rebuild state

          Algorithm:
            1. Acquire state lock
            2. Build list of ImageListEntry for all indices:
               a. For each index in image_index_map:
                  - Get BufferedImage
                  - Determine if deleted (index in deleted_indices)
                  - If deleted: path="", display_path=""
                  - If not deleted: use buffered_image.temp_path
                  - Create ImageListEntry
               b. Sort by index
            3. Release lock
            4. Send IMAGE_LIST event with all entries
        """
        from textbrush.ipc.protocol import ImageListEvent

        with self._state_lock:
            image_entries = []
            for index in sorted(self._image_index_map.keys()):
                buffered_image = self._image_index_map[index]
                is_deleted = index in self._deleted_indices

                if is_deleted:
                    path = ""
                    display_path_str = ""
                else:
                    path = str(buffered_image.temp_path) if buffered_image.temp_path else ""
                    display_path_str = (
                        display_path(buffered_image.temp_path) if buffered_image.temp_path else ""
                    )

                image_entries.append(
                    {
                        "index": index,
                        "path": path,
                        "display_path": display_path_str,
                        "deleted": is_deleted,
                    }
                )

        server.send(
            Message(
                MessageType.IMAGE_LIST,
                dataclass_to_dict(ImageListEvent(images=image_entries)),
            )
        )

    def _emit_state_changed(
        self,
        server: "IPCServer",  # type: ignore  # noqa: F821
        state: str,
        prompt: str | None = None,
        message: str | None = None,
        fatal: bool | None = None,
    ) -> None:
        """Emit STATE_CHANGED event with current backend state.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events
            - state: BackendState enum value as string (loading, idle, generating, paused, error)
            - prompt: string, present only when state = generating
            - message: string, present only when state = error
            - fatal: boolean, present only when state = error

          Outputs: none (sends STATE_CHANGED event)

          Invariants:
            - state is one of: loading, idle, generating, paused, error
            - If state = generating: prompt must be non-None
            - If state = error: message must be non-None
            - StateChangedEvent payload matches state requirements

          Properties:
            - Atomic state broadcast: single event for all state information
            - Validation: ensures state-specific fields are present
            - Non-blocking: returns immediately after sending

          Algorithm:
            1. Validate inputs:
               a. If state = generating: assert prompt is not None
               b. If state = error: assert message is not None
            2. Create StateChangedEvent with state, prompt, message, fatal
            3. Send STATE_CHANGED message via server
            4. Log state change
        """
        from textbrush.ipc.protocol import BackendState, StateChangedEvent

        # Validate state-specific fields
        if state == BackendState.GENERATING.value:
            if prompt is None:
                raise ValueError("prompt must be provided when state=GENERATING")
        if state == BackendState.ERROR.value:
            if message is None:
                raise ValueError("message must be provided when state=ERROR")

        # Thread-safe state update
        with self._state_lock:
            self._current_state = state

        # Create and send event
        event = StateChangedEvent(state=state, prompt=prompt, message=message, fatal=fatal)
        server.send(Message(MessageType.STATE_CHANGED, dataclass_to_dict(event)))

        # Log state change
        if state == BackendState.GENERATING.value:
            logger.info(f"State changed: {state} (prompt: '{prompt[:50] if prompt else ''}...')")
        elif state == BackendState.ERROR.value:
            logger.error(f"State changed: {state} (message: {message}, fatal: {fatal})")
        else:
            logger.info(f"State changed: {state}")

    def _assign_image_index(self, buffered_image: BufferedImage) -> int:
        """Assign next available index to image and store in index map.

        CONTRACT:
          Inputs:
            - buffered_image: BufferedImage instance to assign index to

          Outputs:
            - index: non-negative integer, stable and unique

          Invariants:
            - Acquires state lock before modifying _next_index
            - Index is monotonically increasing (never reused)
            - Stores mapping: index → buffered_image in _image_index_map
            - Thread-safe: uses state lock

          Properties:
            - Monotonic counter: indices are 0, 1, 2, 3, ...
            - Append-only: no gaps in assignment sequence
            - Permanent: index never changes once assigned
            - Thread-safe: protected by state lock

          Algorithm:
            1. Acquire state lock
            2. Read current _next_index value
            3. Store buffered_image in _image_index_map[_next_index]
            4. Increment _next_index by 1
            5. Release lock
            6. Return assigned index
        """
        with self._state_lock:
            index = self._next_index
            self._image_index_map[index] = buffered_image
            self._delivery_order.append(index)
            self._next_index += 1
            return index

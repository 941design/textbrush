"""Message handler integrating IPC server with TextbrushBackend.

Implements business logic for each IPC command, managing backend lifecycle and
coordinating image delivery to UI.
"""

from __future__ import annotations

import base64
import io
import logging
import threading
from pathlib import Path

from textbrush.backend import TextbrushBackend
from textbrush.config import Config
from textbrush.ipc.protocol import (
    BufferStatusEvent,
    Message,
    MessageType,
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
                       seed (int|None), aspect_ratio (str), format (str)
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
               b. Call backend.start_generation() with prompt, seed, aspect_ratio
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
        self.backend = TextbrushBackend(self.config)

        def on_ready():
            server.send(Message(MessageType.READY))
            self.backend.start_generation(
                prompt=cmd.prompt, seed=cmd.seed, aspect_ratio=cmd.aspect_ratio
            )
            self._start_image_delivery(server, cmd.output_path)

        threading.Thread(target=self._init_backend, args=(on_ready, server), daemon=True).start()

    def handle_skip(self, server: "IPCServer") -> None:  # type: ignore  # noqa: F821
        """Handle SKIP command: discard current image and continue.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (clears current image, sends status)

          Invariants:
            - Current image reference is cleared
            - Image delivery thread is signaled to continue
            - BUFFER_STATUS event is sent with updated buffer info

          Properties:
            - Non-blocking: returns immediately
            - Thread coordination: signals waiting delivery thread
            - Status reporting: sends buffer status after skip

          Algorithm:
            1. Clear current_image reference (set to None)
            2. Signal image delivery thread to continue (unblock wait)
            3. If backend exists: send BUFFER_STATUS event with:
               - count: len(backend.buffer)
               - max: backend.buffer.max_size
               - generating: True
        """
        with self._state_lock:
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
        """Handle ACCEPT command: save current image and report path.

        CONTRACT:
          Inputs:
            - server: IPCServer instance for sending events

          Outputs: none (saves image, sends event)

          Invariants:
            - If no current image: sends non-fatal ERROR event
            - If current image exists: saves to disk via backend.accept_current()
            - ACCEPTED event sent with absolute path where image was saved
            - Image delivery thread is signaled to continue (optional: could auto-close)

          Properties:
            - Blocking: waits for file I/O to complete
            - Error handling: sends non-fatal ERROR if no image or save fails
            - Path reporting: sends absolute path in ACCEPTED event
            - Uses stored output_path or auto-generates via backend

          Algorithm:
            1. Check if current_image exists
            2. If not: send non-fatal ERROR event, return
            3. Try:
               a. Call backend.accept_current(output_path from INIT)
               b. Get absolute path returned
               c. Send ACCEPTED event with path
            4. Catch exceptions:
               a. Log error
               b. Send non-fatal ERROR event
            5. Signal image delivery thread to continue (or server can shutdown)
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
            path = self.backend.accept_current(self._output_path)
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
            while True:
                try:
                    buffered = self.backend.get_next_image()
                    if buffered is None:
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

                    buffer = io.BytesIO()
                    buffered.image.save(buffer, format="PNG")
                    image_b64 = base64.b64encode(buffer.getvalue()).decode()

                    server.send(
                        Message(
                            MessageType.IMAGE_READY,
                            dataclass_to_dict(
                                ImageReadyEvent(
                                    image_data=image_b64,
                                    seed=buffered.seed,
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
            self.backend.initialize()
            on_ready()
        except Exception as e:
            logger.error(f"Backend init failed: {e}")
            server.send(
                Message(
                    MessageType.ERROR, dataclass_to_dict(ErrorEvent(message=str(e), fatal=True))
                )
            )

"""IPC server for stdio-based communication with Tauri.

Runs in Python sidecar process, reads commands from stdin, writes events to stdout.
"""

from __future__ import annotations

import json
import logging
import sys
import threading

from textbrush.ipc.protocol import Message, MessageType

logger = logging.getLogger(__name__)


class IPCServer:
    """Stdio-based IPC server.

    Reads JSON messages from stdin, dispatches to handler, writes responses to stdout.
    Thread-safe for concurrent event sending from background threads.
    """

    def __init__(self, handler: "MessageHandler"):  # type: ignore  # noqa: F821
        """Initialize IPC server.

        CONTRACT:
          Inputs:
            - handler: MessageHandler instance to process incoming commands

          Outputs: none (constructs instance)

          Invariants:
            - Server is not running until run() is called
            - Write lock is initialized for thread-safe stdout access
            - Handler is stored for command dispatch

          Properties:
            - Lazy start: server does not begin processing until run()
            - Thread-safe writes: send() can be called from any thread
        """
        self.handler = handler
        self._running = False
        self._write_lock = threading.Lock()

    def send(self, message: Message) -> None:
        """Send message to Tauri (thread-safe).

        CONTRACT:
          Inputs:
            - message: Message instance to send

          Outputs: none (writes to stdout)

          Invariants:
            - Message is serialized to JSON
            - JSON is written to stdout followed by newline
            - Stdout is flushed immediately
            - Write operation is atomic (protected by lock)

          Properties:
            - Thread-safe: can be called concurrently from multiple threads
            - Blocking: waits for lock and I/O to complete
            - Newline-delimited: each message is a single line
            - Immediate flush: ensures message is delivered without buffering

          Algorithm:
            1. Acquire write lock
            2. Serialize message to JSON string
            3. Write JSON + newline to stdout
            4. Flush stdout
            5. Release write lock
        """
        with self._write_lock:
            sys.stdout.write(message.to_json() + "\n")
            sys.stdout.flush()

    def run(self) -> None:
        """Main event loop - read commands from stdin and dispatch.

        CONTRACT:
          Inputs: none

          Outputs: none (reads stdin until EOF or error)

          Invariants:
            - Runs until stdin closes (EOF) or abort command received
            - Each line from stdin is parsed as JSON message
            - Valid messages are dispatched to handler
            - Invalid JSON triggers error event (non-fatal)
            - Handler exceptions trigger error event (non-fatal)

          Properties:
            - Blocking: runs until shutdown
            - Error recovery: continues processing after non-fatal errors
            - EOF handling: clean exit when stdin closes
            - Logging: logs startup, errors, and shutdown

          Algorithm:
            1. Set running flag to True
            2. Log server start
            3. Loop while running:
               a. Read line from stdin
               b. If EOF: log and break
               c. Strip whitespace
               d. If empty line: continue
               e. Try:
                  - Parse line as JSON message
                  - Dispatch to handler based on message type
               f. Catch JSONDecodeError:
                  - Log error
                  - Send non-fatal error event
               g. Catch other exceptions:
                  - Log error
                  - Send non-fatal error event
            4. Set running flag to False
            5. Log shutdown

        Message Dispatch Rules:
            - INIT → handler.handle_init(payload, server)
            - SKIP → handler.handle_skip(server)
            - ACCEPT → handler.handle_accept(server)
            - ABORT → handler.handle_abort(server), then stop loop
            - STATUS → handler.handle_status(server)
            - Unknown type → log warning, no error event
        """
        self._running = True
        logger.info("IPC server started")

        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    logger.info("Stdin closed, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                message = Message.from_json(line)
                self._handle_message(message)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                self.send(
                    Message(MessageType.ERROR, {"message": f"Invalid JSON: {e}", "fatal": False})
                )
            except Exception as e:
                logger.error(f"Handler error: {e}")
                self.send(Message(MessageType.ERROR, {"message": str(e), "fatal": False}))

        self._running = False
        logger.info("IPC server shutdown")

    def _handle_message(self, message: Message) -> None:
        """Dispatch message to handler based on type."""
        if message.type == MessageType.INIT:
            self.handler.handle_init(message.payload, self)
        elif message.type == MessageType.SKIP:
            self.handler.handle_skip(self)
        elif message.type == MessageType.ACCEPT:
            self.handler.handle_accept(self)
        elif message.type == MessageType.ABORT:
            self.handler.handle_abort(self)
            self._running = False
        elif message.type == MessageType.STATUS:
            self.handler.handle_status(self)
        elif message.type == MessageType.UPDATE_CONFIG:
            self.handler.handle_update_config(message.payload, self)
        else:
            logger.warning(f"Unknown message type: {message.type}")

    def shutdown(self) -> None:
        """Stop the server.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After shutdown(), running flag is False
            - Server will exit run() loop on next iteration

          Properties:
            - Non-blocking: returns immediately
            - Idempotent: safe to call multiple times
            - Signal only: does not force-close stdin

          Algorithm:
            1. Set running flag to False
        """
        self._running = False

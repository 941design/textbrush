"""IPC server entry point for sidecar process.

Entry point when Tauri spawns: python -m textbrush.ipc
"""

import logging
import sys

from textbrush.config import load_config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.server import IPCServer


def main():
    """Main entry point for IPC sidecar process."""
    # Configure logging to stderr (stdout is used for IPC)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    logger = logging.getLogger(__name__)
    logger.info("Starting IPC server")

    handler = None
    try:
        # Load configuration
        config = load_config()

        # Create handler and server
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Run server (blocks until shutdown)
        server.run()

    except KeyboardInterrupt:
        logger.info("Received interrupt, shutting down")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        # Ensure backend resources are cleaned up
        if handler and handler.backend:
            try:
                handler.backend.shutdown()
                logger.info("Backend shutdown complete")
            except Exception as e:
                logger.error(f"Backend shutdown error: {e}")
        logger.info("IPC server stopped")


if __name__ == "__main__":
    main()

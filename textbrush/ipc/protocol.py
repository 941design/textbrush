"""IPC protocol message types and data structures.

Defines JSON message format for Tauri <-> Python communication via stdio.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import Enum


class MessageType(str, Enum):
    """Message types for IPC protocol.

    Commands flow from Tauri → Python.
    Events flow from Python → Tauri.
    """

    # Commands (Tauri → Python)
    INIT = "init"
    SKIP = "skip"
    ACCEPT = "accept"
    ABORT = "abort"
    STATUS = "status"
    UPDATE_CONFIG = "update_config"
    PAUSE = "pause"

    # Events (Python → Tauri)
    READY = "ready"
    IMAGE_READY = "image_ready"
    BUFFER_STATUS = "buffer_status"
    ERROR = "error"
    ACCEPTED = "accepted"
    ABORTED = "aborted"
    PAUSED = "paused"


@dataclass
class InitCommand:
    """Command to initialize backend and start generation."""

    prompt: str
    output_path: str | None = None
    seed: int | None = None
    aspect_ratio: str = "1:1"
    format: str = "png"


@dataclass
class UpdateConfigCommand:
    """Command to update generation configuration.

    Triggers generation restart with new prompt and/or aspect ratio.
    """

    prompt: str
    aspect_ratio: str = "1:1"


@dataclass
class ImageReadyEvent:
    """Event indicating new image is ready for display."""

    image_data: str  # Base64 encoded PNG
    seed: int
    buffer_count: int
    buffer_max: int


@dataclass
class BufferStatusEvent:
    """Event reporting current buffer status."""

    count: int
    max: int
    generating: bool


@dataclass
class AcceptedEvent:
    """Event indicating image was saved successfully."""

    path: str


@dataclass
class ErrorEvent:
    """Event reporting an error."""

    message: str
    fatal: bool = False


@dataclass
class PausedEvent:
    """Event reporting pause state change."""

    paused: bool


class Message:
    """IPC message with type and payload.

    JSON format:
    {
        "type": "message_type",
        "payload": {...}
    }
    """

    def __init__(self, type: MessageType, payload: dict | None = None):
        """Create message.

        Args:
            type: MessageType enum value
            payload: Optional dict payload (default: empty dict)
        """
        self.type = type
        self.payload = payload or {}

    def to_json(self) -> str:
        """Serialize message to JSON string.

        Returns:
            JSON string representation
        """
        return json.dumps({"type": self.type.value, "payload": self.payload})

    @classmethod
    def from_json(cls, data: str) -> Message:
        """Deserialize message from JSON string.

        Args:
            data: JSON string

        Returns:
            Message instance

        Raises:
            json.JSONDecodeError: If data is not valid JSON
            ValueError: If message type is unknown
        """
        parsed = json.loads(data)
        return cls(type=MessageType(parsed["type"]), payload=parsed.get("payload", {}))


def dataclass_to_dict(obj: object) -> dict:
    """Convert dataclass instance to dict for JSON payload.

    Args:
        obj: Dataclass instance

    Returns:
        Dict representation
    """
    return asdict(obj)  # type: ignore

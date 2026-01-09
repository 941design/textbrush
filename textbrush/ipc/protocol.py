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
    width: int | None = None
    height: int | None = None


@dataclass
class UpdateConfigCommand:
    """Command to update generation configuration.

    Triggers generation restart with new prompt and/or aspect ratio/dimensions.
    When width and height are provided, they override the aspect_ratio setting.
    """

    prompt: str
    aspect_ratio: str = "1:1"
    width: int | None = None
    height: int | None = None


@dataclass
class ImageReadyEvent:
    """Event indicating new image is ready for display.

    CONTRACT (dimension fields):
      Invariants:
        - final_width and final_height are image dimensions after any cropping
        - If generated_width is not None, it is divisible by 16
        - If generated_height is not None, it is divisible by 16
        - generated_width and generated_height are either both present or both absent
        - If generated dimensions present: generated_width ≥ final_width,
          generated_height ≥ final_height
        - If generated dimensions equal final dimensions, no cropping occurred

      Properties:
        - Backward compatibility: UI handles missing generated_width/generated_height
        - Optional: generated dimensions default to None for images without alignment
        - Semantic: None for generated dimensions means "no dimension alignment performed"
        - Always present: final_width and final_height always transmitted

      Algorithm (IPC handler):
        1. Extract final dimensions from buffered_image.image.size
        2. Extract generated dimensions from buffered_image.generated_width/generated_height
        3. Populate ImageReadyEvent with all dimension fields
    """

    image_data: str  # Base64 encoded PNG
    seed: int
    buffer_count: int
    buffer_max: int
    prompt: str = ""
    model_name: str = ""
    generated_width: int | None = None
    generated_height: int | None = None
    final_width: int | None = None
    final_height: int | None = None


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

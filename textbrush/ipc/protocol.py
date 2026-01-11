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
    DELETE = "delete"

    # Events (Python → Tauri)
    READY = "ready"  # DEPRECATED: Use STATE_CHANGED with state="idle"
    IMAGE_READY = "image_ready"
    # DEPRECATED: Use STATE_CHANGED with state="generating"
    GENERATION_STARTED = "generation_started"
    BUFFER_STATUS = "buffer_status"  # DEPRECATED: Buffer concept removed
    ERROR = "error"
    ACCEPTED = "accepted"
    ABORTED = "aborted"
    PAUSED = "paused"  # DEPRECATED: Use STATE_CHANGED with state="paused"
    DELETE_ACK = "delete_ack"

    # New events for backend state synchronization
    STATE_CHANGED = "state_changed"
    IMAGE_LIST = "image_list"
    GET_IMAGE_LIST = "get_image_list"


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
class DeleteCommand:
    """Command to delete a delivered image by backend index.

    CONTRACT:
      Inputs:
        - index: non-negative integer, backend index of image to delete

      Outputs: none (command triggers handler action)

      Invariants:
        - index ≥ 0
        - index refers to backend's stable image index

      Properties:
        - Idempotency: deleting same index twice should not error
          (second is no-op, still sends DELETE_ACK)
        - Soft delete: backend marks image as deleted, doesn't remove from list
        - File cleanup: backend deletes temp file from disk

      Algorithm (for handler):
        1. Search delivered_images for matching index
        2. If found and not already deleted:
           a. Mark image as deleted (soft delete)
           b. Delete temp file via buffered_image.cleanup()
           c. Send DELETE_ACK event with index
        3. If found and already deleted:
           a. Send DELETE_ACK event with index (idempotent no-op)
        4. If not found (invalid index):
           a. Send non-fatal ERROR event "Invalid index: {index}"
    """

    index: int


@dataclass
class ImageReadyEvent:
    """Event indicating new image is ready for display.

    CONTRACT:
      Inputs: none (dataclass fields)

      Outputs:
        - index: non-negative integer, stable backend index for this image
        - path: absolute path string to PNG file in preview directory
        - display_path: path string with home directory replaced by ~

      Invariants:
        - index ≥ 0
        - index is permanent and unique for this image
        - path is absolute path to PNG file
        - display_path is path with ~ for home directory
        - PNG file contains metadata in tEXt chunks (parsed by frontend)

      Properties:
        - Index stability: index never changes or reused for this image
        - Path-based loading: frontend loads image from filesystem via asset protocol
        - Metadata in PNG: prompt, model, seed, dimensions stored in PNG tEXt chunks
        - Frontend parses metadata using ExifReader library
        - Append-only: new images get next available index (monotonic counter)

      Algorithm (IPC handler):
        1. Assign next index from monotonic counter
        2. Save image to preview directory with full metadata
        3. Store in delivered_images with index, path, deleted=false
        4. Send IMAGE_READY event with index, path, display_path
        5. Frontend appends to display list, maps index for deletion
    """

    index: int  # Stable backend index
    path: str  # Absolute path to preview PNG file
    display_path: str  # Path with home dir replaced by ~


@dataclass
class GenerationStartedEvent:
    """Event indicating image generation has started.

    Sent when the backend begins generating a new image, allowing the frontend
    to show meaningful progress info (seed) instead of generic "waiting" message.
    """

    seed: int
    queue_position: int  # 0 = generating for immediate display, 1+ = for buffer


@dataclass
class BufferStatusEvent:
    """Event reporting current buffer status."""

    count: int
    max: int
    generating: bool


@dataclass
class AcceptedEvent:
    """Event indicating all retained images were saved successfully.

    CONTRACT:
      Inputs: none (dataclass fields)

      Outputs:
        - paths: collection of absolute path strings, non-empty
        - display_paths: collection of display path strings with ~ for home directory

      Invariants:
        - len(paths) equals len(display_paths)
        - len(paths) ≥ 1 (at least one image was accepted)
        - All paths are absolute paths to saved PNG files
        - paths[i] corresponds to display_paths[i] for all i

      Properties:
        - Order preservation: paths appear in delivery order (order images were generated)
        - Path format: paths are absolute, display_paths use ~ for home directory
        - Non-empty: ACCEPT command only succeeds if at least one image was delivered

      Algorithm (for creating this event):
        For each accepted image in delivered_images (in order):
          1. Append absolute path to paths list
          2. Append display path (with ~ for home) to display_paths list
        Return event with both lists
    """

    paths: list[str]  # Absolute paths to all saved files
    display_paths: list[str]  # Display paths with home dir replaced by ~


@dataclass
class ErrorEvent:
    """Event reporting an error."""

    message: str
    fatal: bool = False


@dataclass
class PausedEvent:
    """Event reporting pause state change."""

    paused: bool


@dataclass
class DeleteAckEvent:
    """Event acknowledging successful image deletion.

    CONTRACT:
      Inputs: none (dataclass fields)

      Outputs:
        - index: non-negative integer, backend index of deleted image

      Invariants:
        - index ≥ 0
        - Image at this index has been soft-deleted (marked deleted, not removed)
        - Temp file for image has been deleted

      Properties:
        - Confirmation: frontend can use this to confirm deletion succeeded
        - Error alternative: if deletion fails, ERROR event sent instead
        - Idempotent handling: deleting already-deleted index is treated as
          success (sends DELETE_ACK)
    """

    index: int


class BackendState(str, Enum):
    """Backend state enumeration for state machine.

    CONTRACT:
      States:
        - LOADING: Model initializing, not ready for generation
        - IDLE: Model ready, not generating
        - GENERATING: Actively generating an image
        - PAUSED: Generation paused by user
        - ERROR: Error occurred (fatal or non-fatal)

      Transitions:
        - LOADING → IDLE (model load success, not paused)
        - LOADING → PAUSED (if start_paused=true, overrides for display)
        - LOADING → ERROR (model load failure)
        - IDLE → GENERATING (generation starts)
        - GENERATING → IDLE (image completed and buffer check)
        - GENERATING → PAUSED (user pauses)
        - PAUSED → GENERATING (user resumes)
        - Any → ERROR (on fatal or non-fatal error)

      Properties:
        - Exhaustive: all backend lifecycle states covered
        - Display priority: PAUSED overrides LOADING for user display
        - Single state: backend is in exactly one state at any time
    """

    LOADING = "loading"
    IDLE = "idle"
    GENERATING = "generating"
    PAUSED = "paused"
    ERROR = "error"


@dataclass
class StateChangedEvent:
    """Event indicating backend state transition.

    CONTRACT:
      Inputs: none (dataclass fields)

      Outputs:
        - state: BackendState enum value (required)
        - prompt: string, present only when state = GENERATING
        - message: string, present only when state = ERROR
        - fatal: boolean, present only when state = ERROR

      Invariants:
        - state is one of: loading, idle, generating, paused, error
        - If state = GENERATING: prompt field is non-empty string
        - If state = ERROR: message field is non-empty string, fatal is boolean
        - If state ≠ GENERATING: prompt field is None
        - If state ≠ ERROR: message and fatal fields are None

      Properties:
        - Complete state representation: all backend state information in one event
        - No optimistic updates: frontend must wait for this event before changing state
        - Transition atomicity: state change is atomic, no partial updates

      Algorithm (backend emits this when):
        1. Model load completes → state = IDLE or PAUSED
        2. Generation starts → state = GENERATING, prompt = current_prompt
        3. Image completes → state = IDLE or GENERATING (if buffer not empty)
        4. User pauses → state = PAUSED
        5. User resumes → state = GENERATING, prompt = current_prompt
        6. Error occurs → state = ERROR, message = error_message, fatal = is_fatal
    """

    state: str  # BackendState enum value as string
    prompt: str | None = None
    message: str | None = None
    fatal: bool | None = None


@dataclass
class ImageListEntry:
    """Single image entry in backend-owned image list.

    CONTRACT:
      Invariants:
        - index ≥ 0, stable and permanent
        - path is absolute path to PNG file (or empty if deleted)
        - display_path is path with ~ for home (or empty if deleted)
        - deleted is boolean flag

      Properties:
        - Soft delete: deleted=True means image is flagged, not removed
        - Gaps allowed: indices may be non-consecutive due to deletions
        - Immutable index: once assigned, index never changes or reused
    """

    index: int
    path: str
    display_path: str
    deleted: bool


@dataclass
class ImageListEvent:
    """Event transmitting full backend image list.

    CONTRACT:
      Inputs: none (dataclass fields)

      Outputs:
        - images: collection of ImageListEntry, ordered by index

      Invariants:
        - images is ordered by index (ascending)
        - Includes soft-deleted images (deleted=True)
        - All indices are unique and ≥ 0

      Properties:
        - Complete state: frontend can rebuild entire display from this
        - Includes deletions: deleted images present with deleted=True
        - Recovery mechanism: used on reconnect or consistency check

      Algorithm (frontend processes by):
        1. Clear current image list
        2. For each entry in images:
           a. If deleted=False: add to display list
           b. If deleted=True: skip (don't display)
        3. Rebuild navigation with filtered list + spinner
    """

    images: list[dict]  # List of ImageListEntry dicts (index, path, display_path, deleted)


@dataclass
class GetImageListCommand:
    """Command to request full image list from backend.

    CONTRACT:
      Inputs: none (command has no payload)

      Outputs: none (triggers IMAGE_LIST event)

      Invariants:
        - Backend responds with IMAGE_LIST event containing all images
        - Response includes soft-deleted images

      Properties:
        - Synchronous response: IMAGE_LIST event sent immediately
        - Consistency: snapshot of current backend state at response time
        - Used for recovery: frontend reconnect, consistency check
    """

    pass  # No fields, command has no payload


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

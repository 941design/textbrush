# Feature Specification: Wire GET_IMAGE_LIST for State Recovery

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The spec (spec.md:293, 336) defines `GET_IMAGE_LIST` as a command for frontend state recovery on reconnect. The full stack exists in fragments:

- **Protocol:** `MessageType.GET_IMAGE_LIST` defined (protocol.py:44)
- **Handler:** `handle_get_image_list` fully implemented (handler.py:870-934) — builds an ordered list of all images including soft-deleted ones and sends an `IMAGE_LIST` event
- **Server dispatch:** `_handle_message` (server.py:156-176) has no branch for `GET_IMAGE_LIST` — falls through to `logger.warning("Unknown message type")`
- **Rust commands:** No `get_image_list` Tauri command exists in commands.rs
- **Frontend:** No code sends a `get_image_list` command or handles `image_list` events

The handler is dead code. State recovery after any interruption (e.g., frontend reload during development, future reconnect scenarios) is impossible.

## Core Functionality

Wire `GET_IMAGE_LIST` end-to-end: server dispatch → Rust command → frontend invocation and `image_list` event handling.

## Functional Requirements

### FR1: Add Server Dispatch for GET_IMAGE_LIST

**Requirement:** Add a branch in `IPCServer._handle_message` for `MessageType.GET_IMAGE_LIST` that calls `self.handler.handle_get_image_list(self)`.

**Location:** `textbrush/ipc/server.py`, `_handle_message` method, after the `DELETE` branch.

### FR2: Add Rust Tauri Command

**Requirement:** Add a `get_image_list` Tauri command in `commands.rs` that sends a `get_image_list` message to the sidecar.

**Signature:**
```rust
#[command]
pub fn get_image_list(state: State<'_, AppState>) -> Result<(), String>
```

**Behavior:** Same pattern as `skip_image` — lock sidecar mutex, send `{"type": "get_image_list", "payload": null}`, return Ok/Err.

### FR3: Frontend IMAGE_LIST Event Handler

**Requirement:** Add handling for `type: "image_list"` in the frontend `handleMessage` switch.

**Behavior:**
1. Parse payload as `ImageListPayload` (array of `{index, path, display_path, deleted}` entries)
2. Filter out deleted entries
3. For each non-deleted entry: create an `ImageRecord` (fetch metadata from PNG if needed)
4. Replace `state.imageList` with the rebuilt list
5. Set `state.currentIndex` to the last entry (or -1 if empty)
6. Update nav dots and display

### FR4: Frontend Recovery Invocation

**Requirement:** After the frontend receives the first `state_changed` event (confirming the backend is alive), invoke `get_image_list` to synchronize any pre-existing state.

**Trigger:** On receiving `state_changed` with `state` not equal to `"loading"` and `state.imageList.length === 0`. This covers:
- Normal startup: Backend transitions loading → idle → generating. First non-loading state triggers sync. Since no images exist yet, the response will be empty — harmless.
- Recovery after reload: Backend is already in `generating` or `idle` state with existing images.

**Guard:** Only invoke once per session (use a `recoveryAttempted` boolean flag).

## Critical Constraints

1. **No behavior change for normal flow.** The `image_list` response during normal startup will be empty. Existing `image_ready` events continue to be the primary mechanism for adding images.
2. **Idempotent.** Receiving an `image_list` event must be safe at any time — it replaces the frontend list entirely.
3. **Ordered.** The handler returns images sorted by index. Frontend must preserve this order.
4. **Soft-deleted images.** The response includes deleted images (flagged). Frontend must filter them out, matching existing deletion semantics.

## Integration Points

### Backend
- `textbrush/ipc/server.py`: Add dispatch branch in `_handle_message`
- `textbrush/ipc/handler.py`: No changes (already implemented)
- `textbrush/ipc/protocol.py`: No changes (types already defined)

### Rust
- `src-tauri/src/commands.rs`: Add `get_image_list` command
- Register command in Tauri app builder

### Frontend
- `src-tauri/ui/main.ts`: Add `case 'image_list':` in `handleMessage`, add recovery invocation
- `src-tauri/ui/types.ts`: Add `ImageListPayload` type

## Out of Scope

- WebSocket reconnection logic (the app uses stdio IPC, not WebSocket)
- Automatic periodic state sync
- Conflict resolution between `image_list` and in-flight `image_ready` events (the recovery guard prevents this)
- Streaming large image lists (current design sends all at once)

## Success Criteria

1. Sending `get_image_list` via the Python IPC server returns a complete image list.
2. Frontend correctly rebuilds its image list from an `image_list` event.
3. After a frontend-only reload (dev scenario), the image history is restored.
4. Normal startup flow is unaffected — first `image_list` response is empty, `image_ready` events populate the list as before.
5. Soft-deleted images in the response are filtered out by the frontend.

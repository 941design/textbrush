# Feature: Backend Owns Image List

## Summary

Refactor image lifecycle management so the Python backend maintains the authoritative list of retained images. This eliminates the awkward frontend-backend ping-pong during accept and creates consistent semantics for DELETE, ACCEPT, and ABORT commands.

## Problem Statement

### Current Architecture Issues

1. **Split responsibility**: The frontend maintains `imageList` with retention state, but the backend manages temp files. Neither has complete authority.

2. **Unnecessary round-trip on accept**:
   - Frontend sends ACCEPT
   - Backend saves *only* current image, returns path
   - Frontend stores path, collects all retained paths
   - Frontend tells Rust to print paths and exit

   The frontend must track `outputPath` for each image and coordinate file saves.

3. **Spec vs implementation mismatch**: The spec says "save all retained images" but implementation only saves the currently displayed image.

4. **Redundant code paths**: `print_and_exit` and `print_paths_and_exit` exist separately when the multi-path version handles both cases.

5. **Frontend manages file state**: The frontend tracks `outputPath`, `path` (preview), and deletion state - concerns that belong in the backend.

## Proposed Solution

### Backend Owns the List

The backend tracks all images delivered to the frontend in a `delivered_images` list. The frontend becomes stateless regarding file management.

### Command Semantics

| Command | Payload | Effect on `delivered_images` | Temp Files | Exit |
|---------|---------|------------------------------|------------|------|
| DELETE  | image_id | Remove one entry | Delete one | No |
| ACCEPT  | (none) | Clear all | Move all to output | 0 + paths |
| ABORT   | (none) | Clear all | Delete all | 1 |

### Data Flow

```
Generation:
  Backend generates image → adds to delivered_images → sends IMAGE_READY to frontend

DELETE:
  Frontend sends DELETE {image_id}
  Backend removes from delivered_images, deletes temp file
  Backend sends DELETE_ACK (or error)

ACCEPT:
  Frontend sends ACCEPT
  Backend moves all delivered_images to output directory
  Backend sends ACCEPTED {paths: [...]}
  Backend exits with code 0, prints paths to stdout

ABORT:
  Frontend sends ABORT
  Backend deletes all delivered_images temp files
  Backend sends ABORTED
  Backend exits with code 1
```

### Frontend Responsibilities (Reduced)

- Display images from IMAGE_READY events
- Track navigation position (UI state only)
- Send DELETE when user removes an image
- Send ACCEPT when user clicks Done
- Send ABORT when user cancels

### Backend Responsibilities (Expanded)

- Generate images
- Maintain `delivered_images` list with temp file paths
- Handle DELETE: remove from list, delete temp file
- Handle ACCEPT: move all to output, report paths, exit 0
- Handle ABORT: delete all temps, exit 1

## Required Changes

### spec.md Updates

**Section 3.2 Actions** - Clarify that backend manages the retained image list:

```markdown
* **Delete**
  * Frontend sends DELETE command with image identifier
  * Backend removes image from retained list and deletes temp file
  * Frontend updates UI to show next image

* **Accept**
  * Frontend sends ACCEPT command (no payload)
  * Backend saves all retained images to output directory
  * Backend prints absolute paths to stdout (newline-separated)
  * Backend exits with code 0

* **Abort**
  * Frontend sends ABORT command
  * Backend deletes all retained temp files
  * Backend prints nothing to stdout
  * Backend exits with code 1
```

**Section 5.3 IPC Layer** - Update command/event definitions:

```markdown
Commands: INIT, SKIP, DELETE, ACCEPT, ABORT, PAUSE
  - DELETE payload: {image_id: string}
  - ACCEPT payload: (none)
  - ABORT payload: (none)

Events: READY, IMAGE_READY, BUFFER_STATUS, ERROR, ACCEPTED, ABORTED, PAUSED
  - ACCEPTED payload: {paths: string[]}
```

**Section 9.1 CLI Exit Contract** - Simplify (remove single/multi distinction):

```markdown
* **Accept**
  * Exit code: 0
  * Stdout: newline-separated absolute image paths (one or more)
  * Paths in delivery order (chronological)

* **Abort**
  * Exit code: 1
  * Stdout: empty
```

### Python Backend Changes

**textbrush/ipc/handler.py**:
- Add `delivered_images: list[BufferedImage]` to track delivered images
- On IMAGE_READY delivery: append to `delivered_images`
- `handle_delete(image_id)`: remove from list, delete temp file
- `handle_accept()`: iterate `delivered_images`, move all to output, send paths
- `handle_abort()`: iterate `delivered_images`, delete all temp files

**textbrush/ipc/protocol.py**:
- Add `DELETE` message type
- Update `ACCEPTED` event payload to include `paths: list[str]`
- Add `DELETE_ACK` event (optional, for confirmation)

**textbrush/backend.py**:
- `accept_all(images: list[BufferedImage]) -> list[Path]`: batch save
- Remove or deprecate `accept_from_preview` (single image version)

### Rust/Tauri Changes

**src-tauri/src/commands.rs**:
- Add `delete_image(image_id: String)` command
- Simplify `accept_image` (no longer needs path handling)

**src-tauri/src/exit_handlers.rs**:
- Remove `print_and_exit` (redundant)
- Keep only `print_paths_and_exit` (rename to `print_paths_and_exit` or just `accept_exit`)

### Frontend Changes

**src-tauri/ui/main.js**:
- Remove `outputPath` tracking from image entries
- `deleteCurrentImage()`: send DELETE command with image_id to backend
- `handleAccepted(payload)`: receive paths array from backend, pass to exit handler
- Remove `ListManager.getAllRetainedPaths()` (no longer needed)

**src-tauri/ui/list-manager.js**:
- Remove `getAllRetainedPaths()` function
- Simplify image entry structure (remove `outputPath` field)

## Migration Notes

1. The frontend's `imageList` still exists for UI navigation but no longer tracks file state
2. Image identifiers (for DELETE) can use the existing `path` (preview path) or add explicit IDs
3. Backward compatibility not required (internal refactor)

## Testing Considerations

- Test DELETE removes correct image and deletes temp file
- Test ACCEPT with 0, 1, and N images in list
- Test ABORT cleans up all temp files
- Test interleaved DELETE + navigation + ACCEPT
- Test DELETE of already-deleted image (error handling)
- Verify stdout output format unchanged (paths newline-separated)

## Benefits

1. **Single source of truth**: Backend owns file lifecycle
2. **Simpler frontend**: UI logic only, no file state
3. **Consistent semantics**: DELETE/ACCEPT/ABORT are symmetric and predictable
4. **Reduced IPC**: ACCEPT needs no payload, returns all paths at once
5. **Spec alignment**: Implementation matches "save all retained images"

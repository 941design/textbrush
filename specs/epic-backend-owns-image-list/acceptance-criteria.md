# Acceptance Criteria: Backend Owns Image List

Generated: 2026-02-21
Source: spec.md, exploration.json

## Overview

This epic is substantially complete. The single remaining gap is behavioral test coverage
for `handle_delete` in `textbrush/ipc/handler.py`. These criteria verify the missing
`TestDeleteCommand` test class that must be added to `tests/test_ipc_handler.py`.

## Criteria

### AC-001: DELETE adds index to `_deleted_indices`

- **Description**: When `handle_delete` is called with a valid index that is present in
  `_image_index_map` and not yet in `_deleted_indices`, the handler adds that index to
  `_deleted_indices`.
- **Verification**: Set `handler._image_index_map = {0: mock_image}` and
  `handler._deleted_indices = set()`. Call `handler.handle_delete({"index": 0}, mock_server)`.
  Assert `0 in handler._deleted_indices`.
- **Type**: unit
- **Source**: spec.md "Testing Considerations" — "Test DELETE removes correct image"; exploration.json
  pattern "Soft-delete via _deleted_indices"

### AC-002: DELETE sends DELETE_ACK event with the correct index

- **Description**: After `handle_delete` is called with a valid index, `server.send` is
  called with a `Message` whose type is `MessageType.DELETE_ACK` and whose payload contains
  `{"index": <the requested index>}`.
- **Verification**: Call `handler.handle_delete({"index": 0}, mock_server)`. Assert
  `mock_server.send.call_args[0][0].type == MessageType.DELETE_ACK` and
  `mock_server.send.call_args[0][0].payload["index"] == 0`.
- **Type**: unit
- **Source**: spec.md "Data Flow" — DELETE sends DELETE_ACK; protocol.py `DeleteAckEvent`

### AC-003: DELETE deletes the temp file from disk

- **Description**: When `handle_delete` is called with a valid index whose `BufferedImage`
  has a real `temp_path`, the file at `temp_path` is deleted from the filesystem.
- **Verification**: Using `tmp_path`, create a real file at a temp path. Construct a
  `BufferedImage` with `temp_path` set to that path. Insert it into
  `handler._image_index_map`. Call `handler.handle_delete({"index": 0}, mock_server)`.
  Assert the file no longer exists (`not temp_file.exists()`).
- **Type**: unit
- **Source**: spec.md "Testing Considerations" — "Test DELETE removes correct image and
  deletes temp file"

### AC-004: DELETE of an already-deleted index is idempotent — no-op, sends DELETE_ACK

- **Description**: When `handle_delete` is called with an index that is already in
  `_deleted_indices`, the handler does not modify `_deleted_indices` further, does not call
  `cleanup()` again, and still sends a `DELETE_ACK` event.
- **Verification**: Set `handler._image_index_map = {0: mock_image}` and
  `handler._deleted_indices = {0}` (already deleted). Call
  `handler.handle_delete({"index": 0}, mock_server)`. Assert `mock_server.send` was called
  with `MessageType.DELETE_ACK` and `mock_image.cleanup` was NOT called.
- **Type**: unit
- **Source**: spec.md "Testing Considerations" — "Test DELETE of already-deleted image
  (error handling)"; exploration.json pattern "Idempotent DELETE_ACK"

### AC-005: DELETE of a non-existent index is idempotent — sends DELETE_ACK

- **Description**: When `handle_delete` is called with an index that is not present in
  `_image_index_map` at all, no state change occurs and a `DELETE_ACK` event is still sent.
- **Verification**: Set `handler._image_index_map = {}` (empty). Call
  `handler.handle_delete({"index": 99}, mock_server)`. Assert `mock_server.send` was called
  with `MessageType.DELETE_ACK` and `handler._deleted_indices` remains empty.
- **Type**: unit
- **Source**: exploration.json pattern "Idempotent DELETE_ACK"; handler.py contract
  "If index not found or already deleted: DELETE_ACK event still sent (no-op)"

### AC-006: DELETE then ACCEPT excludes the deleted image from accepted paths

- **Description**: When an image is deleted via `handle_delete` and subsequently
  `handle_accept` is called, `backend.accept_all` receives only the non-deleted images
  (those not in `_deleted_indices`), and the resulting ACCEPTED event's paths list does not
  include a path for the deleted image.
- **Verification**: Set `handler._image_index_map = {0: image1, 1: image2}` with
  `handler._deleted_indices = set()`. Call `handler.handle_delete({"index": 0}, mock_server)`.
  Then call `handler.handle_accept(mock_server)` with a `mock_backend.accept_all` returning
  one path. Assert `mock_backend.accept_all` was called with `[image2]` only (index 0 excluded).
- **Type**: unit
- **Source**: spec.md "Testing Considerations" — "Test interleaved DELETE + navigation + ACCEPT"

## Verification Plan

### Automated Tests

- Unit tests: AC-001, AC-002, AC-003, AC-004, AC-005, AC-006

### Manual Verification

None. All criteria are automatable via pytest unit tests.

## E2E Test Plan

This is a Tauri desktop application; E2E tests are CLI subprocess invocations, not
Playwright/Docker scenarios.

### Infrastructure Requirements

- Python environment via `uv` with the project installed
- `pytest` with `tmp_path` fixture (built-in)
- No external services required

### E2E Scenarios

| Scenario | Steps | Expected Outcome | ACs Validated |
|----------|-------|------------------|---------------|
| delete-removes-file-and-acks | 1. Construct `MessageHandler` with real `BufferedImage` (real temp file). 2. Call `handler.handle_delete({"index": 0}, mock_server)`. 3. Assert temp file gone. 4. Assert DELETE_ACK sent. | File deleted from filesystem; `mock_server.send` called with `MessageType.DELETE_ACK` and `payload["index"] == 0`. | AC-002, AC-003 |
| delete-then-accept-excludes-deleted | 1. Construct `MessageHandler` with two images at indices 0 and 1. 2. Call `handle_delete` for index 0. 3. Call `handle_accept`. 4. Inspect `accept_all` call args. | `backend.accept_all` receives only the image at index 1. | AC-006 |

### Test Flow: `delete-removes-file-and-acks`

1. **Setup**: Use `tmp_path` fixture. Create a real PNG file at `tmp_path / "img0.png"`.
   Construct a `BufferedImage` with `temp_path` set to that file. Set
   `handler._image_index_map = {0: buffered_image}` and `handler._deleted_indices = set()`.
2. **Preconditions**: `(tmp_path / "img0.png").exists()` is `True`.
3. **Steps**: Call `handler.handle_delete({"index": 0}, mock_server)`.
4. **Assertions**:
   - `not (tmp_path / "img0.png").exists()`
   - `mock_server.send` called once
   - `mock_server.send.call_args[0][0].type == MessageType.DELETE_ACK`
   - `mock_server.send.call_args[0][0].payload["index"] == 0`
5. **Teardown**: `tmp_path` fixture handles cleanup automatically.

### E2E Coverage Rule

All ACs (AC-001 through AC-006) are `unit` type and covered by the `TestDeleteCommand`
class in `tests/test_ipc_handler.py`. The E2E scenarios above exercise the same code paths
against real filesystem state, satisfying end-to-end validation for this Tauri desktop app.

## Coverage Matrix

| Spec Requirement | Acceptance Criteria |
|------------------|---------------------|
| Test DELETE removes correct image and deletes temp file | AC-001, AC-003 |
| Test ACCEPT with 0, 1, and N images in list | Covered by existing `TestAcceptCommand` |
| Test ABORT cleans up all temp files | Covered by existing `TestAbortCommand` |
| Test interleaved DELETE + navigation + ACCEPT | AC-006 |
| Test DELETE of already-deleted image (error handling) | AC-004 |
| Verify stdout output format unchanged | Covered by existing `TestAcceptCommand` |
| DELETE adds index to `_deleted_indices` | AC-001 |
| DELETE sends DELETE_ACK with correct index | AC-002 |
| DELETE of non-existent index is no-op, sends DELETE_ACK | AC-005 |

# Acceptance Criteria: Fix Init Error Event Handling

Generated: 2026-02-21T23:30:00Z
Source: spec.md

## Criteria

### AC-001: _init_backend uses _emit_state_changed for fatal errors
- **Description**: `_init_backend` must emit errors via `_emit_state_changed(server, "error", message=str(e), fatal=True)` instead of `server.send(Message(MessageType.ERROR, ...))`. The `MessageType.ERROR` send at handler.py:868-872 must be replaced.
- **Verification**: `grep -n "MessageType.ERROR" textbrush/ipc/handler.py` must not include line ~870 (the `_init_backend` exception handler). `_emit_state_changed` must be called in its place.
- **Type**: unit

### AC-002: Frontend handleMessage has case 'error' branch
- **Description**: The `handleMessage` switch in `src-tauri/ui/main.ts` must have an explicit `case 'error':` branch that handles both fatal and non-fatal error payloads. Fatal errors delegate to `handleFatalError(payload.message)`. Non-fatal errors display a transient notification.
- **Verification**: `grep -n "case 'error'" src-tauri/ui/main.ts` must return a result. No `console.warn('Unknown message type: error')` should appear when receiving error messages.
- **Type**: unit

### AC-003: Worker errors in _start_image_delivery use state-machine path (FR3 audit result)
- **Description**: Per FR3 audit, `_start_image_delivery` at handler.py:737 sends `MessageType.ERROR` with `fatal=True` for worker errors. Since this represents a state-changing fatal error (not a transient operational error), it should also use `_emit_state_changed`.
- **Verification**: `grep -n "MessageType.ERROR" textbrush/ipc/handler.py` - the worker_error send at line ~737 should be replaced with `_emit_state_changed`. All remaining `MessageType.ERROR` uses must have `fatal=False`.
- **Type**: unit

### AC-004: All remaining MessageType.ERROR usages are non-fatal operational errors
- **Description**: After changes, all remaining `server.send(Message(MessageType.ERROR, ...))` calls in handler.py must use `fatal=False`. Fatal errors must exclusively use `_emit_state_changed`.
- **Verification**: `grep -A2 "MessageType.ERROR" textbrush/ipc/handler.py | grep "fatal"` - all must show `fatal=False`.
- **Type**: unit

### AC-005: Existing test updated to reflect new behavior
- **Description**: `test_init_backend_failure_sends_fatal_error` in `tests/test_ipc_handler.py` must be updated to assert `MessageType.STATE_CHANGED` (not `MessageType.ERROR`) with `state="error"` and `fatal=True`. Success criterion 5: "All existing tests pass without modification" - since the test verifies behavior (not implementation), it must be updated to verify the new correct behavior.
- **Verification**: `uv run pytest tests/test_ipc_handler.py -v` passes. Test method checks `call_args.type == MessageType.STATE_CHANGED` and payload has `state="error"`.
- **Type**: unit

### AC-006: No console.warn for unknown message type 'error'
- **Description**: The frontend must not log `console.warn('Unknown message type: error')` when receiving an error message. The case 'error' branch must prevent fallthrough to default.
- **Verification**: Code review of `handleMessage` switch - `case 'error':` must appear before `default:` with a `break` or `return`.
- **Type**: unit

## Verification Plan

1. Run `uv run pytest tests/test_ipc_handler.py -v` to verify backend tests pass
2. Run `uv run pytest tests/ -v --ignore=tests/e2e` to verify all non-integration tests pass
3. Static code review of `textbrush/ipc/handler.py` - `_init_backend` exception handler uses `_emit_state_changed`
4. Static code review of `src-tauri/ui/main.ts` - `handleMessage` has `case 'error':` branch
5. `grep -n "MessageType.ERROR" textbrush/ipc/handler.py` shows only `fatal=False` usages remain

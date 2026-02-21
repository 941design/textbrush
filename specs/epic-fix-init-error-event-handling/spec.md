# Feature Specification: Unify Init Error Events with State Machine

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The backend has two distinct error emission paths:

1. **State-machine errors** via `state_changed` with `state="error"` — fully handled by the frontend (disables UI, shows error, schedules window close).
2. **Legacy error events** via `MessageType.ERROR` — emitted by `_init_backend` (handler.py:862) when model loading fails. The frontend `handleMessage` switch (main.ts:228) has no `case 'error':` branch, so these fall through to `default: console.warn('Unknown message type')`.

The result: if the Python backend fails during model initialization (e.g., out of memory, missing model files, corrupted weights), the user sees no feedback — the UI stays on the loading spinner indefinitely.

The spec (spec.md:386-396) defines error as a state machine state broadcast via `state_changed`. The legacy `MessageType.ERROR` event type should not be used for fatal state transitions.

## Core Functionality

Replace the legacy `MessageType.ERROR` emission in `_init_backend` with a `state_changed` event using `state="error"`, ensuring all backend errors flow through the single state-machine channel that the frontend already handles.

## Functional Requirements

### FR1: Replace Legacy Error Event in _init_backend

**Requirement:** `_init_backend` must emit errors via `_emit_state_changed(server, "error", message=str(e), fatal=True)` instead of directly sending `MessageType.ERROR`.

**Current behavior** (handler.py:858-868):
```python
except Exception as e:
    logger.error(f"Backend init failed: {e}", exc_info=True)
    server.send(
        Message(
            MessageType.ERROR, dataclass_to_dict(ErrorEvent(message=str(e), fatal=True))
        )
    )
```

**Required behavior:**
```python
except Exception as e:
    logger.error(f"Backend init failed: {e}", exc_info=True)
    self._emit_state_changed(server, "error", message=str(e), fatal=True)
```

**Rationale:** `_emit_state_changed` already validates payloads, updates `_current_state` under lock, and sends a properly formatted `STATE_CHANGED` message. The frontend's `handleStateChanged` already handles `state="error"` including the fatal path with UI lockdown and auto-close.

### FR2: Emit Loading State on Init Start

**Requirement:** `handle_init` must emit `state_changed(loading)` before starting the background init thread, so the backend explicitly broadcasts every state transition.

**Current behavior:** No `loading` state is ever emitted. The frontend hardcodes `backendState.state = "loading"` as its initial state (main.ts:32).

**Required behavior:** Add `self._emit_state_changed(server, "loading")` at the start of `handle_init`, before spawning the background thread.

**Rationale:** Spec (spec.md:411) says "Frontend never infers state; only reflects received `state_changed` events." The current frontend-side default is a workaround for this missing emission.

### FR3: Audit All Direct MessageType.ERROR Usages

**Requirement:** All remaining `server.send(Message(MessageType.ERROR, ...))` calls in handler.py must be reviewed. Non-fatal operational errors (e.g., "No images to accept" in `handle_accept`) may legitimately use the legacy `ERROR` event type for non-state-changing error responses, but any error that represents a state transition must use `_emit_state_changed`.

**Distinction:**
- **State-changing errors** (fatal failures, unrecoverable states): Must use `_emit_state_changed(server, "error", ...)`
- **Operational errors** (non-fatal, transient): May continue using `MessageType.ERROR` as a fire-and-forget notification, but the frontend must handle `type: "error"` in its message switch.

### FR4: Add Frontend Handler for Legacy Error Events

**Requirement:** Add a `case 'error':` branch to the frontend `handleMessage` switch that logs the error and displays it to the user, as a defense-in-depth measure.

**Behavior:**
- If `payload.fatal` is true: delegate to `handleFatalError(payload.message)`
- If `payload.fatal` is false: display a transient error notification (e.g., in the loading prompt area for 3 seconds)

**Rationale:** Even after FR1, the backend still uses `MessageType.ERROR` for non-fatal operational errors (e.g., "No images to accept"). These should not be silently dropped.

## Critical Constraints

1. **No new event types.** All errors must flow through existing `state_changed` or `error` message types.
2. **Backward compatible.** The frontend must handle both old and new backend versions gracefully.
3. **Thread safety.** `_emit_state_changed` already acquires `_state_lock`; verify that `_init_backend` (which runs in a background thread) does not create a deadlock when calling it.

## Integration Points

### Backend (`textbrush/ipc/handler.py`)
- `_init_backend`: Replace `MessageType.ERROR` send with `_emit_state_changed`
- `handle_init`: Add `_emit_state_changed(server, "loading")` at start

### Frontend (`src-tauri/ui/main.ts`)
- `handleMessage`: Add `case 'error':` branch
- Existing `handleStateChanged` and `handleFatalError`: No changes needed

### Protocol (`textbrush/ipc/protocol.py`)
- No changes. `MessageType.ERROR` and `MessageType.STATE_CHANGED` already exist.

## Out of Scope

- Changing the non-fatal error pattern for `handle_accept` / `handle_delete` operational errors
- Adding error recovery or retry logic
- Modifying the state machine transitions beyond what's specified

## Success Criteria

1. Model load failure in `_init_backend` causes the frontend to show the fatal error overlay with message and auto-close countdown.
2. Backend emits `state_changed(loading)` immediately on receiving `INIT`.
3. Frontend `handleMessage` switch has explicit `case 'error':` branch.
4. No `console.warn('Unknown message type: error')` appears in frontend logs during any error scenario.
5. All existing tests pass without modification.

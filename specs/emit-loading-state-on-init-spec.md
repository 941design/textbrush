# Feature Specification: Emit Loading State on Backend Init

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

The spec (spec.md:398-400) defines state transitions starting from `loading`:

> - `loading` → `idle` (model loaded successfully)
> - `loading` → `error` (model load failed)

The spec (spec.md:411) also states:

> Frontend never infers state; only reflects received `state_changed` events

However, the backend never emits `state_changed(loading)`. The first state emission is `state_changed(idle)` after model load completes (handler.py:130). The frontend works around this by hardcoding `backendState.state = "loading"` as the initial value (main.ts:32).

This means:
1. The frontend violates the "never infers state" principle.
2. If the backend is restarted (or in a future recovery scenario), the frontend has no way to know the backend is loading unless it emits the state explicitly.
3. The state machine is incomplete — the `loading` state exists conceptually but is never broadcast.

## Core Functionality

Emit `state_changed(loading)` at the start of backend initialization, making the loading state an explicit broadcast rather than a frontend assumption.

## Functional Requirements

### FR1: Emit Loading State in handle_init

**Requirement:** At the start of `handle_init`, before spawning the background init thread, emit `state_changed(loading)`.

**Implementation:**
```python
def handle_init(self, payload: dict, server: "IPCServer") -> None:
    # ... parse payload ...
    self._emit_state_changed(server, "loading")  # NEW
    # ... create backend, spawn thread ...
```

**Rationale:** This is the earliest point where the backend knows it's about to start loading. The emission happens synchronously before any async work begins.

### FR2: Frontend Removes Hardcoded Initial State (Optional)

**Requirement:** The frontend may keep its hardcoded initial `loading` state as a safe default, since the first `state_changed(loading)` event arrives almost immediately after `INIT` is sent. Removing the hardcoded default is optional but would make the frontend purely event-driven.

**If removed:** The initial state could be `null` or `"unknown"`, and the UI would show a neutral state until the first `state_changed` event arrives (milliseconds after init).

**Recommendation:** Keep the hardcoded `"loading"` default for robustness (it's the correct initial state), but add a comment noting that the backend will confirm this via an explicit `state_changed(loading)` event.

### FR3: Emit Loading State in _init_backend Thread

**Requirement:** The `_init_backend` method (which runs in a background thread) should NOT re-emit `loading` — it was already emitted synchronously in `handle_init`. This avoids a redundant state emission.

## Critical Constraints

1. **No behavioral change for normal flow.** The frontend already shows "loading model" on startup. This change makes that state backend-confirmed rather than frontend-assumed.
2. **Thread safety.** `_emit_state_changed` acquires `_state_lock`. Called from the main thread in `handle_init` before the background thread starts — no contention.
3. **Order guarantee.** The `loading` event must arrive at the frontend before `idle` or `error`. Since `handle_init` is called synchronously from `_handle_message`, and the background thread starts after the emission, this is guaranteed.

## Integration Points

### Backend (`textbrush/ipc/handler.py`)
- `handle_init`: Add `self._emit_state_changed(server, "loading")` before thread spawn

### Frontend (`src-tauri/ui/main.ts`)
- Optional: Add comment to initial state clarifying backend will confirm it

## Out of Scope

- Progress reporting during model loading (percentage, ETA)
- Sub-states of loading (downloading vs. initializing vs. compiling)
- Frontend state machine validation (asserting valid transitions)

## Success Criteria

1. After sending `INIT`, the frontend receives `state_changed(loading)` as the first event.
2. Subsequent `state_changed(idle)` or `state_changed(error)` follows after model load completes/fails.
3. Frontend rendering is unchanged (still shows "loading model" with spinner).
4. All existing tests pass.

## Note

This spec overlaps with FR2 of `fix-init-error-event-handling-spec.md`. If both specs are implemented, coordinate to ensure `handle_init` emits `loading` exactly once and `_init_backend` emits `error` via `_emit_state_changed` on failure.

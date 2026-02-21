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

**Requirement:** At the start of `handle_init`, before spawning the background init thread, emit `state_changed(loading)`. This emission is unconditional — it happens regardless of the `start_paused` flag or any other parameter.

**Implementation:**
```python
def handle_init(self, payload: dict, server: "IPCServer") -> None:
    # ... parse payload ...
    self._emit_state_changed(server, "loading")  # NEW — always emitted first
    # ... create backend, spawn thread ...
```

**start_paused path:** When `start_paused=True`, `state_changed(loading)` is still emitted at the top of `handle_init`. The paused state is then emitted afterward by the existing paused-path logic. This produces the valid `loading → paused` transition defined in spec.md:401.

**Rationale:** This is the earliest point where the backend knows it's about to start loading. The emission happens synchronously before any async work begins.

### FR2: Frontend Removes Hardcoded Initial State

**Requirement:** The frontend MUST remove its hardcoded `backendState.state = "loading"` initial value (main.ts:32). The initial state must be set to `null` (or an equivalent "unknown" sentinel), making the frontend purely event-driven. The first `state_changed(loading)` event from the backend will arrive almost immediately and establish the correct state.

**Rationale:** The frontend should never infer state (spec.md:411). The hardcoded default is a workaround for the missing emission; FR1 eliminates the need for it.

### FR3: Emit Loading State in _init_backend Thread

**Requirement:** The `_init_backend` method (which runs in a background thread) should NOT re-emit `loading` — it was already emitted synchronously in `handle_init`. This avoids a redundant state emission.

## Critical Constraints

1. **No behavioral change for normal flow.** The frontend already shows "loading model" on startup. This change makes that state backend-confirmed rather than frontend-assumed.
2. **Thread safety.** `_emit_state_changed` acquires `_state_lock`. Called from the main thread in `handle_init` before the background thread starts — no contention.
3. **Order guarantee.** The `loading` event must arrive at the frontend before `idle` or `error`. Since `handle_init` is called synchronously from `_handle_message`, and the background thread starts after the emission, this is guaranteed.
4. **loading emission is unconditional.** `state_changed(loading)` must be the first emission regardless of any payload parameters (including `start_paused`).

## Integration Points

### Backend (`textbrush/ipc/handler.py`)
- `handle_init`: Add `self._emit_state_changed(server, "loading")` before thread spawn

### Frontend (`src-tauri/ui/main.ts`)
- Remove the hardcoded `backendState.state = "loading"` initial value
- Set initial state to `null` so the UI reflects received events only

## Out of Scope

- Progress reporting during model loading (percentage, ETA)
- Sub-states of loading (downloading vs. initializing vs. compiling)
- Frontend state machine validation (asserting valid transitions)

## Success Criteria

1. After sending `INIT`, the frontend receives `state_changed(loading)` as the first event.
2. Subsequent `state_changed(idle)` or `state_changed(error)` follows after model load completes/fails.
3. Frontend rendering is unchanged (still shows "loading model" with spinner, now driven by the received `state_changed(loading)` event).
4. All existing tests pass.
5. A new unit test for `handle_init` asserts that `_emit_state_changed` is called with `state="loading"` as the first emission, before the background thread is started.
6. The frontend's initial state variable is `null` (not hardcoded `"loading"`), confirming purely event-driven state management.

## Note

This spec overlaps with FR2 of `fix-init-error-event-handling-spec.md`. If both specs are implemented, coordinate to ensure `handle_init` emits `loading` exactly once and `_init_backend` emits `error` via `_emit_state_changed` on failure. This spec is a prerequisite for `fix-init-error-event-handling-spec.md` — implement this first so the companion spec can build on the guaranteed loading emission.

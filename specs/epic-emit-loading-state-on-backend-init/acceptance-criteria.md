# Acceptance Criteria: Emit Loading State on Backend Init

Generated: 2026-02-21T21:15:00Z
Source: spec.md

## Overview

These criteria verify that `handle_init` emits `state_changed(loading)` as its first synchronous
action, that the frontend no longer hardcodes the initial loading state, and that all dependent
guards and tests are updated to reflect a `null` initial `backendState`.

## Criteria

### AC-001: handle_init emits state_changed(loading) before spawning the background thread

- **Description**: After `handle_init` is called, `_emit_state_changed` is invoked with `state="loading"` synchronously in the main thread, before `threading.Thread(...).start()` is called. The `loading` emission must be the first `STATE_CHANGED` call in `mock_server.send.call_args_list` when `_init_backend` is patched out.
- **Verification**: Unit test in `TestInitCommand`: patch `handler._init_backend`, call `handler.handle_init(payload, mock_server)`, filter `mock_server.send.call_args_list` for `MessageType.STATE_CHANGED`, assert the first such call has `msg.data["state"] == "loading"`.
- **Type**: unit
- **Source**: FR1 — Emit Loading State in handle_init

### AC-002: handle_init emits state_changed(loading) unconditionally regardless of start_paused

- **Description**: When `handle_init` is called with any payload combination (including `start_paused=True` if that field is present), `STATE_CHANGED(loading)` is still the first state emission. No conditional branch skips the loading emission.
- **Verification**: Unit test: call `handle_init` with `start_paused=True` in the payload (if the field is accepted) with `_init_backend` patched; assert first `STATE_CHANGED` message has `state == "loading"`.
- **Type**: unit
- **Source**: FR1 — loading emission is unconditional; spec constraint: "emission is unconditional"

### AC-003: _init_backend does not re-emit state_changed(loading)

- **Description**: The `_init_backend` method does not call `_emit_state_changed` with `state="loading"`. Exactly one `STATE_CHANGED(loading)` message is sent per `handle_init` invocation.
- **Verification**: Unit test: call `handle_init` with a mock `_init_backend` that does call `_emit_state_changed(server, "loading")` — this test should NOT exist and no such call should appear in the real implementation. Verify by inspecting `_init_backend` source and confirming absence of any `_emit_state_changed(server, "loading")` call there. Additionally, in a full integration flow test, count `STATE_CHANGED(loading)` messages and assert count == 1.
- **Type**: unit
- **Source**: FR3 — _init_backend must NOT re-emit loading

### AC-004: loading event arrives at frontend before idle or error

- **Description**: In the full IPC message sequence, the `STATE_CHANGED` event with `state="loading"` has a lower sequence index than any subsequent `STATE_CHANGED` event with `state="idle"` or `state="error"`.
- **Verification**: Integration test (slow): start the backend with a real IPC session, collect all received `state_changed` events in order; assert first event is `loading`, and eventual `idle` or `error` follows it.
- **Type**: integration
- **Source**: Spec constraint: "The loading event must arrive at the frontend before idle or error"

### AC-005: Frontend initial backendState is null

- **Description**: In `src-tauri/ui/main.ts`, the `AppState` initializer sets `backendState` to `null`, not `{ state: "loading" }`. The string literal `"loading"` must not appear in the `backendState` field of the initial state object at line 31-33.
- **Verification**: Code inspection of `main.ts` lines 29-46: confirm `backendState: null` (or a TypeScript `null` assignment). Running `grep -n "state.*loading" src-tauri/ui/main.ts` must not match the initial state block at lines 31-33.
- **Type**: unit
- **Source**: FR2 — Frontend Removes Hardcoded Initial State

### AC-006: updateLoadingOverlayForState guards against null backendState

- **Description**: `updateLoadingOverlayForState` in `main.ts` does not throw a TypeError when `state.backendState` is `null`. Any access to `state.backendState.state` is guarded by a null check before dereferencing.
- **Verification**: Unit test or static inspection: call `updateLoadingOverlayForState()` with `state.backendState = null`; assert no uncaught TypeError is thrown and the function returns without crashing.
- **Type**: unit
- **Source**: FR2 — setting backendState to null requires guarding all access sites; exploration note: "requires updating all guards that access state.backendState.state"

### AC-007: next() isAlreadyGenerating guard handles null backendState

- **Description**: The `isAlreadyGenerating` check at `main.ts:1008` (`state.backendState.state === "generating" || state.backendState.state === "loading"`) does not throw when `state.backendState` is `null`. The expression evaluates to `false` (not generating) when `backendState` is null.
- **Verification**: Unit test: set `state.backendState = null`, call `next()`; assert no uncaught TypeError and the function proceeds past the guard without early return.
- **Type**: unit
- **Source**: FR2 — exploration note: "isAlreadyGenerating at main.ts:1008 is one such guard"

### AC-008: createMockState() in state-sync-integration.test.js initializes backendState to null

- **Description**: `createMockState()` in `src-tauri/ui/state-sync-integration.test.js` sets `backendState: null`, mirroring the updated `AppState` initializer in `main.ts`. The previous value `{ state: "loading" }` is removed.
- **Verification**: Code inspection of `state-sync-integration.test.js` lines 28-47: confirm `backendState: null`. Running `node --test src-tauri/ui/state-sync-integration.test.js` passes with no failures.
- **Type**: unit
- **Source**: FR2 — exploration note: "createMockState() mirrors main.ts AppState init; must be updated when main.ts changes"

### AC-009: Existing TestInitCommand tests continue to pass after the change

- **Description**: All pre-existing test methods in `TestInitCommand` (`test_init_payload_parsing`, `test_init_creates_backend`, `test_init_starts_background_thread`, etc.) pass without modification, confirming the new `_emit_state_changed` call does not break existing behaviour.
- **Verification**: Run `uv run pytest tests/test_ipc_handler.py::TestInitCommand -v`; all tests pass with exit code 0.
- **Type**: unit
- **Source**: Spec success criterion 4 — "All existing tests pass"

### AC-010: New unit test asserts loading is the first STATE_CHANGED emission from handle_init

- **Description**: A new test method exists in `TestInitCommand` (e.g. `test_init_emits_loading_state_first`) that patches `handler._init_backend`, calls `handler.handle_init`, filters `mock_server.send.call_args_list` for `MessageType.STATE_CHANGED`, and asserts: (a) at least one `STATE_CHANGED` message was sent, (b) the first `STATE_CHANGED` message has `data["state"] == "loading"`.
- **Verification**: Run `uv run pytest tests/test_ipc_handler.py::TestInitCommand::test_init_emits_loading_state_first -v`; test exists and passes.
- **Type**: unit
- **Source**: Spec success criterion 5 — "A new unit test for handle_init asserts _emit_state_changed is called with state=loading as the first emission"

### AC-011: Frontend renders loading overlay when state_changed(loading) event is received

- **Description**: When `handleStateChanged` is called with payload `{ state: "loading" }` and `state.backendState` was previously `null`, `state.backendState` is set to `{ state: "loading" }` and `updateLoadingOverlayForState()` subsequently sets the loading label text to `"loading model"` and removes the `hidden` class from the loading spinner.
- **Verification**: Frontend integration test in `state-sync-integration.test.js`: start with `state.backendState = null`, call `handleStateChanged({ state: "loading" })`, assert `state.backendState.state === "loading"` and loading spinner is visible.
- **Type**: unit
- **Source**: Spec success criterion 3 — "Frontend rendering is unchanged (still shows loading model with spinner, now driven by the received state_changed(loading) event)"

### AC-012: Frontend state-sync integration tests pass with null initial backendState

- **Description**: The full `state-sync-integration.test.js` test suite passes after `createMockState()` is updated to `backendState: null`. No test relies on the initial hardcoded `{ state: "loading" }` value as a precondition.
- **Verification**: Run `node --test src-tauri/ui/state-sync-integration.test.js`; all tests pass with exit code 0.
- **Type**: unit
- **Source**: FR2 — frontend test file must be kept consistent with main.ts

---

## E2E Test Plan

### Infrastructure Requirements

- **Docker Compose**: Not applicable — textbrush runs as a Tauri desktop application with a sidecar Python backend. E2E tests use the built application binary or `tauri dev` mode.
- **Playwright**: Browser automation against the Tauri WebView (via `@playwright/test` with Tauri plugin or headless WebView capture).
- **Preconditions**: A valid model config that the backend can load within the test timeout.

### E2E Scenarios

| Scenario | User Steps (Browser) | Expected Outcome | ACs Validated |
|----------|---------------------|-------------------|---------------|
| loading-state-received-before-idle | 1. Launch application. 2. Observe loading overlay immediately on startup. 3. Wait for model to finish loading. | Loading overlay shows "loading model" spinner immediately from first frame; transitions to idle/generation state after model loads. | AC-001, AC-004, AC-011 |
| no-initial-hardcoded-state | 1. Launch application with network inspector or console logging enabled. 2. Observe first `state_changed` event logged to console. | Console log shows `Backend state changed: loading` as the first state_changed log line, confirming the state came from the backend event, not a hardcoded value. | AC-005, AC-001 |

### Test Flow: loading-state-received-before-idle

1. **Setup**: Build or start textbrush in dev mode with a valid model config.
2. **Preconditions**: Application is not already running; no cached backend state.
3. **User steps**:
   1. Launch the application window.
   2. Immediately capture the loading overlay state (within 500 ms of window showing).
   3. Wait up to 60 seconds for the overlay to transition away from "loading model".
4. **Assertions** (Playwright):
   - Within 500 ms: `#loading-overlay` is visible and `#loading-label` has text content `"loading model"`.
   - `#loading-spinner` does not have the `hidden` class.
   - Console contains `"Backend state changed: loading"` logged by `handleStateChanged`.
   - Eventually: `#loading-overlay` transitions to a non-loading state (`"ready"` or `"generating"`).
5. **Teardown**: Close the application window.

### E2E Coverage

- AC-001, AC-004, AC-011 are covered by the `loading-state-received-before-idle` scenario.
- AC-005 is covered by the `no-initial-hardcoded-state` scenario confirming event origin.
- AC-006, AC-007 are covered implicitly: if null-guard is missing, the application crashes on startup before the E2E scenario can complete.

---

## Verification Plan

### Automated Tests

- **Unit tests** (Python): AC-001, AC-002, AC-003, AC-009, AC-010 — run via `uv run pytest tests/test_ipc_handler.py::TestInitCommand -v`
- **Unit tests** (JavaScript): AC-005, AC-006, AC-007, AC-008, AC-011, AC-012 — run via `node --test src-tauri/ui/state-sync-integration.test.js`
- **Integration tests**: AC-004 — run via `uv run pytest tests/test_ipc_integration.py --run-slow` (requires user confirmation per CLAUDE.md)
- **E2E tests**: AC-001, AC-004, AC-005, AC-011 (and implicitly AC-006, AC-007) — run via Playwright against built Tauri application

### Manual Verification

- **AC-005**: Inspect `src-tauri/ui/main.ts` lines 29-46 to confirm `backendState: null` with no string literal `"loading"` in the initial state block.
- **AC-011**: Launch the application and visually confirm the loading overlay appears immediately with "loading model" text before the model finishes loading.

## Coverage Matrix

| Spec Requirement | Acceptance Criteria |
|------------------|---------------------|
| FR1: Emit state_changed(loading) at start of handle_init before thread spawn | AC-001, AC-002, AC-010 |
| FR2: Frontend removes hardcoded backendState initial value, sets to null | AC-005, AC-008 |
| FR2: All access sites guarded against null backendState | AC-006, AC-007 |
| FR2: Frontend rendering unchanged (loading overlay still appears) | AC-011, AC-012 |
| FR3: _init_backend must not re-emit loading | AC-003 |
| Constraint: loading event arrives before idle/error | AC-004 |
| Constraint: thread safety (called from main thread before background thread starts) | AC-001 (patching _init_backend proves synchronous call ordering) |
| Success criterion: all existing tests pass | AC-009 |
| Success criterion: new unit test for loading emission | AC-010 |
| Success criterion: frontend initial state is null | AC-005 |

# Textbrush: Missed Acceptance Criteria Report

Generated: 2026-02-21
Sources: pipeline improvement JSON files, verification results CSV, spec files, user-stories.md, conversation transcripts (125 sessions)

## Summary

- **Total missed/failed acceptance criteria: 63**
- **Still open/unfixed: 21** (12 not fixed, 4 partially addressed, 3 not implemented, 2 systemic)
- **Fixed during remediation: 42**

### By Severity

| Severity | Count | Description |
|----------|-------|-------------|
| 10 (Critical) | 6 | Tauri config, sidecar spawn, DELETE field mismatch, undefined commands, runtime crash |
| 9 (High) | 8 | Race conditions, missing E2E tests, behavior changes, exit contract violations |
| 8 (Major) | 12 | Memory leaks, skip latency, missing integration tests, metadata sync |
| 7 (Significant) | 7 | Download failure tests, edge case tests, dependency versions, layout issues |
| 6 (Moderate) | 11 | Security gaps, credential masking, dead code, config conflicts |
| 4-5 (Minor) | 7 | Obsolete files, type hints, documentation |
| Unknown | 5 | Unresolved or low-confidence findings |

---

## Feature 1: Increment 1 -- Foundation (2026-01-06)

**Outcome:** ACCEPTED (after remediation)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | CLI exit code contract: exit 0 for success, exit 1 for error, exit 2 for not-implemented | Hardcoded `sys.exit(1)` for all paths instead of distinguishing failure types | 8 | Fixed |
| 2 | Model download failure scenarios produce clear error messages | No tests for network/auth error handling | 7 | Fixed |
| 3 | Dependency version constraints prevent breaking changes | No upper bounds on dependencies in pyproject.toml | 7 | Fixed |
| 4 | Output path handling must not allow path traversal attacks | No path normalization via `expanduser().resolve()` | 6 | Fixed |
| 5 | Configuration precedence does not unexpectedly override critical settings | Config precedence conflict tests missing | 6 | Fixed |
| 6 | HuggingFace token handling does not expose credentials | Token handling lacked explicit masking in error messages | 6 | Fixed |
| 7 | TOML configuration parsing handles edge cases | Missing tests for XDG paths, type mismatches, unknown sections | 6 | Fixed |
| 8 | All public functions are properly type-hinted | 7 module variables lacked PEP 526 type annotations | 4 | Fixed |
| 9 | Obsolete files cleaned up | `.exploration/` directory not cleaned up | 2 | Fixed |

---

## Feature 2: Increment 3 -- Tauri IPC Integration (2026-01-07)

**Outcome:** REVISION_REQUIRED

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | No race conditions between image delivery thread and skip/accept handlers on shared state | `_current_image` accessed by multiple threads without lock | 9 | Fixed |
| 2 | Backend properly cleaned up on abnormal IPC server termination | No `finally` block to ensure `backend.shutdown()` on abnormal termination | 8 | Fixed |
| 3 | Integration tests validate complete workflow through `server.run()` | No E2E integration tests existed | 8 | Fixed |
| 4 | Worker errors propagated through IPC layer to UI | Errors from inference worker not propagated via IPC | 7 | Fixed |
| 5 | No parallel/duplicate implementations | Duplicate message formatting logic in multiple locations | 6 | Fixed |
| 6 | IPC layer validates all incoming message payloads | Only partial validation -- no explicit injection protection | 5 | **Partially addressed** |
| 7 | All message types in IPC protocol covered by tests | Not all IPC message types had dedicated tests | 5 | **NOT FIXED** |
| 8 | Backpressure handled when UI cannot consume images fast enough | No explicit backpressure handling in spec | 4 | **Partially addressed** |

---

## Feature 3: Increment 4 -- UI Implementation (2026-01-07)

**Outcome:** REVISION_REQUIRED

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | Tauri 2.x `withGlobalTauri:true` configured | Missing from `tauri.conf.json` -- JS API not injected | 10 | Fixed |
| 2 | Tauri 2.x permissions properly configured | Missing permissions blocked event listening entirely | 10 | Fixed |
| 3 | Python sidecar spawned with correct environment | Used `python` instead of `uv run python` | 10 | Fixed |
| 4 | UI state updates and IPC messages do not race | Race conditions, no action queue to serialize operations | 9 | Fixed |
| 5 | Exit handling maintains stdout contract on OS window close | Missing `window.on_window_event` handler | 9 | Fixed |
| 6 | Integration tests validate complete UI workflow | No E2E integration tests for complete UI workflow | 9 | **NOT FIXED** |
| 7 | Base64 image data does not accumulate in memory without cleanup | Memory leak: data URLs accumulated without cleanup | 8 | Fixed |
| 8 | Skip latency < 100ms when buffer is non-empty | Animations blocked skip even when buffer had images | 8 | Fixed |
| 9 | Edge case tests for empty buffer, sidecar crash, window close during generation | No tests for critical edge cases | 7 | **NOT FIXED** |
| 10 | No duplicate CSS @keyframes | Duplicate `@keyframes` in both `main.css` and `animations.css` | 7 | Fixed |
| 11 | Obsolete files cleaned up | `test_main.js` and `.audit-reports/` not deleted | 4 | Fixed |
| 12 | No unused CSS variables | 3 unused CSS variables in `variables.css` | 2 | Fixed |

---

## Feature 4: Increment 5 -- Integration, Testing & Packaging (2026-01-07)

**Outcome:** REVISION_REQUIRED (user rejected despite verification passing)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | CI workflows validate both fast unit tests AND slow integration tests | CI excluded ALL E2E tests via pytest marker filtering | 8 | Fixed |
| 2 | Tauri bundle config separates dev and release settings | No `[profile.release]` in `Cargo.toml` | 8 | Fixed |
| 3 | Documentation accurately reflects implemented features | README showed incorrect CLI syntax | 6 | Fixed |
| 4 | Obsolete files cleaned up | `.exploration/`, `.verification-questions.md`, stale files | 5 | Fixed |
| 5 | No dead code | `textbrush/errors.py` (114 lines) completely unused | 4 | Fixed |
| 6 | User's unstated quality expectations met | User rejected despite all verification passing -- blind spot in verification questions | ? | **NOT RESOLVED** |

---

## Feature 5: UI Enhancements (2026-01-08)

**Outcome:** ACCEPTED (after remediation)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | Refactored `navigateToNext()` preserves original behavior | Changed: only requested images when `buffer > 0`, but original always requested | 9 | Fixed (regression introduced then caught) |
| 2 | Multi-path exit contract: `handleAccepted` uses `getAllRetainedPaths` | Called `print_and_exit` with single path instead of `print_paths_and_exit` | 9 | Fixed |
| 3 | Blob URLs properly revoked in ALL navigation paths | Missing cleanup in `handleAccepted` and `handleAborted` exit paths | 8 | Fixed |
| 4 | Integration tests validate complete workflow | No E2E multi-path acceptance test | 8 | Fixed |
| 5 | Dead code detected and removed | Functions reported "unused" were actually needed but not wired up | 6 | Fixed |

---

## Feature 6: Image Metadata Split View (2026-01-09)

**Outcome:** BLOCKED (application fails to launch)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | Application launches successfully after remediation | App fails to launch despite all tests passing -- runtime/test environment mismatch | 10 | **NOT FIXED** |
| 2 | Tests validate metadata sync across all state transitions | No tests for metadata (prompt, model, seed) sync across generation/navigation/history | 8 | Tests added but **feature blocked** |
| 3 | IPC contract tests for backend-frontend metadata flow | No IPC contract tests existed | 8 | Tests added but **feature blocked** |
| 4 | Responsive layout at <820px viewport width | Layout violation detected | 7 | **Status unclear** |
| 5 | Metadata panel visibility: hide when no image loaded | Missing `updateMetadataPanel(null)` calls in 2 code paths | 6 | Fixed but **feature blocked** |
| 6 | No dead code (unused CSS classes) | 7 unused CSS classes and duplicate rule definitions | 6 | Fixed |
| 7 | FR3: 4 acceptance criteria, only 2 correctly implemented | Loading state and empty state handling broken (50% compliance) | High | **Partially fixed** |

---

## Feature 7: Backend Owns Image List (2026-01-10)

**Outcome:** ACCEPTED (after remediation)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | Frontend does not call undefined Tauri commands | Called undefined `print_and_exit` Tauri command, runtime failure | 9 | Fixed |
| 2 | Integration tests for DELETE command workflow | Missing integration tests for DELETE workflow E2E | 8 | **NOT FIXED** |
| 3 | Tests for ACCEPT with 0 images, DELETE of already-deleted images, interleaved operations | Edge cases listed in spec's Testing Considerations but not implemented | 7 | **NOT FIXED** |
| 4 | Spec: what happens when user deletes all images then clicks Accept? | Implementation sent ERROR event, violating CLI Exit Contract (exit 0 on acceptance) | High | **Spec gap -- behavior undefined** |
| 5 | No parallel implementations | Duplicate exit handlers: `print_and_exit` and `print_paths_and_exit` | 6 | Fixed |
| 6 | Obsolete test files cleaned up | Obsolete test file not deleted | 4 | Fixed |

---

## Feature 8: Backend State Synchronization (2026-01-11)

**Outcome:** ACCEPTED (after remediation)

| # | Acceptance Criterion | Failure Reason | Severity | Status |
|---|---|---|---|---|
| 1 | DELETE command uses correct field name from dataclass | Used non-existent `image_id` field instead of `index`, causing runtime crash | 10 | Fixed |
| 2 | Integration tests validate complete workflow | Missing E2E tests; round 2 reached only "partial" status | 9->5 | **Partially fixed** |
| 3 | Frontend handles state_changed events for all 5 states | Missing E2E tests for Tauri event listener wiring and message dispatch | High | **NOT FULLY TESTED** |
| 4 | Frontend eliminates all optimistic state updates | Low confidence (0.5) in verification | Medium | **Uncertain** |
| 5 | Spinner correctly displays all 5 backend states | Low confidence (0.5) in verification | Medium | **Uncertain** |

---

## Cross-Cutting / Planned Features (Not Yet Implemented)

| # | Feature | AC Description | Status |
|---|---|---|---|
| 1 | Story 8.1: CLI Model Download (`--download-model`) | Error messages reference non-existent flag, confusing users | **NOT IMPLEMENTED** (spec exists) |
| 2 | Story 8.2: Manual Update Check (`--check-updates`) | Feature not implemented | **NOT IMPLEMENTED** (spec exists) |
| 3 | JPEG EXIF metadata support | PNG metadata works but JPEG EXIF requires `piexif` dependency | **NOT IMPLEMENTED** |
| 4 | Specification gap: No "Test Strategy" section | Specs define WHAT but omit HOW to validate -- root cause of repeated E2E gaps | **SYSTEMIC GAP** |

---

## Persistent Unfixed Items (High Priority)

These items recur across multiple features and remain unresolved:

1. **Missing E2E integration tests for full Tauri UI workflow** -- repeated in Features 3, 7, 8. No end-to-end test exercises the complete Tauri sidecar + IPC + frontend flow.
2. **Image Metadata Split View entirely BLOCKED** -- Feature 6 app crashes at runtime despite tests passing. Runtime/test environment mismatch.
3. **DELETE workflow edge case tests missing** -- Feature 7: ACCEPT with 0 images, DELETE of already-deleted, interleaved operations.
4. **Frontend state_changed for all 5 states not E2E tested** -- Feature 8: property tests exist but no real Tauri environment test.
5. **`--download-model` flag referenced in errors but not implemented** -- Users see misleading error messages.
6. **Zero-images-then-accept behavior undefined in spec** -- Feature 7: implementation sends ERROR, violating exit contract.
7. **Specification lacks Test Strategy section** -- systemic cause of repeatedly missing integration/E2E tests across all features.

# Acceptance Criteria: Fix Default Resolution Inconsistency

Generated: 2026-02-21T00:00:00Z
Source: spec.md

## Criteria

### AC-001: Rust get_default_resolution returns smallest values
- **Description**: The `get_default_resolution` function in `launch_args.rs` must return the first (smallest) resolution for each supported aspect ratio, matching `cli.py`'s `SUPPORTED_RATIOS[ratio][0]`.
- **Verification**: Run `cargo test get_default_resolution_returns_correct_values` in `src-tauri/` — all assertions must pass.
- **Type**: unit

### AC-002: All Rust tests pass
- **Description**: No existing tests are broken by the change.
- **Verification**: Run `cargo test` in `src-tauri/` — all tests pass with no failures.
- **Type**: unit

### AC-003: Three sources agree on defaults
- **Description**: `cli.py` SUPPORTED_RATIOS first entries, `config_controls.ts` ASPECT_RATIO_RESOLUTIONS first entries, and `launch_args.rs` get_default_resolution all return the same (width, height) for each ratio.
- **Verification**: Manual inspection of the three files confirms matching values for all 6 ratios (1:1, 16:9, 3:1, 4:1, 4:5, 9:16).
- **Type**: manual

### AC-004: spec.md documents first-entry-is-default
- **Description**: `specs/spec.md` includes a note that the first resolution in each ratio list is the default.
- **Verification**: `grep -n "default" specs/spec.md` shows a note near the resolution tables.
- **Type**: manual

## Verification Plan

1. Update `get_default_resolution` in `launch_args.rs` with the correct smaller values.
2. Update the test assertions to match new values.
3. Run `cargo test` to confirm all tests pass.
4. Inspect `cli.py`, `config_controls.ts`, and `launch_args.rs` to confirm all three agree.
5. Add a note to `specs/spec.md` near the resolution tables.

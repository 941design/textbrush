# Feature Specification: Unify Default Resolutions Across Components

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

Default resolutions for aspect ratios are defined in three places with inconsistent values:

| Component | Location | 16:9 Default | 1:1 Default |
|-----------|----------|-------------|-------------|
| Python CLI | `textbrush/cli.py:16-23` (SUPPORTED_RATIOS, first entry) | 640×360 | 256×256 |
| TS config controls | `src-tauri/ui/config_controls.ts:20-48` (first entry) | 640×360 | 256×256 |
| Rust launch_args | `src-tauri/src/launch_args.rs:21-30` | **1280×720** | **256×256** |

The Python CLI and TypeScript config controls agree — both use the first (smallest) resolution as the default. But `launch_args.rs` uses a different, larger resolution for several ratios:

| Ratio | CLI/TS Default | Rust Default |
|-------|---------------|-------------|
| 1:1   | 256×256       | 256×256     |
| 16:9  | 640×360       | **1280×720** |
| 3:1   | 900×300       | **1500×500** |
| 4:1   | 1200×300      | **1600×400** |
| 4:5   | 540×675       | **1080×1350** |
| 9:16  | 360×640       | **1080×1920** |

The Rust defaults are applied when the user launches the Tauri GUI without explicit `--width`/`--height` arguments. The Python defaults are used in CLI mode. The result: the same `--aspect-ratio 16:9` produces different compute costs depending on the entry path (GUI: 1280×720 = 921,600 pixels; CLI: 640×360 = 230,400 pixels — a 4× difference).

## Core Functionality

Establish a single source of truth for default resolutions and ensure all components use it.

## Functional Requirements

### FR1: Choose Canonical Defaults

**Decision required:** Should the default be the smallest or a middle resolution?

**Option A — Smallest (match CLI/TS):**
- Lower compute cost, faster generation
- Better for development/testing
- Consistent with "start small" philosophy
- Update `launch_args.rs` to use first entries

**Option B — Middle (match Rust):**
- More useful output quality for users
- Closer to typical display resolution
- Update `cli.py` and `config_controls.ts` to use middle entries

**Recommendation:** Option A (smallest). The default should be the cheapest option. Users can increase resolution explicitly via `+` button in UI or `--width`/`--height` in CLI.

### FR2: Update launch_args.rs Defaults

**Requirement:** Change `get_default_resolution` in `launch_args.rs` to return the first (smallest) resolution for each ratio, matching `SUPPORTED_RATIOS[ratio][0]` in `cli.py`.

**Required values:**
```rust
fn get_default_resolution(aspect_ratio: &str) -> (u32, u32) {
    match aspect_ratio {
        "1:1" => (256, 256),
        "16:9" => (640, 360),
        "3:1" => (900, 300),
        "4:1" => (1200, 300),
        "4:5" => (540, 675),
        "9:16" => (360, 640),
        _ => (256, 256),
    }
}
```

### FR3: Update launch_args.rs Tests

**Requirement:** Update `get_default_resolution_returns_correct_values` test (launch_args.rs:213-221) to match new values.

### FR4: Document Resolution Tables

**Requirement:** The spec (spec.md:266-272) already lists the correct resolution tables. Add a note clarifying that the first entry in each list is the default.

## Critical Constraints

1. **All three sources must agree.** After this change, `cli.py`, `config_controls.ts`, and `launch_args.rs` must all produce the same default for each aspect ratio.
2. **No new resolution options.** The available resolutions per ratio are unchanged — only the default selection changes.
3. **UI config controls unchanged.** The TypeScript config controls already use the first entry as default and provide +/- buttons to change resolution.

## Integration Points

### Rust (`src-tauri/src/launch_args.rs`)
- `get_default_resolution`: Update all return values
- `tests::get_default_resolution_returns_correct_values`: Update assertions

### Python (`textbrush/cli.py`)
- No changes needed (already correct)

### TypeScript (`src-tauri/ui/config_controls.ts`)
- No changes needed (already correct)

### Spec (`specs/spec.md`)
- Add note that first resolution in each ratio's list is the default

## Out of Scope

- Adding more resolution options per ratio
- Allowing user-configurable default resolution in config file
- Non-standard aspect ratios
- Automatic resolution selection based on hardware capability

## Success Criteria

1. `launch_args.rs` defaults match `cli.py` SUPPORTED_RATIOS first entries for all ratios.
2. Launching the GUI without explicit dimensions uses the smallest resolution for the selected aspect ratio.
3. Launching CLI without explicit dimensions uses the same smallest resolution.
4. All Rust tests pass with updated assertions.
5. No user-visible behavior change for users who explicitly set dimensions.

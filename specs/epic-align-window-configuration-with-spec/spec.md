---
epic: align-window-configuration-with-spec
created: 2026-02-21T00:00:00Z
status: initializing
---

# Feature Specification: Align Window Configuration with Spec

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The spec (spec.md:354-357) defines the window configuration:

> **Window Configuration:**
> * Fixed size: 800x700 pixels
> * Centered, non-resizable
> * macOS minimum: 10.15

The actual configuration in `tauri.conf.json` diverges on all dimension and resize properties:

| Property   | Spec     | Actual   |
|------------|----------|----------|
| Width      | 800      | 1024     |
| Height     | 700      | 768      |
| Resizable  | false    | true     |
| Centered   | true     | true     |

## Core Functionality

Update `tauri.conf.json` to match the spec, or update the spec to match the implementation. This requires a deliberate decision on which values are correct.

## Functional Requirements

### FR1: Resolve Window Dimensions

**Decision required:** Which dimensions are correct?

**Option A — Match spec (800x700):**
- Smaller footprint, more constrained layout
- May cause layout issues if CSS was designed for 1024x768
- Requires CSS audit to ensure all elements fit

**Option B — Update spec (1024x768):**
- Current layout already works at this size
- More room for image preview and controls
- Common desktop resolution ratio

**Recommendation:** Option B is lower risk — the UI already works at 1024x768 and this is a more reasonable size for an image review application. Update the spec rather than break the UI.

### FR2: Resolve Resizable Property

**Decision required:** Should the window be resizable?

**Option A — Non-resizable (match spec):**
- Simpler layout — no responsive design needed
- Predictable UI appearance
- Set `"resizable": false` in tauri.conf.json

**Option B — Resizable (keep current):**
- More flexible for different screen sizes
- Requires responsive CSS (which may or may not exist)
- Update spec to say "resizable" or remove the constraint

**Recommendation:** Set non-resizable (Option A) unless responsive CSS is already in place and tested. A fixed-size image review tool benefits from a predictable layout.

### FR3: Apply Configuration Changes

**Requirement:** Update `tauri.conf.json` to the resolved values.

**If Option A (both):**
```json
{
  "width": 800,
  "height": 700,
  "resizable": false,
  "center": true
}
```

**If Option B (dimensions) + Option A (resize):**
```json
{
  "width": 1024,
  "height": 768,
  "resizable": false,
  "center": true
}
```

### FR4: Update Spec to Match Final Decision

**Requirement:** After resolving FR1 and FR2, update `specs/spec.md` line 355-356 to match the chosen configuration. Spec and implementation must agree.

## Critical Constraints

1. **CSS audit required.** If dimensions change, verify that all UI elements (header bar, image container, controls, nav dots, metadata panel, status bar) render correctly at the target size.
2. **No minimum size constraints.** Tauri's `minWidth`/`minHeight` are not currently set. If resizable is kept, these should be added to prevent the window from being shrunk below usable dimensions.
3. **Cross-platform.** Both macOS and Linux must be tested at the final dimensions.

## Integration Points

### Tauri Configuration (`src-tauri/tauri.conf.json`)
- `app.windows[0].width`: Update value
- `app.windows[0].height`: Update value
- `app.windows[0].resizable`: Set to resolved value

### Spec (`specs/spec.md`)
- Line 355-356: Update to match implementation

### CSS (`src-tauri/ui/`)
- Audit and adjust if dimensions change

## Out of Scope

- Adding responsive/fluid layout support
- Multi-monitor awareness
- Window position persistence across launches
- Fullscreen mode

## Success Criteria

1. `tauri.conf.json` window properties match `spec.md` exactly.
2. All UI elements render correctly at the configured dimensions.
3. If non-resizable: window cannot be resized by the user.
4. Window appears centered on screen on both macOS and Linux.

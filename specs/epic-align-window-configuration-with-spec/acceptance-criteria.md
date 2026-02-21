# Acceptance Criteria: Align Window Configuration with Spec

Generated: 2026-02-21T00:00:00Z
Source: spec.md

## Decision

Following the spec's recommendations:
- **Dimensions**: Keep 1024x768 (Option B) — the CSS metadata panel (350px wide) requires at least ~800px horizontal space, and the 820px responsive breakpoint would degrade layout at 800px.
- **Resizable**: Set to false (Option A) — non-resizable gives predictable, tested layout.
- **Spec update**: Update spec.md to reflect 1024x768, non-resizable.

## Criteria

### AC-001: tauri.conf.json window width is 1024
- **Description**: `src-tauri/tauri.conf.json` must have `app.windows[0].width` set to `1024`.
- **Verification**: `jq '.app.windows[0].width' src-tauri/tauri.conf.json` returns `1024`
- **Type**: unit

### AC-002: tauri.conf.json window height is 768
- **Description**: `src-tauri/tauri.conf.json` must have `app.windows[0].height` set to `768`.
- **Verification**: `jq '.app.windows[0].height' src-tauri/tauri.conf.json` returns `768`
- **Type**: unit

### AC-003: tauri.conf.json window is non-resizable
- **Description**: `src-tauri/tauri.conf.json` must have `app.windows[0].resizable` set to `false`.
- **Verification**: `jq '.app.windows[0].resizable' src-tauri/tauri.conf.json` returns `false`
- **Type**: unit

### AC-004: tauri.conf.json window is centered
- **Description**: `src-tauri/tauri.conf.json` must have `app.windows[0].center` set to `true`.
- **Verification**: `jq '.app.windows[0].center' src-tauri/tauri.conf.json` returns `true`
- **Type**: unit

### AC-005: spec.md window configuration section matches tauri.conf.json
- **Description**: `specs/spec.md` Window Configuration section must say 1024x768, non-resizable, and centered — matching the tauri.conf.json values exactly.
- **Verification**: `grep -A3 'Window Configuration' specs/spec.md` shows 1024x768 and non-resizable
- **Type**: unit

## Verification Plan

All criteria are verifiable via `jq` queries on `tauri.conf.json` and `grep` on `specs/spec.md`. No build or runtime testing is required since this is a pure configuration + documentation update. The CSS layout analysis (in exploration.json) confirms 1024x768 is safe for the current layout.

# Feature Specification: Remove Runtime uv Dependency for Packaged Builds

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The Tauri app spawns the Python backend sidecar via (commands.rs:64):

```rust
Sidecar::spawn("uv", &["run", "python", "-m", "textbrush.ipc"])
```

This requires `uv` to be installed and on `PATH` at runtime. While this works in a development environment (where `uv` is used for package management per CLAUDE.md), a packaged `.app` or Linux binary distributed via GitHub Releases will fail on systems without `uv` installed.

The spec (spec.md:240) says "Tauri app spawns Python backend on startup" — it does not prescribe the spawn mechanism. A production build must not depend on external tooling that end users may not have.

## Core Functionality

Establish a sidecar spawning strategy that works both in development (using `uv`) and in packaged releases (without requiring `uv` on the target system).

## Functional Requirements

### FR1: Packaged Build — Bundled Python Sidecar

**Requirement:** For release builds, the Python backend must be bundled with the application and spawnable without `uv`.

**Approach options:**

**Option A — PyInstaller / Nuitka compiled sidecar:**
- Compile `textbrush.ipc` into a standalone executable during the release build
- Bundle the executable inside the `.app` or alongside the Linux binary
- Spawn it directly: `Sidecar::spawn("./textbrush-backend", &[])`
- Pros: No Python runtime needed on target system
- Cons: Large binary size (~500MB+ with PyTorch), complex build pipeline

**Option B — Bundled Python virtualenv:**
- Ship a pre-built virtualenv inside the app bundle
- Spawn via: `Sidecar::spawn("path/to/venv/bin/python", &["-m", "textbrush.ipc"])`
- Pros: Simpler build, standard Python
- Cons: Still large, platform-specific venv, Python version dependency

**Option C — Require system Python with installed package:**
- Document that users must `pip install textbrush` or `uv pip install textbrush`
- Spawn via: `Sidecar::spawn("python3", &["-m", "textbrush.ipc"])`
- Pros: Smallest app bundle, leverages user's Python
- Cons: Requires Python 3.11+ and all dependencies installed

**Recommendation:** Option C for the current project stage (pre-1.0, developer-focused audience). Document the Python dependency requirement clearly. Option A for a future truly self-contained distribution.

### FR2: Development Build — Continue Using uv

**Requirement:** Development builds must continue using `uv run` for sidecar spawning, since `uv` manages the virtualenv and dependencies.

**Implementation:** Use a compile-time feature flag or environment variable to select the spawn strategy:

```rust
#[cfg(debug_assertions)]
let sidecar = Sidecar::spawn("uv", &["run", "python", "-m", "textbrush.ipc"])?;

#[cfg(not(debug_assertions))]
let sidecar = Sidecar::spawn("python3", &["-m", "textbrush.ipc"])?;
```

Or use an environment variable:
```rust
let (cmd, args) = if std::env::var("TEXTBRUSH_DEV").is_ok() {
    ("uv", vec!["run", "python", "-m", "textbrush.ipc"])
} else {
    ("python3", vec!["-m", "textbrush.ipc"])
};
```

### FR3: Sidecar Spawn Error Reporting

**Requirement:** If the sidecar fails to spawn (e.g., `python3` not found, missing module), the error must be reported to the user clearly.

**Current behavior:** `Sidecar::spawn` returns `Err(String)` which propagates to the frontend as an invoke error. The frontend shows it in the loading prompt area.

**Required behavior:** Enhance error messages to be actionable:
- "Failed to start backend: python3 not found. Ensure Python 3.11+ is installed."
- "Failed to start backend: No module named 'textbrush'. Run: pip install textbrush"
- "Failed to start backend: uv not found. Install uv or set TEXTBRUSH_DEV=0."

### FR4: Update Release Workflow Documentation

**Requirement:** Document the sidecar strategy in:
- `README.md`: Installation section — clarify Python dependency for packaged builds
- `specs/spec.md`: Architecture section — note the spawn mechanism distinction between dev and release
- `.github/workflows/release.yml`: Add any necessary build steps (e.g., `pip install` in the release artifact)

## Critical Constraints

1. **Development workflow unchanged.** `cargo tauri dev` must continue to work with `uv run` as today.
2. **No new runtime dependencies for users** beyond Python 3.11+ and the textbrush package.
3. **Cross-platform.** Must work on macOS (ARM64, x64) and Linux x64.
4. **Tauri sidecar mechanism.** Must use Tauri's `Sidecar` type or equivalent process spawning within the Tauri framework.

## Integration Points

### Rust (`src-tauri/src/commands.rs`)
- `init_generation`: Modify `Sidecar::spawn` call to use conditional spawn strategy
- Add error message enhancement for spawn failures

### Build Configuration
- `src-tauri/Cargo.toml`: Optionally add feature flags for dev/release spawn modes
- `.github/workflows/release.yml`: Ensure Python package is available in release artifacts

### Documentation
- `README.md`: Installation requirements section
- `specs/spec.md`: Architecture notes

## Out of Scope

- Fully self-contained binary with bundled Python runtime (future enhancement)
- PyInstaller/Nuitka compilation pipeline
- Auto-detection of Python installation paths
- Windows support

## Success Criteria

1. `cargo tauri dev` continues to spawn sidecar via `uv run python -m textbrush.ipc`.
2. A release build spawns the sidecar without requiring `uv` on the target system.
3. Clear error messages when sidecar spawn fails due to missing Python or missing package.
4. Release workflow produces artifacts that work on a clean system with Python 3.11+ installed.

# Feature Specification: Integrate Model Management into Startup Flow

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

The spec (spec.md:91-94) defines the UI mode lifecycle as:

> 1. Parse CLI + config
> 2. Discover local models
> 3. Download required model(s) if missing and credentials allow
> 4. Launch UI immediately

The spec also defines model management behavior (spec.md:431-451):

> On startup:
> 1. Check Hugging Face cache (respect HF_HOME)
> 2. Check configured custom model directories
> 3. Validate required files
>
> If token missing: App blocks generation, UI displays clear instructions

The actual startup path in the IPC sidecar (`textbrush/ipc/__main__.py:29-33`) does:

```python
config = load_config()
handler = MessageHandler(config)
server = IPCServer(handler)
server.run()
```

Model loading happens later, inside `_init_backend` (handler.py:857), which calls `backend.initialize()` directly. The `textbrush/model/weights.py` module provides `is_flux_available()`, `ensure_flux_available()`, and `download_flux_weights()` — none of which are called anywhere in the startup path.

The result: if the model is not present, `backend.initialize()` fails with a generic error from the inference engine, rather than providing the user-friendly discovery and download workflow the spec describes.

## Core Functionality

Add a model discovery and validation step before model loading, providing actionable feedback when models are missing and optionally triggering download when credentials are available.

## Functional Requirements

### FR1: Model Discovery Before Init

**Requirement:** When `handle_init` receives the `INIT` command, before calling `backend.initialize()`, it must check model availability via `textbrush.model.weights.is_flux_available()`.

**Behavior:**
- If model is available: proceed with `backend.initialize()` as today
- If model is not available: check for download credentials and act accordingly (FR2)

### FR2: Missing Model with Credentials — Auto-Download

**Requirement:** If model is missing but HuggingFace credentials are available (via env var or config), attempt automatic download.

**Behavior:**
1. Emit `state_changed(loading)` with a descriptive message (see FR4)
2. Call `download_flux_weights()`
3. If download succeeds: proceed with `backend.initialize()`
4. If download fails: emit `state_changed(error, message="Model download failed: <reason>", fatal=True)`

**Credential sources** (checked in order):
1. `HUGGINGFACE_HUB_TOKEN` environment variable
2. `config.huggingface.token` from config file
3. HuggingFace CLI login cache (`~/.cache/huggingface/token`)

### FR3: Missing Model without Credentials — Actionable Error

**Requirement:** If model is missing and no credentials are available, emit a fatal error with clear instructions.

**Error message:**
```
FLUX.1 schnell model not found. To set up the model:

1. Get a HuggingFace token from https://huggingface.co/settings/tokens
2. Accept the license at https://huggingface.co/black-forest-labs/FLUX.1-schnell
3. Run: HUGGINGFACE_HUB_TOKEN=hf_xxx textbrush --download-model

Or manually place model files in the HuggingFace cache directory.
```

**Behavior:** Emit `state_changed(error, message=<above>, fatal=True)`. The frontend will display this in the fatal error overlay and auto-close after 3 seconds (existing behavior).

### FR4: Loading State Feedback During Download

**Requirement:** If auto-download is triggered, the frontend should show download progress.

**Minimal implementation:** Emit `state_changed(loading)` before download starts. The frontend already shows "loading model" with a spinner for this state.

**Enhanced implementation (optional):** Use a periodic progress callback from `huggingface_hub.snapshot_download` to emit status updates. This is out of scope for the initial implementation.

### FR5: Custom Model Directory Support

**Requirement:** Model discovery must also check directories listed in `config.model.directories` (spec.md:278).

**Behavior:** Before checking HuggingFace cache, check each configured custom directory for model files. If found in any custom directory, use that path.

## Critical Constraints

1. **No blocking the IPC server.** Model discovery and download run in the background thread (`_init_backend`), not in the server's message loop.
2. **Config-driven.** All paths and tokens come from the existing config system.
3. **Graceful degradation.** If discovery logic fails unexpectedly, fall back to the current behavior (let `backend.initialize()` fail and report the error).
4. **No new dependencies.** Use existing `textbrush.model.weights` functions.

## Integration Points

### Backend (`textbrush/ipc/handler.py`)
- `_init_backend`: Add model discovery check before `backend.initialize()`
- Import and use `is_flux_available`, `download_flux_weights` from `textbrush.model.weights`

### Model Module (`textbrush/model/weights.py`)
- Verify `is_flux_available()` correctly checks HuggingFace cache and custom dirs
- Verify `download_flux_weights()` returns a usable path
- May need to accept a config parameter for custom directories

### Configuration (`textbrush/config.py`)
- Ensure `config.model.directories` is accessible in the handler context
- Ensure `config.huggingface.token` is accessible for credential check

## Out of Scope

- Download progress bars or percentage reporting to the frontend
- Model selection (only FLUX.1 schnell)
- Model integrity verification beyond what `huggingface_hub` provides
- Automatic re-download on corruption
- The `--download-model` CLI flag (separate spec: `cli-download-model-spec.md`)

## Success Criteria

1. Starting the app without the model installed shows an actionable error message explaining how to install it.
2. Starting the app without the model but with `HUGGINGFACE_HUB_TOKEN` set triggers automatic download, after which generation begins normally.
3. Starting the app with the model already installed works identically to current behavior.
4. Custom model directories from config are checked before HuggingFace cache.
5. All existing tests pass (model availability is mocked in tests).

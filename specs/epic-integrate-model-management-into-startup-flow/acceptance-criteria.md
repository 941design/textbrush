# Acceptance Criteria: Integrate Model Management into Startup Flow

Generated: 2026-02-21T00:00:00Z
Source: spec.md

## Criteria

### AC-001: Model available — proceeds as before
- **Description**: When model is present in HuggingFace cache (or custom directories), `_init_backend` calls `backend.initialize()` without extra logic
- **Verification**: Unit test: mock `is_flux_available` returning True, verify `backend.initialize()` is called and no error event is emitted
- **Type**: unit

### AC-002: Model missing, no credentials — actionable error message
- **Description**: When model is not present and no HuggingFace credentials are found, a fatal error event is emitted with the exact error message template from FR3
- **Verification**: Unit test: mock `is_flux_available` returning False, no HF credentials set, verify `state_changed(error, fatal=True)` is emitted with instructional message containing "FLUX.1 schnell", HF URL, and textbrush CLI example
- **Type**: unit

### AC-003: Model missing, credentials present — auto-download triggered
- **Description**: When model is not present but HuggingFace credentials are available, a loading state is emitted then `download_flux_weights()` is called
- **Verification**: Unit test: mock `is_flux_available` returning False, mock credential detection returning a token, verify `state_changed(loading)` emitted before download, and download function is called
- **Type**: unit

### AC-004: Auto-download succeeds — backend proceeds to initialize
- **Description**: After successful download, `backend.initialize()` is called to proceed with model loading
- **Verification**: Unit test: mock `download_flux_weights()` returning successfully, verify `backend.initialize()` is still called
- **Type**: unit

### AC-005: Auto-download fails — fatal error emitted
- **Description**: If download raises an exception, a fatal error state_changed event is emitted with the failure reason
- **Verification**: Unit test: mock `download_flux_weights()` raising RuntimeError("network error"), verify `state_changed(error, message contains "Model download failed", fatal=True)` is emitted and `backend.initialize()` is NOT called
- **Type**: unit

### AC-006: Credential detection — multiple sources
- **Description**: Credentials are checked in order: HUGGINGFACE_HUB_TOKEN env var, config.huggingface.token, ~/.cache/huggingface/token file
- **Verification**: Unit tests: (a) HUGGINGFACE_HUB_TOKEN env var set → credentials found; (b) env var absent, config.huggingface.token set → credentials found; (c) both absent, HF CLI cache file present → credentials found; (d) none present → no credentials
- **Type**: unit

### AC-007: Custom model directories checked before HF cache
- **Description**: `is_flux_available()` (or the handler logic) checks directories from `config.model.directories` before falling back to HuggingFace cache
- **Verification**: Unit test: configure model directory with a valid model_index.json, verify `is_flux_available()` with custom dirs returns True before HF cache is checked
- **Type**: unit

### AC-008: Graceful degradation on unexpected errors
- **Description**: If model discovery logic itself throws an unexpected exception, it falls back to original behavior (lets backend.initialize() proceed and fail naturally with its own error)
- **Verification**: Unit test: mock `is_flux_available` raising an unexpected exception, verify backend.initialize() is still called and no additional error state is emitted prematurely
- **Type**: unit

### AC-009: Existing tests pass unmodified
- **Description**: All existing tests continue to pass — model availability is still mockable with the same patterns
- **Verification**: Run full test suite, verify zero regressions
- **Type**: unit

## Verification Plan

Run `uv run pytest tests/ -x -v` after each story to verify no regressions. For the specific new behavior:
- Story 01: run `uv run pytest tests/test_weights.py -v` to verify custom dir support
- Story 02: run `uv run pytest tests/test_ipc_handler.py -v` to verify handler behavior

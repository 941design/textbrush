# Acceptance Criteria: CLI Model Download Command

Generated: 2026-02-21
Source: spec.md

## Overview

These criteria verify the `--download-model` CLI flag: registration in the argument parser, conflict
detection with mutually exclusive flags, HuggingFace token resolution and error messaging, license
notice printing, the updated `download_flux_weights()` return type and `TokenRequiredError` class, and
the `ensure_flux_available()` error message referencing the new flag.

---

## Criteria

### AC-001: --download-model flag registered in build_parser()

- **Description**: `build_parser()` in `textbrush/cli.py` registers `--download-model` as an
  `action="store_true"` flag with `default=False`, so `parser.parse_args(["--download-model"]).download_model`
  evaluates to `True`.
- **Verification**: Unit test calls `build_parser().parse_args(["--download-model"])` and asserts
  `args.download_model is True`; also asserts `build_parser().parse_args([]).download_model is False`.
- **Type**: unit
- **Source**: FR1 — CLI Flag Implementation; Success Criteria #5

### AC-002: --download-model appears in --help output

- **Description**: `textbrush --help` stdout contains the string `--download-model`.
- **Verification**: `uv run textbrush --help | grep -- --download-model` exits 0 and prints the flag line.
- **Type**: unit
- **Source**: FR1 — Discoverability constraint

### AC-003: --prompt is no longer a required argument

- **Description**: `build_parser()` registers `--prompt` with `required=False`, so
  `parser.parse_args([])` does not raise `SystemExit` (argparse required-arg error).
- **Verification**: Unit test calls `build_parser().parse_args([])` without `--prompt` and asserts no
  exception is raised; `args.prompt` is `None`.
- **Type**: unit
- **Source**: FR1 + Integration Points: "Make --prompt optional (required=False)"

### AC-004: validate_args() rejects empty invocation (no --prompt, no --download-model)

- **Description**: `validate_args()` in `textbrush/cli.py` calls `parser.error()` with a message
  containing "one of --prompt or --download-model is required" when both `args.prompt` is falsy and
  `args.download_model` is `False`.
- **Verification**: Unit test constructs `args` with `prompt=None, download_model=False`, calls
  `validate_args(args)`, and asserts `SystemExit` is raised with exit code 2 (argparse error).
- **Type**: unit
- **Source**: Integration Points: validate_args() mutual exclusivity logic

### AC-005: validate_args() rejects --download-model combined with --prompt

- **Description**: `validate_args()` calls `parser.error()` with a message containing
  "Cannot use --download-model with --prompt" when `args.download_model is True` and
  `args.prompt` is a non-empty string.
- **Verification**: Unit test constructs `args` with `download_model=True, prompt="test"`, calls
  `validate_args(args)`, and asserts `SystemExit` is raised with exit code 2.
- **Type**: unit
- **Source**: FR1 — Validation; Success Criteria #4

### AC-006: validate_args() rejects --download-model combined with --headless

- **Description**: `validate_args()` calls `parser.error()` with a message containing
  "Cannot use --download-model with --headless" when `args.download_model is True` and
  `args.headless is True`.
- **Verification**: Unit test constructs `args` with `download_model=True, headless=True, prompt=None`,
  calls `validate_args(args)`, and asserts `SystemExit` is raised with exit code 2.
- **Type**: unit
- **Source**: FR1 — Validation

### AC-007: TokenRequiredError class defined in textbrush/model/weights.py

- **Description**: `textbrush.model.weights.TokenRequiredError` is a class that inherits from
  `Exception` and can be imported and raised without error.
- **Verification**: Unit test runs `from textbrush.model.weights import TokenRequiredError` and asserts
  `issubclass(TokenRequiredError, Exception)` is `True`; also asserts `isinstance(TokenRequiredError("msg"), Exception)`.
- **Type**: unit
- **Source**: FR2 — Error Handling; FR3 token resolution

### AC-008: download_flux_weights() returns Path on success

- **Description**: `download_flux_weights()` in `textbrush/model/weights.py` returns a `pathlib.Path`
  object equal to `Path(snapshot_download(...))` when `snapshot_download` succeeds.
- **Verification**: Unit test patches `textbrush.model.weights.snapshot_download` to return
  `"/tmp/hf_cache/flux"`, calls `download_flux_weights(force=True)`, and asserts the return value is
  `Path("/tmp/hf_cache/flux")`.
- **Type**: unit
- **Source**: FR2 — Return Value; architecture return_type_change note

### AC-009: download_flux_weights() raises TokenRequiredError when no token is available

- **Description**: `download_flux_weights()` raises `TokenRequiredError` (not `RuntimeError`) when
  `snapshot_download` raises an exception whose string representation contains "401" or "403", or when
  `HF_TOKEN` env var is absent and `config.huggingface.token` is empty and no token can be resolved
  before calling `snapshot_download`.
- **Verification**: Unit test patches `textbrush.model.weights.snapshot_download` to raise
  `Exception("401 Client Error")`, calls `download_flux_weights(force=True)`, and asserts
  `TokenRequiredError` is raised (not `RuntimeError`). Second test patches to raise
  `Exception("403 Forbidden")` and asserts same.
- **Type**: unit
- **Source**: FR2 — Error Handling; FR3 token resolution

### AC-010: main() prints license notice to stderr before download begins

- **Description**: When `main()` is invoked with `["--download-model"]` and `download_flux_weights`
  succeeds (mocked), `sys.stderr` output contains the string
  `"https://huggingface.co/black-forest-labs/FLUX.1-schnell"` before the success message.
- **Verification**: Unit test patches `textbrush.cli.download_flux_weights` to return
  `Path("/tmp/flux")` and patches `textbrush.cli.load_config`; calls `main(["--download-model"])`;
  captures stderr with `capsys`; asserts stderr contains the license URL string.
- **Type**: unit
- **Source**: FR4 — License Acceptance Verification

### AC-011: main() prints "Downloading FLUX.1 schnell model (~23 GB)..." to stderr

- **Description**: When `main(["--download-model"])` is called with a mocked successful
  `download_flux_weights`, `sys.stderr` output contains the string
  `"Downloading FLUX.1 schnell model (~23 GB)..."`.
- **Verification**: Same unit test as AC-010; assert `"Downloading FLUX.1 schnell model (~23 GB)..."` in captured stderr.
- **Type**: unit
- **Source**: FR2 — Download Workflow step 1

### AC-012: main() prints success path to stderr and exits 0

- **Description**: When `main(["--download-model"])` completes with a mocked `download_flux_weights`
  returning `Path("/tmp/hf_cache/flux")`, stderr contains `"Model downloaded successfully to: /tmp/hf_cache/flux"`
  and the process exits with code 0.
- **Verification**: Unit test patches `download_flux_weights` and `load_config`; wraps
  `main(["--download-model"])` in `pytest.raises(SystemExit)`; asserts `exc.value.code == 0` and the
  success string appears in captured stderr.
- **Type**: unit
- **Source**: FR2 — Download Workflow steps 4 and 5

### AC-013: main() handles TokenRequiredError with multi-line instructions and exits 1

- **Description**: When `download_flux_weights` raises `TokenRequiredError` and `main(["--download-model"])`
  is called, stderr contains all of the following substrings:
  - `"HuggingFace token required"`
  - `"HF_TOKEN"`
  - `"https://huggingface.co/settings/tokens"`
  And the process exits with code 1.
- **Verification**: Unit test patches `download_flux_weights` to raise `TokenRequiredError`; calls
  `main(["--download-model"])`; captures stderr; asserts each required substring is present and
  `exc.value.code == 1`.
- **Type**: unit
- **Source**: FR3 — Token Requirement; Success Criteria #3

### AC-014: main() handles generic download failure with retry hint and exits 1

- **Description**: When `download_flux_weights` raises a generic `Exception("connection timeout")`
  and `main(["--download-model"])` is called, stderr contains `"Download failed"` and the process
  exits with code 1.
- **Verification**: Unit test patches `download_flux_weights` to raise `RuntimeError("connection timeout")`;
  calls `main(["--download-model"])`; asserts `exc.value.code == 1` and `"Download failed"` in stderr.
- **Type**: unit
- **Source**: FR2 — Error Handling (network errors)

### AC-015: ensure_flux_available() error message references --download-model flag

- **Description**: The `RuntimeError` raised by `ensure_flux_available()` in `textbrush/model/weights.py`
  contains the string `"--download-model"` and does not contain `"make download-model"` or `"scripts/download_model.py"`.
- **Verification**: Unit test calls `ensure_flux_available()` (with `is_flux_available` patched to return
  `False`); catches `RuntimeError`; asserts `"--download-model"` in `str(exc)` and
  `"make download-model"` not in `str(exc)`.
- **Type**: unit
- **Source**: FR5 — Integration with Existing Discovery; Discoverability constraint

### AC-016: README.md download section uses --download-model and HF_TOKEN

- **Description**: `README.md` installation section contains `uv run textbrush --download-model`
  as the model download command, and uses `HF_TOKEN` (not `HUGGINGFACE_HUB_TOKEN`) as the env var name.
- **Verification**: `grep "uv run textbrush --download-model" README.md` exits 0;
  `grep "HF_TOKEN" README.md` exits 0; `grep "HUGGINGFACE_HUB_TOKEN" README.md` exits 1 (or the
  variable only appears in comments referencing the old way).
- **Type**: manual
- **Source**: Documentation constraint; FR1 Discoverability; FR3 token resolution (HF_TOKEN canonical name)

---

## Verification Plan

### Automated Tests

- **Unit tests (AC-001 to AC-015)**: All implemented as pytest unit tests using `unittest.mock.patch`
  to mock `snapshot_download`, `download_flux_weights`, `is_flux_available`, and `load_config`.
  Run with: `uv run pytest tests --ignore=tests/test_buffer_stress.py -m "not slow and not integration" -v`

- Tests for AC-001 to AC-006: `tests/test_cli.py` — `TestBuildParser` and `TestValidateArgs` classes
- Tests for AC-007 to AC-009, AC-015: `tests/test_weights.py` — `TestTokenRequiredError` and `TestDownloadFluxWeights` classes
- Tests for AC-010 to AC-014: `tests/test_cli.py` — `TestMain` class, download dispatch section

### Manual Verification

- **AC-002**: `uv run textbrush --help | grep -- --download-model` (shell verification)
- **AC-016**: README.md reviewed to confirm `--download-model` example and `HF_TOKEN` usage

---

## E2E Test Plan (MANDATORY)

E2E tests for this feature exercise the CLI through the installed entry point, using mocked network
calls to avoid requiring an actual HuggingFace token during CI. The download workflow exits before
entering the GUI/backend path, so no Tauri process or browser automation is needed.

### Infrastructure Requirements

- **Docker Compose**: Not required — the download path exits before the backend or GUI starts.
  The CLI process itself is the system under test.
- **Playwright**: Not applicable — no browser is involved. The E2E tests invoke `uv run textbrush`
  as a subprocess and assert on stdout/stderr and exit code.
- **Test data**: A mock `snapshot_download` that returns a predictable path string. For the real
  integration path, an `HF_TOKEN` env var is required (integration tests only, marked `@pytest.mark.integration`).

### E2E Scenarios

| Scenario | User Steps (subprocess) | Expected Outcome | ACs Validated |
|----------|------------------------|------------------|---------------|
| help-flag-discoverability | `uv run textbrush --help` | stdout contains `--download-model` | AC-001, AC-002 |
| download-no-token | `unset HF_TOKEN; uv run textbrush --download-model` (with patched snapshot_download raising 401) | exit 1; stderr contains token instructions and `HF_TOKEN` | AC-013 |
| download-conflict-prompt | `uv run textbrush --download-model --prompt "test"` | exit 2; stderr contains conflict message | AC-005 |
| download-conflict-headless | `uv run textbrush --download-model --headless` | exit 2; stderr contains conflict message | AC-006 |
| no-args-error | `uv run textbrush` (no --prompt, no --download-model) | exit 2; stderr contains "one of --prompt or --download-model" | AC-004 |

### Test Flow Per Scenario

**Scenario: help-flag-discoverability**
1. Docker Compose setup: none
2. Preconditions: textbrush installed via `uv sync`
3. User steps: invoke `uv run textbrush --help` as subprocess
4. Assertions: return code 0; stdout contains `--download-model`
5. Teardown: none

**Scenario: download-no-token**
1. Docker Compose setup: none
2. Preconditions: `HF_TOKEN` not set; `textbrush.model.weights.snapshot_download` patched (unit-level)
   or integration test with missing token
3. User steps: invoke `uv run textbrush --download-model` as subprocess
4. Assertions: exit code 1; stderr contains `"HF_TOKEN"` and `"https://huggingface.co/settings/tokens"`
5. Teardown: none

**Scenario: download-conflict-prompt**
1. Docker Compose setup: none
2. Preconditions: none
3. User steps: `uv run textbrush --download-model --prompt "test"`
4. Assertions: exit code 2; stderr contains "Cannot use --download-model with --prompt"
5. Teardown: none

**Scenario: download-conflict-headless**
1. Docker Compose setup: none
2. Preconditions: none
3. User steps: `uv run textbrush --download-model --headless`
4. Assertions: exit code 2; stderr contains "Cannot use --download-model with --headless"
5. Teardown: none

**Scenario: no-args-error**
1. Docker Compose setup: none
2. Preconditions: none
3. User steps: `uv run textbrush` (no arguments)
4. Assertions: exit code 2; stderr contains "one of --prompt or --download-model"
5. Teardown: none

### E2E Coverage Rule

All ACs of type `unit` are covered by subprocess-invocable behavior (the CLI is the boundary).
Integration download path (AC-008, AC-009) requires `@pytest.mark.integration` and real HF token;
excluded from standard CI run.

---

## Coverage Matrix

| Spec Requirement | Acceptance Criteria |
|------------------|---------------------|
| FR1: --download-model flag registered | AC-001, AC-002 |
| FR1: --prompt optional | AC-003 |
| FR1: conflict --prompt | AC-005 |
| FR1: conflict --headless | AC-006 |
| FR1: neither --prompt nor --download-model | AC-004 |
| FR2: download workflow — progress print | AC-011 |
| FR2: download workflow — success print + exit 0 | AC-012 |
| FR2: download workflow — TokenRequiredError handling | AC-013 |
| FR2: download workflow — generic error handling + exit 1 | AC-014 |
| FR2: download_flux_weights() returns Path | AC-008 |
| FR3: TokenRequiredError class | AC-007 |
| FR3: TokenRequiredError raised on 401/403 | AC-009 |
| FR3: token required message with HF_TOKEN and URL | AC-013 |
| FR4: license URL printed before download | AC-010 |
| FR5: ensure_flux_available references --download-model | AC-015 |
| Documentation: README --download-model example | AC-016 |

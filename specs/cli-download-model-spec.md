# Feature Specification: CLI Model Download Command

**Status:** Planned (Not Implemented)
**Priority:** Medium
**Target Version:** TBD

## Problem Statement

Users currently must use `make download-model` or manually run `scripts/download_model.py` to download the FLUX.1 schnell model. This requires knowledge of the project structure and is not discoverable through `textbrush --help`.

Error messages from model discovery (e.g., `ModelNotFoundError`) reference a `--download-model` flag that doesn't exist, creating user confusion.

## Core Functionality

Add a `--download-model` CLI flag that downloads the FLUX.1 schnell model weights from HuggingFace and exits immediately.

This provides a discoverable, self-contained way to set up models without requiring Makefile or project knowledge.

## Functional Requirements

### FR1: CLI Flag Implementation

**Requirement:** Add `--download-model` flag to CLI argument parser

**Behavior:**
- Flag is optional, no value required
- When present, triggers model download workflow
- Takes precedence over normal generation workflow
- Cannot be combined with `--prompt` or `--headless`

**Validation:**
- Conflicts with `--prompt`: Error "Cannot use --download-model with --prompt"
- Conflicts with `--headless`: Error "Cannot use --download-model with --headless"

### FR2: Download Workflow

**Requirement:** Execute model download using existing `download_flux_weights()` function

**Behavior:**
1. Print: "Downloading FLUX.1 schnell model (~23 GB)..."
2. Call `textbrush.model.weights.download_flux_weights()`
3. Show download progress (if HuggingFace hub supports it)
4. Print: "Model downloaded successfully to: <path>"
5. Exit with code 0 on success

**Error Handling:**
- `TokenRequiredError`: Print "HuggingFace token required. Set HUGGINGFACE_HUB_TOKEN environment variable."
- Network errors: Print "Download failed: <error>. Retry with same command."
- Permission errors: Print "Cannot write to cache directory: <path>. Check permissions."
- Exit with code 1 on any error

### FR3: HuggingFace Token Requirement

**Requirement:** Require HuggingFace token for download

**Behavior:**
- Check `HUGGINGFACE_HUB_TOKEN` environment variable first
- Check `config.huggingface.token` from config file if env var not set
- If neither available, print error with instructions:
  ```
  HuggingFace token required to download models.

  Options:
    1. Set environment variable:
       export HUGGINGFACE_HUB_TOKEN="hf_xxxxxxxxxxxxx"

    2. Add to config file (~/.config/textbrush/config.toml):
       [huggingface]
       token = "hf_xxxxxxxxxxxxx"

  Get token from: https://huggingface.co/settings/tokens
  Required scope: Read access to public repos
  ```

### FR4: License Acceptance Verification

**Requirement:** Inform user about HuggingFace license acceptance requirement

**Behavior:**
- Print before download begins:
  ```
  This will download FLUX.1 schnell from HuggingFace.
  Ensure you have accepted the license at:
  https://huggingface.co/black-forest-labs/FLUX.1-schnell
  ```

- If download fails with 403/401 error, print specific message:
  ```
  Download failed: Access denied.
  Visit https://huggingface.co/black-forest-labs/FLUX.1-schnell
  and click "Agree and access repository" before retrying.
  ```

### FR5: Integration with Existing Discovery

**Requirement:** Downloaded model should be automatically discovered on next run

**Behavior:**
- Download to standard HuggingFace cache location
- No configuration changes required
- Next `textbrush --prompt "test"` should find and use downloaded model

**Validation:** After download completes:
```bash
textbrush --download-model
# Should succeed

textbrush --prompt "test"
# Should find model without errors
```

## Critical Constraints

### Technical Constraints

1. **Reuse Existing Code:**
   - Must use `textbrush.model.weights.download_flux_weights()` function
   - No duplication of download logic
   - Leverage existing error handling in weights module

2. **Cache Location:**
   - Use HuggingFace default cache directory
   - Respect `HF_HOME` and `HF_HUB_CACHE` environment variables
   - Do not create custom cache locations

3. **Error Handling:**
   - All errors must be user-friendly (no stack traces by default)
   - Provide actionable next steps in error messages
   - Non-zero exit codes for all failure cases

### User Experience Constraints

1. **Discoverability:**
   - Flag must appear in `textbrush --help` output
   - Error messages should reference this flag, not `make download-model`

2. **Simplicity:**
   - No interactive prompts (fully automated if token is set)
   - Clear progress indication during long download
   - Success message with cache path for verification

3. **Documentation:**
   - Update README with example: `uv run textbrush --download-model`
   - Update error messages in `ModelNotFoundError` to reference correct flag
   - Update user-stories.md with corresponding story

## Integration Points

### CLI Module (`textbrush/cli.py`)

**Changes Required:**
```python
parser.add_argument(
    "--download-model",
    action="store_true",
    help="Download FLUX.1 schnell model and exit"
)

# In main():
if args.download_model:
    if args.prompt:
        print("Error: Cannot use --download-model with --prompt", file=sys.stderr)
        sys.exit(1)
    if args.headless:
        print("Error: Cannot use --download-model with --headless", file=sys.stderr)
        sys.exit(1)

    from textbrush.model.weights import download_flux_weights
    try:
        print("Downloading FLUX.1 schnell model (~23 GB)...")
        path = download_flux_weights()
        print(f"Model downloaded successfully to: {path}")
        sys.exit(0)
    except TokenRequiredError:
        print("Error: HuggingFace token required.", file=sys.stderr)
        # ... (print instructions)
        sys.exit(1)
    except Exception as e:
        print(f"Download failed: {e}", file=sys.stderr)
        sys.exit(1)
```

### Model Weights Module (`textbrush/model/weights.py`)

**Changes Required:**
- Update `ModelNotFoundError` message to reference `--download-model`
- Ensure `download_flux_weights()` returns cache path on success
- Add license acceptance check with 403 error handling

### Documentation Updates

**Files to Update:**
1. **README.md:** Add `--download-model` to usage examples
2. **specs/spec.md:** Reference this spec in "Out of Scope" note
3. **user-stories.md:** Add story for Developer persona
4. **docs/troubleshooting.md:** Update model download section

## Out of Scope

- Model selection (only FLUX.1 schnell supported)
- Progress bars or fancy UI (simple text output only)
- Auto-detection of missing models during generation (existing behavior remains)
- Download resume/retry logic (HuggingFace hub handles this)
- Verification of downloaded files (trust HuggingFace checksums)
- Custom download locations (use HF standard cache)

## Success Criteria

### Functional Acceptance

1. **Basic Download:**
   ```bash
   export HUGGINGFACE_HUB_TOKEN="hf_xxx"
   textbrush --download-model
   # Prints progress, exits 0, model saved to HF cache
   ```

2. **Subsequent Generation:**
   ```bash
   textbrush --prompt "test"
   # Finds and uses downloaded model without errors
   ```

3. **Error Handling:**
   ```bash
   unset HUGGINGFACE_HUB_TOKEN
   textbrush --download-model
   # Prints token required error, exits 1
   ```

4. **Conflict Detection:**
   ```bash
   textbrush --download-model --prompt "test"
   # Prints error about conflicting flags, exits 1
   ```

5. **Help Text:**
   ```bash
   textbrush --help
   # Shows --download-model flag with description
   ```

### Non-Functional Acceptance

1. **Performance:** Download should not be slower than `make download-model`
2. **User Experience:** All error messages are actionable and clear
3. **Consistency:** Behavior matches existing download script exactly
4. **Documentation:** All docs updated to reference new flag

## Implementation Notes

**Estimated Effort:** Small (1-2 hours)

**Testing Requirements:**
- Unit test for CLI argument parsing with conflicts
- Integration test for successful download (requires HF token)
- Error case tests (missing token, network failure, etc.)
- E2E test: download → generate workflow

**Rollout Plan:**
1. Implement CLI flag and logic in `textbrush/cli.py`
2. Update error messages in `textbrush/model/weights.py`
3. Add tests for download workflow
4. Update all documentation
5. Mark user story as [Implemented] in user-stories.md

**Future Enhancements (Not in Scope):**
- Support for downloading other models
- `--verify-model` flag to check integrity
- `--remove-model` flag to clean cache
- Progress bars with download speed/ETA

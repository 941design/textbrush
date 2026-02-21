# Feature Specification: Headless Mode Without Auto-Action Flag

**Status:** Planned (Not Implemented)
**Priority:** High
**Target Version:** TBD

## Problem Statement

The spec (spec.md:108) defines headless behavior when neither `--auto-accept` nor `--auto-abort` is provided:

> Neither: Wait for completion, exit 0 on success, 1 on failure

The current implementation (cli.py:536-538) rejects this case:

```python
print("Error: Headless mode requires --auto-accept or --auto-abort", file=sys.stderr)
sys.exit(1)
```

This breaks the spec contract and prevents a natural "generate and report" workflow where the user simply wants headless generation to complete and get the result.

## Core Functionality

When `--headless` is provided without `--auto-accept` or `--auto-abort`, generate a single image, save it to the output path, print the path to stdout, and exit 0. On any failure, exit 1 with error on stderr.

## Functional Requirements

### FR1: Default Headless Behavior (Neither Flag)

**Requirement:** Replace the error exit with a generate-and-save workflow.

**Behavior:**
1. Initialize backend and load model
2. Start generation with provided prompt, seed, aspect ratio
3. Wait for first image to be generated (120-second timeout, matching existing `--auto-accept` behavior)
4. Save image to output path (`--out` if provided, otherwise auto-generate)
5. Print absolute path to stdout
6. Shut down backend
7. Exit with code 0

**On failure:**
- Timeout: Print "Error: No image generated within 120 second timeout" to stderr, exit 1
- Any exception: Print error to stderr, exit 1
- Never print to stdout on failure

### FR2: Behavioral Equivalence

**Requirement:** The "neither flag" behavior must be identical to `--auto-accept` behavior.

**Rationale:** The spec says "Wait for completion, exit 0 on success." This is semantically the same as auto-accept — generate one image, save it, report the path. The only difference from `--auto-accept` is that this is the implicit default, not an explicit opt-in.

**Implementation:** The code path for "neither flag" should fall through to the same logic as `auto_accept`, or the `auto_accept` check should be restructured so that `auto_abort` is checked first (as it already is), and everything else generates-and-saves.

### FR3: Auto-Abort Precedence

**Requirement:** `--auto-abort` must continue to take precedence when both flags are provided.

**Current behavior:** Already correct — `auto_abort` is checked first in `run_headless`. No change needed.

### FR4: Update CLI Help Text

**Requirement:** Update `--headless` help text to document the default behavior.

**Current:** `"Run without UI (for testing)"`
**Required:** `"Run without UI — generates one image and saves it (use --auto-abort to skip saving)"`

## Critical Constraints

1. **Exit code contract unchanged.** Exit 0 on success with path on stdout, exit 1 on failure with nothing on stdout.
2. **Timeout unchanged.** 120-second timeout per existing implementation.
3. **No interactive prompts.** Headless mode must remain fully non-interactive.
4. **stderr for progress.** "Loading model..." and "Generating..." messages continue going to stderr.

## Integration Points

### CLI Module (`textbrush/cli.py`)
- `run_headless`: Remove the "neither flag" error block (lines 536-538). The function flow becomes: check `auto_abort` first → otherwise generate-and-save (which is the current `auto_accept` path).
- `build_parser`: Update `--headless` help text.

## Out of Scope

- Multi-image generation in headless mode
- Interactive headless mode (stdin-based commands)
- Progress reporting beyond existing stderr messages
- Streaming output

## Success Criteria

1. `textbrush --headless --prompt "test"` generates an image, prints path to stdout, exits 0.
2. `textbrush --headless --prompt "test" --auto-abort` aborts without saving, exits 1.
3. `textbrush --headless --prompt "test" --auto-accept` continues to work identically to case 1.
4. `textbrush --help` shows updated description for `--headless`.
5. All existing headless tests pass.

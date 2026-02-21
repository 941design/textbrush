# Feature Specification: Fix README CLI Examples

**Status:** Planned (Not Implemented)
**Priority:** Low
**Target Version:** TBD

## Problem Statement

Several CLI usage examples in `README.md` use argument syntax that doesn't match the actual parser in `textbrush/cli.py`:

### Issue 1: Positional Prompt (README.md:67)

```bash
uv run textbrush "a serene mountain landscape" --output output.png
```

The parser requires `--prompt` as a named flag (`required=True`). Positional arguments are not accepted. This command would fail with: `error: the following arguments are required: --prompt`.

### Issue 2: --output Flag (README.md:67, 125)

```bash
uv run textbrush "a serene mountain landscape" --output output.png
uv run textbrush --prompt "sunset over mountains" --output ~/Desktop/sunset.png
```

The parser defines `--out`, not `--output` (cli.py:91-95). The `--output` flag is not recognized. This command would fail with: `error: unrecognized arguments: --output`.

### Issue 3: --format Flag (README.md:128)

```bash
uv run textbrush --prompt "abstract art" --format jpg --seed 42
```

This is actually correct — `--format` is a valid flag (cli.py:127-131). No change needed.

## Core Functionality

Update all CLI examples in README.md to match the actual argument parser.

## Functional Requirements

### FR1: Fix Positional Prompt Usage

**Requirement:** Replace all positional prompt usage with `--prompt` flag.

**Affected lines:**
- README.md:67: `uv run textbrush "a serene mountain landscape" --output output.png`

**Corrected:**
```bash
uv run textbrush --prompt "a serene mountain landscape" --out output.png
```

### FR2: Fix --output to --out

**Requirement:** Replace all `--output` references with `--out`.

**Affected lines:**
- README.md:67: `--output output.png`
- README.md:125: `--output ~/Desktop/sunset.png`

**Corrected:**
```bash
uv run textbrush --prompt "sunset over mountains" --out ~/Desktop/sunset.png
```

### FR3: Verify All Other Examples

**Requirement:** Audit all CLI examples in README.md against the parser. Verify each flag name, argument format, and option validity.

**Known correct examples:**
- `uv run textbrush --prompt "a watercolor painting of a cat"` (README.md:58) — correct
- `uv run textbrush "test image" --headless --auto-accept --out output.png` (README.md:106) — positional prompt incorrect, `--out` correct
- `uv run textbrush "test" --headless --auto-abort` (README.md:109) — positional prompt incorrect
- `uv run textbrush --prompt "portrait" --aspect-ratio 9:16` (README.md:131) — correct
- `uv run textbrush --config ./project-config.toml --prompt "portrait"` (README.md:134) — correct

### FR4: Verify Headless Examples

**Requirement:** Fix headless mode examples that use positional prompts.

**Affected lines:**
- README.md:106: `uv run textbrush "test image" --headless --auto-accept --out output.png`
- README.md:109: `uv run textbrush "test" --headless --auto-abort`

**Corrected:**
```bash
uv run textbrush --prompt "test image" --headless --auto-accept --out output.png
uv run textbrush --prompt "test" --headless --auto-abort
```

## Critical Constraints

1. **Match parser exactly.** Every example must be a valid invocation of `build_parser()`.
2. **Keep examples practical.** Examples should demonstrate real usage patterns, not just flag syntax.
3. **Consistent style.** Use `uv run textbrush` prefix consistently (per CLAUDE.md, uv is the package manager).

## Integration Points

### Documentation (`README.md`)
- Section "Desktop UI Workflow" (~line 67): Fix prompt and output flag
- Section "Headless Mode" (~line 106): Fix prompt syntax
- Section "Configuration Options" (~line 125): Fix output flag

## Out of Scope

- Adding new examples for features not yet documented
- Restructuring the README layout
- Adding shell-specific caveats (bash vs zsh quoting)

## Success Criteria

1. Every CLI example in README.md is a syntactically valid invocation.
2. Copy-pasting any example with a valid model installed produces the expected result.
3. No references to `--output` remain (all replaced with `--out`).
4. No positional prompt usage remains (all use `--prompt` flag).

# Acceptance Criteria: Fix README CLI Examples

Generated: 2026-02-21T21:14:18Z
Source: spec.md

## Criteria

### AC-001: No positional prompt arguments remain
- **Description**: All CLI examples use --prompt flag, no positional string arguments
- **Verification**: grep -n '"[^"]*"' README.md | grep 'uv run textbrush' — no lines should show positional prompt before a flag
- **Type**: manual

### AC-002: No --output flag references remain
- **Description**: All --output references replaced with --out
- **Verification**: grep --output README.md returns no results
- **Type**: manual

### AC-003: Headless examples use --prompt flag
- **Description**: Headless mode examples (README.md ~line 106, 109) use --prompt
- **Verification**: Check lines around "headless" section in README.md
- **Type**: manual

### AC-004: All examples are syntactically valid invocations
- **Description**: Every CLI example in README.md can be parsed by build_parser()
- **Verification**: Extract each example command and verify against parser
- **Type**: manual

## Verification Plan

1. Search README.md for all "uv run textbrush" lines
2. For each line, verify: (a) uses --prompt flag, not positional, (b) uses --out not --output
3. grep -n "\-\-output" README.md must return 0 results
4. All positional usage (textbrush "text") replaced with (textbrush --prompt "text")

# Increment 1: Foundation - Requirements Specification

## Problem Statement

The textbrush project needs a foundational implementation that establishes the core project structure, command-line interface, configuration system, and model weight management. This foundation will enable subsequent increments to build the inference backend and desktop UI.

The project currently has only specifications and no implementation code. This increment creates the skeleton that all subsequent work builds upon.

## Core Functionality

This increment delivers:
1. A Python package with proper structure and tooling (uv-based)
2. A CLI interface matching spec requirements for image generation invocation
3. A TOML-based configuration system with environment variable and CLI overrides
4. HuggingFace model weight management ported from avatar-generator
5. A minimal Tauri v2 project shell that compiles and shows an empty window
6. Build system (Makefile) with standard development targets

## Functional Requirements

### FR1: Python Package Structure
**Acceptance**: Package can be installed with `uv sync` and invoked with `uv run textbrush`
- Package name: `textbrush`
- Structure includes:
  - `textbrush/__init__.py`
  - `textbrush/cli.py` (CLI entry point)
  - `textbrush/config.py` (configuration loading)
  - `textbrush/paths.py` (path constants)
  - `textbrush/model/__init__.py`
  - `textbrush/model/weights.py` (HuggingFace model caching)
- Entry point: `textbrush` command maps to `textbrush.cli:main`
- Python version requirement: >=3.11
- Dependencies: huggingface-hub>=0.20.0
- Dev dependencies: pytest>=8.0, ruff>=0.1.0

### FR2: CLI Argument Parsing
**Acceptance**: `uv run textbrush --help` shows all options, `uv run textbrush --prompt "test"` validates prompt is provided

**Required arguments:**
- `--prompt TEXT` - Image generation prompt (required)

**Optional arguments:**
- `--out PATH` - Output file path
- `--config PATH` - Config file (default: ~/.config/textbrush/config.toml)
- `--seed INT` - Random seed for reproducibility
- `--aspect-ratio CHOICE` - Choices: 1:1 | 16:9 | 9:16
- `--format CHOICE` - Choices: png | jpg
- `--verbose` - Enable debug logging

**Exit codes (per spec section 9.1):**
- `0` + stdout path: Accept
- Non-zero + empty stdout: Abort/No accept

**Implementation:**
- Use argparse with `build_parser()` function pattern
- Main function signature: `def main(argv: List[str] | None = None) -> None:`
- Type validation for arguments
- Help text generation

### FR3: TOML Configuration System
**Acceptance**: Config file is created on first run if missing, CLI args override config values

**Default location:** `~/.config/textbrush/config.toml`

**Configuration schema:**
```toml
[output]
directory = "~/Pictures/textbrush"
format = "png"

[model]
directories = []  # Additional model search paths
buffer_size = 8

[huggingface]
token = ""  # Or use HUGGINGFACE_HUB_TOKEN env var

[inference]
backend = "flux"  # Pluggable backend selection

[logging]
verbosity = "info"  # debug | info | warning | error
```

**Implementation requirements:**
- Use `tomllib` (Python 3.11+) for TOML parsing
- Environment variable overrides with `TEXTBRUSH_*` prefix
- CLI args override config file values
- XDG-compliant paths
- Create default config file if missing on first run
- Use additional library (toml or tomli_w) for writing TOML since tomllib is read-only

### FR4: Model Weight Management
**Acceptance**: Model discovery finds HuggingFace cache, `make download-model` downloads FLUX.1 schnell with token

**Port from:** `/Users/mrother/Projects/941design/avatar-generator/avatar_generator/model/weights.py`

**Key functions to implement:**
- `get_model_path()` - Locate cached models
- `validate_model_files()` - Check required files exist
- `download_model()` - HuggingFace Hub download with token
- `get_hf_token()` - Token from env or config

**Model discovery order (per spec 6.2):**
1. HuggingFace cache (`HF_HOME` or default)
2. Custom model directories from config
3. Validate required files exist

**Model ID:** FLUX.1 schnell from black-forest-labs
**Token handling:** Environment variable `HUGGINGFACE_HUB_TOKEN` or config file
**Cache integration:** Use huggingface_hub utilities for cache detection and download

### FR5: Tauri Project Shell
**Acceptance**: Tauri shell compiles and shows empty window

**Project structure:**
```
src-tauri/
├── Cargo.toml
├── tauri.conf.json
├── src/
│   └── main.rs          # Minimal Tauri app shell
└── capabilities/
    └── default.json
```

**Tauri configuration:**
- Window: Fixed size, centered, minimal chrome
- Sidecar: Python backend definition (placeholder for Increment 3)
- Permissions: File system access for outputs
- Version: Tauri v2
- Rust dependencies: tauri v2, serde, serde_json

**Deliverable:** Running `cargo build` in src-tauri/ produces executable that opens empty window

### FR6: Makefile Targets
**Acceptance**: `make install` sets up complete dev environment

**Required targets (port and adapt from avatar-generator Makefile):**

```makefile
# Setup
install                # Install Python dependencies (uv sync)
download-model         # Download FLUX.1 schnell (with token)

# Development
dev                    # Run in development mode
test                   # Run test suite (pytest)
lint                   # Code linting (ruff)
format                 # Code formatting (ruff format)

# Build
build                  # Build Tauri app
build-python           # Build Python package (uv build)

# Cleanup
clean                  # Remove build artifacts
```

## Critical Constraints

### C1: Direct Porting from avatar-generator
- **Constraint**: Must port code from `/Users/mrother/Projects/941design/avatar-generator` without altering the source project
- **Rationale**: Preserve proven, working implementations while keeping source project intact
- **Files to port**:
  - `avatar_generator/model/weights.py` → `textbrush/model/weights.py` (minimal changes: update model ID)
  - `avatar_generator/paths.py` → `textbrush/paths.py` (update path constants)
  - Reference patterns from `avatar_generator/cli.py` for CLI structure
  - Reference `Makefile` and `pyproject.toml` structure

### C2: Use uv for Package Management
- **Constraint**: Exclusively use `uv` for virtual environment and dependency management
- **Rationale**: Project standard per CLAUDE.md guidelines
- **Impact**: All setup, install, and run commands use `uv` (not pip, poetry, etc.)

### C3: Python 3.11+ Requirement
- **Constraint**: Requires Python >=3.11
- **Rationale**: Built-in tomllib support, modern type hints, performance improvements
- **Impact**: Can use tomllib for TOML reading without external dependency

### C4: XDG Base Directory Compliance
- **Constraint**: Configuration files must follow XDG Base Directory Specification
- **Rationale**: Standard Linux/macOS practice for user configuration
- **Impact**: Config at `~/.config/textbrush/config.toml`, not project-relative or home-directory root

### C5: No Implementation Until Foundation Complete
- **Constraint**: This increment must be complete before starting Increment 2
- **Rationale**: Incremental development approach per spec
- **Impact**: All acceptance criteria must pass before proceeding

## Integration Points

### IP1: CLI to Configuration System
- CLI loads config from `~/.config/textbrush/config.toml`
- CLI arguments override config file values
- Environment variables override config file but are overridden by CLI args
- Priority: CLI args > env vars > config file > defaults

### IP2: CLI to Model Management
- CLI needs to validate model availability before starting generation (Increment 2)
- Model management provides functions to check cache, download if needed
- Token from config or environment variable

### IP3: Configuration to Model Management
- Config provides custom model directories
- Config provides HuggingFace token if not in environment
- Config specifies backend selection (for Increment 2)

### IP4: Tauri to Python Backend (Future)
- Tauri sidecar configuration defines Python backend (Increment 3)
- Shell exists as placeholder, no active integration yet
- Window configuration established for UI work (Increment 4)

## User Preferences

### UP1: CLI Command Name
- User preference: `textbrush` (matches package name)
- Config directory: `~/.config/textbrush/` (matches command)
- Entry point: `textbrush` command in PATH after install

### UP2: Tauri Scope
- Preference: Minimal running window (not just structure)
- Deliverable: Window compiles and displays, even if empty
- Validates Tauri setup completeness

### UP3: Code Porting Approach
- Preference: Direct file copying from avatar-generator
- Approach: Read source files, port to textbrush with minimal necessary changes
- Constraint: Do not modify avatar-generator source

## Codebase Context

See `.exploration/increment-1-foundation-context.md` for detailed exploration findings including:
- Similar features in avatar-generator
- Key patterns observed (package structure, CLI, config, model caching)
- Integration points
- Recommendations for architect

## Related Artifacts

- **Exploration Context**: `.exploration/increment-1-foundation-context.md`
- **Original Increment Spec**: `specs/increment-1-foundation.md`
- **Master Spec**: `specs/spec.md`
- **Project Guidelines**: `CLAUDE.md`

## Out of Scope

**This increment explicitly does NOT include:**
- Image generation inference (Increment 2)
- Tauri IPC protocol implementation (Increment 3)
- UI implementation beyond empty window (Increment 4)
- Testing infrastructure setup (Increment 5)
- CI/CD pipelines (Increment 5)
- Actual model downloading during build (optional via make target)
- Error handling for inference failures (Increment 2)
- Background worker threads (Increment 2)
- Image buffering system (Increment 2)

**Edge cases and details to be determined during architecture:**
- Exact error messages for missing config/models
- Logging format and output destinations
- Specific path resolution logic for Windows (not supported but may need graceful failure)
- Config file corruption handling
- Model download progress indication

---

**Note**: This is a requirements specification, not an architecture design.
The integration-architect will determine implementation approach, file organization details,
error handling strategies, and testing approach during Phase 2.

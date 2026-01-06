# Increment 1: Foundation - Project Structure & CLI

## Overview
Establish the foundational project structure, CLI interface, and configuration system. This increment creates the skeleton that all subsequent work builds upon.

## Goals
- Set up Python package structure with proper tooling
- Implement CLI argument parsing matching spec requirements
- Create TOML configuration system
- Establish Tauri project shell (no UI yet)
- Port model weight management from avatar-generator

## Deliverables

### 1.1 Python Package Structure

```
textbrush/
├── textbrush/                    # Main Python package
│   ├── __init__.py
│   ├── cli.py                    # CLI entry point
│   ├── config.py                 # Configuration loading
│   ├── paths.py                  # Path constants
│   └── model/
│       ├── __init__.py
│       └── weights.py            # HuggingFace model caching (port from avatar-generator)
├── pyproject.toml                # Python package config (uv)
├── Makefile                      # Build targets
└── README.md
```

### 1.2 CLI Implementation (`textbrush/cli.py`)

Port and adapt CLI patterns from `avatar_generator/cli.py`:

```python
# Required arguments
--prompt TEXT          # Image generation prompt (required)

# Optional arguments
--out PATH             # Output file path
--config PATH          # Config file (default: ~/.config/image-reviewer/config.toml)
--seed INT             # Random seed for reproducibility
--aspect-ratio CHOICE  # 1:1 | 16:9 | 9:16
--format CHOICE        # png | jpg
--verbose              # Enable debug logging
```

**Exit Codes (per spec section 9.1):**
- `0` + stdout path: Accept
- Non-zero + empty stdout: Abort/No accept

### 1.3 Configuration System (`textbrush/config.py`)

Port config patterns from `avatar_generator/generation/config.py`:

**Default location:** `~/.config/image-reviewer/config.toml`

```toml
# Default configuration
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

**Implementation:**
- Use `tomllib` (Python 3.11+) for TOML parsing
- Environment variable overrides (`TEXTBRUSH_*` prefix)
- CLI args override config file values
- XDG-compliant paths

### 1.4 Model Weight Management (`textbrush/model/weights.py`)

**Directly port from:** `avatar_generator/model/weights.py`

Key functions to port:
- `get_model_path()` - Locate cached models
- `validate_model_files()` - Check required files exist
- `download_model()` - HuggingFace Hub download with token
- `get_hf_token()` - Token from env or config

**Model discovery order (per spec 6.2):**
1. HuggingFace cache (`HF_HOME` or default)
2. Custom model directories from config
3. Validate required files exist

### 1.5 Tauri Project Shell

Initialize Tauri v2 project structure:

```
src-tauri/
├── Cargo.toml
├── tauri.conf.json
├── src/
│   └── main.rs          # Minimal Tauri app shell
└── capabilities/
    └── default.json
```

**Tauri Configuration:**
- Window: Fixed size, centered, minimal chrome
- Sidecar: Python backend definition
- Permissions: File system access for outputs

### 1.6 Makefile Targets

Port and adapt from avatar-generator Makefile:

```makefile
# Setup
install                # Install Python dependencies (uv)
download-model         # Download FLUX.1 schnell

# Development
dev                    # Run in development mode
test                   # Run test suite
lint                   # Code linting

# Build
build                  # Build Tauri app
build-python           # Build Python package
```

## Dependencies

**Python (pyproject.toml):**
```toml
[project]
requires-python = ">=3.11"
dependencies = [
    "huggingface-hub>=0.20.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.1.0",
]
```

**Rust/Tauri (Cargo.toml):**
- tauri v2
- serde
- serde_json

## Acceptance Criteria

1. [ ] `uv run textbrush --help` shows all CLI options
2. [ ] `uv run textbrush --prompt "test"` validates prompt is provided
3. [ ] Config file is created on first run if missing
4. [ ] CLI args override config values
5. [ ] Model discovery finds HuggingFace cache
6. [ ] `make install` sets up complete dev environment
7. [ ] `make download-model` downloads FLUX.1 schnell (with token)
8. [ ] Tauri shell compiles and shows empty window

## Files to Port from avatar-generator

| Source | Destination | Changes |
|--------|-------------|---------|
| `avatar_generator/model/weights.py` | `textbrush/model/weights.py` | Minimal - update model ID |
| `avatar_generator/paths.py` | `textbrush/paths.py` | Update path constants |
| `avatar_generator/cli.py` | `textbrush/cli.py` | Rewrite for spec CLI |
| `Makefile` | `Makefile` | Adapt targets |
| `pyproject.toml` | `pyproject.toml` | New package name, deps |

## Testing

- Unit tests for config loading/merging
- Unit tests for CLI argument parsing
- Unit tests for model path discovery
- Integration test: CLI → config → model check flow

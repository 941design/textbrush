# Textbrush

Text-to-image generation tool with customizable workflows and local model inference.

## Features

- **Command-line interface** for text-to-image generation with FLUX.1 schnell model
- **Background image generation** with 8-image FIFO buffer for smooth workflows
- **Desktop slideshow UI** for rapid image review with keyboard/mouse controls
- **Real-time buffer visualization** showing generation progress as images are created
- **Flexible configuration** via CLI arguments, environment variables, or TOML config file
- **Local model management** with automatic HuggingFace cache discovery
- **Hardware auto-detection** supporting CUDA, Apple MPS, and CPU backends
- **XDG-compliant** configuration directory (~/.config/textbrush/)
- **Reproducible results** via seed parameter for deterministic generation
- **IPC Protocol** for Tauri-Python communication with thread-safe message delivery

## Installation

```bash
uv sync
```

## Usage

### Basic Usage

Generate an image from a text prompt:

```bash
uv run textbrush --prompt "a watercolor painting of a cat"
```

### Desktop UI Workflow

Launch the interactive slideshow UI to review generated images:

```bash
# Launch UI with prompt
uv run textbrush "a serene mountain landscape" --output output.png

# UI opens showing:
# - First generated image displayed automatically
# - Buffer indicator showing generation progress (visual dots + count)
# - Controls: Abort / Skip / Accept buttons

# Keyboard shortcuts:
# Space or → : Skip to next image
# Enter: Accept current image (saves to specified path and exits)
# Esc: Abort (exits without saving)

# Exit behavior:
# Accept: prints saved file path to stdout, exits with code 0
# Abort: exits with code 1 (empty stdout)
```

The UI provides:
- **Real-time buffer status**: Visual indicator showing how many images are ready to review
- **Smooth transitions**: GPU-accelerated animations between images (<100ms skip latency)
- **Memory efficiency**: Uses blob URLs instead of base64 encoding for large images
- **Exit contracts**: Predictable stdout/exit-code behavior for scripting integration

### Headless Mode (for CI/Testing)

Run textbrush without GUI for automated workflows:

```bash
# Accept first generated image (for CI pipelines)
uv run textbrush "test image" --headless --auto-accept --out output.png

# Abort immediately (for testing error paths)
uv run textbrush "test" --headless --auto-abort

# Exit codes:
# 0: Image accepted successfully (path printed to stdout)
# 1: Aborted or error (empty stdout)
```

Headless mode is designed for:
- **CI/CD pipelines**: Automated image generation without UI
- **Integration testing**: End-to-end workflow verification
- **Scripted workflows**: Batch processing with predictable exit codes

### Configuration Options

```bash
# Specify output location
uv run textbrush --prompt "sunset over mountains" --output ~/Desktop/sunset.png

# Set format and seed for reproducibility
uv run textbrush --prompt "abstract art" --format jpg --seed 42

# Specify aspect ratio
uv run textbrush --prompt "portrait" --aspect-ratio 9:16

# Use custom config file
uv run textbrush --config ./project-config.toml --prompt "portrait"

# Enable verbose logging
uv run textbrush --verbose --prompt "landscape"
```

### Configuration File

Create or edit `~/.config/textbrush/config.toml`:

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
backend = "flux"

[logging]
verbosity = "info"  # debug | info | warning | error
```

### Environment Variables

Override config values with environment variables:

```bash
export TEXTBRUSH_OUTPUT_FORMAT=jpg
export TEXTBRUSH_LOGGING_VERBOSITY=debug
uv run textbrush --prompt "test"
```

Configuration priority: CLI arguments > environment variables > config file > defaults

## Development

### Setup

```bash
make install        # Install dependencies
make download-model # Download FLUX.1 schnell (requires HuggingFace token)
```

### Development Tasks

```bash
make test          # Run fast tests (excludes slow/integration)
make test-all      # Run full test suite including slow/integration tests
make lint          # Check Python code quality (ruff)
make format        # Format Python code (ruff)
make clippy        # Check Rust code quality (cargo clippy)
make fmt-rust      # Format Rust code (cargo fmt)
make fmt-check     # Verify all code is formatted (CI)
make build         # Build Tauri application
make run           # Run Tauri application locally
make run-debug     # Run Tauri with debug logging
make dev           # Run CLI with --help
make clean         # Remove build artifacts
```

For detailed development guidelines and coding standards, see `CLAUDE.md`.

For detailed technical guides and troubleshooting, see [docs/](docs/).

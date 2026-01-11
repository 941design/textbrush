# Textbrush

Text-to-image generation tool with customizable workflows and local model inference.

## Features

- **Command-line interface** for text-to-image generation with FLUX.1 schnell model
- **Background image generation** with 8-image FIFO buffer for smooth workflows
- **Desktop slideshow UI** for rapid image review with keyboard/mouse controls
- **Real-time buffer visualization** showing generation progress as images are created
- **Dark/light theme toggle** with persistent preference and smooth transitions
- **Bidirectional navigation** through image history with position indicator
- **Image deletion** with Cmd/Ctrl+Delete to curate selections
- **Multi-image workflows** with batch acceptance of all retained images
- **Visual feedback** for keyboard shortcuts with button flash animations
- **Image metadata display** with split-view panel showing prompt, model, and seed for each image
- **Flexible configuration** via CLI arguments, environment variables, or TOML config file
- **Local model management** with automatic HuggingFace cache discovery
- **Hardware auto-detection** supporting CUDA, Apple MPS, and CPU backends
- **XDG-compliant** configuration directory (~/.config/textbrush/)
- **Reproducible results** via seed parameter for deterministic generation
- **IPC Protocol** for Tauri-Python communication with thread-safe message delivery

## Requirements

- **Python 3.11+** - For running the inference backend
- **Rust 1.70+ and Cargo** - For building the Tauri desktop application
- **uv** - Package and virtual environment manager
- **System dependencies** - For GPU acceleration and UI rendering (see [GPU Setup Guide](docs/gpu-setup.md))

**Supported Platforms:**
- macOS (Apple Silicon ARM64, Intel x64)
- Linux (x64)

## Installation

### From Source

```bash
# Install dependencies
uv sync

# Download model (requires HuggingFace token)
export HUGGINGFACE_HUB_TOKEN="hf_xxxxxxxxxxxxx"
make download-model

# Build the application
make build
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
# - Theme toggle button (dark/light mode)
# - Position indicator showing current image in history (e.g., "[2/5]")
# - Controls: Abort / Skip / Accept buttons

# Keyboard shortcuts:
# ← : Navigate to previous image in history
# → : Navigate forward or skip to next buffered image
# Space : Pause/resume image generation
# Enter: Accept all retained images (prints paths to stdout, exits with code 0)
# Esc: Abort (exits without saving)
# Cmd+Delete (macOS) / Ctrl+Delete (Linux): Delete current image from history

# Exit behavior:
# Accept: prints saved file paths to stdout (newline-separated), exits with code 0
# Abort: exits with code 1 (empty stdout)
```

The UI provides:
- **Real-time buffer status**: Visual indicator showing how many images are ready to review
- **Smooth transitions**: GPU-accelerated animations between images (<100ms skip latency)
- **Memory efficiency**: Uses Tauri asset protocol for direct file access (no base64 encoding)
- **Exit contracts**: Predictable stdout/exit-code behavior for scripting integration
- **Theme customization**: Toggle between dark and light themes with persistent preference
- **Image navigation**: Review previously viewed images with ← and → arrow keys
- **Image curation**: Delete unwanted images with keyboard shortcut before accepting
- **Multi-image acceptance**: Accept multiple images from single session (all retained paths printed)
- **Visual feedback**: Button flash animations confirm keyboard shortcut actions

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

For detailed technical guides and troubleshooting, see [docs/](docs/).

## TODO / Future Ideas

- [ ] **JPEG output with EXIF metadata** - Support JPEG as well as PNG. Add a radio button group next to control buttons to toggle output format. Add corresponding CLI parameters. Default to PNG. For JPEG, use EXIF for metadata storage.

- [ ] **Daemon mode for local models** - Since startup time is relatively high due to model loading, consider optionally running the service as a daemon for local models. This pairs well with pluggable model support.

- [ ] **Post-processing tools** - Add image post-processing capabilities (cropping, filters, adjustments, etc.)

- [ ] **Pluggable model support** - Allow plugging in other models beyond FLUX.1 schnell, including remote/API-based models (e.g., OpenAI DALL-E, Stability AI, etc.)

- [ ] **Tauri MCP integration** - Explore [tauri-mcp](https://github.com/dirvine/tauri-mcp) for enhanced Tauri capabilities

- [ ] **Architecture diagram** - Create a visual representation of the Tauri-Python-IPC architecture for documentation

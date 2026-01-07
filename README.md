# Textbrush

Text-to-image generation tool with customizable workflows and local model inference.

## Features

- **Command-line interface** for text-to-image generation with FLUX.1 schnell model
- **Background image generation** with 8-image FIFO buffer for smooth workflows
- **Flexible configuration** via CLI arguments, environment variables, or TOML config file
- **Local model management** with automatic HuggingFace cache discovery
- **Hardware auto-detection** supporting CUDA, Apple MPS, and CPU backends
- **XDG-compliant** configuration directory (~/.config/textbrush/)
- **Reproducible results** via seed parameter for deterministic generation
- **Desktop UI** (Tauri-based) with stdio IPC protocol for seamless image review workflow
- **IPC Protocol** for Tauri-Python communication with thread-safe message delivery

## Installation

```bash
uv sync
```

## Usage

### Basic Usage

Generate an image from a text prompt:

```bash
uv run textbrush generate "a watercolor painting of a cat"
```

### Configuration Options

```bash
# Specify output location
uv run textbrush generate "sunset over mountains" --output ~/Desktop/sunset.png

# Set format and seed for reproducibility
uv run textbrush generate "abstract art" --format jpg --seed 42

# Specify aspect ratio
uv run textbrush generate "portrait" --aspect-ratio 9:16

# Use custom config file
uv run textbrush --config ./project-config.toml generate "portrait"

# Enable verbose logging
uv run textbrush --verbose generate "landscape"
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
make test          # Run test suite
make lint          # Check code quality
make format        # Format code
make build         # Build Tauri application
make clean         # Remove build artifacts
```

See `CLAUDE.md` for detailed development guidelines.

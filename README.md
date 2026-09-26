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

## Reference editing

Textbrush can edit local images with locally installed FLUX models. Reference
images are **optional for the models that support them at all**:
`flux1-schnell` is text-to-image only and accepts none; `flux1-kontext-dev`
requires exactly one; `flux2-klein-4b` generates from a prompt alone and also
accepts up to four, and is required for two or more. References are local PNG,
JPG, or JPEG files (including `.JPG`); order preserved, duplicates allowed. See
[Reference Editing](docs/reference-editing.md) for the full guide — model
capabilities, output sizes, CLI and desktop flows, credentials, hardware,
privacy, and limitations.

In the desktop app the reference control is always on screen; for a model that
takes no references it is greyed out rather than hidden.

```bash
# One reference with Kontext
uv run textbrush --model flux1-kontext-dev --reference portrait.jpg \
  --preset portrait-medium --prompt "paint this person as a 1920s poster"

# Three ordered references with FLUX.2
uv run textbrush --model flux2-klein-4b \
  --reference subject.png --reference palette.jpg --reference lighting.png \
  --preset landscape-large --prompt "render the subject in the palette and lighting"

# FLUX.2 with no references at all, at a 16:9 output size
uv run textbrush --model flux2-klein-4b --aspect-ratio 16:9 \
  --prompt "a wide shot of a harbour at dawn"
```

## Choosing a model in the desktop app

No model is loaded when the window opens. The app lists every registered model
with its reference capability and whether its weights are installed, and loads
one only once you pick it — loading takes tens of seconds, so nothing is loaded
on the chance that you wanted it. A model pinned in the config
(`[model] selected_id`) or passed on the command line counts as that choice and
loads at launch.

Output size is one group, shared by every model: each aspect ratio shows the
pixel dimensions it currently produces, and the `−`/`+` step moves all of them
up or down the ladder together. The `4:3` and `3:4` options are the same sizes
the `landscape-*` and `portrait-*` preset names refer to.

The native executable accepts `--prompt`, `--out`, `--seed`, `--aspect-ratio`,
`--width` with `--height`, `--buffer-max`, `--model`, repeated `--reference`,
and `--preset`. Unknown options and missing values are errors. Reference order
and duplicates are preserved. A preset selects its named canvas and cannot be
combined with a ratio or explicit dimensions; otherwise explicit dimensions
win over the ratio's smallest desktop size. Buffer capacity must be positive.
Seeds must fit JavaScript's exact integer range (−9007199254740991 through
9007199254740991); zero is preserved. Model capabilities and reference validity
are checked by the backend. Python CLI flags are a separate interface.

Desktop abort and window close give the backend five seconds to finish cleanup,
then terminate and reap it if needed. Abort adds a short (500 ms) UI exit delay.
Each desktop session keeps previews in its own temporary directory, removed on
normal exit or a backend crash; accepted output files remain in the chosen output
directory. Shutdown waits for any active model load or inference inside Python;
the desktop enforces the process deadline. Headless Python keeps its existing
`.preview` location under the output directory.

## Requirements

- **Python 3.11+** - For running the inference backend
- **Rust 1.70+ and Cargo** - For building the Tauri desktop application
- **uv** - Package and virtual environment manager (development only)
- **System dependencies** - For GPU acceleration and UI rendering (see [GPU Setup Guide](docs/gpu-setup.md))

**Supported Platforms:**
- macOS (Apple Silicon ARM64, Intel x64)
- Linux (x64)

## Installation

### From a Release Build

Packaged release builds spawn the Python backend using `python3` on the system `PATH`. The `textbrush` Python package must be installed and accessible to the `python3` executable:

```bash
# Install the textbrush Python package system-wide or in the active environment
pip install 'textbrush[model]'

# Or with uv
uv pip install 'textbrush[model]'
```

Local `make package` and release CI use the same locked frontend tools and
platform bundle configuration. They require Node.js 22 and install frontend
packages with `npm ci`. Packages contain the desktop executable and runtime web
assets; Python and model dependencies are installed separately. Copying a local
virtual environment into the application is not supported.

The base `textbrush` package supports help, update checks, and model downloads without the model extra. Image generation requires `textbrush[model]`.

Then download the release binary for your platform and run it directly. `uv` is **not** required on the target system.

### From Source

```bash
# Install dependencies, including inference
uv sync --extra model

# Download the default model, FLUX.1 schnell (gated: needs a HuggingFace token)
export HF_TOKEN="hf_xxxxxxxxxxxxx"
uv run textbrush --download-model

# Or download one of the reference-editing models by slug
uv run textbrush --download-model flux1-kontext-dev   # gated, needs HF_TOKEN
uv run textbrush --download-model flux2-klein-4b      # ungated, no token needed

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
uv run textbrush --prompt "a serene mountain landscape" --out output.png

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

Acceptance saves images in delivery order. If a save fails, completed files are reported and retained; retry finishes the remaining saves without duplicating them. Previews remain available across partial save failures. Delivery waits during acceptance and resumes if saving fails.

`--out image.png` names the first image; additional images use `image-002.png`, `image-003.png`, and so on. Existing files are never overwritten. The filename extension chooses PNG or JPEG; without `--out`, the configured output directory and format apply. PNG retains generation metadata. JPEG is encoded as JPEG, converts unsupported pixel modes to RGB, and does not include custom metadata or reference provenance.

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
uv run textbrush --prompt "test image" --headless --auto-accept --out output.png

# Abort immediately (for testing error paths)
uv run textbrush --prompt "test" --headless --auto-abort

# Exit codes:
# 0: Image accepted successfully (path printed to stdout)
# 1: Aborted or error (empty stdout)
```

Generation uses a bounded queue. When it fills, the worker retains at most one completed image and waits for space; it does not discard images or keep generating. Pausing retains that pending image until resume. A configuration change discards pending and queued output from the previous configuration.

Generation waits for an image without a fixed inference deadline. Inference errors end the run and report the original error; start a new run to retry. Python backend shutdown waits for active inference to return before releasing the model, so cleanup can take as long as the current generation.

Headless mode is designed for:
- **CI/CD pipelines**: Automated image generation without UI
- **Integration testing**: End-to-end workflow verification
- **Scripted workflows**: Batch processing with predictable exit codes

### Configuration Options

```bash
# Specify output location
uv run textbrush --prompt "sunset over mountains" --out ~/Desktop/sunset.png

# Set format and seed for reproducibility
uv run textbrush --prompt "abstract art" --format jpg --seed 42

# Specify aspect ratio (1:1, 16:9, 4:3, 3:4, 3:1, 4:1, 4:5, 9:16)
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
token = ""  # Or use HF_TOKEN env var

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
uv run textbrush --download-model  # Download FLUX.1 schnell (requires HF_TOKEN)
uv run textbrush --download-model flux2-klein-4b  # Or any registry slug
```

### Development Tasks

```bash
make test          # Run fast tests (excludes slow/integration)
make test-all      # Run full test suite including slow/integration tests
make test-ui-a11y  # Run headless-browser accessibility harness (downloads Chromium on first run)
make lint          # Check Python code quality (ruff)
make format        # Format Python code (ruff)
make clippy        # Check Rust code quality (cargo clippy)
make fmt-rust      # Format Rust code (cargo fmt)
make fmt-check     # Verify all code is formatted (CI)
make build         # Build Tauri application
make package       # Package native app: .app/.dmg on macOS, .deb on Linux
make release       # Full release build (clean, install, package)
make run           # Run Tauri application locally
make run-debug     # Run Tauri with debug logging
make dev           # Run CLI with --help
make clean         # Remove build artifacts
```

For detailed technical guides and troubleshooting, see [docs/](docs/).

## TODO / Future Ideas

- [ ] **JPEG metadata and desktop format selector** - JPEG encoding and CLI format selection are supported. EXIF metadata and a desktop format selector remain future work.

- [ ] **Daemon mode for local models** - Since startup time is relatively high due to model loading, consider optionally running the service as a daemon for local models. This pairs well with pluggable model support.

- [ ] **Post-processing tools** - Add image post-processing capabilities (cropping, filters, adjustments, etc.)

- [ ] **Pluggable model support** - Allow plugging in other models beyond FLUX.1 schnell, including remote/API-based models (e.g., OpenAI DALL-E, Stability AI, etc.)

- [ ] **Tauri MCP integration** - Explore [tauri-mcp](https://github.com/dirvine/tauri-mcp) for enhanced Tauri capabilities

- [ ] **Architecture diagram** - Create a visual representation of the Tauri-Python-IPC architecture for documentation

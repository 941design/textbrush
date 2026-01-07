## Textbrush - Image Generation and Review Desktop App — Production-Ready Specification

### 1. Purpose & Scope

**Purpose**
Provide a robust, open-source, cross-platform desktop application for generating images from **local text-to-image models** and reviewing them in a fast, native-feeling slideshow UI. The tool is designed to integrate cleanly with editor-driven workflows (e.g. Emacs), enabling rapid accept/skip/abort decisions and deterministic machine-readable output.

**Scope**

* Production-ready, open-source desktop software
* Local-only inference (no external APIs, no telemetry)
* CLI-driven invocation with desktop UI review
* Power-user–oriented setup and documentation

**Target Release Type**
Production

**Primary Users**

* Technical writers and developers using editors (Emacs, Vim, etc.)
* Power users comfortable with local ML models and GPU setup

**Desired Outcomes**

* Deterministic, scriptable image generation + review workflow
* Smooth UI with background-prefetched images
* Reliable packaging, documentation, and releases

**Non-Goals**

* Cloud inference or SaaS operation
* Image editing or post-processing
* Model training or fine-tuning
* Casual/non-technical user onboarding

**Success Metrics**

* CLI invocation → UI visible in <500ms
* First image rendered as soon as inference allows
* Skip action latency <100ms when buffer is non-empty
* Clean exit with stable stdout/exit-code contract
* Reproducible builds and tagged releases

---

### 2. Core Workflow

#### 2.1 Invocation

```bash
textbrush --prompt "A watercolor cat" [--out /path/to/file.png]
```

Optional:

* `--config /path/to/config.toml`
* `--seed <int>`
* `--aspect-ratio 1:1|16:9|9:16`
* `--format png|jpg`
* `--verbose`
* `--headless` - Run without UI (for CI/CD)
* `--auto-accept` - Auto-accept first image in headless mode
* `--auto-abort` - Auto-abort in headless mode

CLI arguments override config file values.

#### 2.1.1 CLI Arguments (Implemented)

**Required:**
* `--prompt TEXT` - Text prompt for image generation (must be non-empty)

**Optional:**
* `--out PATH` - Output file path (default: auto-generated in configured directory)
* `--config PATH` - Config file path (default: `~/.config/textbrush/config.toml`)
* `--seed INT` - Random seed for reproducibility (must be non-negative)
* `--aspect-ratio CHOICE` - Image aspect ratio: `1:1`, `16:9`, or `9:16`
* `--format CHOICE` - Output format: `png` or `jpg`
* `--verbose` - Enable debug logging (overrides config `logging.verbosity` to `debug`)
* `--headless` - Run without UI (for CI/CD and automated testing)
* `--auto-accept` - Auto-accept first generated image in headless mode (exit 0)
* `--auto-abort` - Auto-abort immediately in headless mode (exit 1)

**Validation:**
* Prompt cannot be empty or whitespace-only
* Seed must be non-negative integer
* Format must be valid choice (png or jpg)
* Aspect ratio must be valid choice if provided

#### 2.2 Lifecycle

**UI Mode (Default):**
1. Parse CLI + config
2. Discover local models
3. Download required model(s) if missing and credentials allow
4. Launch UI immediately
5. Start background image generation
6. Present slideshow review
7. Exit on Accept or Abort

**Headless Mode (`--headless`):**
1. Parse CLI + config
2. Discover local models
3. Initialize inference engine
4. Generate single image (120-second timeout)
5. Handle based on auto-action flag:
   * `--auto-accept`: Save image, print path to stdout, exit 0
   * `--auto-abort`: Exit 1 without saving
   * Neither: Wait for completion, exit 0 on success, 1 on failure
6. Clean up and exit

Headless mode is designed for CI/CD pipelines and automated testing, providing predictable exit codes and stdout behavior.

---

### 3. Image Review Behavior

#### 3.1 Buffering

* Maintain a **pipeline of up to 8 images**
* Backend continuously refills buffer while UI is active
* FIFO semantics

#### 3.2 Actions

* **Skip**

  * Discard current image
  * Immediately show next buffered image if available
* **Accept**

  * Save image to disk
  * Print absolute saved path to stdout
  * Exit application
* **Abort**

  * Discard all images
  * Print nothing to stdout
  * Exit application

---

### 4. User Interface

#### 4.1 UI Characteristics

* Cross-platform desktop window
* Fixed-size, centered
* Minimal, distraction-free layout
* One image visible at a time
* Clear loading / buffer-empty indicators

#### 4.2 Controls

**Keyboard**

* `Enter`: Accept
* `Space` or `→`: Skip
* `Esc`: Abort

**Mouse**

* On-screen buttons for Accept / Skip / Abort

---

### 5. Architecture

#### 5.1 High-Level Design

* **Tauri**: desktop shell + UI (HTML/CSS/JS)
* **Python backend (sidecar process)**:

  * Local model inference
  * Image buffering
  * Disk I/O
* IPC via localhost HTTP or stdio-based protocol

#### 5.2 Process Model

* Tauri app spawns Python backend on startup
* Backend terminates when UI exits
* Abort immediately stops inference

#### 5.3 Python Backend Components

**Package Structure:**
* Package: `textbrush` (Python >=3.11)
* Entry point: `textbrush` CLI command

**Core Modules:**

| Module | Purpose |
|--------|---------|
| `textbrush.cli` | Command-line argument parsing and application entry |
| `textbrush.config` | TOML configuration with environment variable support |
| `textbrush.paths` | XDG-compliant path constants |
| `textbrush.backend` | High-level workflow orchestration |
| `textbrush.buffer` | Thread-safe FIFO image buffer |
| `textbrush.worker` | Background generation worker thread |

**Inference Engine (`textbrush.inference`):**
* Abstract `InferenceEngine` interface for pluggable backends
* `FluxInferenceEngine` implementation for FLUX.1 schnell
* Hardware auto-detection: CUDA > MPS > CPU
* Seed-based deterministic generation
* Aspect ratio presets: 1:1, 16:9, 9:16

**Model Management (`textbrush.model`):**
* HuggingFace cache discovery (respects `HF_HOME`, `HF_HUB_CACHE`)
* Custom model directory support via config
* Model availability validation
* Token-based model download via huggingface_hub

**IPC Layer (`textbrush.ipc`):**
* JSON-over-stdio protocol for Tauri communication
* Commands: INIT, SKIP, ACCEPT, ABORT, STATUS
* Events: READY, IMAGE_READY, BUFFER_STATUS, ERROR, ACCEPTED, ABORTED
* Thread-safe message delivery
* Error propagation from worker to UI

#### 5.4 Tauri Desktop Shell

**Rust Components (`src-tauri/src/`):**

| Module | Purpose |
|--------|---------|
| `main.rs` | Application entry and window management |
| `sidecar.rs` | Python process spawning and lifecycle |
| `commands.rs` | Tauri commands: init, skip, accept, abort |
| `exit_handlers.rs` | Exit code contract handling |

**Frontend (`src-tauri/ui/`):**
* Single-page HTML/CSS/JS application
* Minimal dark theme (#1a1a1a background)
* Real-time buffer status visualization
* GPU-accelerated image transitions
* Keyboard shortcuts: Space/→ (skip), Enter (accept), Esc (abort)
* State machine: idle → loading → ready → action states

**Window Configuration:**
* Fixed size: 800x700 pixels
* Centered, non-resizable
* macOS minimum: 10.15

#### 5.5 Headless Mode

For CI/CD and automated workflows:
* `--headless` flag disables UI
* `--auto-accept` accepts first image (exit 0)
* `--auto-abort` aborts immediately (exit 1)
* 120-second timeout for generation
* Machine-readable stdout (path only on accept)

#### 5.6 CI/CD Pipeline

**Continuous Integration (`.github/workflows/ci.yml`):**
* Multi-platform builds: macOS ARM64/x64, Linux x64
* Python tests (pytest) and Rust tests (cargo test)
* Linting and formatting checks
* E2E smoke tests with headless mode

**Release Automation (`.github/workflows/release.yml`):**
* Triggered by version tags (v*)
* Binary packaging: .app, .dmg (macOS), .tar.gz (Linux)
* SHA256 checksums for verification
* GitHub Releases upload

---

### 6. Local Model Management

#### 6.1 Supported Model

* **FLUX.1 schnell** (default)
* Local-only inference
* No bundled weights

#### 6.2 Model Discovery

On startup:

1. Check Hugging Face cache (respect `HF_HOME`)
2. Check configured custom model directories
3. Validate required files

#### 6.3 Model Download

* Automatic download **only if** Hugging Face token is available
* Token supplied via:

  * Environment variable (`HUGGINGFACE_HUB_TOKEN`)
  * Config file
* User must manually accept license on Hugging Face
* If token missing:

  * App blocks generation
  * UI displays clear instructions
* Manual model placement is always supported

---

### 7. Inference Engine

* Inference backend is **pluggable** via abstract `InferenceEngine` interface
* Reference implementation: **FLUX.1 schnell** via `FluxInferenceEngine`
* Engine abstraction:
  * `load()` - Initialize model and load weights to device
  * `unload()` - Release model resources
  * `generate(prompt, options) -> GenerationResult`
* Hardware selection (automatic detection with priority):
  * CUDA (Linux/Windows with NVIDIA GPU)
  * Apple MPS (macOS with Apple Silicon)
  * CPU fallback (significantly slower, warned)
* Generation options:
  * `seed` - Deterministic generation (auto-incremented if None)
  * `steps` - Inference steps (default: 4 for schnell)
  * `aspect_ratio` - Image dimensions ("1:1", "16:9", "9:16")

---

### 8. Data & Storage

#### 8.1 Output Handling

* If `--out` is provided:

  * Save exactly to that path
* Otherwise:

  * Save to configured default output directory
  * Auto-generate filename (timestamp or UUID)

#### 8.2 Temporary Files

* Skipped images stored in temp directory
* Best-effort cleanup on exit

---

### 9. Interfaces & Contracts

#### 9.1 CLI Exit Contract

* **Accept**

  * Exit code: `0`
  * Stdout: absolute image path
* **Abort / No accept**

  * Exit code: non-zero
  * Stdout: empty

Stable and scriptable from editors (e.g. Emacs).

---

### 10. Configuration

#### 10.1 Format

* **TOML** (commentable)

#### 10.2 Default Location

* XDG-compliant:

  * `~/.config/textbrush/config.toml`

#### 10.3 Configurable Fields

* Default output directory
* Output format (png | jpg)
* Model directories
* Buffer size (default: 8)
* Hugging Face token
* Inference backend selection (default: flux)
* Logging verbosity (debug | info | warning | error)

#### 10.4 Configuration Priority (Implemented)

Configuration values are resolved in the following priority order:

1. **CLI arguments** (highest priority) - e.g., `--format png`
2. **Environment variables** - e.g., `TEXTBRUSH_OUTPUT_FORMAT=png`
3. **Config file** - `~/.config/textbrush/config.toml`
4. **Defaults** (lowest priority)

Environment variables use the `TEXTBRUSH_` prefix followed by section and key:
* `TEXTBRUSH_OUTPUT_FORMAT` overrides `[output].format`
* `TEXTBRUSH_LOGGING_VERBOSITY` overrides `[logging].verbosity`

#### 10.5 Config File Schema (Implemented)

```toml
[output]
directory = "~/Pictures/textbrush"
format = "png"

[model]
directories = []
buffer_size = 8

[huggingface]
token = ""

[inference]
backend = "flux"

[logging]
verbosity = "info"
```

The config file is automatically created with defaults on first run if it does not exist.

---

### 11. Non-Functional Requirements

#### Performance

* UI thread never blocked by inference
* Background generation cancellable

#### Reliability

* Graceful handling of missing models
* Clear error states in UI
* Deterministic cleanup on exit

#### Security & Privacy

* No telemetry
* No analytics
* No crash reporting
* No network access beyond optional model download

---

### 12. Testing Strategy

**Balanced Testing**

* Python:

  * Unit tests for buffering, config, model discovery
  * Integration tests with mocked inference backend
  * Property-based tests for core algorithms
* UI:

  * Automated smoke tests (launch, skip, accept, abort)
* End-to-end:

  * CLI invocation → UI → exit contract tests in CI
  * Headless mode tests with subprocess execution
  * Seed determinism verification via file hash comparison
  * Exit code contract validation
  * `--auto-accept` and `--auto-abort` workflow tests
  * CI smoke test execution in GitHub Actions

---

### 13. Distribution & Releases

#### Platforms

* **macOS**
* **Linux**

#### Signing

* macOS:

  * Non-Apple signing (ad-hoc codesign)
  * Not notarized
  * Documented Gatekeeper workarounds
* Linux:

  * Signed artifacts (checksums)

---

### 14. Open Source & Project Hygiene

* Public GitHub repository
* Clear README + installation docs
* Power-user setup guide (GPU, HF tokens, models)
* CHANGELOG.md
* Semantic versioning
* GitHub Actions:

  * CI (tests)
  * Build artifacts
  * Tagged releases

---

### 15. Out of Scope

* Windows support
* Model fine-tuning
* Auto-updates (only manual updates allowed)
* Telemetry or usage metrics
* Image editing or post-processing
* Model training

**Note:** For planned features not yet implemented, see separate feature specifications in `specs/` directory.

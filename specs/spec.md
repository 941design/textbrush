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

**Validation:**
* Prompt cannot be empty or whitespace-only
* Seed must be non-negative integer
* Format must be valid choice (png or jpg)
* Aspect ratio must be valid choice if provided

#### 2.2 Lifecycle

1. Parse CLI + config
2. Discover local models
3. Download required model(s) if missing and credentials allow
4. Launch UI immediately
5. Start background image generation
6. Present slideshow review
7. Exit on Accept or Abort

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

#### 5.3 Implemented Components (Increment 1)

**Python Package Structure:**
* Package: `textbrush` (Python >=3.11)
* Entry point: `textbrush` CLI command
* Core modules:
  * `textbrush.cli` - Command-line argument parsing and application entry
  * `textbrush.config` - TOML configuration loading with environment variable support
  * `textbrush.paths` - XDG-compliant path constants
  * `textbrush.model.weights` - HuggingFace model cache discovery and validation

**Configuration System:**
* TOML-based configuration at `~/.config/textbrush/config.toml`
* Configuration priority: CLI arguments > environment variables > config file > defaults
* Environment variables: `TEXTBRUSH_*` prefix (e.g., `TEXTBRUSH_OUTPUT_FORMAT`)
* Auto-creates default config on first run
* Sections: output, model, huggingface, inference, logging

**Model Weight Management:**
* Automatic discovery of FLUX.1 schnell in HuggingFace cache
* Respects `HF_HOME` and `HF_HUB_CACHE` environment variables
* Support for custom model directories via config
* Model availability checking and validation
* Integration with huggingface_hub for cache management

**Tauri Shell:**
* Minimal Tauri v2 project structure in `src-tauri/`
* Compiles and displays empty window (foundation for UI development)
* Configured for sidecar process integration (future increments)

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

* Inference backend is **pluggable**
* Reference implementation: **TBD**
* Engine abstraction:

  * `generate(prompt, options) -> image`
* Hardware selection:

  * CUDA (Linux)
  * Apple MPS (macOS)
  * CPU fallback (best-effort, warned)

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
* UI:

  * Automated smoke tests (launch, skip, accept, abort)
* End-to-end:

  * CLI invocation → UI → exit contract tests in CI

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

#### Updates

* Manual updates only
* User-triggered “Check for updates”
* Uses GitHub Releases metadata

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
* Auto-updates
* Telemetry or usage metrics

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed
- **A configuration change could wait forever after the worker had
  parked.** The delivery loop re-announces `paused` after each image
  without a `settled` value; the UI read that silence as "not settled"
  and, if it arrived after the worker's own `settled=true`, kept a
  parked model or reference change waiting for a signal that had already
  come, with every control held. A `paused` event without the field now
  leaves the gate as the last statement set it.
- **Opening the reference file dialog froze the desktop app.** The
  dialog command was synchronous, so Tauri ran its blocking file picker
  on the main thread, stalling the event loop the picker itself waits
  on. The command is now asynchronous and runs off the main thread, as
  the dialog plugin requires.

### Added
- **WebP reference images.** The file picker, the CLI, and the decoder
  accept `.webp` alongside PNG and JPEG. WebP files are decoded and
  converted to RGB in memory exactly like the other formats; nothing is
  written to disk.

### Changed
- **Model, reference, and output-size changes no longer require a
  manual pause.** The desktop app takes them while the worker is
  running: it pauses the worker, applies the change once the in-flight
  generation has returned, and resumes if generation was running when
  the user asked. Previously the model selector and the reference picker
  were disabled until the user paused and the worker settled, which
  read as the controls not working at all.
- **A requested model is shown as selected at once, marked pending.**
  The clicked radio checks immediately and a spinner turns on its line
  (and in the viewer) until the backend acknowledges the load; a
  rejection restores the acknowledged model. Previously a model load
  showed no progress at all when an image was on screen. While the
  change is pending, every operational control and keyboard shortcut is
  disabled.
- **Reference images are optional for every model that supports them at
  all.** `flux2-klein-4b` now declares `min_references=0`: it generates
  from a prompt alone as readily as it edits one to four references.
  `flux1-kontext-dev` still requires exactly one. The desktop UI always
  shows the reference control and greys it out for a model that accepts
  none, so the capability is visible rather than absent.
- **Model loading is deferred until a model is selected.** The desktop
  app no longer loads a model at launch: it publishes the model
  catalogue (new `model_list` IPC event, carrying each model's display
  name, reference cardinality, and local availability), parks in the new
  `awaiting_model` state, and loads only what the user picks. A model
  pinned in `[model] selected_id` or passed on the command line is
  already a selection and still loads at launch. An unavailable
  selection is reported non-fatally and leaves the selection open.
- **One output-size vocabulary for every model.** `4:3` and `3:4` join
  the aspect-ratio table with exactly the dimensions the `landscape-*`
  and `portrait-*` presets name, and the editing-only "Output size"
  preset fieldset is gone: every model sees the same group, each option
  labelled with the pixel dimensions it currently produces, with one
  `−`/`+` ladder step shared across ratios. Aspect ratios are no longer
  rejected for reference-capable models, `apply_configuration` and
  `config_ack` carry explicit width/height, and `--preset` keeps working
  as a name for six of those sizes.
- Desktop header rearranged into three side-by-side groups — model
  (vertical), output size, reference images — under the prompt.

### Added
- Local multi-reference FLUX editing workflow, additive to the existing
  FLUX.1 [schnell] text-to-image path. Three registered models:
  `flux1-schnell` (text-to-image, 0 references), `flux1-kontext-dev`
  (single-reference editing, exactly 1), and `flux2-klein-4b`
  (multi-reference editing, 1 to 4). FLUX.2 [klein] 4B is **required** for
  any configuration with two to four references and is preferred for
  single-reference edits when no model is pinned.
- CLI flags `--model`, repeatable `--reference`, and `--preset` with
  cardinality and preset validation; CLI exit code 1 on cardinality,
  preset, and aspect-ratio mismatches. Cardinality, preset, and
  text-only aspect-ratio rules are shared between CLI and IPC through
  the `textbrush.validation` module.
- Six canonical editing output presets (`landscape-small` / `-medium` /
  `-large`, `portrait-small` / `-medium` / `-large`), owned by
  `textbrush.validation.EDITING_PRESETS`. Default for an editing-capable
  model with no explicit preset is `landscape-medium`, configurable under
  `[editing] default_preset`.
- Desktop UI: model selector, reference picker with per-reference
  previews, removal, and replacement; preset radios; compatibility
  messaging; editing controls enabled only after the worker has reached
  a settled state. See [docs/reference-editing.md](docs/reference-editing.md)
  for the full user guide.

### Changed
- The minimum supported `diffusers` version is now `0.37.0`; the lockfile
  resolves to `0.39.0`. Earlier releases did not export
  `Flux2KleinPipeline`, which the FLUX.2 editing path requires.

## [Unreleased]

### Added
- **UI Enhancements**: Improved user experience with theme customization, navigation, and visual feedback
  - Dark/light theme toggle with persistent preference and smooth transitions
  - Bidirectional image navigation with ← and → keys through viewing history
  - Position indicator showing current image in history (e.g., "[2/5]")
  - Image deletion with Cmd+Delete (macOS) / Ctrl+Delete (Linux) for curation
  - Multi-image workflow with batch acceptance of all retained images
  - Visual button flash animations for keyboard shortcut feedback
  - Multi-path acceptance: stdout prints newline-separated paths for all retained images
  - Modular frontend architecture: ThemeManager, HistoryManager, ButtonFlash modules
  - localStorage persistence for theme preference (key: textbrush-theme)
  - System theme preference detection on first launch
- **Path-based IPC Protocol**: Improved image delivery using file paths instead of base64
  - Images saved to preview directory (`.preview/`) on generation
  - IPC sends file path instead of base64-encoded image data
  - Frontend uses Tauri asset protocol for direct file access
  - Preview files moved to output on accept, deleted on skip
  - PNG metadata parsing with ExifReader for prompt/model/seed/dimensions
- **Headless Mode**: CLI operation without UI for CI/CD and automated testing
  - `--headless` flag for non-interactive operation
  - `--auto-accept` to accept first generated image and exit with code 0
  - `--auto-abort` to abort immediately and exit with code 1
  - Predictable exit codes and stdout behavior for scripting
  - 120-second timeout for image generation in headless mode
- **CI/CD Pipeline**: GitHub Actions workflows for automated testing and builds
  - CI workflow: lint, test Python, test Rust, multi-platform builds
  - Release workflow: automated binary packaging for macOS (ARM64/x64) and Linux
  - Matrix builds for macos-latest, macos-13, ubuntu-latest
  - Artifact uploads with SHA256 checksums
  - macOS releases now produce .dmg disk images via Tauri bundler (`cargo tauri build`)
  - .dmg and .tar.gz both uploaded as release assets for macOS
- **Tauri Bundling**: macOS app bundle configuration with ad-hoc signing
  - Bundle targets: .app and .dmg for macOS distribution
  - Ad-hoc code signing (signingIdentity: "-") for local builds
  - Minimum system version: macOS 10.15
- **E2E Integration Tests**: End-to-end test suite for full CLI workflows
  - Subprocess-based tests for CLI argument validation
  - Headless accept/abort workflow verification
  - Seed determinism testing with file hash comparison
  - Exit code contract verification
- **Desktop UI Implementation**: Complete slideshow review interface for generated images
  - Minimal dark-themed UI with centered image display
  - Real-time buffer status indicator (visual dots + count showing generation progress)
  - Keyboard shortcuts: Space/→ for skip, Enter for accept, Esc for abort
  - Mouse controls: on-screen buttons for Skip/Accept/Abort actions
  - Smooth GPU-accelerated image transitions with <100ms skip latency
  - Memory-efficient blob URLs (replaced base64 data URLs for large images)
  - Action queue preventing race conditions during rapid user input
  - Exit handling for OS window close events (maps to abort action)
  - Conditional animation skipping for performance optimization
  - Frontend state machine for robust action flow control
  - Window: 800x700, non-resizable, centered
  - Exit contract: Accept prints path + exit 0, Abort/close exits 1
- **Tauri IPC Integration**: Complete communication layer between Tauri desktop shell and Python backend
  - Stdio-based JSON protocol for cross-process communication
  - `IPCServer` with thread-safe message sending and dispatch
  - `MessageHandler` coordinating backend operations via IPC commands
  - Message types: INIT, SKIP, ACCEPT, ABORT, STATUS (commands) and READY, IMAGE_READY, BUFFER_STATUS, ERROR, ACCEPTED, ABORTED (events)
  - Base64 image encoding for JSON transport
  - Thread-safe image delivery with proper synchronization
  - Worker error propagation to UI via fatal error events
  - Graceful shutdown with resource cleanup
  - Rust sidecar management for spawning/killing Python process
  - Tauri commands: init_generation, skip_image, accept_image, abort_generation
  - Minimal test UI with keyboard shortcuts (Space/Enter/Escape)
- **Inference Backend**: Complete image generation backend with FLUX.1 integration
  - `FluxInferenceEngine` with FLUX.1 schnell model support
  - Hardware auto-detection (CUDA > MPS > CPU)
  - Seed-based deterministic generation
  - Aspect ratio presets (1:1, 16:9, 9:16)
- **Image Buffer System**: Thread-safe 8-image FIFO buffer
  - Blocking put/get operations with timeout support
  - Grace period shutdown for clean termination
  - Resource cleanup for temporary files
- **Background Worker**: Continuous image generation
  - Thread-safe error queue for error propagation
  - Immutable options progression via dataclass replace
  - Graceful shutdown support
- **Backend Coordinator**: High-level `TextbrushBackend` API
  - Complete workflow: initialize → generate → accept/skip → shutdown
  - Timeout protection for all blocking operations
  - Error checking and propagation to main thread
- **CLI `generate` Command**: Fully functional image generation
  - `textbrush generate PROMPT` produces single image
  - Progress messages to stderr, output path to stdout
  - Proper cleanup in finally block
- Foundation infrastructure including CLI, configuration system, and model weight management
- TOML-based configuration with environment variable and CLI argument overrides
- Command-line interface with arguments: --prompt, --out, --config, --seed, --aspect-ratio, --format, --verbose
- HuggingFace model weight discovery and caching support for FLUX.1 schnell
- XDG-compliant configuration directory (~/.config/textbrush/config.toml)
- Configuration priority system: CLI args > environment variables > config file > defaults
- Minimal Tauri v2 project shell with empty window
- Development tooling: Makefile with install, test, lint, format, build targets
- Python package structure with uv-based dependency management

# User Stories

## Personas

### 1. Technical Writer
Documentation authors who need quick image generation for technical docs, diagrams, or illustrations without leaving their text editor workflow (Emacs, Vim, etc.). They value:
- Scriptable, deterministic workflows that can be integrated into documentation builds
- Fast iteration cycles with immediate visual feedback
- Reproducible results via seed values for version-controlled documentation
- Local execution without dependency on external services

### 2. Developer
Software developers integrating image generation into build pipelines, editor environments, or automation scripts. They value:
- Clean CLI interface with stable exit codes and stdout contracts
- Configuration file support for project-specific defaults
- Environment variable overrides for CI/CD integration
- Reliable local model management without manual downloads

---

## Epic: Foundation Setup

Foundation infrastructure that enables subsequent increments to build the inference backend and desktop UI.

### [Implemented] Story 1.1: Command-Line Configuration

**As a** Technical Writer
**I want** to configure textbrush via command-line arguments, environment variables, or a config file
**So that** I can adapt the tool to different projects and workflows without modifying scripts

**Acceptance Criteria:**
- CLI accepts --prompt (required), --out, --config, --seed, --aspect-ratio, --format, --verbose
- Configuration loaded from ~/.config/textbrush/config.toml by default
- Environment variables with TEXTBRUSH_ prefix override config file values
- CLI arguments take precedence over environment variables and config file
- Help text displays all available options
- Invalid arguments produce clear error messages

**Test Coverage:**
- Priority order verified: CLI > env > file > defaults
- Config file created on first run if missing
- Round-trip config serialization maintains values
- CLI argument parsing validates types and constraints

---

### [Implemented] Story 1.2: Model Weight Management

**As a** Developer
**I want** the tool to automatically discover and manage FLUX.1 model weights
**So that** I can run image generation without manual model setup

**Acceptance Criteria:**
- Model discovery checks HuggingFace cache (respects HF_HOME, HF_HUB_CACHE)
- Model discovery checks custom directories from config
- Cache location reported via cache info API
- Environment variables HF_HOME and HF_HUB_CACHE respected
- Model availability check is idempotent
- Clear indication when models are missing or incomplete

**Test Coverage:**
- Cache discovery respects HF_HUB_CACHE environment variable
- Cache discovery falls back to HF_HOME/hub when HF_HUB_CACHE not set
- Multiple availability checks return consistent results
- Custom cache locations correctly identified

---

### [Implemented] Story 1.3: Development Workflow Tooling

**As a** Developer
**I want** standard development targets and build commands
**So that** I can efficiently develop, test, and build the application

**Acceptance Criteria:**
- `make install` sets up complete development environment with uv
- `make test` runs full test suite with pytest
- `make lint` checks code quality with ruff
- `make format` formats code consistently
- `make build` compiles Tauri application
- `make clean` removes build artifacts
- All commands succeed in clean environment

**Test Coverage:**
- 121 total tests (unit + integration + property-based)
- CLI, config, and model management integration verified
- End-to-end CLI workflow tested
- Configuration persistence and round-trip properties verified

---

## Epic: Inference Backend

Complete image generation backend with FLUX.1 integration, background worker, and CLI workflow.

### [Implemented] Story 2.1: Image Generation Engine

**As a** Developer
**I want** a pluggable inference engine abstraction with FLUX.1 implementation
**So that** I can generate images locally without external API dependencies

**Acceptance Criteria:**
- Abstract `InferenceEngine` interface with load, unload, generate methods
- `FluxInferenceEngine` implementation using FLUX.1 schnell model
- Hardware auto-detection (CUDA > MPS > CPU) with appropriate device selection
- Seed-based deterministic generation for reproducibility
- Aspect ratio presets for common image dimensions (1:1, 16:9, 9:16)
- Generation timing tracked and reported in results

**Test Coverage:**
- Property-based tests for dimension resolution from aspect ratios
- Engine lifecycle tests (load/unload)
- Determinism tests with mocked and real inference

---

### [Implemented] Story 2.2: Image Buffer System

**As a** Developer
**I want** a thread-safe FIFO buffer for generated images
**So that** I can decouple generation speed from UI consumption

**Acceptance Criteria:**
- Thread-safe buffer with configurable max size (default 8)
- Blocking put/get operations with optional timeout
- FIFO semantics maintained under concurrent access
- Graceful shutdown with grace period for in-flight operations
- Resource cleanup for temporary files on clear

**Test Coverage:**
- Property-based concurrency tests for thread safety
- Stress tests for fast producer/slow consumer scenarios
- Shutdown behavior with grace period verification
- FIFO order preservation under load

---

### [Implemented] Story 2.3: Background Generation Worker

**As a** Developer
**I want** a background worker that continuously generates images
**So that** the UI can have images ready without blocking

**Acceptance Criteria:**
- Continuous generation loop with stop signal support
- Seed auto-increment for variation (immutable options progression)
- Error capture via thread-safe error queue for main thread retrieval
- Graceful shutdown without blocking
- Logging of generation activity

**Test Coverage:**
- Worker start/stop lifecycle tests
- Error propagation tests
- Options immutability tests (seed increment via replace)
- Buffer interaction tests under various scenarios

---

### [Implemented] Story 2.4: Backend Coordinator

**As a** Technical Writer
**I want** a high-level backend API for the complete workflow
**So that** I can generate, review, and save images with simple commands

**Acceptance Criteria:**
- `initialize()` - Load model to device
- `start_generation()` - Begin background generation with prompt
- `get_next_image()` - Retrieve next buffered image with timeout
- `accept_current()` - Save current image to disk
- `skip_current()` - Discard current image, get next
- `abort()` - Stop generation and discard all images
- `shutdown()` - Clean resource release
- Error checking and propagation to main thread

**Test Coverage:**
- Complete workflow tests (initialize → generate → accept → shutdown)
- Timeout behavior tests
- Error propagation from worker to backend
- Resource cleanup verification

---

## Epic: Tauri IPC Integration

Communication layer enabling Tauri desktop shell to orchestrate Python inference backend via IPC protocol.

### [Implemented] Story 3.1: Stdio IPC Protocol

**As a** Developer
**I want** a JSON-based stdio protocol for Tauri-Python communication
**So that** the desktop UI can control inference backend across process boundaries

**Acceptance Criteria:**
- JSON message format over stdin/stdout with newline delimiters
- Command messages: INIT, SKIP, ACCEPT, ABORT, STATUS
- Event messages: READY, IMAGE_READY, BUFFER_STATUS, ERROR, ACCEPTED, ABORTED
- Base64 image encoding for JSON transport
- Thread-safe message sending with proper synchronization
- Error propagation from worker to UI via fatal error events

**Test Coverage:**
- Message serialization/deserialization tests
- Command dispatch tests
- Thread-safe message delivery tests
- Error propagation tests

---

### [Implemented] Story 3.2: IPC Server

**As a** Developer
**I want** a Python IPC server that handles UI commands and emits backend events
**So that** the Tauri shell can orchestrate generation workflow

**Acceptance Criteria:**
- `IPCServer` with thread-safe `send()` method
- Message dispatcher coordinating backend operations
- Command handlers: init, skip, accept, abort, status
- Event emission: ready, image_ready, buffer_status, error, accepted, aborted
- Graceful shutdown with resource cleanup
- Worker error propagation to UI

**Test Coverage:**
- Server lifecycle tests
- Command dispatch integration tests
- Event emission tests
- Shutdown behavior tests

---

### [Implemented] Story 3.3: Tauri Sidecar Management

**As a** Developer
**I want** Rust sidecar spawning and lifecycle management
**So that** Tauri can launch and control Python backend process

**Acceptance Criteria:**
- Sidecar process spawning with environment configuration
- Stdio stream capture for IPC communication
- Process termination on UI exit
- Tauri commands: init_generation, skip_image, accept_image, abort_generation
- Event relay from Python to frontend

**Test Coverage:**
- Process lifecycle tests
- Command relay tests
- Event handling tests

---

## Epic: Desktop UI

Complete slideshow review interface for generated images with real-time buffer visualization.

### [Implemented] Story 4.1: UI Implementation

**As a** Technical Writer
**I want** a minimal dark-themed slideshow UI with keyboard and mouse controls
**So that** I can quickly review generated images and accept/skip/abort

**Acceptance Criteria:**
- Minimal dark theme with centered image display
- Real-time buffer status indicator (visual dots + count)
- Keyboard shortcuts: Space/→ for skip, Enter for accept, Esc for abort
- Mouse controls: on-screen buttons for Skip/Accept/Abort
- Smooth image transitions with GPU-accelerated animations
- <100ms skip latency when buffer is non-empty
- Window: 800x700, non-resizable, centered
- Exit contract: Accept prints path + exit 0, Abort/close exits 1

**Test Coverage:**
- UI component rendering tests
- Keyboard event handling tests
- Image transition tests
- Buffer status display tests
- Exit behavior verification

**Implementation Details:**
- HTML/CSS/JS UI with Tailwind-inspired utility classes
- Path-based IPC with Tauri asset protocol (no base64 encoding)
- Preview directory pattern: save on generate, move on accept, delete on skip
- Action queue preventing race conditions
- Exit handling for OS window close events
- Conditional animation skipping for performance
- Frontend state machine for action flow control

---

### [Implemented] Story 2.5: CLI Integration

**As a** Technical Writer
**I want** a `generate` command that produces an image file
**So that** I can integrate image generation into my documentation workflow

**Acceptance Criteria:**
- `textbrush generate PROMPT` command generates single image
- Progress messages to stderr, output path to stdout
- Exit code 0 on success, 1 on error
- Supports --output, --seed, --aspect-ratio, --format options
- Proper cleanup in finally block (model unloaded even on error)
- Timeout protection for generation operations

**Test Coverage:**
- CLI invocation tests with CliRunner
- Full workflow integration tests
- Error handling tests
- Cleanup verification tests

---

## Epic: CI/CD and Production Readiness

Headless mode for automated testing, end-to-end test coverage, and CI/CD pipeline for reliable releases.

### [Implemented] Story 5.1: Headless Mode

**As a** Developer
**I want** headless CLI operation without UI
**So that** I can integrate textbrush into CI/CD pipelines and automated testing workflows

**Acceptance Criteria:**
- `--headless` flag disables UI launch
- `--auto-accept` automatically accepts first generated image and exits 0
- `--auto-abort` immediately exits with code 1
- Predictable exit codes (0 for success, 1 for failure/abort)
- Machine-readable stdout (only output path on accept)
- Progress messages to stderr for monitoring
- 120-second timeout for image generation

**Test Coverage:**
- Subprocess-based CLI execution tests
- Headless accept workflow verification
- Headless abort workflow verification
- Exit code contract validation
- Timeout behavior tests

---

### [Implemented] Story 5.2: End-to-End Test Suite

**As a** Developer
**I want** comprehensive E2E tests covering full CLI workflows
**So that** I can detect integration issues and regressions before release

**Acceptance Criteria:**
- E2E test suite using subprocess execution
- Seed determinism verification with file hash comparison
- Exit code contract tests for all modes
- Headless workflow tests (accept/abort)
- Timeout behavior verification
- CI smoke test integration

**Test Coverage:**
- CLI argument validation tests
- Headless accept/abort workflow tests
- Seed determinism with SHA256 hash comparison
- Exit code contract verification across modes
- Integration with GitHub Actions CI

---

### [Implemented] Story 5.3: CI/CD Pipeline

**As a** Developer
**I want** automated testing and release workflows
**So that** I can ensure code quality and deliver reliable builds

**Acceptance Criteria:**
- GitHub Actions CI workflow with multi-platform builds
- Python test suite execution (pytest)
- Rust test suite execution (cargo test)
- Linting and formatting checks
- E2E smoke test execution
- Automated release workflow with binary packaging
- Artifact generation with SHA256 checksums

**Test Coverage:**
- CI workflow tests on macOS (ARM64/x64) and Linux
- Release workflow for tagged versions
- Artifact upload and checksum generation
- E2E smoke tests running in CI environment

---

## Additional Personas

### 3. DevOps/CI Engineer
Engineers maintaining continuous integration pipelines and automated testing infrastructure. They value:
- Headless operation without UI dependencies
- Predictable exit codes (0/1) for pipeline integration
- Machine-readable stdout for scripting
- Timeout protection for resource management
- Multi-platform support (macOS ARM64/x64, Linux)

### 4. Power User (Interactive)
Advanced users who want rapid visual review and selection of AI-generated images. They value:
- Keyboard-driven workflow for speed
- Real-time buffer visualization showing generation progress
- Minimal, distraction-free UI
- GPU-accelerated performance (<100ms skip latency)
- Accessibility features (ARIA labels, semantic HTML)

### 5. Open Source Maintainer
Project maintainers and contributors managing releases, builds, and project hygiene. They value:
- Automated release workflows
- Multi-platform binary packaging
- Clear development tooling (Makefile targets)
- Reproducible builds with checksums
- Semantic versioning

---

## Epic: Accessibility and Usability

Accessibility features and user experience enhancements for keyboard navigation and screen readers.

### [Implemented] Story 6.1: Keyboard Accessibility

**As a** Power User
**I want** comprehensive keyboard shortcuts for all UI actions
**So that** I can review images without touching the mouse

**Acceptance Criteria:**
- Space or → keys skip to next image
- Enter key accepts current image
- Esc key aborts generation
- All actions accessible via keyboard
- No mouse required for complete workflow

**Implementation:**
- Event handlers in src-tauri/ui/main.js (lines 401-419)
- Keyboard events prevent default browser behavior
- Focus management for accessibility

---

### [Implemented] Story 6.2: Screen Reader Support

**As a** Visually Impaired User
**I want** semantic HTML with ARIA labels
**So that** I can use the application with assistive technology

**Acceptance Criteria:**
- `aria-label` attributes on all interactive elements
- `aria-live="polite"` on loading overlay
- `role="status"` on buffer indicator
- Semantic button elements with descriptive text
- Proper heading hierarchy

**Implementation:**
- ARIA labels on buffer dots (index.html lines 40-47)
- Live regions for dynamic content updates
- Semantic HTML5 elements throughout

---

### [Implemented] Story 6.3: Real-Time Visual Feedback

**As a** Power User
**I want** real-time buffer status visualization
**So that** I know how many images are ready to review

**Acceptance Criteria:**
- Buffer dots indicator with fill states
- Numeric count display (0/8 format)
- Loading overlay with spinner
- Success feedback on accept (green glow effect)
- Visual state changes are immediate

**Implementation:**
- Buffer visualization with CSS animations
- State-driven UI updates
- Performance optimizations for smooth transitions

---

## Epic: Configuration and Customization

Advanced configuration options for reproducible workflows and environment-specific settings.

### [Implemented] Story 7.1: Multi-Source Configuration

**As a** Developer
**I want** configuration from CLI args, environment variables, and config files with clear priority
**So that** I can adapt the tool to different environments without code changes

**Acceptance Criteria:**
- Priority system: CLI > env > file > defaults
- `TEXTBRUSH_*` environment variable prefix
- TOML config file support at ~/.config/textbrush/config.toml
- Clear precedence rules documented
- Config file auto-created on first run

**Implementation:**
- Three-tier config merging in textbrush/config.py
- Environment variable naming convention
- Path expansion and validation

---

### [Implemented] Story 7.2: Reproducible Generation

**As a** Technical Writer
**I want** seed-based deterministic image generation
**So that** I can generate identical images for version-controlled documentation

**Acceptance Criteria:**
- `--seed` CLI argument for reproducibility
- Seed display in UI during generation
- Auto-increment for variation in continuous generation
- SHA256 hash verification in E2E tests
- Same seed + prompt = identical image (on same hardware)

**Implementation:**
- Seed parameter in inference engine (textbrush/inference/flux.py)
- Determinism tests with hash comparison
- UI seed display (index.html lines 51-53)

---

### [Implemented] Story 7.3: Aspect Ratio Presets

**As a** Technical Writer
**I want** common aspect ratio presets (1:1, 16:9, 9:16)
**So that** I can generate images that fit standard layouts

**Acceptance Criteria:**
- `--aspect-ratio` CLI argument with choices validation
- 1:1 (1024x1024), 16:9 (1344x768), 9:16 (768x1344)
- Dimension resolution in FluxInferenceEngine
- Property-based tests for all presets

**Implementation:**
- Aspect ratio parsing in CLI
- Dimension calculation in inference engine
- Property tests for dimension resolution

---

## Epic: Planned Features

Features documented but not yet implemented. See separate feature specifications in `specs/` directory.

### [Planned] Story 8.1: CLI Model Download

**As a** Developer
**I want** to download models via a CLI flag
**So that** I can automate model setup without using Makefile commands

**Acceptance Criteria:**
- `--download-model` flag downloads FLUX.1 schnell
- Requires HuggingFace token (env var or config)
- Clear progress indication
- Success message with cache path
- Cannot be combined with `--prompt`

**Specification:** See `specs/cli-download-model-spec.md`

---

### [Planned] Story 8.2: Manual Update Check

**As a** Developer
**I want** to check for newer textbrush releases
**So that** I can stay up to date with bug fixes and features

**Acceptance Criteria:**
- `--check-updates` flag queries GitHub Releases API
- Compares current version with latest release
- Displays update notification if newer version available
- Provides download link to GitHub Releases
- Manual trigger only (no automatic checks)

**Specification:** See `specs/update-check-spec.md`

---

## Epic: User Experience Enhancements

Enhanced UI features for improved usability, workflow flexibility, and visual feedback.

### [Implemented] Story 9.1: Dark/Light Theme Toggle

**As a** Power User
**I want** to toggle between dark and light themes
**So that** I can adapt the UI to my environment and reduce eye strain

**Acceptance Criteria:**
- Theme toggle button in UI
- Themes: dark (#1a1a1a background) and light (#f5f5f5 background)
- Theme preference persisted to localStorage
- Theme restored on subsequent launches
- System preference detection as default
- Smooth CSS transition between themes

**Test Coverage:**
- Theme initialization with system preference fallback
- Theme toggle changes data-theme attribute
- localStorage persistence and restoration
- CSS variables update correctly for both themes

**Implementation Details:**
- ThemeManager module (src-tauri/ui/theme-manager.js)
- CSS custom properties for themeable colors
- localStorage key: textbrush-theme
- window.matchMedia for system preference detection

---

### [Implemented] Story 9.2: Bidirectional Image Navigation

**As a** Technical Writer
**I want** to navigate backward and forward through generated images
**So that** I can review previous images before deciding which to accept

**Acceptance Criteria:**
- ← Arrow key navigates to previous image
- → Arrow key navigates forward through history
- Navigation stays within bounds (no wrap-around)
- Position indicator shows current position (e.g., "[2/5]")
- Previously viewed images retained in memory
- Navigation available when not at buffer end
- Image history preserved with blob URLs and metadata

**Test Coverage:**
- Navigate through history with bound checking
- Position indicator updates correctly
- Cannot navigate before first or after last image
- Display callback invoked with correct image data

**Implementation Details:**
- HistoryManager module (src-tauri/ui/history-manager.js)
- imageHistory array stores viewed images with blob URLs
- historyIndex tracks current position
- Position indicator format: "[current/total]"

---

### [Implemented] Story 9.3: Image Deletion

**As a** Developer
**I want** to delete unwanted images from the history
**So that** I can curate only relevant images before accepting

**Acceptance Criteria:**
- Cmd+Delete (macOS) / Ctrl+Delete (Linux) deletes current image
- Deleted image removed from history
- Blob URL revoked for memory cleanup
- Navigate to next image after deletion
- Show empty state if all images deleted
- Deletion available at any history position

**Test Coverage:**
- Delete image from middle of history
- Delete last image triggers empty state
- Blob URL revocation verified
- History length and index adjustment correct
- Empty history shows empty state

**Implementation Details:**
- Keyboard shortcut: Cmd/Ctrl+Delete
- Blob URL cleanup via URL.revokeObjectURL()
- History array splice and index adjustment
- Empty state shown when history.length === 0

---

### [Implemented] Story 9.4: Visual Feedback for Actions

**As a** Power User
**I want** visual feedback when I press keyboard shortcuts
**So that** I know my actions are registered

**Acceptance Criteria:**
- Button flash animation when keyboard shortcut pressed
- Space/→ flashes Skip button
- Enter flashes Accept button
- Esc flashes Abort button
- Cmd/Ctrl+Delete flashes image container
- Animation duration: 200ms
- CSS class-based animation for performance

**Test Coverage:**
- Keyboard shortcuts trigger correct button flashes
- Unmapped keys do not trigger flashes
- CSS class added and removed correctly
- Modifier key detection for delete shortcut

**Implementation Details:**
- ButtonFlash module (src-tauri/ui/button-flash.js)
- CSS class: btn-pressed (box-shadow animation)
- 200ms animation duration with automatic cleanup
- Keyboard-to-button mapping for all actions

---

### [Implemented] Story 9.5: Multi-Image Workflow and Acceptance

**As a** Technical Writer
**I want** to retain all reviewed images and accept multiple at once
**So that** I can batch-select images from a single generation session

**Acceptance Criteria:**
- All viewed images saved to temporary location
- Accept action collects all retained image paths
- Multi-path acceptance prints all paths to stdout (newline-separated)
- Exit code 0 on multi-path acceptance
- Paths printed in chronological order (viewing order)
- Deleted images excluded from acceptance

**Test Coverage:**
- getAllRetainedPaths collects all history paths
- Paths filtered to exclude null values
- Empty history returns empty path array
- Deleted images not included in retained paths
- Multi-path workflow integration test

**Implementation Details:**
- getAllRetainedPaths() function in HistoryManager
- Backend IMAGE_READY event includes path field
- Multi-path exit via print_paths_and_exit command
- Newline-separated stdout format for scripting

---

### [Implemented] Story 9.6: Image Metadata Display Panel

**As a** Technical Writer
**I want** to see generation metadata (prompt, model, seed) alongside each image
**So that** I can understand the context and parameters used for each generated image

**Acceptance Criteria:**
- Split-view layout with image on left and metadata panel on right
- Metadata panel displays: prompt, model name, and seed
- Fixed-width panel (350px) with scrollable content for long prompts
- Metadata panel hidden when no image is loaded
- Metadata updates automatically when navigating through history
- Metadata persists for each image in history
- Responsive layout stacks vertically on narrow viewports (<820px)

**Test Coverage:**
- Metadata panel visibility toggling based on image state
- Metadata synchronization across navigation (forward/backward)
- Metadata persistence through history deletion
- IPC contract tests for prompt/model_name propagation
- Frontend display tests for all three metadata fields
- Responsive layout tests for narrow viewports

**Implementation Details:**
- Backend: Extended ImageReadyEvent with prompt and model_name fields
- Frontend: Split-view flexbox layout with image-panel and metadata-panel
- State: imageHistory stores metadata alongside image data
- CSS: Fixed 350px width with responsive media query for <820px viewports
- Metadata panel uses CSS custom properties for theme compatibility

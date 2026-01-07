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
- Memory-efficient blob URLs (replaced base64 data URLs)
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

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

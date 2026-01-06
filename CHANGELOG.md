# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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

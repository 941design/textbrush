# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Foundation infrastructure including CLI, configuration system, and model weight management
- TOML-based configuration with environment variable and CLI argument overrides
- Command-line interface with arguments: --prompt, --out, --config, --seed, --aspect-ratio, --format, --verbose
- HuggingFace model weight discovery and caching support for FLUX.1 schnell
- XDG-compliant configuration directory (~/.config/textbrush/config.toml)
- Configuration priority system: CLI args > environment variables > config file > defaults
- Minimal Tauri v2 project shell with empty window
- Development tooling: Makefile with install, test, lint, format, build targets
- Python package structure with uv-based dependency management

.PHONY: help install download-model dev test test-all test-e2e test-rust test-ui lint lint-ui typecheck-ui check-ui check-all format format-all clippy fmt-rust fmt-check build build-ui build-python release clean run run-debug

# Default target: show help
.DEFAULT_GOAL := help

help:  ## Show this help message
	@echo "Textbrush - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_0-9-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Setup
# ============================================================================

install:  ## Install Python dependencies with uv
	uv sync

download-model:  ## Download FLUX.1 schnell model (requires HuggingFace token)
	uv run python scripts/download_model.py

# ============================================================================
# Development
# ============================================================================

dev:  ## Run textbrush CLI with --help
	uv run textbrush --help

# Example prompt and dimensions for development
# NOTE: DEV_WIDTH and DEV_HEIGHT are internal Tauri launch args used during development only.
# They are NOT part of the textbrush CLI interface. The user-facing CLI uses --aspect-ratio instead.
DEV_PROMPT ?= "A watercolor painting of a cat"
DEV_WIDTH ?= 256
DEV_HEIGHT ?= 256

run: build  ## Build frontend/backend, then run Tauri application
	cd src-tauri && cargo run -- --prompt $(DEV_PROMPT) --width $(DEV_WIDTH) --height $(DEV_HEIGHT)

run-debug: build  ## Build frontend/backend, then run Tauri application with debug logging
	cd src-tauri && RUST_LOG=debug cargo run -- --prompt $(DEV_PROMPT) --width $(DEV_WIDTH) --height $(DEV_HEIGHT)

test:  ## Run test suite with pytest (excludes slow/integration tests)
	uv run pytest tests --ignore=tests/test_buffer_stress.py -m "not slow and not integration" -v
	cd src-tauri && cargo check

test-all:  ## Run full test suite including slow/integration tests
	uv run pytest tests -v --run-slow
	cd src-tauri && cargo check

test-e2e:  ## Run end-to-end smoke tests
	uv run pytest tests -m "e2e_smoke" -v

test-rust:  ## Run Rust test suite
	cd src-tauri && cargo test

test-ui:  ## Run UI TypeScript tests
	cd src-tauri/ui && npm run test

lint:  ## Check Python code quality with ruff
	uv run ruff check textbrush tests

lint-ui:  ## Check TypeScript code quality with ESLint
	cd src-tauri/ui && npm run lint

typecheck-ui:  ## Type-check TypeScript code
	cd src-tauri/ui && npm run typecheck

check-ui:  ## Run all UI checks (typecheck + lint)
	cd src-tauri/ui && npm run check

check-all:  ## Run all code quality checks (format-check + lint + clippy + typecheck)
	@echo "Running format checks..."
	@$(MAKE) -s fmt-check
	@echo "Running Python linting..."
	@$(MAKE) -s lint
	@echo "Running UI linting..."
	@$(MAKE) -s lint-ui
	@echo "Running Rust clippy..."
	@$(MAKE) -s clippy
	@echo "Running UI type checking..."
	@$(MAKE) -s typecheck-ui
	@echo "✓ All checks passed!"

format:  ## Format Python code with ruff
	uv run ruff format textbrush tests

format-all:  ## Format all code (Python + Rust)
	@echo "Formatting Python code..."
	@$(MAKE) -s format
	@echo "Formatting Rust code..."
	@$(MAKE) -s fmt-rust
	@echo "✓ All code formatted!"

clippy:  ## Check Rust code quality with clippy
	cd src-tauri && cargo clippy -- -D warnings

fmt-rust:  ## Format Rust code with rustfmt
	cd src-tauri && cargo fmt

fmt-check:  ## Verify all code is formatted (for CI)
	uv run ruff format --check textbrush tests
	cd src-tauri && cargo fmt --check

# ============================================================================
# Build
# ============================================================================

build-ui:  ## Build UI TypeScript bundle
	cd src-tauri/ui && npm run build

build: build-ui  ## Build Tauri application (includes UI)
	cd src-tauri && cargo build

build-python:  ## Build Python package wheel
	uv build

release:  ## Build optimized release binary
	cd src-tauri && cargo build --release

# ============================================================================
# Cleanup
# ============================================================================

clean:  ## Remove build artifacts and caches
	rm -rf dist build .pytest_cache __pycache__ .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

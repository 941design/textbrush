.PHONY: help install download-model dev test lint format build build-python clean run run-debug

# Default target: show help
.DEFAULT_GOAL := help

help:  ## Show this help message
	@echo "Textbrush - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

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

run:  ## Run Tauri application
	cd src-tauri && cargo run

run-debug:  ## Run Tauri application with debug logging
	cd src-tauri && RUST_LOG=debug cargo run

test:  ## Run test suite with pytest (excludes slow/integration tests)
	uv run pytest tests --ignore=tests/test_buffer_stress.py -m "not slow and not integration" -v
	cd src-tauri && cargo check

test-all:  ## Run full test suite including slow/integration tests
	uv run pytest tests -v
	cd src-tauri && cargo check

lint:  ## Check code quality with ruff
	uv run ruff check textbrush tests

format:  ## Format code with ruff
	uv run ruff format textbrush tests

# ============================================================================
# Build
# ============================================================================

build:  ## Build Tauri application
	cd src-tauri && cargo build

build-python:  ## Build Python package wheel
	uv build

# ============================================================================
# Cleanup
# ============================================================================

clean:  ## Remove build artifacts and caches
	rm -rf dist build .pytest_cache __pycache__ .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

.PHONY: help install download-model dev test test-all test-e2e test-rust test-ui test-ui-a11y lint lint-ui typecheck-ui check-ui check-all format format-all clippy fmt-rust fmt-check build ui-install build-ui build-python ensure-model-env bundle-python-env package release clean run run-debug ui-deps distclean

# Use a user-writable Cargo home (the system CARGO_HOME may be read-only)
override CARGO_HOME := $(HOME)/.cargo
export CARGO_HOME

# ----------------------------------------------------------------------------
# Cross-environment guard (host OS + VM/container sharing one project tree)
#
# npm resolves the cpu/os fields of optional dependencies against whichever
# platform runs the install, so packages shipping native binaries (esbuild
# here) end up architecture-specific. When a macOS host and a Linux VM share
# this tree over a mount, an install on one side leaves the other executing a
# foreign binary: `cannot execute binary file` (exit 126) out of esbuild.
#
# `node_modules/.platform` records the platform the current install targeted.
# Every UI target routes through `ui-deps`, which reinstalls from scratch when
# the stamp disagrees with the running platform -- or is missing, which is the
# same situation minus the evidence (a tree installed before this guard, or by
# a bare `npm install`). Never hand-edit the stamp; delete it and re-run make.
# ----------------------------------------------------------------------------
UI_DIR := src-tauri/ui
UI_PLATFORM_STAMP := $(UI_DIR)/node_modules/.platform
CURRENT_PLATFORM := $(shell node -e "console.log(process.platform+'-'+process.arch)" 2>/dev/null || echo unknown)
RECORDED_PLATFORM := $(shell cat $(UI_PLATFORM_STAMP) 2>/dev/null)

# The stamp is a real file, so make would otherwise call it up to date
# whenever it is newer than package.json/package-lock.json -- and skip the
# recipe that holds the platform check, which is the whole point of it.
# Forcing it PHONY on a mismatch (or when it is missing, giving an empty
# RECORDED_PLATFORM) makes the check run regardless of timestamps. On a
# match the target stays an ordinary file and make skips it as usual.
ifneq ($(RECORDED_PLATFORM),$(CURRENT_PLATFORM))
.PHONY: $(UI_PLATFORM_STAMP)
endif

# Default target: show help
.DEFAULT_GOAL := help

DMG_PATH = $(firstword $(wildcard src-tauri/target/release/bundle/dmg/*.dmg))

help:  ## Show this help message
	@echo "Textbrush - Development Commands"
	@echo ""
	@grep -E '^[a-zA-Z_0-9-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ============================================================================
# Setup
# ============================================================================

install:  ## Install Python dependencies with uv (includes model extras)
	uv sync --extra model

ensure-model-env:  ## Ensure Python model dependencies are installed
	uv sync --extra model

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

run: ensure-model-env build  ## Build frontend/backend, then run Tauri application
	cd src-tauri && cargo run -- --prompt $(DEV_PROMPT) --width $(DEV_WIDTH) --height $(DEV_HEIGHT)

run-debug: ensure-model-env build  ## Build frontend/backend, then run Tauri application with debug logging
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

test-ui: ui-deps  ## Run UI TypeScript tests
	cd src-tauri/ui && npm run test

test-ui-a11y: ui-deps  ## Run headless-browser accessibility harness (downloads Chromium on first run; not part of make test)
	cd src-tauri/ui && npx playwright install chromium && npm run test:a11y

lint:  ## Check Python code quality with ruff
	uv run ruff check textbrush tests

lint-ui: ui-deps  ## Check TypeScript code quality with ESLint
	cd src-tauri/ui && npm run lint

typecheck-ui: ui-deps  ## Type-check TypeScript code
	cd src-tauri/ui && npm run typecheck

check-ui: ui-deps  ## Run all UI checks (typecheck + lint)
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

ui-deps: $(UI_PLATFORM_STAMP)  ## Install UI dependencies, rebuilding them on a platform switch

$(UI_PLATFORM_STAMP): $(UI_DIR)/package.json $(UI_DIR)/package-lock.json
	@if [ -d $(UI_DIR)/node_modules ]; then \
		if [ ! -f $(UI_PLATFORM_STAMP) ]; then \
			echo "No platform stamp (installed before this guard, or by a bare npm install); cleaning $(UI_DIR)/node_modules..."; \
			rm -rf $(UI_DIR)/node_modules; \
		elif [ "$$(cat $(UI_PLATFORM_STAMP))" != "$(CURRENT_PLATFORM)" ]; then \
			echo "Platform changed ($$(cat $(UI_PLATFORM_STAMP)) -> $(CURRENT_PLATFORM)); cleaning $(UI_DIR)/node_modules..."; \
			rm -rf $(UI_DIR)/node_modules; \
		fi; \
	fi
	cd $(UI_DIR) && npm install
	@echo "$(CURRENT_PLATFORM)" > $(UI_PLATFORM_STAMP)

build-ui: ui-deps  ## Build UI TypeScript bundle
	cd $(UI_DIR) && npm run build

ui-install: ui-deps  ## Install or refresh UI dependencies

build: build-ui  ## Build Tauri application (includes UI)
	cd src-tauri && cargo build

build-python:  ## Build Python package wheel
	uv build

bundle-python-env: ensure-model-env  ## Prepare bundled Python environment for packaged app
	rm -rf src-tauri/target/python-env
	cp -R .venv src-tauri/target/python-env
	uv pip install --python src-tauri/target/python-env/bin/python --no-deps .

package: build-ui bundle-python-env  ## Build and package the application (.app + .dmg)
	rm -rf src-tauri/ui-dist
	mkdir -p src-tauri/ui-dist/styles
	cp src-tauri/ui/index.html src-tauri/ui/bundle.js src-tauri/ui-dist/
	cp src-tauri/ui/styles/*.css src-tauri/ui-dist/styles/
	rm -rf src-tauri/target/release/bundle/macos/Textbrush.app
	rm -f src-tauri/target/release/bundle/macos/Textbrush.dmg
	rm -f src-tauri/target/release/bundle/macos/rw.*.dmg
	rm -rf src-tauri/target/release/bundle/dmg
	cd src-tauri && npx @tauri-apps/cli build -c '{"build":{"beforeBuildCommand":"","frontendDist":"ui-dist"},"bundle":{"resources":["target/python-env"]}}'
	rm -rf src-tauri/ui-dist
	@echo "App bundle: src-tauri/target/release/bundle/macos/Textbrush.app"
	@echo "DMG: $(DMG_PATH)"

release: clean install package  ## Full release build (clean, install, build, package)
	@echo "Release build completed successfully!"
	@echo "App bundle: src-tauri/target/release/bundle/macos/Textbrush.app"
	@echo "DMG: $(DMG_PATH)"

# ============================================================================
# Cleanup
# ============================================================================

distclean: clean  ## Also remove UI dependencies (nuke option for a corrupt node_modules)
	rm -rf $(UI_DIR)/node_modules

clean:  ## Remove build artifacts and caches
	rm -rf dist build src-tauri/target .pytest_cache __pycache__ .ruff_cache src-tauri/ui-dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

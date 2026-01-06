# Increment 5: Integration, Testing & Packaging

## Overview
Final increment to integrate all components, implement comprehensive testing, set up CI/CD, and prepare distribution packages for macOS and Linux.

## Goals
- End-to-end integration testing
- Error handling and edge cases
- CI/CD pipeline with GitHub Actions
- macOS and Linux builds
- Documentation and release preparation

## Prerequisites
- All previous increments complete and functional

## Deliverables

### 5.1 End-to-End Integration

**Integration Test Suite:**

```python
# tests/e2e/test_full_workflow.py
import subprocess
import tempfile
import pytest
from pathlib import Path

class TestCLIWorkflow:
    """End-to-end CLI tests."""

    @pytest.fixture
    def temp_output(self):
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            yield Path(f.name)

    def test_help_shows_options(self):
        """CLI --help shows all required options."""
        result = subprocess.run(
            ['textbrush', '--help'],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        assert '--prompt' in result.stdout
        assert '--out' in result.stdout
        assert '--seed' in result.stdout
        assert '--aspect-ratio' in result.stdout

    def test_missing_prompt_fails(self):
        """CLI without prompt exits with error."""
        result = subprocess.run(
            ['textbrush'],
            capture_output=True,
            text=True
        )
        assert result.returncode != 0
        assert 'prompt' in result.stderr.lower()

    @pytest.mark.slow
    def test_accept_workflow(self, temp_output):
        """Accept saves image and prints path."""
        # This test requires UI automation or mock
        # Simulated with headless mode for CI
        result = subprocess.run(
            ['textbrush', '--prompt', 'test', '--out', str(temp_output), '--headless', '--auto-accept'],
            capture_output=True,
            text=True,
            timeout=120
        )
        assert result.returncode == 0
        assert str(temp_output) in result.stdout
        assert temp_output.exists()

    @pytest.mark.slow
    def test_abort_workflow(self):
        """Abort exits with non-zero, empty stdout."""
        result = subprocess.run(
            ['textbrush', '--prompt', 'test', '--headless', '--auto-abort'],
            capture_output=True,
            text=True,
            timeout=120
        )
        assert result.returncode != 0
        assert result.stdout.strip() == ''

    @pytest.mark.slow
    def test_seed_determinism(self, temp_output):
        """Same seed produces identical images."""
        # Generate twice with same seed
        # Compare file hashes
        pass
```

### 5.2 Error Handling & Recovery

**Model Not Found:**
```python
# textbrush/errors.py
class TextbrushError(Exception):
    """Base exception for Textbrush errors."""
    pass

class ModelNotFoundError(TextbrushError):
    """Model files not found in any search location."""

    def __init__(self, model_id: str, searched_paths: list[Path]):
        self.model_id = model_id
        self.searched_paths = searched_paths
        paths_str = '\n  '.join(str(p) for p in searched_paths)
        super().__init__(
            f"Model '{model_id}' not found.\n"
            f"Searched locations:\n  {paths_str}\n\n"
            f"To download the model:\n"
            f"  1. Set HUGGINGFACE_HUB_TOKEN environment variable\n"
            f"  2. Run: textbrush --download-model\n"
            f"Or manually place model files in one of the above directories."
        )

class TokenRequiredError(TextbrushError):
    """HuggingFace token required but not provided."""

    def __init__(self):
        super().__init__(
            "HuggingFace token required to download model.\n"
            "Please set HUGGINGFACE_HUB_TOKEN environment variable\n"
            "or add token to config file."
        )

class InferenceError(TextbrushError):
    """Error during image generation."""
    pass
```

**UI Error States:**
```javascript
// Error display in UI
function showErrorState(message, recoverable = false) {
    const overlay = document.getElementById('error-overlay');
    const errorMessage = overlay.querySelector('.error-message');
    const retryBtn = overlay.querySelector('.retry-btn');

    errorMessage.textContent = message;
    retryBtn.style.display = recoverable ? 'block' : 'none';
    overlay.classList.remove('hidden');
}

// Recovery options
async function retryGeneration() {
    hideErrorState();
    showLoading(true, 'Retrying...');
    await invoke('retry_generation');
}
```

### 5.3 Headless Mode for CI

Add headless mode for automated testing:

```python
# textbrush/cli.py additions
@click.option('--headless', is_flag=True, help='Run without UI (for testing)')
@click.option('--auto-accept', is_flag=True, help='Accept first image (headless)')
@click.option('--auto-abort', is_flag=True, help='Abort immediately (headless)')
def main(prompt, out, config, seed, aspect_ratio, format, verbose,
         headless, auto_accept, auto_abort):
    if headless:
        run_headless(prompt, out, seed, aspect_ratio, auto_accept, auto_abort)
    else:
        run_gui(prompt, out, config, seed, aspect_ratio, format, verbose)

def run_headless(prompt, out, seed, aspect_ratio, auto_accept, auto_abort):
    """Run without GUI for CI testing."""
    from .backend import TextbrushBackend
    from .config import load_config

    config = load_config()
    backend = TextbrushBackend(config)
    backend.initialize()
    backend.start_generation(prompt, seed, aspect_ratio)

    if auto_abort:
        backend.abort()
        sys.exit(1)

    if auto_accept:
        # Wait for first image
        image = backend.get_next_image()
        if image:
            path = backend.accept_current(Path(out) if out else None)
            print(str(path.absolute()))
            backend.shutdown()
            sys.exit(0)

    backend.shutdown()
    sys.exit(1)
```

### 5.4 CI/CD Pipeline

**.github/workflows/ci.yml:**

```yaml
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Lint Python
        run: uv run ruff check textbrush tests

      - name: Type check
        run: uv run mypy textbrush

  test-python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync

      - name: Run fast tests
        run: uv run pytest -m "not slow" --tb=short

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable

      - name: Install Tauri dependencies
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev

      - name: Build Rust
        working-directory: src-tauri
        run: cargo build

      - name: Test Rust
        working-directory: src-tauri
        run: cargo test

  build:
    needs: [lint, test-python, test-rust]
    strategy:
      matrix:
        include:
          - os: macos-latest
            target: aarch64-apple-darwin
          - os: macos-13
            target: x86_64-apple-darwin
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      - name: Install Tauri dependencies (Linux)
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev

      - name: Install dependencies
        run: |
          uv sync

      - name: Build Tauri app
        run: uv run tauri build --target ${{ matrix.target }}

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: textbrush-${{ matrix.target }}
          path: |
            src-tauri/target/${{ matrix.target }}/release/bundle/
```

### 5.5 Release Workflow

**.github/workflows/release.yml:**

```yaml
name: Release

on:
  push:
    tags:
      - 'v*'

permissions:
  contents: write

jobs:
  build-release:
    strategy:
      matrix:
        include:
          - os: macos-latest
            target: aarch64-apple-darwin
            asset_name: textbrush-macos-arm64
          - os: macos-13
            target: x86_64-apple-darwin
            asset_name: textbrush-macos-x64
          - os: ubuntu-latest
            target: x86_64-unknown-linux-gnu
            asset_name: textbrush-linux-x64

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install Rust
        uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      - name: Install Tauri dependencies (Linux)
        if: matrix.os == 'ubuntu-latest'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev

      - name: Build release
        run: |
          uv sync
          uv run tauri build --target ${{ matrix.target }}

      - name: Package macOS
        if: startsWith(matrix.os, 'macos')
        run: |
          cd src-tauri/target/${{ matrix.target }}/release/bundle/macos
          tar -czf ${{ matrix.asset_name }}.tar.gz *.app
          shasum -a 256 ${{ matrix.asset_name }}.tar.gz > ${{ matrix.asset_name }}.tar.gz.sha256

      - name: Package Linux
        if: matrix.os == 'ubuntu-latest'
        run: |
          cd src-tauri/target/${{ matrix.target }}/release/bundle
          tar -czf ${{ matrix.asset_name }}.tar.gz appimage/*.AppImage deb/*.deb
          sha256sum ${{ matrix.asset_name }}.tar.gz > ${{ matrix.asset_name }}.tar.gz.sha256

      - name: Upload release assets
        uses: softprops/action-gh-release@v1
        with:
          files: |
            src-tauri/target/${{ matrix.target }}/release/bundle/**/*.tar.gz
            src-tauri/target/${{ matrix.target }}/release/bundle/**/*.sha256

  create-release:
    needs: build-release
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Generate changelog
        id: changelog
        run: |
          # Extract changelog for this version
          VERSION=${GITHUB_REF#refs/tags/v}
          echo "version=$VERSION" >> $GITHUB_OUTPUT

      - name: Create release
        uses: softprops/action-gh-release@v1
        with:
          name: Textbrush v${{ steps.changelog.outputs.version }}
          body: |
            ## What's New
            See [CHANGELOG.md](CHANGELOG.md) for details.

            ## Installation

            ### macOS
            1. Download `textbrush-macos-arm64.tar.gz` (Apple Silicon) or `textbrush-macos-x64.tar.gz` (Intel)
            2. Extract and move to Applications
            3. Run `xattr -cr /Applications/Textbrush.app` to bypass Gatekeeper

            ### Linux
            1. Download `textbrush-linux-x64.tar.gz`
            2. Use the AppImage or install the .deb package

            ## Verification
            Verify downloads with the provided .sha256 checksums.
          draft: true
```

### 5.6 macOS Signing (Ad-hoc)

```rust
// src-tauri/tauri.conf.json
{
  "bundle": {
    "active": true,
    "targets": ["app", "dmg"],
    "identifier": "com.textbrush.app",
    "icon": ["icons/icon.icns"],
    "macOS": {
      "entitlements": null,
      "signingIdentity": "-",  // Ad-hoc signing
      "minimumSystemVersion": "10.15"
    }
  }
}
```

**Gatekeeper Workaround Documentation:**
```markdown
## macOS Installation

Textbrush is not notarized by Apple. After downloading:

1. Extract the .tar.gz archive
2. Move Textbrush.app to /Applications
3. Open Terminal and run:
   ```bash
   xattr -cr /Applications/Textbrush.app
   ```
4. Right-click the app and select "Open" the first time

Alternatively, run from the command line:
```bash
/Applications/Textbrush.app/Contents/MacOS/textbrush --prompt "Your prompt"
```
```

### 5.7 Documentation

**README.md:**

```markdown
# Textbrush

A desktop application for generating images from local text-to-image models with a fast, native-feeling slideshow review UI.

## Features

- 🎨 Local FLUX.1 schnell inference
- ⚡ Background image buffering (up to 8 images)
- ⌨️ Keyboard-driven workflow (Enter/Space/Esc)
- 📝 Scriptable CLI for editor integration
- 🔒 No telemetry, no cloud

## Installation

### Requirements
- Python 3.11+
- GPU with 16GB+ VRAM (CUDA or Apple MPS)
- ~25GB disk space for model

### Quick Start

```bash
# Install
brew install textbrush  # macOS (coming soon)
# or download from GitHub Releases

# Download model (requires HuggingFace account)
export HUGGINGFACE_HUB_TOKEN=your_token
textbrush --download-model

# Generate
textbrush --prompt "A watercolor cat"
```

## Usage

```bash
# Basic usage
textbrush --prompt "A watercolor painting of mountains"

# Specify output
textbrush --prompt "Abstract art" --out ~/Pictures/abstract.png

# Set seed for reproducibility
textbrush --prompt "Sunset" --seed 42

# Different aspect ratios
textbrush --prompt "Landscape" --aspect-ratio 16:9
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter | Accept current image |
| Space / → | Skip to next image |
| Esc | Abort and exit |

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Image accepted (path on stdout) |
| 1 | Aborted or error |

### Emacs Integration

```elisp
(defun my/insert-generated-image ()
  "Generate and insert an image."
  (interactive)
  (let* ((prompt (read-string "Prompt: "))
         (path (shell-command-to-string
                (format "textbrush --prompt %s" (shell-quote-argument prompt)))))
    (when (and path (not (string-empty-p path)))
      (insert (format "[[%s]]" (string-trim path))))))
```

## Configuration

Config file: `~/.config/image-reviewer/config.toml`

```toml
[output]
directory = "~/Pictures/textbrush"
format = "png"

[model]
buffer_size = 8

[huggingface]
token = ""  # Or use HUGGINGFACE_HUB_TOKEN env var
```

## Building from Source

```bash
# Clone
git clone https://github.com/yourusername/textbrush
cd textbrush

# Install dependencies
make install

# Download model
make download-model

# Development
make dev

# Build release
make build
```

## License

MIT
```

**CHANGELOG.md:**

```markdown
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.1.0] - YYYY-MM-DD

### Added
- Initial release
- FLUX.1 schnell model support
- Image buffer with up to 8 images
- Keyboard shortcuts (Enter/Space/Esc)
- CLI with scriptable exit codes
- macOS (ARM64, x64) and Linux support
```

### 5.8 Final Directory Structure

```
textbrush/
├── textbrush/                 # Python package
│   ├── __init__.py
│   ├── cli.py
│   ├── config.py
│   ├── paths.py
│   ├── errors.py
│   ├── backend.py
│   ├── buffer.py
│   ├── worker.py
│   ├── model/
│   │   ├── __init__.py
│   │   └── weights.py
│   ├── inference/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── flux.py
│   │   └── factory.py
│   └── ipc/
│       ├── __init__.py
│       ├── __main__.py
│       ├── protocol.py
│       ├── server.py
│       └── handler.py
├── src-tauri/
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── src/
│   │   ├── main.rs
│   │   ├── commands.rs
│   │   └── sidecar.rs
│   ├── ui/
│   │   ├── index.html
│   │   ├── main.js
│   │   ├── styles/
│   │   └── components/
│   ├── icons/
│   └── capabilities/
├── tests/
│   ├── conftest.py
│   ├── test_buffer.py
│   ├── test_worker.py
│   ├── test_config.py
│   ├── test_cli.py
│   ├── test_ipc_protocol.py
│   ├── test_ipc_server.py
│   └── e2e/
│       └── test_full_workflow.py
├── specs/
│   ├── spec.md
│   ├── increment-1-foundation.md
│   ├── increment-2-inference-backend.md
│   ├── increment-3-tauri-ipc.md
│   ├── increment-4-ui-implementation.md
│   └── increment-5-integration-packaging.md
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── release.yml
├── pyproject.toml
├── Makefile
├── README.md
├── CHANGELOG.md
└── LICENSE
```

## Acceptance Criteria

1. [ ] All unit tests pass
2. [ ] E2E tests pass in CI (headless mode)
3. [ ] macOS ARM64 build succeeds
4. [ ] macOS x64 build succeeds
5. [ ] Linux x64 build succeeds
6. [ ] GitHub Actions CI pipeline green
7. [ ] Release workflow creates draft release
8. [ ] README has complete documentation
9. [ ] CHANGELOG documents v0.1.0

## Testing Checklist

**Unit Tests:**
- [ ] Buffer FIFO semantics
- [ ] Worker start/stop
- [ ] Config loading and merging
- [ ] CLI argument parsing
- [ ] IPC protocol serialization
- [ ] Error handling paths

**Integration Tests:**
- [ ] CLI → Config → Backend flow
- [ ] IPC command/response cycle
- [ ] Headless accept workflow
- [ ] Headless abort workflow

**Manual Tests:**
- [ ] Fresh install on macOS (no prior Python)
- [ ] Fresh install on Linux
- [ ] Model download with token
- [ ] Full generation workflow
- [ ] Rapid skip stress test
- [ ] Memory usage over time

## Launch Checklist

- [ ] All tests passing
- [ ] Documentation reviewed
- [ ] Screenshots/demo GIF created
- [ ] Release notes written
- [ ] Version bumped in pyproject.toml
- [ ] Git tag created
- [ ] Release published

# Troubleshooting Guide

Common issues and solutions for textbrush.

## Installation Issues

### `uv sync` fails

**Symptoms:**
```
error: Failed to download package
```

**Solutions:**
1. Check internet connection
2. Verify Python 3.11+ installed: `python --version`
3. Try clearing UV cache: `uv cache clean`
4. Check disk space (PyTorch packages are large: ~5GB)

### Missing system dependencies (Linux)

**Symptoms:**
```
error: failed to compile tauri
Package libwebkit2gtk-4.1-dev was not found
```

**Solutions:**
```bash
# Ubuntu/Debian
sudo apt install libwebkit2gtk-4.1-dev libappindicator3-dev librsvg2-dev

# Fedora
sudo dnf install webkit2gtk4.1-devel libappindicator-gtk3-devel librsvg2-devel

# Arch
sudo pacman -S webkit2gtk libappindicator-gtk3 librsvg
```

## Model Download Issues

### Model not found

**Symptoms:**
```
ModelNotFoundError: FLUX.1 schnell model weights not found
```

**Solutions:**

1. **Set HuggingFace token:**
```bash
export HUGGINGFACE_HUB_TOKEN="hf_xxxxxxxxxxxxx"
# Get token from: https://huggingface.co/settings/tokens
```

2. **Download model manually:**
```bash
make download-model
# Or:
uv run python scripts/download_model.py
```

3. **Accept license on HuggingFace:**
- Visit https://huggingface.co/black-forest-labs/FLUX.1-schnell
- Click "Agree and access repository"
- Then retry download

4. **Check model cache:**
```bash
# Default HuggingFace cache
ls ~/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-schnell

# If found but not detected, add to config:
# ~/.config/textbrush/config.toml
[model]
directories = ["~/.cache/huggingface/hub"]
```

### Download interrupted

**Symptoms:**
```
urllib.error.URLError: Connection reset
```

**Solutions:**
1. Retry download (resumes automatically)
2. Check network stability
3. Model is ~23GB - ensure sufficient bandwidth
4. Try at different time if HuggingFace is overloaded

### Permission denied on model cache

**Symptoms:**
```
PermissionError: [Errno 13] Permission denied: '/home/user/.cache/huggingface'
```

**Solutions:**
```bash
# Fix permissions
chmod -R u+w ~/.cache/huggingface/

# Or download to custom directory
export HF_HOME="/path/to/custom/cache"
make download-model
```

## Runtime Issues

### GPU not detected

**Symptoms:**
```
Using device: cpu
(when you expect cuda or mps)
```

**Solutions:**

**For NVIDIA/CUDA:**
```bash
# Verify GPU visible
nvidia-smi

# Check CUDA available in PyTorch
uv run python -c "import torch; print(torch.cuda.is_available())"

# If False, reinstall PyTorch with CUDA:
# (This is rare - uv should install correct version)
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**For Apple Silicon/MPS:**
```bash
# Verify macOS 12.3+
sw_vers

# Check MPS available
uv run python -c "import torch; print(torch.backends.mps.is_available())"

# If False, update macOS or PyTorch
uv sync --upgrade
```

### Out of memory (OOM)

**Symptoms:**
```
RuntimeError: CUDA out of memory
torch.cuda.OutOfMemoryError
```

**Solutions:**

1. **Close other GPU applications**
```bash
# Check GPU usage
nvidia-smi
# Or on Mac:
sudo powermetrics --samplers gpu_power -i 1000 -n 1
```

2. **Reduce buffer size**
```toml
# ~/.config/textbrush/config.toml
[model]
buffer_size = 4  # Default is 8
```

3. **Check minimum VRAM**
- FLUX.1 schnell needs ~12GB VRAM minimum
- If less, consider CPU mode (slow but works)

4. **Restart to clear GPU memory**
```bash
# NVIDIA
sudo nvidia-smi --gpu-reset

# Apple Silicon - just restart app
```

### UI doesn't launch

**Symptoms:**
- CLI runs but no window appears
- Process hangs

**Solutions:**

1. **Check Tauri process**
```bash
# Look for hung tauri processes
ps aux | grep textbrush
killall textbrush  # If found
```

2. **Run with debug logging**
```bash
uv run textbrush --prompt "test" --verbose
# Check for errors in tauri spawning
```

3. **Test headless mode**
```bash
# If headless works, issue is UI-specific
uv run textbrush --prompt "test" --headless --auto-accept --out test.png
```

4. **macOS Gatekeeper blocking**
```bash
# If error mentions "damaged app"
xattr -dr com.apple.quarantine /path/to/textbrush.app
```

5. **Missing display (SSH/remote)**
- Textbrush requires X11/Wayland on Linux, window server on macOS
- Use `--headless` for remote/SSH environments

### Image generation times out

**Symptoms:**
```
Timeout waiting for image generation
```

**Solutions:**

1. **Expected on first run**
- Model loading takes 10-30 seconds
- First inference slower than subsequent
- Be patient!

2. **Check CPU vs GPU**
```bash
# If using CPU, expect 60-120 seconds per image
uv run textbrush --prompt "test" --verbose | grep "Using device"
```

3. **Increase timeout (headless mode only)**
- Default: 120 seconds
- CPU mode may need more time
- Current implementation has fixed timeout (future: make configurable)

### IPC communication errors

**Symptoms:**
```
Failed to communicate with backend
IPC protocol error
```

**Solutions:**

1. **Check Python backend running**
```bash
# Look for python sidecar process
ps aux | grep textbrush

# If not running, tauri failed to spawn it
# Check with --verbose for spawn errors
```

2. **Verify Python entry point**
```bash
# Test IPC server directly
uv run python -m textbrush.ipc
# Should wait for stdin (working correctly)
# Press Ctrl+C to exit
```

3. **Check for conflicts**
- Ensure no other textbrush instance running
- `killall textbrush` before retrying

## Configuration Issues

### Config file not loaded

**Symptoms:**
- Changes to `~/.config/textbrush/config.toml` ignored

**Solutions:**

1. **Check config file path**
```bash
# Verify file exists
cat ~/.config/textbrush/config.toml

# Or use custom path
uv run textbrush --config /path/to/config.toml --prompt "test" --verbose
```

2. **Check TOML syntax**
```bash
# Invalid TOML causes silent fallback to defaults
# Look for syntax errors: missing quotes, brackets, etc.
```

3. **Environment variables override config**
```bash
# Check for conflicting env vars
env | grep TEXTBRUSH

# Unset to test config file
unset TEXTBRUSH_OUTPUT_FORMAT
```

### Seed doesn't produce same image

**Symptoms:**
- Same seed + prompt produces different images

**Causes:**
- **Different hardware** (CUDA vs MPS vs CPU) - Not guaranteed deterministic across platforms
- **Different model version** - Ensure same weights
- **PyTorch version differences** - Update to match

**Solutions:**

1. **Use same hardware**
- Deterministic on same GPU/CPU
- Not guaranteed across CUDA ↔ MPS ↔ CPU

2. **Verify model version**
```bash
# Check model commit hash
ls -la ~/.cache/huggingface/hub/models--black-forest-labs--FLUX.1-schnell/
# Should have same snapshots
```

3. **Document environment**
- For critical reproducibility, record: hardware, PyTorch version, model version

## Performance Issues

### Slow image generation

**Benchmarks:**
- NVIDIA RTX 4090: 2-3s per image
- Apple M3 Max: 6-8s per image
- CPU: 60-120s per image

**If slower than expected:**

1. **Verify GPU usage**
```bash
# NVIDIA
nvidia-smi dmon -s u
# Should show high GPU utilization during generation

# Apple Silicon
sudo powermetrics --samplers gpu_power
```

2. **Check thermal throttling**
- GPU may throttle if overheating
- Monitor temps with `nvidia-smi` or `sudo powermetrics`

3. **Close background apps**
- Other GPU workloads reduce performance
- Check with `nvidia-smi` / Activity Monitor

### UI laggy or unresponsive

**Symptoms:**
- Slow transitions
- High CPU usage
- Choppy animations

**Solutions:**

1. **Reduce buffer size**
```toml
[model]
buffer_size = 4  # Less memory, less UI overhead
```

2. **Disable animations**
- (Currently no config for this - planned feature)

3. **Check system resources**
```bash
# Look for memory pressure
top
# or
htop
```

## Testing & Development Issues

### Tests fail

**Symptoms:**
```
FAILED tests/test_buffer.py::test_buffer_cleanup
```

**Solutions:**

1. **Run fast tests only**
```bash
make test  # Excludes slow/integration tests
```

2. **Check test markers**
```bash
# Run specific test
uv run pytest tests/test_buffer.py -v

# Skip slow tests
uv run pytest -m "not slow and not integration"
```

3. **Model required for some tests**
- Tests marked `@pytest.mark.slow` may require model download
- Skip with `make test` (default)

### Build fails

**Symptoms:**
```
cargo build failed
error: could not compile `textbrush`
```

**Solutions:**

1. **Update Rust toolchain**
```bash
rustup update
```

2. **Clean build**
```bash
make clean
cd src-tauri && cargo clean
make build
```

3. **Check Tauri dependencies (Linux)**
```bash
# See Installation Issues above for system deps
```

## Getting Help

If issue persists:

1. **Collect diagnostic info:**
```bash
# System info
uname -a
python --version
cargo --version

# GPU info
nvidia-smi  # or sudo powermetrics

# Textbrush logs
uv run textbrush --prompt "test" --verbose 2>&1 | tee debug.log
```

2. **Open GitHub issue:**
- Repository: https://github.com/941design/textbrush/issues
- Include: diagnostic info, error messages, steps to reproduce
- Redact any sensitive info (tokens, paths)

3. **Check existing issues:**
- Search for similar problems: https://github.com/941design/textbrush/issues
- May already have solution

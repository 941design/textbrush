# GPU Setup Guide

This guide covers GPU configuration for optimal textbrush performance.

## Supported Hardware Backends

Textbrush automatically detects and uses the best available hardware:

1. **CUDA** (NVIDIA GPUs) - Best performance
2. **Apple MPS** (Apple Silicon M1/M2/M3/M4) - Optimized for Mac
3. **CPU** - Fallback for systems without GPU

## NVIDIA GPU Setup (CUDA)

### Requirements

- NVIDIA GPU with CUDA Compute Capability 7.0 or higher
- CUDA 11.8 or later
- cuDNN 8.x
- At least 12GB VRAM (for FLUX.1 schnell)

### Installation

**Linux:**

```bash
# Install CUDA Toolkit
# Visit https://developer.nvidia.com/cuda-downloads
# Follow NVIDIA's official instructions for your distribution

# Verify installation
nvidia-smi
nvcc --version
```

**Verify PyTorch CUDA Support:**

```bash
uv run python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
uv run python -c "import torch; print(f'CUDA version: {torch.version.cuda}')"
```

### Troubleshooting

**CUDA not detected:**
- Verify `nvidia-smi` shows your GPU
- Check PyTorch was installed with CUDA support: `uv run python -c "import torch; print(torch.version.cuda)"`
- Ensure CUDA runtime libraries are in `LD_LIBRARY_PATH`

**Out of memory errors:**
- Close other GPU-intensive applications
- FLUX.1 schnell requires ~12GB VRAM for BFloat16 precision
- Use `--verbose` flag to see memory usage logs

## Apple Silicon Setup (MPS)

### Requirements

- Apple Silicon Mac (M1, M2, M3, M4, or later)
- macOS 12.3 or later
- At least 16GB unified memory recommended

### Verification

```bash
# Check MPS availability
uv run python -c "import torch; print(f'MPS available: {torch.backends.mps.is_available()}')"
```

### Performance Notes

- MPS uses Float32 precision (CUDA uses BFloat16)
- Slightly slower than CUDA but still much faster than CPU
- Memory sharing with system means performance degrades with other apps

### Troubleshooting

**MPS not detected:**
- Ensure macOS is 12.3 or later
- Update PyTorch: `uv sync` (should install latest version)
- Some older PyTorch versions had MPS bugs - ensure you're on latest

**Model loading errors:**
- Ensure at least 16GB unified memory (8GB may work but can cause swapping)
- Close memory-intensive applications before running textbrush

## CPU-Only Setup

### When to Use

- No GPU available
- Testing on systems without CUDA/MPS
- CI/CD environments

### Performance Expectations

- **Much slower** than GPU (10-30x slower)
- Model loading takes several minutes
- Each image generation: 30-120 seconds (vs 2-5 seconds on GPU)

### Verification

```bash
# Force CPU mode for testing
uv run python -c "import torch; print(f'CPU count: {torch.get_num_threads()}')"
```

### Optimization Tips

- Set `OMP_NUM_THREADS` to number of physical cores
- Use `--verbose` to monitor performance
- Consider using smaller buffer size in config (reduces memory)

## Hardware Auto-Detection

Textbrush automatically selects the best backend:

```python
# Priority order:
1. CUDA (if torch.cuda.is_available())
2. Apple MPS (if torch.backends.mps.is_available())
3. CPU (fallback)
```

You can verify which backend was selected with `--verbose`:

```bash
uv run textbrush --prompt "test" --verbose
# Look for: "Using device: cuda" or "Using device: mps" or "Using device: cpu"
```

## Performance Benchmarks

Approximate image generation times (1024x1024, 4 inference steps):

| Hardware | First Image | Subsequent Images |
|----------|-------------|-------------------|
| NVIDIA RTX 4090 | 2-3s | 2-3s |
| NVIDIA RTX 3080 | 4-5s | 4-5s |
| Apple M3 Max | 6-8s | 6-8s |
| Apple M1 | 12-15s | 12-15s |
| CPU (16-core) | 60-120s | 60-120s |

Model loading time: 10-30 seconds (one-time per session)

## Recommended Hardware

**Minimum:**
- Apple M1 or NVIDIA GPU with 8GB VRAM
- 16GB system RAM

**Recommended:**
- Apple M2/M3 or NVIDIA RTX 3080+ with 12GB+ VRAM
- 32GB system RAM

**Optimal:**
- Apple M3/M4 Max or NVIDIA RTX 4080/4090 with 16GB+ VRAM
- 64GB system RAM

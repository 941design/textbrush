"""Utilities for managing model weights in HuggingFace cache.

Models are stored in HuggingFace's global cache (~/.cache/huggingface/hub by default).
The cache location can be customized via HF_HOME or HF_HUB_CACHE environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from huggingface_hub import snapshot_download, try_to_load_from_cache


def _mask_token(token: str | None) -> str:
    """Mask HuggingFace token for safe display in error messages.

    Args:
        token: Token string to mask, or None.

    Returns:
        Masked token string showing first 4 and last 4 characters, or "None".
    """
    if token is None:
        return "None"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


FLUX_SCHNELL_ID: str = "black-forest-labs/FLUX.1-schnell"

# Filter patterns: download only safetensors + config files
ALLOW_PATTERNS: list[str] = [
    "*.json",  # Root-level config (model_index.json)
    "**/*.safetensors",
    "**/*.json",
    "**/tokenizer*",
    "**/*.txt",
    "**/*.md",
    "**/*.model",  # For T5 tokenizer
]

IGNORE_PATTERNS: list[str] = [
    "*.bin",
    "*.onnx",
    "*.onnx_data",
    "*.msgpack",
    "openvino*",
    "*.pb",
    "flax*",
]


class CacheInfo(TypedDict):
    """Information about the HuggingFace cache location."""

    cache_dir: Path
    custom_location: bool
    env_var: str | None


def get_cache_info() -> CacheInfo:
    """Get information about the HuggingFace cache location.

    Returns:
        CacheInfo with cache directory path and whether it's customized.
    """
    # Check for custom cache location
    hf_home = os.environ.get("HF_HOME")
    hf_hub_cache = os.environ.get("HF_HUB_CACHE")

    if hf_hub_cache:
        return CacheInfo(
            cache_dir=Path(hf_hub_cache),
            custom_location=True,
            env_var="HF_HUB_CACHE",
        )
    elif hf_home:
        return CacheInfo(
            cache_dir=Path(hf_home) / "hub",
            custom_location=True,
            env_var="HF_HOME",
        )
    else:
        # Default location
        return CacheInfo(
            cache_dir=Path.home() / ".cache" / "huggingface" / "hub",
            custom_location=False,
            env_var=None,
        )


def is_flux_available() -> bool:
    """Check if FLUX.1 Schnell is available in the HuggingFace cache.

    Uses model_index.json as a marker file since it's required for loading.

    Returns:
        True if the model appears to be cached.
    """
    result = try_to_load_from_cache(
        FLUX_SCHNELL_ID,
        filename="model_index.json",
    )
    return result is not None


def ensure_flux_available() -> None:
    """Ensure FLUX.1 Schnell is available, raising a helpful error if not.

    Raises:
        RuntimeError: If the model is not cached, with instructions to download.
    """
    if not is_flux_available():
        cache_info = get_cache_info()
        raise RuntimeError(
            f"FLUX.1 Schnell model not found in HuggingFace cache.\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"To download the model (~23 GB), run:\n"
            f"  make download-model\n"
            f"\n"
            f"Or with uv:\n"
            f"  uv run python scripts/download_model.py\n"
        )


def download_flux_weights(*, force: bool = False) -> None:
    """Download FLUX.1 Schnell weights to HuggingFace cache.

    Args:
        force: If True, re-download even if already cached.

    Raises:
        RuntimeError: If download fails due to network, auth, or corruption issues.
    """
    if not force and is_flux_available():
        return

    try:
        snapshot_download(
            FLUX_SCHNELL_ID,
            allow_patterns=ALLOW_PATTERNS,
            ignore_patterns=IGNORE_PATTERNS,
            force_download=force,
        )
    except Exception as e:
        cache_info = get_cache_info()
        raise RuntimeError(
            f"Failed to download FLUX.1 Schnell model.\n"
            f"Error: {e}\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"Common issues:\n"
            f"  - Network timeout or connection error\n"
            f"  - Authentication required (set HF_TOKEN environment variable)\n"
            f"  - Insufficient disk space\n"
        ) from e

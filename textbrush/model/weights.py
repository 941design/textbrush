"""Utilities for managing model weights in HuggingFace cache.

Models are stored in HuggingFace's global cache (~/.cache/huggingface/hub by default).
The cache location can be customized via HF_HOME or HF_HUB_CACHE environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TypedDict

from huggingface_hub import snapshot_download, try_to_load_from_cache
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError


class TokenRequiredError(Exception):
    """Raised when a HuggingFace token is required but not available or invalid.

    Triggered when:
    - No HF_TOKEN environment variable is set before attempting a download.
    - The download attempt returns a 401 (Unauthorized) or 403 (Forbidden) response,
      indicating the token is missing, invalid, or the user has not accepted the
      model license.
    """


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


def is_flux_available(custom_dirs: list[Path] | None = None) -> bool:
    """Check if FLUX.1 Schnell is available in custom directories or the HuggingFace cache.

    Checks custom directories first (if provided), then falls back to the
    HuggingFace cache. Uses model_index.json as a marker file since it's
    required for loading.

    Args:
        custom_dirs: Optional list of directories to check before the HuggingFace
            cache. Each directory is checked for a model_index.json marker file.

    Returns:
        True if the model appears to be available.
    """
    if custom_dirs:
        for directory in custom_dirs:
            if Path(directory).is_dir() and (Path(directory) / "model_index.json").exists():
                return True

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
            f"  textbrush --download-model\n"
        )


def download_flux_weights(*, force: bool = False) -> Path:
    """Download FLUX.1 Schnell weights to HuggingFace cache.

    CONTRACT:
        Inputs:
            force: If True, re-download even if already cached.
        Outputs:
            Path: Absolute path to the HuggingFace snapshot directory containing
                  the downloaded model files.
        Invariants:
            - HF_TOKEN is only required when actually downloading (not for cached reads).
        Algorithm:
            1. If already cached and not force: return cached snapshot path (no token needed).
            2. Guard against missing token (check HF_TOKEN env var).
            3. Call snapshot_download(); return Path to snapshot directory.
            4. On auth/gated-repo errors, raise TokenRequiredError.
            5. On all other errors, raise RuntimeError with actionable message.

    Args:
        force: If True, re-download even if already cached.

    Returns:
        Path to the HuggingFace snapshot directory for the downloaded model.

    Raises:
        TokenRequiredError: If HF_TOKEN is not set, or if the download returns
            a 401/403 auth error (token invalid or license not accepted).
        RuntimeError: If download fails for other reasons (network, disk space, etc.).
    """
    if not force and is_flux_available():
        # Model already cached — no token needed; locate and return its snapshot directory.
        cache_info = get_cache_info()
        hub_cache = cache_info["cache_dir"]
        model_dir = hub_cache / f"models--{FLUX_SCHNELL_ID.replace('/', '--')}"
        snapshots_dir = model_dir / "snapshots"
        if snapshots_dir.is_dir():
            snapshots = sorted(snapshots_dir.iterdir())
            if snapshots:
                return snapshots[-1]
        return hub_cache

    if not os.environ.get("HF_TOKEN"):
        raise TokenRequiredError(
            "HF_TOKEN environment variable is not set. "
            "A valid HuggingFace token is required to download model weights."
        )

    try:
        snapshot_path = snapshot_download(
            FLUX_SCHNELL_ID,
            allow_patterns=ALLOW_PATTERNS,
            ignore_patterns=IGNORE_PATTERNS,
            force_download=force,
        )
        return Path(snapshot_path)
    except (GatedRepoError, RepositoryNotFoundError) as e:
        raise TokenRequiredError(
            f"Access denied when downloading {FLUX_SCHNELL_ID}. "
            "Ensure your HF_TOKEN is valid and you have accepted the model license at "
            "https://huggingface.co/black-forest-labs/FLUX.1-schnell"
        ) from e
    except HfHubHTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            raise TokenRequiredError(
                f"Authentication failed when downloading {FLUX_SCHNELL_ID} "
                f"(HTTP {e.response.status_code}). "
                "Ensure your HF_TOKEN is valid and you have accepted the model license at "
                "https://huggingface.co/black-forest-labs/FLUX.1-schnell"
            ) from e
        cache_info = get_cache_info()
        raise RuntimeError(
            f"Failed to download FLUX.1 Schnell model.\n"
            f"Error: {e}\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"Common issues:\n"
            f"  - Network timeout or connection error\n"
            f"  - Insufficient disk space\n"
        ) from e
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "403" in error_msg:
            raise TokenRequiredError(
                f"Authentication failed when downloading {FLUX_SCHNELL_ID}. "
                "Ensure your HF_TOKEN is valid and you have accepted "
                "the model license at "
                "https://huggingface.co/black-forest-labs/FLUX.1-schnell"
            ) from e
        cache_info = get_cache_info()
        raise RuntimeError(
            f"Failed to download FLUX.1 Schnell model.\n"
            f"Error: {e}\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"Common issues:\n"
            f"  - Network timeout or connection error\n"
            f"  - Insufficient disk space\n"
        ) from e

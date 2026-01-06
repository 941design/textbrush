#!/usr/bin/env python3
"""Download FLUX.1 Schnell model weights to HuggingFace cache.

This script downloads the FLUX.1 Schnell model (~23 GB) to the HuggingFace
cache directory. The download location can be customized via HF_HOME or
HF_HUB_CACHE environment variables.

Requires HUGGINGFACE_HUB_TOKEN environment variable for authentication.
"""

import sys

from textbrush.model.weights import download_flux_weights, get_cache_info


def main() -> None:
    """Download FLUX.1 Schnell model weights."""
    cache_info = get_cache_info()

    print("=== Textbrush Model Download ===")
    print()
    print("Downloading FLUX.1 Schnell model...")
    print(f"Cache location: {cache_info['cache_dir']}")
    if cache_info['custom_location']:
        print(f"(customized via {cache_info['env_var']})")
    print()
    print("This will download approximately 23 GB of model weights.")
    print()

    try:
        download_flux_weights()
        print()
        print("✓ Download complete!")
        print()
        print("The model is now cached and ready to use.")
    except Exception as e:
        print(f"✗ Download failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Download a registered model's weights to the HuggingFace cache.

Downloads any slug in `textbrush.model.registry.MODEL_REGISTRY`, defaulting
to FLUX.1 schnell. The download location can be customized via HF_HOME or
HF_HUB_CACHE environment variables.

Gated models (FLUX.1 schnell, FLUX.1 Kontext-dev) require the
HUGGINGFACE_HUB_TOKEN environment variable and an accepted license;
ungated ones (FLUX.2 klein-4B) download anonymously.
"""

import argparse
import sys

from textbrush.model.registry import FLUX1_SCHNELL, get_model_spec, iter_model_slugs
from textbrush.model.weights import download_model_weights, get_cache_info


def main() -> None:
    """Download one registered model's weights."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "model",
        nargs="?",
        default=FLUX1_SCHNELL,
        choices=list(iter_model_slugs()),
        help=f"Registry slug to download (default: {FLUX1_SCHNELL})",
    )
    args = parser.parse_args()

    spec = get_model_spec(args.model)
    cache_info = get_cache_info()

    print("=== Textbrush Model Download ===")
    print()
    print(f"Downloading {spec.display_name} ({spec.repo_id})...")
    print(f"Cache location: {cache_info['cache_dir']}")
    if cache_info["custom_location"]:
        print(f"(customized via {cache_info['env_var']})")
    print()
    if spec.gated:
        print("This model is gated: a HuggingFace token and an accepted license are required.")
        if spec.license_url:
            print(f"License: {spec.license_url}")
        print()

    try:
        download_model_weights(spec.slug)
        print()
        print("✓ Download complete!")
        print()
        print("The model is now cached and ready to use.")
    except Exception as e:
        print(f"✗ Download failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

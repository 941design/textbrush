"""Command line interface for textbrush image generation."""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import List

from .config import Config, load_config
from .model.registry import FLUX1_SCHNELL, FLUX2_KLEIN_4B, iter_model_slugs, resolve_model_selection
from .model.weights import check_model_availability
from .paths import CONFIG_PATH
from .references import (
    SUPPORTED_EXTENSIONS,
)
from .validation import (
    EDITING_PRESETS,
    validate_selection,
)

# Supported aspect ratios with their available resolutions (smallest to largest)
# Each ratio maps to a list of (width, height) tuples
# The one output-size table: every ratio, with its resolution ladder from
# smallest to largest. Ordering and key set mirror
# `validation.TEXT_ASPECT_RATIOS` and the desktop UI's
# ASPECT_RATIO_RESOLUTIONS (src-tauri/ui/config_controls.ts); the 4:3 and
# 3:4 ladders are, entry for entry, the dimensions
# `validation.EDITING_PRESETS` names landscape-small/medium/large and
# portrait-small/medium/large. Every model is offered every entry --
# there is no separate editing size vocabulary any more.
#
# Declaration order is height/width ascending: widest (4:1, h/w 0.25)
# through square (1:1, 1.0) to tallest (9:16, 1.78). It is the order the
# desktop UI renders the group in, so the list reads as one continuous
# progression of shapes rather than as an arbitrary sequence. Keep any
# new ratio in its place in that progression.
SUPPORTED_RATIOS: dict[str, list[tuple[int, int]]] = {
    "4:1": [(1200, 300), (1600, 400)],
    "3:1": [(900, 300), (1500, 500), (1800, 600)],
    "16:9": [(640, 360), (1280, 720), (1920, 1080)],
    "4:3": [(512, 384), (768, 576), (1024, 768)],
    "1:1": [(256, 256), (512, 512), (1024, 1024)],
    "4:5": [(540, 675), (1080, 1350)],
    "3:4": [(384, 512), (576, 768), (768, 1024)],
    "9:16": [(360, 640), (1080, 1920)],
}


def get_default_resolution(aspect_ratio: str) -> tuple[int, int]:
    """Get the default (first/smallest) resolution for an aspect ratio."""
    if aspect_ratio not in SUPPORTED_RATIOS:
        raise ValueError(f"Unsupported aspect ratio: {aspect_ratio}")
    return SUPPORTED_RATIOS[aspect_ratio][0]


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for textbrush CLI.

    CONTRACT:
      Inputs: none

      Outputs:
        - argparse.ArgumentParser configured with all textbrush CLI options

      Invariants:
        - Optional arguments:
          · --prompt (type: str, default: None) — mutually exclusive with --download-model
          · --download-model (optional registry slug, default: None; bare use
            means flux1-schnell) — mutually exclusive with --prompt/--headless
          · --out (type: Path)
          · --config (type: Path, default: None)
          · --seed (type: int)
          · --aspect-ratio (choices: SUPPORTED_RATIOS.keys())
          · --format (choices: ["png", "jpg"])
          · --verbose (flag, default: False)
          · --headless (flag, default: False)
          · --auto-accept (flag, default: False)
          · --auto-abort (flag, default: False)
          · --check-updates (flag, default: False)
        - Description includes program purpose
        - Help text is user-friendly
        - Mutual exclusivity enforced in main() via parser.error()

      Properties:
        - Completeness: parser accepts all arguments from spec FR2
        - Type safety: arguments have appropriate types
        - Validation: choices are enforced for aspect-ratio and format
        - Identity: build_parser() always returns parser with same configuration

      Algorithm:
        1. Create ArgumentParser with program description
        2. Add optional argument: --prompt (required=False, default=None)
        3. Add --download-model (nargs="?", const=flux1-schnell)
        4. Add optional arguments with types and defaults:
           - --out as Path
           - --config as Path
           - --seed as int
           - --aspect-ratio with choices validation
           - --format with choices validation
           - --verbose as store_true flag
           - --headless as store_true flag
           - --auto-accept as store_true flag
           - --auto-abort as store_true flag
        5. Return configured parser
    """
    parser = argparse.ArgumentParser(
        prog="textbrush",
        description="Generate images from text prompts using local models",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        required=False,
        default=None,
        metavar="TEXT",
        help="Text prompt for image generation",
    )

    parser.add_argument(
        "--download-model",
        nargs="?",
        const=FLUX1_SCHNELL,
        default=None,
        metavar="MODEL",
        help=(
            "Download a model's weights and exit. Accepts a registry slug "
            f"({', '.join(iter_model_slugs())}); defaults to {FLUX1_SCHNELL} "
            "when given without a value."
        ),
    )

    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output file path for generated image",
    )

    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to TOML configuration file",
    )

    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )

    parser.add_argument(
        "--aspect-ratio",
        choices=list(SUPPORTED_RATIOS.keys()),
        default=None,
        help=f"Image aspect ratio (choices: {', '.join(SUPPORTED_RATIOS.keys())})",
    )
    parser.add_argument(
        "--model",
        choices=list(iter_model_slugs()),
        default=None,
        help="Local model: flux1-schnell, flux1-kontext-dev, or flux2-klein-4b",
    )
    parser.add_argument(
        "--reference",
        action="append",
        type=Path,
        default=[],
        metavar="PATH",
        help="Reference image (repeat up to four times; order is preserved)",
    )
    parser.add_argument(
        "--preset", choices=list(EDITING_PRESETS), default=None, help="Editing output preset"
    )

    parser.add_argument(
        "--format",
        choices=["png", "jpg"],
        default=None,
        help="Output image format",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable debug logging",
    )

    parser.add_argument(
        "--headless",
        action="store_true",
        default=False,
        help="Run without UI — generates one image and saves it (use --auto-abort to skip saving)",
    )

    parser.add_argument(
        "--auto-accept",
        action="store_true",
        default=False,
        help="Accept first image automatically (requires --headless)",
    )

    parser.add_argument(
        "--auto-abort",
        action="store_true",
        default=False,
        help="Abort immediately after starting (requires --headless)",
    )

    parser.add_argument(
        "--check-updates",
        action="store_true",
        default=False,
        help="Check for newer textbrush releases",
    )

    return parser


def merge_cli_args_with_config(args: argparse.Namespace, config: Config) -> Config:
    """Merge CLI arguments into configuration, giving CLI args highest priority.

    CONTRACT:
      Inputs:
        - args: parsed CLI arguments from build_parser()
        - config: base configuration from config file + env vars

      Outputs:
        - new Config object with CLI argument overrides applied

      Invariants:
        - Original config is not mutated (return new instance)
        - Only non-None CLI arguments override config values
        - CLI argument names map to config fields:
          · args.out → config.output.directory (parent directory)
          · args.format → config.output.format
          · args.verbose → config.logging.verbosity ("debug" if True, unchanged if False)
          · args.config is not merged (only used for loading)

      Properties:
        - Immutability: original config unchanged
        - Selective override: only provided CLI args override config
        - Priority: CLI args have highest priority
        - Type conversion: args values converted to config types

      Algorithm:
        1. Create copy of input config
        2. For each CLI argument that maps to a config field:
           a. If argument value is not None:
              i. Convert to appropriate config type if needed
              ii. Update corresponding field in config copy
        3. Special handling:
           - args.verbose=True → config.logging.verbosity = "debug"
           - args.out → config.output.directory (if provided)
           - args.format → config.output.format (if provided)
        4. Return modified config copy
    """
    merged_config = deepcopy(config)

    if args.out is not None:
        merged_config.output.directory = args.out.parent

    if args.format is not None:
        merged_config.output.format = args.format

    if args.verbose:
        merged_config.logging.verbosity = "debug"

    return merged_config


def validate_args(args: argparse.Namespace) -> None:
    """Validate parsed CLI arguments for semantic correctness.

    CONTRACT:
      Inputs:
        - args: parsed CLI arguments from build_parser()

      Outputs:
        - None (raises exception if validation fails)

      Invariants:
        - args.prompt must not be empty string
        - If args.seed provided, must be non-negative integer
        - If args.out provided, parent directory must exist or be creatable
        - If args.config provided, file must exist or parent directory must be writable
        - Paths are normalized to prevent traversal attacks

      Properties:
        - Error messages: validation failures raise ValueError with clear message
        - Completeness: all semantic validations performed
        - Order independence: validation order doesn't affect result
        - Security: path traversal attempts are rejected

      Algorithm:
        1. Check args.prompt is not empty string
        2. If args.seed provided, verify it's >= 0
        3. If args.out provided:
           a. Normalize and resolve path
           b. Check parent directory exists
           c. If not, check if it can be created (permissions)
        4. If args.config provided:
           a. Normalize and resolve path
           b. If file exists, verify it's readable
           c. If not, verify parent directory is writable for creation
        5. Raise ValueError with descriptive message on first failure
    """
    if args.prompt is not None and args.prompt.strip() == "":
        raise ValueError("--prompt cannot be empty")

    if args.seed is not None and args.seed < 0:
        raise ValueError("--seed must be non-negative")

    references = getattr(args, "reference", [])
    preset = getattr(args, "preset", None)
    # When no model was explicitly selected, the launch resolver chooses
    # FLUX.2 for references. Validate that prospective mode here so errors
    # still precede backend construction.
    model_id = getattr(args, "model", None) or (FLUX2_KLEIN_4B if references else FLUX1_SCHNELL)
    verdict = validate_selection(model_id, len(references), preset, args.aspect_ratio)
    if not verdict.valid:
        raise ValueError(verdict.reason)
    # T08: do NOT decode here. Validate only that each --reference
    # path exists, is a file, and has a supported extension (case-
    # insensitive). Decode lives in the backend's apply_configuration
    # so the decoded data outlives exactly one acknowledged
    # configuration (AC-PROCESS-3).
    for path in references:
        p = Path(path)
        if not p.exists():
            raise ValueError(f"--reference file does not exist: {path}")
        if not p.is_file():
            raise ValueError(f"--reference is not a regular file: {path}")
        if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"--reference has unsupported extension: {path} "
                f"(supported: {sorted(SUPPORTED_EXTENSIONS)})"
            )

    if args.out is not None:
        # Normalize path to prevent traversal attacks
        try:
            normalized_out = args.out.expanduser().resolve()
            args.out = normalized_out
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid output path '{args.out}': {e}") from e

        parent = args.out.parent
        if not parent.exists():
            try:
                parent.mkdir(parents=True, exist_ok=True)
                parent.rmdir()
            except (OSError, PermissionError) as e:
                raise ValueError(f"Output directory '{parent}' cannot be created: {e}") from e

    if args.config is not None:
        # Normalize path to prevent traversal attacks
        try:
            config_path = args.config.expanduser().resolve()
            args.config = config_path
        except (OSError, RuntimeError) as e:
            raise ValueError(f"Invalid config path '{args.config}': {e}") from e

        if config_path.exists():
            if not config_path.is_file():
                raise ValueError(f"Config path '{config_path}' is not a file")
            if not config_path.stat().st_mode & 0o400:
                raise ValueError(f"Config file '{config_path}' is not readable")
        else:
            config_dir = config_path.parent
            if config_dir.exists() and not config_dir.is_dir():
                raise ValueError(f"Config parent '{config_dir}' exists but is not a directory")
            if not config_dir.exists():
                try:
                    config_dir.mkdir(parents=True, exist_ok=True)
                    config_dir.rmdir()
                except (OSError, PermissionError) as e:
                    raise ValueError(
                        f"Config directory '{config_dir}' cannot be created: {e}"
                    ) from e


def _wait_for_image(backend) -> None:
    """Wait for slow inference without replacing its terminal error with a timeout."""
    import time

    while True:
        error = backend.check_worker_error()
        if error is not None:
            raise error
        if backend.buffer.peek() is not None:
            return
        time.sleep(0.1)


def main(argv: List[str] | None = None) -> None:
    """Dispatch downloads/updates, native desktop review, or headless generation.

    Desktop stdout and exit status belong to the native process. Only headless
    generation constructs a backend here; the desktop sidecar owns its model.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)

        # Mutual exclusivity checks — these use parser.error() to produce exit code 2
        if args.check_updates and args.prompt:
            parser.error("Cannot use --check-updates with --prompt")
        if args.check_updates and args.download_model:
            parser.error("Cannot use --check-updates with --download-model")
        if args.check_updates and args.headless:
            parser.error("Cannot use --check-updates with --headless")
        if args.download_model and args.prompt:
            parser.error("Cannot use --download-model with --prompt")
        if args.download_model and args.headless:
            parser.error("Cannot use --download-model with --headless")
        if not args.check_updates and not args.download_model and args.prompt is None:
            parser.error("one of --prompt or --download-model is required")

        # Update check dispatch — early exit before normal generation flow
        if args.check_updates:
            from .updates import check_for_updates

            check_for_updates(verbose=args.verbose)
            # check_for_updates() calls sys.exit(0), so this line is unreachable
            return

        # Download model dispatch — early exit before normal generation flow
        if args.download_model:
            from .model.registry import get_model_spec
            from .model.weights import TokenRequiredError, download_model_weights

            # The slug is validated here rather than via argparse `choices`
            # so the error names the flag's own vocabulary; `nargs="?"`
            # would otherwise reject a bare --download-model against choices.
            if args.download_model not in iter_model_slugs():
                parser.error(
                    f"unknown model {args.download_model!r} for --download-model; "
                    f"choose from {', '.join(iter_model_slugs())}"
                )
            spec = get_model_spec(args.download_model)

            config_path = args.config if args.config is not None else CONFIG_PATH
            config = load_config(config_path)

            # Resolve token: HF_TOKEN env var takes precedence, then config
            token = os.environ.get("HF_TOKEN") or config.huggingface.token
            if token and not os.environ.get("HF_TOKEN"):
                os.environ["HF_TOKEN"] = token

            if spec.license_url:
                print(
                    f"{spec.display_name} is distributed under its own license.\n"
                    f"Review the license before use: {spec.license_url}",
                    file=sys.stderr,
                )
            print(f"Downloading {spec.display_name}...", file=sys.stderr)

            try:
                model_path = download_model_weights(spec.slug)
                print(f"Model downloaded successfully to: {model_path}", file=sys.stderr)
                sys.exit(0)
            except TokenRequiredError:
                print(
                    f"HuggingFace token required to download {spec.display_name}.\n"
                    "Set your token with:\n"
                    "  export HF_TOKEN=<your_token>\n"
                    "Or add to config file "
                    "(~/.config/textbrush/config.toml):\n"
                    "  [huggingface]\n"
                    '  token = "hf_xxxxxxxxxxxxx"\n'
                    "Get a token at: "
                    "https://huggingface.co/settings/tokens\n"
                    "Then accept the model license at: "
                    f"{spec.license_url}",
                    file=sys.stderr,
                )
                sys.exit(1)
            except Exception as e:
                print(f"Download failed: {e}", file=sys.stderr)
                sys.exit(1)

        if (args.auto_accept or args.auto_abort) and not args.headless:
            parser.error("--auto-accept and --auto-abort require --headless")
        if args.preset and args.aspect_ratio:
            parser.error("--preset cannot be combined with --aspect-ratio")

        validate_args(args)

        config_path = args.config if args.config is not None else CONFIG_PATH
        config = load_config(config_path)
        config = merge_cli_args_with_config(args, config)
        if not args.headless:
            from .desktop import run_desktop

            run_desktop(args, config, config_path)
            return

        references_paths = [str(p) for p in args.reference]
        preset = args.preset

        # AC-MODEL-5b: run the model resolver exactly once at launch
        # (T08 step 2). A blocked resolution prints the discovery reason
        # and the download hint (when a specific model is required) and
        # exits with code 1 -- no model is loaded.
        def availability(slug):
            return check_model_availability(slug, custom_dirs=config.model.directories)

        try:
            resolution = resolve_model_selection(
                selected_id=args.model or config.model.selected_id,
                reference_count=len(references_paths),
                availability=availability,
            )
        except ValueError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

        if resolution.blocked:
            print(
                f"Error: {resolution.reason}",
                file=sys.stderr,
            )
            if resolution.required_model:
                print(
                    f"Run: textbrush --download-model {resolution.required_model}",
                    file=sys.stderr,
                )
            sys.exit(1)

        config.model.selected_id = resolution.model_id
        selected_model = resolution.model_id

        # Dispatch to headless mode if flag is set
        if args.headless:
            run_headless(
                prompt=args.prompt,
                out=args.out,
                config=config,
                seed=args.seed,
                aspect_ratio=args.aspect_ratio if args.aspect_ratio else "custom",
                auto_accept=args.auto_accept,
                auto_abort=args.auto_abort,
                reference_paths=references_paths,
                model_id=selected_model,
                preset=preset,
            )
            # run_headless() calls sys.exit(), so this line is unreachable
            return

    except (ValueError, SystemExit) as e:
        if isinstance(e, SystemExit):
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def run_headless(
    prompt: str,
    out: Path | None,
    config: Config,
    seed: int | None,
    aspect_ratio: str,
    auto_accept: bool,
    auto_abort: bool,
    reference_paths: list[str] | tuple[str, ...] = (),
    model_id: str = FLUX1_SCHNELL,
    preset: str | None = None,
) -> None:
    """Generate and save one image without the desktop.

    Acknowledge the launch canvas and references before starting the worker.
    Wait without an arbitrary inference deadline, surfacing worker errors.
    Success prints one output path and exits 0; auto-abort exits 1 without output.
    Shutdown settles inference before unloading the engine.
    """
    from .backend import TextbrushBackend

    backend = None

    try:
        backend = TextbrushBackend(config)

        print("Loading model...", file=sys.stderr)
        backend.initialize()

        # Resolve one launch canvas for every model, matching the desktop's
        # smallest ratio rung. Acknowledge it before decoding references, then
        # pass the identical dimensions to generation.
        if preset is not None:
            if aspect_ratio not in ("custom", None):
                raise ValueError("--preset cannot be combined with --aspect-ratio")
            width, height = EDITING_PRESETS[preset]
            aspect_ratio = "4:3" if width > height else "3:4"
        else:
            aspect_ratio = "1:1" if aspect_ratio in ("custom", None) else aspect_ratio
            width, height = get_default_resolution(aspect_ratio)
        ack = backend.apply_configuration(
            model_id=model_id,
            reference_paths=list(reference_paths),
            preset=preset,
            width=width,
            height=height,
        )
        if not ack.compatible:
            raise ValueError(ack.incompatibility_reason)

        backend.start_generation(
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
            width=width,
            height=height,
        )

        if auto_abort:
            backend.abort()
            backend.shutdown()
            sys.exit(1)

        print("Generating...", file=sys.stderr)

        _wait_for_image(backend)

        output_path = backend.accept_current(out)
        print(str(output_path.absolute()), file=sys.stdout)
        backend.shutdown()
        sys.exit(0)

    except (ValueError, RuntimeError) as e:
        print(f"Error: {e}", file=sys.stderr)
        if backend is not None:
            backend.shutdown()
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if backend is not None:
            backend.shutdown()
        sys.exit(1)

"""Command line interface for textbrush image generation."""

from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path
from typing import List

from .config import Config, load_config
from .paths import CONFIG_PATH

# Supported aspect ratios with their available resolutions (smallest to largest)
# Each ratio maps to a list of (width, height) tuples
SUPPORTED_RATIOS: dict[str, list[tuple[int, int]]] = {
    "1:1": [(256, 256), (512, 512), (1024, 1024)],
    "16:9": [(640, 360), (1280, 720), (1920, 1080)],
    "3:1": [(900, 300), (1500, 500), (1800, 600)],
    "4:1": [(1200, 300), (1600, 400)],
    "4:5": [(540, 675), (1080, 1350)],
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
          · --download-model (flag, default: False) — mutually exclusive with --prompt/--headless
          · --out (type: Path)
          · --config (type: Path, default: None)
          · --seed (type: int)
          · --aspect-ratio (choices: SUPPORTED_RATIOS.keys())
          · --format (choices: ["png", "jpg"])
          · --verbose (flag, default: False)
          · --headless (flag, default: False)
          · --auto-accept (flag, default: False)
          · --auto-abort (flag, default: False)
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
        3. Add --download-model flag (action=store_true)
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
        action="store_true",
        default=False,
        help="Download FLUX.1 schnell model weights (~23 GB) and exit",
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


def main(argv: List[str] | None = None) -> None:
    """Main entry point for textbrush CLI.

    CONTRACT:
      Inputs:
        - argv: command-line arguments (default: None uses sys.argv)
          Example: ["--prompt", "a cat", "--seed", "42"]

      Outputs:
        - None (side effects: print to stdout, sys.exit with code)

      Invariants:
        - Exit code 0 + stdout path on success (generation)
        - Exit code 0 + stderr path on success (--download-model)
        - Exit code 1 + empty stdout on failure
        - Exit code 2 on argument conflict (parser.error())
        - Either --prompt or --download-model must be given (not both, not neither)
        - Progress messages go to stderr
        - Final output path goes to stdout (generation) or stderr (download)
        - backend.shutdown() always called (even on error, generation path only)
        - If --headless flag set, delegates to run_headless()

      Properties:
        - Configuration priority: CLI args > env vars > config file > defaults
        - Error handling: user-facing error messages on stderr
        - Output: success prints path to stdout (gen) or stderr (download)
        - Cleanup: backend shutdown guaranteed via finally block
        - Mode selection: download vs headless vs GUI based on flags

      Algorithm:
        1. Build argument parser via build_parser()
        2. Parse arguments from argv (or sys.argv if None)
        3. Mutual exclusivity checks (parser.error() → exit 2):
           a. --download-model + --prompt → error
           b. --download-model + --headless → error
           c. neither --download-model nor --prompt → error
        4. If --download-model:
           a. Print license notice URL to stderr
           b. Print "Downloading FLUX.1 schnell model (~23 GB)..." to stderr
           c. Load config, resolve token (HF_TOKEN env var, then config.huggingface.token)
           d. Set HF_TOKEN in env if resolved from config
           e. Call download_flux_weights()
           f. On TokenRequiredError: print instructions (HF_TOKEN, token URL) → exit 1
           g. On other Exception: print "Download failed: ..." → exit 1
           h. On success: print "Model downloaded successfully to: <path>" → exit 0
        5. Determine config file path and load configuration
        6. Validate arguments via validate_args()
        7. If --headless flag is set:
           a. Delegate to run_headless() with all parameters
           b. run_headless() handles everything including exit
        8. Otherwise (GUI mode):
           a. Create TextbrushBackend with config
           b. Initialize backend (load model, print "Loading model..." to stderr)
           c. Start generation with prompt, seed, aspect_ratio
           d. Print "Generating..." to stderr
           e. Get next image from buffer (blocks until ready)
           f. Determine output path (use args.out or generate automatically)
           g. Accept and save current image
           h. Print output path to stdout
           i. Shutdown backend in finally block
           j. Exit with code 0 on success
        9. Error handling:
           - Catch exceptions and print to stderr
           - Call backend.shutdown() in finally
           - Exit with code 1 on any error
           - Never print to stdout on error
    """
    from .backend import TextbrushBackend

    parser = build_parser()
    backend = None

    try:
        args = parser.parse_args(argv)

        # Mutual exclusivity checks — these use parser.error() to produce exit code 2
        if args.download_model and args.prompt:
            parser.error("Cannot use --download-model with --prompt")
        if args.download_model and args.headless:
            parser.error("Cannot use --download-model with --headless")
        if not args.download_model and args.prompt is None:
            parser.error("one of --prompt or --download-model is required")

        # Download model dispatch — early exit before normal generation flow
        if args.download_model:
            from .model.weights import TokenRequiredError, download_flux_weights

            config_path = args.config if args.config is not None else CONFIG_PATH
            config = load_config(config_path)

            # Resolve token: HF_TOKEN env var takes precedence, then config
            token = os.environ.get("HF_TOKEN") or config.huggingface.token
            if token and not os.environ.get("HF_TOKEN"):
                os.environ["HF_TOKEN"] = token

            print(
                "FLUX.1 schnell is available under the FLUX.1 [schnell] Non-Commercial License.\n"
                "Review the license before use: "
                "https://huggingface.co/black-forest-labs/FLUX.1-schnell",
                file=sys.stderr,
            )
            print("Downloading FLUX.1 schnell model (~23 GB)...", file=sys.stderr)

            try:
                model_path = download_flux_weights()
                print(f"Model downloaded successfully to: {model_path}", file=sys.stderr)
                sys.exit(0)
            except TokenRequiredError:
                print(
                    "HuggingFace token required to download FLUX.1 schnell.\n"
                    "Set your token with:\n"
                    "  export HF_TOKEN=<your_token>\n"
                    "Or add to config file "
                    "(~/.config/textbrush/config.toml):\n"
                    "  [huggingface]\n"
                    '  token = "hf_xxxxxxxxxxxxx"\n'
                    "Get a token at: "
                    "https://huggingface.co/settings/tokens\n"
                    "Then accept the model license at: "
                    "https://huggingface.co/black-forest-labs/FLUX.1-schnell",
                    file=sys.stderr,
                )
                sys.exit(1)
            except Exception as e:
                print(f"Download failed: {e}", file=sys.stderr)
                sys.exit(1)

        validate_args(args)

        config_path = args.config if args.config is not None else CONFIG_PATH
        config = load_config(config_path)
        config = merge_cli_args_with_config(args, config)

        # Dispatch to headless mode if flag is set
        if args.headless:
            run_headless(
                prompt=args.prompt,
                out=args.out,
                config=config,
                seed=args.seed,
                aspect_ratio=args.aspect_ratio if args.aspect_ratio else "1:1",
                auto_accept=args.auto_accept,
                auto_abort=args.auto_abort,
            )
            # run_headless() calls sys.exit(), so this line is unreachable
            return

        backend = TextbrushBackend(config)

        print("Loading model...", file=sys.stderr)
        backend.initialize()

        print("Generating...", file=sys.stderr)
        backend.start_generation(
            prompt=args.prompt,
            seed=args.seed,
            aspect_ratio=args.aspect_ratio if args.aspect_ratio else "1:1",
        )

        import time

        timeout = 30.0
        start_time = time.time()
        while time.time() - start_time < timeout:
            if backend.buffer.peek() is not None:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("No image generated within timeout")

        if args.out is not None:
            output_path = backend.accept_current(args.out)
        else:
            output_path = backend.accept_current()

        print(str(output_path), file=sys.stdout)

        sys.exit(0)

    except (ValueError, SystemExit) as e:
        if isinstance(e, SystemExit):
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if backend is not None:
            backend.shutdown()


def run_headless(
    prompt: str,
    out: Path | None,
    config: Config,
    seed: int | None,
    aspect_ratio: str,
    auto_accept: bool,
    auto_abort: bool,
) -> None:
    """Run textbrush in headless mode without GUI (for CI/testing).

    CONTRACT:
      Inputs:
        - prompt: non-empty string, text description for image generation
        - out: optional Path for output file (None = auto-generate)
        - config: Config object with all settings
        - seed: optional integer seed for reproducibility (None = random)
        - aspect_ratio: string, one of "1:1", "16:9", "9:16"
        - auto_accept: boolean, if True accept first generated image
        - auto_abort: boolean, if True abort immediately after starting

      Outputs:
        - None (side effects: print to stdout/stderr, sys.exit with code)

      Invariants:
        - Exit code 0 + stdout path if image saved successfully (auto_accept or neither flag)
        - Exit code 1 + empty stdout if auto_abort or any error
        - auto_abort takes precedence over auto_accept
        - Progress messages go to stderr
        - Final output path goes to stdout (only on accept)
        - Backend shutdown guaranteed

      Properties:
        - Deterministic: same inputs produce same behavior
        - Non-interactive: no UI launched
        - Exit code contract: 0 on accept, 1 on abort/error
        - Cleanup: backend always shut down

      Algorithm:
        1. Create TextbrushBackend with config
        2. Print "Loading model..." to stderr
        3. Initialize backend (load model)
        4. Start generation with prompt, seed, aspect_ratio
        5. If auto_abort:
           a. Call backend.abort()
           b. Shutdown backend
           c. Exit with code 1 (no stdout)
        6. Otherwise (auto_accept or neither flag): generate-and-save
           a. Print "Generating..." to stderr
           b. Wait for first image (timeout 120s):
              - Poll buffer.peek() with 0.1s sleep intervals
              - If timeout: raise RuntimeError
           c. If image available:
              i. Determine output path (use 'out' or generate)
              ii. Call backend.accept_current(output_path)
              iii. Print absolute path to stdout
              iv. Shutdown backend
              v. Exit with code 0
           d. If no image: exit with code 1
        7. Error handling:
           a. Catch exceptions and print to stderr
           b. Shutdown backend in finally block
           c. Exit with code 1
           d. Never print to stdout on error

    IMPLEMENTATION NOTE:
      This function bypasses the Tauri GUI entirely. It uses the backend
      directly for pure CLI-based generation, suitable for CI pipelines
      and automated testing.
    """
    import time

    from .backend import TextbrushBackend

    backend = None

    try:
        backend = TextbrushBackend(config)

        print("Loading model...", file=sys.stderr)
        backend.initialize()

        backend.start_generation(
            prompt=prompt,
            seed=seed,
            aspect_ratio=aspect_ratio,
        )

        if auto_abort:
            backend.abort()
            backend.shutdown()
            sys.exit(1)

        print("Generating...", file=sys.stderr)

        timeout_seconds = 120.0
        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            if backend.buffer.peek() is not None:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("No image generated within 120 second timeout")

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

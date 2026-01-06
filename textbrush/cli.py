"""Command line interface for textbrush image generation."""

from __future__ import annotations

import argparse
import sys
from copy import deepcopy
from pathlib import Path
from typing import List

from .config import Config, load_config
from .paths import CONFIG_PATH


def build_parser() -> argparse.ArgumentParser:
    """Build argument parser for textbrush CLI.

    CONTRACT:
      Inputs: none

      Outputs:
        - argparse.ArgumentParser configured with all textbrush CLI options

      Invariants:
        - Required argument: --prompt (type: str)
        - Optional arguments:
          · --out (type: Path)
          · --config (type: Path, default: None)
          · --seed (type: int)
          · --aspect-ratio (choices: ["1:1", "16:9", "9:16"])
          · --format (choices: ["png", "jpg"])
          · --verbose (flag, default: False)
        - Description includes program purpose
        - Help text is user-friendly

      Properties:
        - Completeness: parser accepts all arguments from spec FR2
        - Type safety: arguments have appropriate types
        - Validation: choices are enforced for aspect-ratio and format
        - Identity: build_parser() always returns parser with same configuration

      Algorithm:
        1. Create ArgumentParser with program description
        2. Add required argument: --prompt (required=True)
        3. Add optional arguments with types and defaults:
           - --out as Path
           - --config as Path
           - --seed as int
           - --aspect-ratio with choices validation
           - --format with choices validation
           - --verbose as store_true flag
        4. Return configured parser
    """
    parser = argparse.ArgumentParser(
        prog="textbrush",
        description="Generate images from text prompts using local models",
    )

    parser.add_argument(
        "--prompt",
        type=str,
        required=True,
        metavar="TEXT",
        help="Text prompt for image generation",
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
        choices=["1:1", "16:9", "9:16"],
        default=None,
        help="Image aspect ratio",
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
    if not args.prompt or args.prompt.strip() == "":
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
        - Exit code 0 + stdout path on success (per spec 9.1)
        - Exit code non-zero + empty stdout on failure
        - Prompt is required (validation failure if missing)

      Properties:
        - Configuration priority: CLI args > env vars > config file > defaults
        - Error handling: user-facing error messages on stderr
        - Output: success prints path to stdout, nothing else

      Algorithm:
        1. Build argument parser via build_parser()
        2. Parse arguments from argv (or sys.argv if None)
        3. Determine config file path:
           - If --config provided, use that path
           - Otherwise, use default from textbrush.paths.CONFIG_PATH
        4. Load configuration:
           a. Load config from file + env via config.load_config()
           b. Merge CLI args via merge_cli_args_with_config()
        5. Validate arguments via validate_args()
        6. Placeholder implementation for Increment 1:
           a. Print "Textbrush foundation ready" to stderr
           b. Print "Config loaded: [config summary]" to stderr
           c. Exit with code 1 (feature not implemented)
        7. Error handling:
           - Catch exceptions and print to stderr
           - Exit with non-zero code on any error
           - Never print to stdout on error

      Note for Increment 1:
        This is a foundation stub. Actual image generation will be
        implemented in Increment 2. For now, validate configuration
        loading and CLI arg parsing work correctly, then exit with
        "not implemented" message.
    """
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
        validate_args(args)

        config_path = args.config if args.config is not None else CONFIG_PATH
        config = load_config(config_path)
        config = merge_cli_args_with_config(args, config)

        print(
            "Textbrush foundation ready",
            file=sys.stderr,
        )
        print(
            f"Config loaded: output={config.output.directory}, format={config.output.format}",
            file=sys.stderr,
        )

        sys.exit(2)

    except (ValueError, SystemExit) as e:
        if isinstance(e, SystemExit):
            raise
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

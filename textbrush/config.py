"""Configuration loading and merging for textbrush.

Implements three-tier configuration system:
1. TOML config file (~/.config/textbrush/config.toml)
2. Environment variables (TEXTBRUSH_* prefix)
3. CLI arguments (highest priority)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path


def _mask_sensitive_value(value: str | None, prefix_len: int = 4, suffix_len: int = 4) -> str:
    """Mask sensitive configuration values for safe display.

    Args:
        value: Sensitive value to mask, or None.
        prefix_len: Number of characters to show at start.
        suffix_len: Number of characters to show at end.

    Returns:
        Masked value string, or "None" if value is None.
    """
    if value is None:
        return "None"
    if len(value) <= prefix_len + suffix_len:
        return "***"
    return f"{value[:prefix_len]}...{value[-suffix_len:]}"


@dataclass
class OutputConfig:
    """Output-related configuration."""

    directory: Path
    format: str


@dataclass
class ModelConfig:
    """Model-related configuration."""

    directories: list[Path]
    buffer_size: int


@dataclass
class HuggingFaceConfig:
    """HuggingFace-specific configuration."""

    token: str | None


@dataclass
class InferenceConfig:
    """Inference backend configuration."""

    backend: str


@dataclass
class LoggingConfig:
    """Logging configuration."""

    verbosity: str


@dataclass
class Config:
    """Complete textbrush configuration."""

    output: OutputConfig
    model: ModelConfig
    huggingface: HuggingFaceConfig
    inference: InferenceConfig
    logging: LoggingConfig


def get_default_config() -> Config:
    """Get default configuration values.

    CONTRACT:
      Inputs: none

      Outputs:
        - Config object with default values matching spec requirements

      Invariants:
        - output.directory = ~/Pictures/textbrush (expanded)
        - output.format = "png"
        - model.directories = empty list
        - model.buffer_size = 8
        - huggingface.token = None
        - inference.backend = "flux"
        - logging.verbosity = "info"

      Properties:
        - Identity: get_default_config() always returns same values
        - Completeness: returned Config has all required fields populated
    """
    return Config(
        output=OutputConfig(
            directory=(Path.home() / "Pictures" / "textbrush").resolve(),
            format="png",
        ),
        model=ModelConfig(
            directories=[],
            buffer_size=8,
        ),
        huggingface=HuggingFaceConfig(
            token=None,
        ),
        inference=InferenceConfig(
            backend="flux",
        ),
        logging=LoggingConfig(
            verbosity="info",
        ),
    )


def create_default_config_file(path: Path) -> None:
    """Create default TOML config file at specified path.

    CONTRACT:
      Inputs:
        - path: filesystem path, must be writable
          Example: Path("~/.config/textbrush/config.toml")

      Outputs:
        - None (side effect: file created on filesystem)

      Invariants:
        - If parent directory doesn't exist, it is created
        - File contains valid TOML matching default config schema
        - File is human-readable and editable

      Properties:
        - Idempotent: creating file multiple times produces same result
        - Round-trip: load_config(path) after create_default_config_file(path)
          equals get_default_config()

      Algorithm:
        1. Get default config values via get_default_config()
        2. Convert Config dataclass to TOML structure with sections:
           [output], [model], [huggingface], [inference], [logging]
        3. Ensure parent directory exists (create if needed)
        4. Write TOML to file using toml library (for TOML writing support)
        5. Handle path expansion (~/ → absolute path)
    """
    import tomli_w

    expanded_path = path.expanduser().resolve()
    expanded_path.parent.mkdir(parents=True, exist_ok=True)

    config = get_default_config()

    huggingface_section = {}
    if config.huggingface.token is not None:
        huggingface_section["token"] = config.huggingface.token

    toml_data = {
        "output": {
            "directory": str(config.output.directory),
            "format": config.output.format,
        },
        "model": {
            "directories": [str(d) for d in config.model.directories],
            "buffer_size": config.model.buffer_size,
        },
        "huggingface": huggingface_section,
        "inference": {
            "backend": config.inference.backend,
        },
        "logging": {
            "verbosity": config.logging.verbosity,
        },
    }

    with open(expanded_path, "wb") as f:
        tomli_w.dump(toml_data, f)


def load_config_file(path: Path) -> Config:
    """Load configuration from TOML file.

    CONTRACT:
      Inputs:
        - path: filesystem path to TOML config file
          Example: Path("~/.config/textbrush/config.toml")

      Outputs:
        - Config object parsed from TOML file

      Invariants:
        - If file doesn't exist, return get_default_config()
        - If file is invalid TOML, raise ValueError with clear error message
        - Path expansion: ~/ → absolute path
        - All paths in config are expanded to absolute paths

      Properties:
        - File existence: non-existent file → default config (no error)
        - Round-trip: load_config_file(P) after create_default_config_file(P)
          equals get_default_config()
        - Type safety: returned Config has correct types for all fields

      Algorithm:
        1. Expand path (handle ~/)
        2. If file doesn't exist, return get_default_config()
        3. Read file and parse TOML using tomllib (Python 3.11+)
        4. Extract sections: [output], [model], [huggingface], [inference], [logging]
        5. Convert TOML data to Config dataclass
        6. Expand all Path values in config to absolute paths
        7. Validate types match Config schema
    """
    import tomllib

    expanded_path = path.expanduser().resolve()

    if not expanded_path.exists():
        return get_default_config()

    try:
        with open(expanded_path, "rb") as f:
            toml_data = tomllib.load(f)
    except Exception as e:
        raise ValueError(f"Invalid TOML file at {expanded_path}: {e}")

    output_section = toml_data.get("output", {})
    model_section = toml_data.get("model", {})
    huggingface_section = toml_data.get("huggingface", {})
    inference_section = toml_data.get("inference", {})
    logging_section = toml_data.get("logging", {})

    output_dir = output_section.get("directory")
    if output_dir:
        output_dir = Path(output_dir).expanduser().resolve()
    else:
        output_dir = get_default_config().output.directory

    output_format = output_section.get("format", get_default_config().output.format)

    model_dirs = model_section.get("directories", [])
    model_dirs = [Path(d).expanduser().resolve() for d in model_dirs]
    model_buffer_size = model_section.get("buffer_size", get_default_config().model.buffer_size)

    hf_token = huggingface_section.get("token", get_default_config().huggingface.token)

    inference_backend = inference_section.get("backend", get_default_config().inference.backend)

    logging_verbosity = logging_section.get("verbosity", get_default_config().logging.verbosity)

    return Config(
        output=OutputConfig(
            directory=output_dir,
            format=output_format,
        ),
        model=ModelConfig(
            directories=model_dirs,
            buffer_size=model_buffer_size,
        ),
        huggingface=HuggingFaceConfig(
            token=hf_token,
        ),
        inference=InferenceConfig(
            backend=inference_backend,
        ),
        logging=LoggingConfig(
            verbosity=logging_verbosity,
        ),
    )


def apply_env_overrides(config: Config) -> Config:
    """Apply environment variable overrides to configuration.

    CONTRACT:
      Inputs:
        - config: base Config object to apply overrides to

      Outputs:
        - new Config object with environment variable overrides applied

      Invariants:
        - Original config is not mutated (return new instance)
        - Only TEXTBRUSH_* environment variables are considered
        - Env var naming: TEXTBRUSH_SECTION_KEY (e.g., TEXTBRUSH_OUTPUT_FORMAT)
        - Section names: OUTPUT, MODEL, HUGGINGFACE, INFERENCE, LOGGING
        - Key names match Config field names (uppercase)

      Properties:
        - Immutability: original config unchanged
        - Selective override: only fields with corresponding env vars are changed
        - Type conversion: env var strings converted to appropriate types
          (e.g., "8" → int for buffer_size, "~/path" → Path for directories)
        - Priority: env var value overrides config file value

      Algorithm:
        1. Create copy of input config
        2. For each possible env var TEXTBRUSH_SECTION_KEY:
           a. Check if env var exists in os.environ
           b. Parse section and key from env var name
           c. Convert string value to appropriate type for that field
           d. Update corresponding field in config copy
        3. Return modified config copy

      Examples:
        - TEXTBRUSH_OUTPUT_FORMAT=jpg → config.output.format = "jpg"
        - TEXTBRUSH_LOGGING_VERBOSITY=debug → config.logging.verbosity = "debug"
        - TEXTBRUSH_MODEL_BUFFER_SIZE=16 → config.model.buffer_size = 16
    """
    output_config = config.output
    model_config = config.model
    huggingface_config = config.huggingface
    inference_config = config.inference
    logging_config = config.logging

    if "TEXTBRUSH_OUTPUT_DIRECTORY" in os.environ:
        output_config = replace(
            output_config,
            directory=Path(os.environ["TEXTBRUSH_OUTPUT_DIRECTORY"]).expanduser().resolve(),
        )

    if "TEXTBRUSH_OUTPUT_FORMAT" in os.environ:
        output_config = replace(output_config, format=os.environ["TEXTBRUSH_OUTPUT_FORMAT"])

    if "TEXTBRUSH_MODEL_DIRECTORIES" in os.environ:
        dirs_str = os.environ["TEXTBRUSH_MODEL_DIRECTORIES"]
        dirs = [Path(d).expanduser().resolve() for d in dirs_str.split(":")]
        model_config = replace(model_config, directories=dirs)

    if "TEXTBRUSH_MODEL_BUFFER_SIZE" in os.environ:
        try:
            buffer_size = int(os.environ["TEXTBRUSH_MODEL_BUFFER_SIZE"])
            model_config = replace(model_config, buffer_size=buffer_size)
        except ValueError:
            pass

    if "TEXTBRUSH_HUGGINGFACE_TOKEN" in os.environ:
        huggingface_config = replace(
            huggingface_config, token=os.environ["TEXTBRUSH_HUGGINGFACE_TOKEN"]
        )

    if "TEXTBRUSH_INFERENCE_BACKEND" in os.environ:
        inference_config = replace(
            inference_config, backend=os.environ["TEXTBRUSH_INFERENCE_BACKEND"]
        )

    if "TEXTBRUSH_LOGGING_VERBOSITY" in os.environ:
        logging_config = replace(
            logging_config, verbosity=os.environ["TEXTBRUSH_LOGGING_VERBOSITY"]
        )

    return Config(
        output=output_config,
        model=model_config,
        huggingface=huggingface_config,
        inference=inference_config,
        logging=logging_config,
    )


def load_config(config_path: Path | None = None) -> Config:
    """Load complete configuration with file + environment variable merging.

    CONTRACT:
      Inputs:
        - config_path: optional path to TOML config file
          If None, use default path from textbrush.paths.CONFIG_PATH
          Example: Path("~/.config/textbrush/config.toml")

      Outputs:
        - Config object with merged configuration from file + environment

      Invariants:
        - Priority order: environment variables override config file values
        - If config_path is None, use textbrush.paths.CONFIG_PATH
        - If config file doesn't exist at path, use defaults
        - If parent directory of config file doesn't exist, create it and
          write default config file

      Properties:
        - Merging: env vars override file values, file values override defaults
        - First-run behavior: missing config file triggers creation of default
        - Completeness: returned Config always has all required fields

      Algorithm:
        1. Determine config path:
           - If config_path provided, use it
           - Otherwise, use textbrush.paths.CONFIG_PATH
        2. Expand path (handle ~/)
        3. If config file doesn't exist:
           a. Create parent directory if needed
           b. Create default config file at path
        4. Load config from file via load_config_file()
        5. Apply environment variable overrides via apply_env_overrides()
        6. Return final merged config
    """
    from textbrush import paths

    if config_path is None:
        config_path = paths.CONFIG_PATH

    expanded_path = config_path.expanduser().resolve()

    if not expanded_path.exists():
        expanded_path.parent.mkdir(parents=True, exist_ok=True)
        create_default_config_file(expanded_path)

    file_config = load_config_file(expanded_path)
    final_config = apply_env_overrides(file_config)

    return final_config

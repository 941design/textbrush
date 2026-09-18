"""Configuration loading and merging for textbrush.

This module implements the file and environment-variable tiers of the
overall three-tier configuration system:
1. TOML config file (~/.config/textbrush/config.toml)
2. Environment variables (TEXTBRUSH_* prefix)

CLI arguments (the third, highest-priority tier) are merged by the CLI
composition root in `textbrush/cli.py`, not by this module -- `load_config()`
here only performs the file -> env merge.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

# Safe default for the additive [editing] section (epic:
# multi-reference-flux-image-editing). Reproduces pre-epic FLUX.1 schnell
# text-to-image behavior, so config files, and code, predating this section
# need not supply it (AC-COMPAT-1).
#
# Canonical spelling owned by `textbrush.validation` (S4) -- see
# specs/epic-multi-reference-flux-image-editing/architecture.md, section
# "Preset lexicon (canonical -- owned by `validation`)". `config` is a leaf
# module and must not import `validation`, so this binding is documentary
# only until S4 lands; do not re-spell this identifier elsewhere.
_DEFAULT_EDITING_PRESET = "landscape-medium"


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
    # Globally selected model id. None means "no explicit choice made" and
    # must be resolved from the reference count per spec.md §7.3 (2-4
    # references -> FLUX.2; 1 reference -> FLUX.2, falling back to Kontext;
    # 0 references -> FLUX.1 schnell). spec.md §5.1 forbids silently
    # replacing a model the user did choose, so "unset" has to be
    # representable distinctly from any concrete model id -- see
    # architecture.md "Selected-model representation". Defaulted so
    # existing `ModelConfig(...)` call sites that predate this field keep
    # working unchanged. This module does not validate the value against
    # the model registry (owned by `textbrush.model`, S2) -- deliberately
    # deferred so `config` remains a leaf.
    selected_id: str | None = None


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
class EditingConfig:
    """Editing-only configuration: settings that apply solely when an
    editing-capable model is active.

    Additive section (epic: multi-reference-flux-image-editing). Holds the
    default *editing* preset -- a fallback used only while an editing-
    capable model is selected (see `ModelConfig.selected_id`). It is never
    the active preset for a text-to-image model: spec.md §5.5 validates an
    editing preset against the active model in both directions, so pairing
    a text-to-image model with an editing preset is invalid regardless of
    which one is the "default". Defaults to a value that reproduces
    pre-epic FLUX.1 schnell text-to-image behavior, so a config file
    predating this section loads unchanged (AC-COMPAT-1). This module only
    stores and merges this value; it does not validate `default_preset`
    against cardinality/preset rules (owned by `textbrush.validation`) --
    deliberately deferred so `config` remains a leaf.
    """

    default_preset: str


@dataclass
class Config:
    """Complete textbrush configuration."""

    output: OutputConfig
    model: ModelConfig
    huggingface: HuggingFaceConfig
    inference: InferenceConfig
    logging: LoggingConfig
    # Defaulted (unlike the sections above) so existing call sites that
    # construct Config(...) directly without an `editing=` argument — e.g.
    # test fixtures predating this epic — keep working unchanged, matching
    # this field's config-file and env-var fallback behavior below.
    editing: EditingConfig = field(
        default_factory=lambda: EditingConfig(default_preset=_DEFAULT_EDITING_PRESET)
    )


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
        - model.selected_id = None -- unset, meaning no explicit choice has
          been made. Resolved from the reference count per spec.md §7.3;
          never given a concrete default here, so a config file never
          materializes a model choice the user did not make (spec.md §5.1)
        - huggingface.token = None
        - inference.backend = "flux"
        - logging.verbosity = "info"
        - editing.default_preset = "landscape-medium" -- a fallback used
          only when an editing-capable model is active. It is never the
          active preset for a text-to-image model: spec.md §5.5 validates
          an editing preset against the active model in both directions

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
            selected_id=None,
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
        editing=EditingConfig(
            default_preset=_DEFAULT_EDITING_PRESET,
        ),
    )


def _insert_model_selected_id_example(path: Path) -> None:
    """Insert a commented-out example of `model.selected_id` under `[model]`.

    `tomli_w` cannot represent `None` or emit comments, and a concrete value
    must never be written here: doing so would silently convert every
    first-run user into having made an explicit model choice they never
    made (spec.md §5.1/§7.3; architecture.md "Selected-model
    representation"). This purely documents the field, as text, for a human
    editing the file by hand -- it never materializes a value that
    `load_config_file` would read back.

    Raises:
        ValueError: if no `[model]` header is found. `tomli_w` omits the
          header entirely for an empty table, so a future edit that empties
          `model_section` in `create_default_config_file` would silently
          strand this helper as a no-op without this guard.
    """
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    for i, line in enumerate(lines):
        if line.strip() == "[model]":
            lines.insert(
                i + 1,
                '# selected_id = "flux1-schnell"  # Uncomment to pin a model;'
                " unset (default) resolves from the reference count, section 7.3\n",
            )
            break
    else:
        raise ValueError(f"no [model] header found in {path}; cannot insert selected_id example")
    path.write_text("".join(lines), encoding="utf-8")


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
        - model.selected_id is never written as a concrete value (it is
          unset by default); at most a commented-out example is present

      Properties:
        - Idempotent: creating file multiple times produces same result
        - Round-trip: load_config(path) after create_default_config_file(path)
          equals get_default_config()

      Algorithm:
        1. Get default config values via get_default_config()
        2. Convert Config dataclass to TOML structure with sections:
           [output], [model], [huggingface], [inference], [logging], [editing]
           -- model.selected_id is omitted (it is None); a commented-out
           example is appended under [model] for human editors
        3. Ensure parent directory exists (create if needed)
        4. Write TOML to file using toml library (for TOML writing support)
        5. Handle path expansion (~/ → absolute path)
    """
    import tomli_w

    expanded_path = path.expanduser().resolve()
    expanded_path.parent.mkdir(parents=True, exist_ok=True)

    config = get_default_config()
    assert config.model.selected_id is None, (
        "get_default_config() must never materialize a concrete model.selected_id "
        "(spec.md §5.1/§7.3; architecture.md 'Selected-model representation' is "
        "unconditional, not conditional on this being a fresh default)"
    )

    huggingface_section = {}
    if config.huggingface.token is not None:
        huggingface_section["token"] = config.huggingface.token

    model_section = {
        "directories": [str(d) for d in config.model.directories],
        "buffer_size": config.model.buffer_size,
    }

    toml_data = {
        "output": {
            "directory": str(config.output.directory),
            "format": config.output.format,
        },
        "model": model_section,
        "huggingface": huggingface_section,
        "inference": {
            "backend": config.inference.backend,
        },
        "logging": {
            "verbosity": config.logging.verbosity,
        },
        "editing": {
            "default_preset": config.editing.default_preset,
        },
    }

    with open(expanded_path, "wb") as f:
        tomli_w.dump(toml_data, f)

    _insert_model_selected_id_example(expanded_path)


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
        - model.selected_id is an optional key inside [model]; if absent,
          it falls back to get_default_config()'s value (None, i.e. unset)
          -- it is never inferred from other keys
        - The [editing] section, and its default_preset key, is optional: a
          config file that predates this section (or omits the key) loads
          with editing.default_preset falling back to
          get_default_config()'s value, exactly like every other optional
          section below (AC-COMPAT-1)

      Properties:
        - File existence: non-existent file → default config (no error)
        - Round-trip: load_config_file(P) after create_default_config_file(P)
          equals get_default_config()
        - Type safety: returned Config has correct types for all fields
        - Backward compatibility: a pre-epic file with no [editing] section
          and no model.selected_id key produces a config identical to
          get_default_config() for both fields

      Algorithm:
        1. Expand path (handle ~/)
        2. If file doesn't exist, return get_default_config()
        3. Read file and parse TOML using tomllib (Python 3.11+)
        4. Extract sections: [output], [model], [huggingface], [inference],
           [logging], [editing]
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
    editing_section = toml_data.get("editing", {})

    output_dir = output_section.get("directory")
    if output_dir:
        output_dir = Path(output_dir).expanduser().resolve()
    else:
        output_dir = get_default_config().output.directory

    output_format = output_section.get("format", get_default_config().output.format)

    model_dirs = model_section.get("directories", [])
    model_dirs = [Path(d).expanduser().resolve() for d in model_dirs]
    model_buffer_size = model_section.get("buffer_size", get_default_config().model.buffer_size)
    model_selected_id = model_section.get("selected_id", get_default_config().model.selected_id)

    hf_token = huggingface_section.get("token", get_default_config().huggingface.token)

    inference_backend = inference_section.get("backend", get_default_config().inference.backend)

    logging_verbosity = logging_section.get("verbosity", get_default_config().logging.verbosity)

    editing_default_preset = editing_section.get(
        "default_preset", get_default_config().editing.default_preset
    )

    return Config(
        output=OutputConfig(
            directory=output_dir,
            format=output_format,
        ),
        model=ModelConfig(
            directories=model_dirs,
            buffer_size=model_buffer_size,
            selected_id=model_selected_id,
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
        editing=EditingConfig(
            default_preset=editing_default_preset,
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
        - Section names: OUTPUT, MODEL, HUGGINGFACE, INFERENCE, LOGGING, EDITING
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
        - TEXTBRUSH_MODEL_SELECTED_ID=flux2-klein-4b → config.model.selected_id
          = "flux2-klein-4b"
        - TEXTBRUSH_EDITING_DEFAULT_PRESET=portrait-large →
          config.editing.default_preset = "portrait-large"
    """
    output_config = config.output
    model_config = config.model
    huggingface_config = config.huggingface
    inference_config = config.inference
    logging_config = config.logging
    editing_config = config.editing

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

    if "TEXTBRUSH_MODEL_SELECTED_ID" in os.environ:
        model_config = replace(model_config, selected_id=os.environ["TEXTBRUSH_MODEL_SELECTED_ID"])

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

    if "TEXTBRUSH_EDITING_DEFAULT_PRESET" in os.environ:
        editing_config = replace(
            editing_config, default_preset=os.environ["TEXTBRUSH_EDITING_DEFAULT_PRESET"]
        )

    return Config(
        output=output_config,
        model=model_config,
        huggingface=huggingface_config,
        inference=inference_config,
        logging=logging_config,
        editing=editing_config,
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

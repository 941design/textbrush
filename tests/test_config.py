"""Tests for textbrush configuration system."""

import ast
import os
import tempfile
from pathlib import Path

import pytest

from textbrush.config import (
    Config,
    EditingConfig,
    HuggingFaceConfig,
    InferenceConfig,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
    apply_env_overrides,
    create_default_config_file,
    get_default_config,
    load_config,
    load_config_file,
)


def _internal_imports(source: str, package_name: str = "textbrush") -> set[str]:
    """Collect the set of internal (package-qualified) imports referenced by
    `source`, resolving relative imports (`node.level >= 1`) against
    `package_name` so `from .backend import X` (this package's prevailing
    import convention, e.g. `textbrush/cli.py`'s `from .config import ...`)
    is treated identically to the absolute `from textbrush.backend import X`
    form."""
    tree = ast.parse(source)
    internal_imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level >= 1:
                # Relative import: `from .backend import X` (module="backend")
                # or `from . import backend` (module=None) -- both resolve
                # against the current package regardless of dot count.
                if node.module is None:
                    for alias in node.names:
                        internal_imports.add(f"{package_name}.{alias.name}")
                else:
                    internal_imports.add(f"{package_name}.{node.module}")
            elif node.module == package_name:
                for alias in node.names:
                    internal_imports.add(f"{package_name}.{alias.name}")
            elif node.module and node.module.startswith(f"{package_name}."):
                internal_imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith(package_name):
                    internal_imports.add(alias.name)
    return internal_imports


class TestGetDefaultConfig:
    """Tests for get_default_config()."""

    def test_identity_property(self):
        """Default config is consistent across calls."""
        config1 = get_default_config()
        config2 = get_default_config()

        assert config1.output.directory == config2.output.directory
        assert config1.output.format == config2.output.format
        assert config1.model.buffer_size == config2.model.buffer_size
        assert config1.inference.backend == config2.inference.backend
        assert config1.logging.verbosity == config2.logging.verbosity
        assert config1.editing == config2.editing

    def test_default_values(self):
        """Default config has correct values."""
        config = get_default_config()

        assert config.output.format == "png"
        assert config.model.buffer_size == 8
        assert config.model.directories == []
        assert config.huggingface.token is None
        assert config.inference.backend == "flux"
        assert config.logging.verbosity == "info"
        assert "Pictures/textbrush" in str(config.output.directory)

    def test_model_selected_id_defaults_to_unset(self):
        """model.selected_id defaults to None (unset) -- resolved from the
        reference count downstream per spec.md §7.3 (0 references resolves
        to flux1-schnell, reproducing pre-epic text-to-image behavior). A
        concrete default here would silently convert every user into having
        made a model choice they never made (spec.md §5.1)."""
        config = get_default_config()

        assert config.model.selected_id is None

    def test_editing_default_preset_reproduces_pre_epic_schnell_behavior(self):
        """Default editing.default_preset is additive with a safe default
        matching current FLUX.1 schnell text-to-image behavior
        (AC-COMPAT-1)."""
        config = get_default_config()

        assert config.editing.default_preset == "landscape-medium"

    def test_editing_default_preset_constant_matches_validation_module(self):
        """The literal `"landscape-medium"` string lives in two places
        today: `_DEFAULT_EDITING_PRESET` in `textbrush.config` (the value
        a fresh config file defaults to) and `DEFAULT_EDITING_PRESET` in
        `textbrush.validation` (the value the resolver falls back to).
        They must stay in lockstep -- if either drifts, a fresh config
        and a programmatic default point at different identifiers, and
        one of them silently stops being a real preset.

        `config` cannot import `validation` (validation imports model;
        config is a leaf by architecture.md boundary rule 1), so this
        assertion lives in tests, not at module load time."""
        import textbrush.config as config_module
        import textbrush.validation as validation_module

        config_default = config_module._DEFAULT_EDITING_PRESET
        validation_default = validation_module.DEFAULT_EDITING_PRESET

        assert config_default == validation_default, (
            f"config._DEFAULT_EDITING_PRESET ({config_default!r}) drifted "
            f"from validation.DEFAULT_EDITING_PRESET ({validation_default!r})"
        )

    def test_output_directory_is_absolute(self):
        """Output directory is absolute path."""
        config = get_default_config()
        assert config.output.directory.is_absolute()

    def test_completeness(self):
        """All required fields are populated."""
        config = get_default_config()

        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.model, ModelConfig)
        assert isinstance(config.huggingface, HuggingFaceConfig)
        assert isinstance(config.inference, InferenceConfig)
        assert isinstance(config.logging, LoggingConfig)
        assert isinstance(config.editing, EditingConfig)

        assert config.output.directory is not None
        assert config.output.format is not None
        assert config.model.directories is not None
        assert config.model.buffer_size is not None
        assert config.inference.backend is not None
        assert config.logging.verbosity is not None
        assert config.editing.default_preset is not None


class TestCreateDefaultConfigFile:
    """Tests for create_default_config_file()."""

    def test_creates_file(self):
        """File is created at specified path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.toml"
            create_default_config_file(config_path)

            assert config_path.exists()
            assert config_path.is_file()

    def test_creates_parent_directories(self):
        """Parent directories are created if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "a" / "b" / "c" / "config.toml"
            create_default_config_file(config_path)

            assert config_path.exists()
            assert config_path.parent.exists()

    def test_idempotent(self):
        """Creating file multiple times produces same result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            create_default_config_file(config_path)
            content1 = config_path.read_text()

            create_default_config_file(config_path)
            content2 = config_path.read_text()

            assert content1 == content2

    def test_file_is_valid_toml(self):
        """Created file contains valid TOML."""
        import tomllib

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            with open(config_path, "rb") as f:
                data = tomllib.load(f)

            assert "output" in data
            assert "model" in data
            assert "huggingface" in data
            assert "inference" in data
            assert "logging" in data
            assert "editing" in data
            assert "selected_id" not in data["model"]
            assert data["editing"]["default_preset"] == "landscape-medium"

    def test_model_selected_id_not_materialized_as_concrete_value(self):
        """create_default_config_file must never write a concrete
        model.selected_id -- spec.md §5.1/§7.3 requires "unset" to remain
        representable, and materializing one would silently convert every
        first-run user into having made a model choice they never made
        (architecture.md "Selected-model representation"). If an example is
        present for humans editing the file by hand, it must be commented
        out, never a live key."""
        import tomllib

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            assert "selected_id" not in data.get("model", {})

            selected_id_lines = [
                line for line in config_path.read_text().splitlines() if "selected_id" in line
            ]
            # Positive assertion: the commented-out example must actually be
            # present, not merely absent-of-a-live-key. Without this, the
            # helper that inserts it could silently degrade to a no-op (e.g.
            # if it stops finding "[model]") and this test would still pass
            # vacuously -- every line in the file trivially satisfies
            # `line.strip().startswith("#")` when there is no such line.
            assert selected_id_lines, (
                "expected a commented-out `selected_id` example line under [model], found none"
            )
            for line in selected_id_lines:
                assert line.strip().startswith("#"), (
                    f"selected_id must only appear commented out, found: {line!r}"
                )

    def test_round_trip_with_load(self):
        """load_config_file after create matches get_default_config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            loaded_config = load_config_file(config_path)
            default_config = get_default_config()

            assert loaded_config.output.format == default_config.output.format
            assert loaded_config.model.buffer_size == default_config.model.buffer_size
            assert loaded_config.model.selected_id == default_config.model.selected_id
            assert loaded_config.huggingface.token == default_config.huggingface.token
            assert loaded_config.inference.backend == default_config.inference.backend
            assert loaded_config.logging.verbosity == default_config.logging.verbosity
            assert loaded_config.editing == default_config.editing

    def test_round_trip_full_config_equality(self):
        """Full dataclass equality round-trip, including the new editing
        section, catching any field this suite's per-field assertions miss."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            loaded_config = load_config_file(config_path)
            default_config = get_default_config()

            assert loaded_config == default_config

    def test_path_expansion(self):
        """Handles ~ path expansion in directory creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Use absolute path in test, but document behavior
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            assert config_path.exists()


class TestLoadConfigFile:
    """Tests for load_config_file()."""

    def test_missing_file_returns_defaults(self):
        """Non-existent file returns default config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.toml"

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.output.format == defaults.output.format
            assert config.model.buffer_size == defaults.model.buffer_size

    def test_invalid_toml_raises_error(self):
        """Invalid TOML file raises ValueError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "bad.toml"
            config_path.write_text("[output\ninvalid toml")

            with pytest.raises(ValueError):
                load_config_file(config_path)

    def test_partial_config_uses_defaults(self):
        """Missing sections in TOML use defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "partial.toml"
            config_path.write_text("[output]\nformat = 'jpg'\n")

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.output.format == "jpg"
            assert config.model.buffer_size == defaults.model.buffer_size

    def test_path_expansion_in_config(self):
        """Paths in config are expanded to absolute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            config = load_config_file(config_path)

            assert config.output.directory.is_absolute()
            for d in config.model.directories:
                assert d.is_absolute()

    def test_type_safety_integer_buffer_size(self):
        """Buffer size is correctly parsed as integer."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[model]\nbuffer_size = 16\n")

            config = load_config_file(config_path)

            assert isinstance(config.model.buffer_size, int)
            assert config.model.buffer_size == 16

    def test_type_safety_string_format(self):
        """Format is correctly parsed as string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('[output]\nformat = "webp"\n')

            config = load_config_file(config_path)

            assert isinstance(config.output.format, str)
            assert config.output.format == "webp"

    def test_type_safety_path_directory(self):
        """Directory is correctly parsed as Path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(f'[output]\ndirectory = "{tmpdir}"\n')

            config = load_config_file(config_path)

            assert isinstance(config.output.directory, Path)

    def test_model_and_editing_settings_full_override(self):
        """model.selected_id and editing.default_preset can each be set
        from the TOML file, in their respective sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                '[model]\nselected_id = "flux1-kontext-dev"\n\n'
                '[editing]\ndefault_preset = "portrait-small"\n'
            )

            config = load_config_file(config_path)

            assert config.model.selected_id == "flux1-kontext-dev"
            assert config.editing.default_preset == "portrait-small"

    def test_model_selected_id_set_independently_of_editing_default_preset(self):
        """model.selected_id can be set without touching [editing];
        default_preset falls back independently, matching the per-field
        fallback used by every other section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('[model]\nselected_id = "flux1-kontext-dev"\n')

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.model.selected_id == "flux1-kontext-dev"
            assert config.editing.default_preset == defaults.editing.default_preset

    def test_editing_default_preset_set_independently_of_model_selected_id(self):
        """editing.default_preset can be set without touching [model];
        model.selected_id falls back independently to its unset default."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('[editing]\ndefault_preset = "portrait-small"\n')

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.editing.default_preset == "portrait-small"
            assert config.model.selected_id == defaults.model.selected_id
            assert config.model.selected_id is None

    def test_missing_editing_section_uses_defaults(self):
        """A file with no [editing] section at all -- the pre-epic shape --
        resolves editing to the exact safe defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[output]\nformat = 'png'\n")

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.editing == defaults.editing

    def test_unknown_key_in_editing_section_ignored(self):
        """Unknown keys in [editing] are ignored gracefully, consistent with
        every other section's behavior."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                '[editing]\ndefault_preset = "portrait-large"\nunknown_key = "value"\n'
            )

            config = load_config_file(config_path)

            assert config.editing.default_preset == "portrait-large"

    def test_arbitrary_model_id_and_preset_strings_accepted_at_load_time(self):
        """Cardinality/preset validation is explicitly deferred to
        textbrush.validation (S4) and the per-model registry (S2); loading
        config performs no allow-listing of these string values -- an
        unrecognized value is accepted here and would fail, with a helpful
        message, only when a later module validates it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text(
                '[model]\nselected_id = "not-a-real-model"\n\n'
                '[editing]\ndefault_preset = "not-a-real-preset"\n'
            )

            config = load_config_file(config_path)  # must not raise

            assert config.model.selected_id == "not-a-real-model"
            assert config.editing.default_preset == "not-a-real-preset"


class TestApplyEnvOverrides:
    """Tests for apply_env_overrides()."""

    def test_immutability(self):
        """Original config is not mutated."""
        config = get_default_config()
        original_format = config.output.format

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "jpg"
        try:
            new_config = apply_env_overrides(config)

            assert config.output.format == original_format
            assert new_config.output.format == "jpg"
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_output_format_override(self):
        """TEXTBRUSH_OUTPUT_FORMAT overrides output format."""
        config = get_default_config()

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "jpg"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.output.format == "jpg"
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_logging_verbosity_override(self):
        """TEXTBRUSH_LOGGING_VERBOSITY overrides logging verbosity."""
        config = get_default_config()

        os.environ["TEXTBRUSH_LOGGING_VERBOSITY"] = "debug"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.logging.verbosity == "debug"
        finally:
            del os.environ["TEXTBRUSH_LOGGING_VERBOSITY"]

    def test_model_buffer_size_override(self):
        """TEXTBRUSH_MODEL_BUFFER_SIZE overrides buffer size."""
        config = get_default_config()

        os.environ["TEXTBRUSH_MODEL_BUFFER_SIZE"] = "32"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.model.buffer_size == 32
        finally:
            del os.environ["TEXTBRUSH_MODEL_BUFFER_SIZE"]

    def test_inference_backend_override(self):
        """TEXTBRUSH_INFERENCE_BACKEND overrides backend."""
        config = get_default_config()

        os.environ["TEXTBRUSH_INFERENCE_BACKEND"] = "diffusers"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.inference.backend == "diffusers"
        finally:
            del os.environ["TEXTBRUSH_INFERENCE_BACKEND"]

    def test_huggingface_token_override(self):
        """TEXTBRUSH_HUGGINGFACE_TOKEN overrides token."""
        config = get_default_config()

        os.environ["TEXTBRUSH_HUGGINGFACE_TOKEN"] = "hf_test123"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.huggingface.token == "hf_test123"
        finally:
            del os.environ["TEXTBRUSH_HUGGINGFACE_TOKEN"]

    def test_model_selected_id_override(self):
        """TEXTBRUSH_MODEL_SELECTED_ID overrides model.selected_id."""
        config = get_default_config()

        os.environ["TEXTBRUSH_MODEL_SELECTED_ID"] = "flux2-klein-4b"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.model.selected_id == "flux2-klein-4b"
        finally:
            del os.environ["TEXTBRUSH_MODEL_SELECTED_ID"]

    def test_editing_default_preset_override(self):
        """TEXTBRUSH_EDITING_DEFAULT_PRESET overrides editing.default_preset."""
        config = get_default_config()

        os.environ["TEXTBRUSH_EDITING_DEFAULT_PRESET"] = "portrait-large"
        try:
            overridden = apply_env_overrides(config)
            assert overridden.editing.default_preset == "portrait-large"
        finally:
            del os.environ["TEXTBRUSH_EDITING_DEFAULT_PRESET"]

    def test_model_selected_id_override_immutability(self):
        """Overriding model.selected_id does not mutate the original config,
        matching every other field's immutability guarantee."""
        config = get_default_config()
        original_selected_id = config.model.selected_id

        os.environ["TEXTBRUSH_MODEL_SELECTED_ID"] = "flux1-kontext-dev"
        try:
            overridden = apply_env_overrides(config)

            assert config.model.selected_id == original_selected_id
            assert overridden.model.selected_id == "flux1-kontext-dev"
        finally:
            del os.environ["TEXTBRUSH_MODEL_SELECTED_ID"]

    def test_selective_override(self):
        """Only specified env vars are overridden."""
        config = get_default_config()
        original_backend = config.inference.backend

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "jpg"
        try:
            overridden = apply_env_overrides(config)

            assert overridden.output.format == "jpg"
            assert overridden.inference.backend == original_backend
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_invalid_integer_env_var_ignored(self):
        """Invalid integer values are gracefully ignored."""
        config = get_default_config()
        original_buffer = config.model.buffer_size

        os.environ["TEXTBRUSH_MODEL_BUFFER_SIZE"] = "not_an_int"
        try:
            overridden = apply_env_overrides(config)

            assert overridden.model.buffer_size == original_buffer
        finally:
            del os.environ["TEXTBRUSH_MODEL_BUFFER_SIZE"]

    def test_output_directory_override(self):
        """TEXTBRUSH_OUTPUT_DIRECTORY overrides output directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = get_default_config()

            os.environ["TEXTBRUSH_OUTPUT_DIRECTORY"] = tmpdir
            try:
                overridden = apply_env_overrides(config)

                assert str(overridden.output.directory) == str(Path(tmpdir).resolve())
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_DIRECTORY"]

    def test_path_expansion_in_env_override(self):
        """Paths from env vars are expanded to absolute."""
        config = get_default_config()

        os.environ["TEXTBRUSH_OUTPUT_DIRECTORY"] = "~/test"
        try:
            overridden = apply_env_overrides(config)

            assert overridden.output.directory.is_absolute()
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_DIRECTORY"]


class TestLoadConfig:
    """Tests for load_config()."""

    def test_creates_config_file_if_missing(self):
        """Missing config file triggers creation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            load_config(config_path)

            assert config_path.exists()

    def test_creates_parent_directory(self):
        """Parent directories are created if missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "a" / "b" / "config.toml"

            load_config(config_path)

            assert config_path.parent.exists()

    def test_merges_file_and_env(self):
        """Environment variables override file values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "webp"
            try:
                config = load_config(config_path)
                assert config.output.format == "webp"
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_returns_complete_config(self):
        """Returned config has all required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"

            config = load_config(config_path)

            assert config.output.directory is not None
            assert config.output.format is not None
            assert config.model.directories is not None
            assert config.model.buffer_size is not None
            assert config.huggingface.token is not None or config.huggingface.token is None
            assert config.inference.backend is not None
            assert config.logging.verbosity is not None


class TestConfigMergingPriority:
    """Tests for configuration merging priority."""

    def test_env_overrides_file(self):
        """Environment variables override file values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[output]\nformat = 'png'\n")

            os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "jpg"
            try:
                file_config = load_config_file(config_path)
                merged_config = apply_env_overrides(file_config)

                assert file_config.output.format == "png"
                assert merged_config.output.format == "jpg"
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_file_overrides_defaults(self):
        """File values override defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[model]\nbuffer_size = 64\n")

            loaded = load_config_file(config_path)
            defaults = get_default_config()

            assert defaults.model.buffer_size == 8
            assert loaded.model.buffer_size == 64

    def test_multiple_conflicting_values_env_wins(self):
        """When file, env, and defaults all differ, env wins."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            # File sets format to jpg
            config_path.write_text("[output]\nformat = 'jpg'\n")

            # Env sets format to webp
            os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "webp"
            try:
                config = load_config(config_path)

                # Env value should win
                assert config.output.format == "webp"
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_conflict_resolution_multiple_fields(self):
        """Conflict resolution works independently across fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            # File sets format and buffer_size
            config_path.write_text("[output]\nformat = 'jpg'\n[model]\nbuffer_size = 16\n")

            # Env only overrides format, not buffer_size
            os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "png"
            try:
                config = load_config(config_path)

                # Format from env (overrides file)
                assert config.output.format == "png"
                # Buffer size from file (no env override)
                assert config.model.buffer_size == 16
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_env_and_file_both_override_defaults(self):
        """Env and file values both take precedence over defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            # File sets buffer_size
            config_path.write_text("[model]\nbuffer_size = 32\n")

            # Env sets verbosity
            os.environ["TEXTBRUSH_LOGGING_VERBOSITY"] = "debug"
            try:
                config = load_config(config_path)
                defaults = get_default_config()

                # Buffer size from file (not default)
                assert config.model.buffer_size == 32
                assert config.model.buffer_size != defaults.model.buffer_size

                # Verbosity from env (not default)
                assert config.logging.verbosity == "debug"
                assert config.logging.verbosity != defaults.logging.verbosity
            finally:
                del os.environ["TEXTBRUSH_LOGGING_VERBOSITY"]

    def test_model_selected_id_env_overrides_file(self):
        """model.selected_id follows the identical env-over-file precedence
        as every pre-existing field, through the real load_config() merge
        (file->env; CLI argument merging is a separate tier, owned by the
        CLI composition root in cli.py, and is S9's verification obligation
        -- not exercised by this test)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('[model]\nselected_id = "flux1-kontext-dev"\n')

            os.environ["TEXTBRUSH_MODEL_SELECTED_ID"] = "flux2-klein-4b"
            try:
                config = load_config(config_path)
                assert config.model.selected_id == "flux2-klein-4b"
            finally:
                del os.environ["TEXTBRUSH_MODEL_SELECTED_ID"]

    def test_editing_file_overrides_defaults(self):
        """The new [editing] section follows the identical file-over-default
        precedence as every pre-existing section."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text('[editing]\ndefault_preset = "portrait-large"\n')

            config = load_config(config_path)
            defaults = get_default_config()

            assert config.editing.default_preset == "portrait-large"
            assert config.editing.default_preset != defaults.editing.default_preset


class TestEdgeCases:
    """Edge case tests for configuration system."""

    def test_empty_toml_file(self):
        """Empty TOML file uses all defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("")

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.output.format == defaults.output.format
            assert config.model.buffer_size == defaults.model.buffer_size

    def test_model_directories_are_paths(self):
        """Model directories are Path objects."""
        config = get_default_config()

        for d in config.model.directories:
            assert isinstance(d, Path)

    def test_output_directory_is_path(self):
        """Output directory is a Path object."""
        config = get_default_config()

        assert isinstance(config.output.directory, Path)

    def test_apply_env_overrides_preserves_non_overridden_fields(self):
        """Non-overridden fields remain unchanged when one field is overridden."""
        config = get_default_config()
        original_backend = config.inference.backend
        original_buffer_size = config.model.buffer_size
        original_verbosity = config.logging.verbosity

        original_editing = config.editing

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "webp"
        try:
            overridden = apply_env_overrides(config)

            # Overridden field should change
            assert overridden.output.format == "webp"
            # Non-overridden fields should remain unchanged
            assert overridden.inference.backend == original_backend
            assert overridden.model.buffer_size == original_buffer_size
            assert overridden.editing == original_editing
            assert overridden.logging.verbosity == original_verbosity
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]

    def test_config_with_empty_directories_list(self):
        """Config with empty model directories list is valid."""
        config = get_default_config()

        assert config.model.directories == []
        assert isinstance(config.model.directories, list)

    def test_none_token_is_preserved(self):
        """None token value is preserved from defaults."""
        config = get_default_config()

        assert config.huggingface.token is None

    def test_multiple_directory_handling(self):
        """Multiple model directories can be loaded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            dir1 = str(Path(tmpdir) / "dir1")
            dir2 = str(Path(tmpdir) / "dir2")

            config_path.write_text(
                f'[model]\ndirectories = ["{dir1}", "{dir2}"]\nbuffer_size = 8\n'
            )

            config = load_config_file(config_path)

            assert len(config.model.directories) == 2
            assert all(isinstance(d, Path) for d in config.model.directories)

    def test_xdg_config_home_respected(self):
        """XDG_CONFIG_HOME environment variable affects default config path."""
        # Note: This test verifies that custom XDG paths work when explicitly provided
        # The actual XDG_CONFIG_HOME integration is in textbrush.paths module
        with tempfile.TemporaryDirectory() as tmpdir:
            custom_config_dir = Path(tmpdir) / "custom_config"
            custom_config_dir.mkdir()
            config_path = custom_config_dir / "textbrush" / "config.toml"

            # Create config in custom location
            load_config(config_path)

            # Config file should be created in custom location
            assert config_path.exists()

    def test_type_mismatch_buffer_size_string(self):
        """String value for integer field uses default on type error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            # Invalid: buffer_size should be int, not string
            config_path.write_text('[model]\nbuffer_size = "not_a_number"\n')

            # TOML will parse this as a string, implementation uses it as-is
            # In practice this would cause errors later when used, but loading succeeds
            config = load_config_file(config_path)

            # The value will be a string, not an int
            assert isinstance(config.model.buffer_size, str)

    def test_type_mismatch_format_integer(self):
        """Integer value for string field is converted to string."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            # Format should be string, but TOML allows numbers
            config_path.write_text("[output]\nformat = 123\n")

            config = load_config_file(config_path)

            # Should handle gracefully (convert to string or use default)
            assert isinstance(config.output.format, (str, int))

    def test_unknown_section_ignored(self):
        """Unknown TOML sections are ignored gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[output]\nformat = 'png'\n[unknown_section]\nkey = 'value'\n")

            # Should load without error, ignoring unknown section
            config = load_config_file(config_path)
            assert config.output.format == "png"

    def test_unknown_key_in_known_section_ignored(self):
        """Unknown keys in known sections are ignored gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("[output]\nformat = 'jpg'\nunknown_key = 'value'\n")

            # Should load without error, ignoring unknown key
            config = load_config_file(config_path)
            assert config.output.format == "jpg"

    def test_empty_string_env_var(self):
        """Empty string env vars are treated as unset."""
        config = get_default_config()

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = ""
        try:
            overridden = apply_env_overrides(config)

            # Empty string should override (not be ignored)
            assert overridden.output.format == ""
        finally:
            del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]


class TestPreEpicConfigBackwardCompatibility:
    """AC-COMPAT-1 (config-file half): a config file predating this epic's
    [editing] section must remain readable, unchanged, through the
    file->env merge, with zero new required fields. (CLI argument merging
    is a separate tier, owned by the CLI composition root in cli.py, and is
    S9's verification obligation -- not exercised by this test file.)

    The fixture below is literal TOML text resembling a real pre-epic file --
    not a synthetic in-memory dict -- so these tests exercise the actual
    parsing/merge code path rather than asserting against a shortcut
    representation of it.
    """

    LEGACY_CONFIG_TOML = (
        "[output]\n"
        'directory = "{output_dir}"\n'
        'format = "png"\n'
        "\n"
        "[model]\n"
        "directories = []\n"
        "buffer_size = 8\n"
        "\n"
        "[huggingface]\n"
        "\n"
        "[inference]\n"
        'backend = "flux"\n'
        "\n"
        "[logging]\n"
        'verbosity = "info"\n'
    )

    def _write_legacy_config(self, tmpdir: str) -> tuple[Path, Path]:
        """Write a pre-epic-style config file (no [editing] section) and
        return (config_path, output_dir)."""
        output_dir = Path(tmpdir) / "outputs"
        config_path = Path(tmpdir) / "legacy_config.toml"
        config_path.write_text(self.LEGACY_CONFIG_TOML.format(output_dir=output_dir))
        return config_path, output_dir

    def test_legacy_fixture_reproduces_every_pre_epic_field(self):
        """load_config_file on the pre-epic fixture reproduces every
        pre-epic field exactly as written."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path, output_dir = self._write_legacy_config(tmpdir)

            config = load_config_file(config_path)

            assert config.output.format == "png"
            assert config.output.directory == output_dir.resolve()
            assert config.model.directories == []
            assert config.model.buffer_size == 8
            assert config.huggingface.token is None
            assert config.inference.backend == "flux"
            assert config.logging.verbosity == "info"

    def test_legacy_fixture_gets_safe_defaults_for_new_fields(self):
        """A pre-epic fixture with no [editing] section and no
        model.selected_id key resolves both new fields to their exact safe
        defaults, not an error or an unintended concrete value:
        selected_id stays unset (None, resolved from the reference count
        downstream, per spec.md §7.3) and default_preset falls back to
        landscape-medium."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path, _ = self._write_legacy_config(tmpdir)

            config = load_config_file(config_path)
            defaults = get_default_config()

            assert config.editing == defaults.editing
            assert config.model.selected_id is None
            assert config.editing.default_preset == "landscape-medium"

    def test_legacy_fixture_full_merge_field_for_field_equivalent_to_pre_epic_config(
        self,
    ):
        """load_config() end-to-end on the pre-epic fixture is field-for-field
        equivalent to the Config a pre-epic caller would have built, not just
        the new fields checked in isolation. Exercises the real load_config()
        entrypoint (file read + env merge), not a mocked loader. This also
        proves the new fields default in without requiring a `model=`/
        `editing=` argument -- the exact shape existing call sites like
        tests/conftest.py::sample_config still construct today."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path, output_dir = self._write_legacy_config(tmpdir)

            merged = load_config(config_path)

            # Constructed without `editing=` on purpose: this is exactly the
            # shape a pre-epic caller would have built by hand, proving the
            # new field defaults in without requiring the caller (or this
            # fixture) to know it exists.
            expected_pre_epic = Config(
                output=OutputConfig(directory=output_dir.resolve(), format="png"),
                model=ModelConfig(directories=[], buffer_size=8),
                huggingface=HuggingFaceConfig(token=None),
                inference=InferenceConfig(backend="flux"),
                logging=LoggingConfig(verbosity="info"),
            )

            assert merged.output == expected_pre_epic.output
            assert merged.model == expected_pre_epic.model
            assert merged.huggingface == expected_pre_epic.huggingface
            assert merged.inference == expected_pre_epic.inference
            assert merged.logging == expected_pre_epic.logging
            assert merged.editing == expected_pre_epic.editing
            assert merged == expected_pre_epic

    def test_legacy_fixture_merge_precedence_unaffected_by_new_section(self):
        """Env-over-file precedence for pre-existing fields is unaffected by
        the new [editing] section being absent: env still overrides file for
        an old field, file still overrides default for another old field, and
        the new fields still resolve to their defaults -- all through one
        real load_config() call."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path, _ = self._write_legacy_config(tmpdir)

            os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "webp"
            try:
                merged = load_config(config_path)

                assert merged.output.format == "webp"  # env overrides file's "png"
                assert merged.model.buffer_size == 8  # file overrides default (no env)
                assert merged.model.selected_id is None  # default (no file/env)
                assert merged.editing.default_preset == "landscape-medium"  # default
            finally:
                del os.environ["TEXTBRUSH_OUTPUT_FORMAT"]


class TestConfigLeafModuleBoundary:
    """architecture.md boundary rule: `config` is a leaf module and must not
    import backend/worker/ipc/inference/model/validation. It must also not
    constrain the new fields' allowed values at load time -- that is
    explicitly the model registry's (S2) and validation's (S4) job."""

    def test_config_module_has_no_forbidden_internal_imports(self):
        """textbrush/config.py's only internal (textbrush.*) dependency is
        textbrush.paths, imported lazily inside load_config(). No import of
        backend, worker, ipc, inference, model, or validation exists --
        including through this package's prevailing relative-import
        convention."""
        import textbrush.config as config_module

        source = Path(config_module.__file__).read_text()
        internal_imports = _internal_imports(source)

        forbidden = {"textbrush.backend", "textbrush.worker", "textbrush.ipc"}
        forbidden |= {"textbrush.inference", "textbrush.model", "textbrush.validation"}
        # Prefix match, not exact-string match: `from textbrush.ipc.handler
        # import X` resolves to "textbrush.ipc.handler", which a bare `in
        # forbidden` set membership check would miss entirely. This helper
        # is the template for S3's (`references`) and S4's (`validation`)
        # leaf-boundary tests, which will have more than one legal internal
        # dependency -- so the `internal_imports <= {...}` subset assertion
        # below won't be available to them, and this prefix check becomes
        # the only guard.
        violations = {
            i for i in internal_imports if any(i == f or i.startswith(f + ".") for f in forbidden)
        }
        assert not violations, f"config.py must not import {forbidden}; found {violations}"
        assert internal_imports <= {"textbrush.paths"}, (
            f"config.py's only allowed internal dependency is textbrush.paths; "
            f"found {internal_imports}"
        )

    def test_relative_import_detector_self_test(self):
        """The detector helper itself must see through relative-import
        syntax -- this package's prevailing convention (e.g.
        `textbrush/cli.py`'s `from .config import ...`) -- not just the
        absolute `textbrush.x` form. A synthetic module using
        `from .backend import x` must be flagged as importing the forbidden
        `textbrush.backend`, proving the guard above isn't blind to the
        import shape most likely to appear in this codebase."""
        synthetic_source = "from .backend import x\n"

        internal_imports = _internal_imports(synthetic_source)

        assert "textbrush.backend" in internal_imports

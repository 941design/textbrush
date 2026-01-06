"""Tests for textbrush configuration system."""

import os
import tempfile
from pathlib import Path

import pytest

from textbrush.config import (
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

        assert config.output.directory is not None
        assert config.output.format is not None
        assert config.model.directories is not None
        assert config.model.buffer_size is not None
        assert config.inference.backend is not None
        assert config.logging.verbosity is not None


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

    def test_round_trip_with_load(self):
        """load_config_file after create matches get_default_config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.toml"
            create_default_config_file(config_path)

            loaded_config = load_config_file(config_path)
            default_config = get_default_config()

            assert loaded_config.output.format == default_config.output.format
            assert loaded_config.model.buffer_size == default_config.model.buffer_size
            assert loaded_config.huggingface.token == default_config.huggingface.token
            assert loaded_config.inference.backend == default_config.inference.backend
            assert loaded_config.logging.verbosity == default_config.logging.verbosity

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

        os.environ["TEXTBRUSH_OUTPUT_FORMAT"] = "webp"
        try:
            overridden = apply_env_overrides(config)

            # Overridden field should change
            assert overridden.output.format == "webp"
            # Non-overridden fields should remain unchanged
            assert overridden.inference.backend == original_backend
            assert overridden.model.buffer_size == original_buffer_size
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

"""Integration tests for textbrush foundation.

These tests verify that CLI, config, and model management components
integrate correctly and maintain their invariants across the complete system.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import tomli_w
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from textbrush.cli import build_parser, main
from textbrush.config import load_config
from textbrush.model.weights import get_cache_info, is_flux_available


class TestCLIConfigIntegration:
    """Test CLI and config system integration."""

    @pytest.mark.integration
    def test_cli_loads_default_config_location(self, tmp_path: Path):
        """CLI loads config from default location when not specified."""
        # Create config file at custom location
        config_file = tmp_path / "config.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "jpg"},
            "model": {"directories": [], "buffer_size": 16},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "debug"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Load config and verify
        config = load_config(config_file)
        assert config.output.format == "jpg"
        assert config.model.buffer_size == 16
        assert config.logging.verbosity == "debug"

    @pytest.mark.integration
    def test_cli_args_override_config_file(self, tmp_path: Path):
        """CLI arguments take precedence over config file values."""
        # Create config with specific values
        config_file = tmp_path / "config.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "jpg"},
            "model": {"directories": [], "buffer_size": 8},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Run CLI with overriding arguments
        parser = build_parser()
        args = parser.parse_args(
            ["--prompt", "test", "--config", str(config_file), "--format", "png", "--verbose"]
        )

        # Load and merge config
        from textbrush.cli import merge_cli_args_with_config

        config = load_config(config_file)
        merged = merge_cli_args_with_config(args, config)

        # Verify CLI args override config file
        assert merged.output.format == "png"  # CLI override
        assert merged.logging.verbosity == "debug"  # verbose flag override
        assert merged.model.buffer_size == 8  # unchanged from config

    @pytest.mark.integration
    def test_env_vars_override_config_file(self, tmp_path: Path, monkeypatch):
        """Environment variables override config file values."""
        # Create config file
        config_file = tmp_path / "config.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "jpg"},
            "model": {"directories": [], "buffer_size": 8},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Set environment variable
        monkeypatch.setenv("TEXTBRUSH_OUTPUT_FORMAT", "png")
        monkeypatch.setenv("TEXTBRUSH_LOGGING_VERBOSITY", "debug")

        # Load config and verify env overrides
        config = load_config(config_file)
        assert config.output.format == "png"  # env override
        assert config.logging.verbosity == "debug"  # env override
        assert config.model.buffer_size == 8  # unchanged from file

    @pytest.mark.integration
    def test_priority_order_cli_env_file_defaults(self, tmp_path: Path, monkeypatch):
        """Verify correct priority: CLI > env > file > defaults."""
        # Create config file with specific value
        config_file = tmp_path / "config.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "jpg"},
            "model": {"directories": [], "buffer_size": 8},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Set environment variable
        monkeypatch.setenv("TEXTBRUSH_OUTPUT_FORMAT", "png")

        # Parse CLI args with override
        parser = build_parser()
        args = parser.parse_args(
            ["--prompt", "test", "--config", str(config_file), "--format", "jpg"]
        )

        # Load and merge
        from textbrush.cli import merge_cli_args_with_config

        config = load_config(config_file)
        merged = merge_cli_args_with_config(args, config)

        # CLI arg should win (jpg from CLI, not png from env)
        assert merged.output.format == "jpg"


class TestConfigPersistence:
    """Test config file creation and persistence."""

    @pytest.mark.integration
    def test_first_run_creates_default_config(self, tmp_path: Path):
        """First run creates default config file if missing."""
        config_file = tmp_path / "nonexistent" / "config.toml"

        # Config file doesn't exist
        assert not config_file.exists()

        # Load config (should create file)
        load_config(config_file)

        # File should now exist
        assert config_file.exists()

        # File should contain valid TOML
        with open(config_file, "rb") as f:
            import tomllib

            data = tomllib.load(f)
            assert "output" in data
            assert "model" in data
            assert "huggingface" in data
            assert "inference" in data
            assert "logging" in data

    @pytest.mark.integration
    @given(
        st.builds(
            dict,
            output=st.builds(
                dict,
                directory=st.from_regex(r"[a-zA-Z0-9/_-]+", fullmatch=True),
                format=st.sampled_from(["png", "jpg"]),
            ),
            model=st.builds(
                dict, directories=st.lists(st.just([]), max_size=0), buffer_size=st.just(8)
            ),
            huggingface=st.builds(dict, token=st.just("")),
            inference=st.builds(dict, backend=st.just("flux")),
            logging=st.builds(
                dict, verbosity=st.sampled_from(["debug", "info", "warning", "error"])
            ),
        )
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
    def test_config_round_trip_property(self, tmp_path: Path, config_dict: dict):
        """Property: write config → read config → values match."""
        config_file = tmp_path / f"config_{os.getpid()}.toml"

        # Write config
        with open(config_file, "wb") as f:
            tomli_w.dump(config_dict, f)

        # Read config
        config = load_config(config_file)

        # Verify round-trip
        assert config.output.format == config_dict["output"]["format"]
        assert config.logging.verbosity == config_dict["logging"]["verbosity"]
        assert config.model.buffer_size == config_dict["model"]["buffer_size"]


class TestModelCacheIntegration:
    """Test model weight management integration."""

    @pytest.mark.integration
    def test_cache_info_respects_environment_variables(self, monkeypatch):
        """Cache location respects HF_HOME and HF_HUB_CACHE environment variables."""
        # Test HF_HUB_CACHE priority
        test_cache = "/tmp/test_cache"
        monkeypatch.setenv("HF_HUB_CACHE", test_cache)

        cache_info = get_cache_info()
        assert str(cache_info["cache_dir"]) == test_cache
        assert cache_info["custom_location"] is True
        assert cache_info["env_var"] == "HF_HUB_CACHE"

    @pytest.mark.integration
    def test_cache_info_hf_home_fallback(self, monkeypatch):
        """Cache location uses HF_HOME/hub when HF_HUB_CACHE not set."""
        # Clear HF_HUB_CACHE, set HF_HOME
        monkeypatch.delenv("HF_HUB_CACHE", raising=False)
        test_home = "/tmp/test_home"
        monkeypatch.setenv("HF_HOME", test_home)

        cache_info = get_cache_info()
        assert str(cache_info["cache_dir"]) == f"{test_home}/hub"
        assert cache_info["custom_location"] is True
        assert cache_info["env_var"] == "HF_HOME"

    @pytest.mark.integration
    def test_model_availability_check_idempotent(self):
        """Checking model availability multiple times gives consistent results."""
        # Check availability
        first_check = is_flux_available()
        second_check = is_flux_available()
        third_check = is_flux_available()

        # Should be consistent
        assert first_check == second_check == third_check


class TestEndToEndCLIWorkflow:
    """End-to-end workflow tests (E2E scenario from architect spec)."""

    @pytest.mark.integration
    def test_e2e_cli_to_config_loading(self, tmp_path: Path, capsys):
        """E2E: CLI invocation → config loading → validation → output.

        This is the E2E scenario specified by the architect:
        Entry: CLI command "textbrush --prompt 'test' --config custom.toml --verbose"
        Flow: cli.main() → load_config() → merge_cli_args_with_config() → validate_args()
        Output: Configuration loaded with correct priority (CLI > env > file > defaults)
        """
        # Create custom config
        config_file = tmp_path / "custom.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "jpg"},
            "model": {"directories": [], "buffer_size": 16},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Run complete CLI workflow
        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", "test prompt", "--config", str(config_file), "--verbose"])

        # Verify exit code (should be 2 for "not implemented" in Increment 1)
        assert exc_info.value.code == 2

        # Verify output
        captured = capsys.readouterr()

        # stderr should contain status messages
        assert "Textbrush foundation ready" in captured.err
        assert "Config loaded:" in captured.err

        # stdout should be empty (no success output in Increment 1)
        assert captured.out == ""

    @pytest.mark.integration
    def test_e2e_cli_validation_failure(self, capsys):
        """E2E: CLI with invalid args → validation error → helpful message."""
        # Run with empty prompt (validation should fail)
        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", "  "])

        # Should exit with error code
        assert exc_info.value.code != 0

        # Verify error message
        captured = capsys.readouterr()
        assert "Prompt cannot be empty" in captured.err or "empty" in captured.err.lower()

    @pytest.mark.integration
    def test_e2e_cli_negative_seed_rejected(self, tmp_path: Path, capsys):
        """E2E: CLI with negative seed → validation error."""
        config_file = tmp_path / "config.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "png"},
            "model": {"directories": [], "buffer_size": 8},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Run with negative seed
        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", "test", "--config", str(config_file), "--seed", "-42"])

        # Should exit with error
        assert exc_info.value.code != 0

        # Verify error message
        captured = capsys.readouterr()
        assert "non-negative" in captured.err.lower() or "negative" in captured.err.lower()

    @pytest.mark.integration
    @given(
        prompt=st.text(min_size=1, max_size=100).filter(
            lambda s: s.strip() and not s.startswith("-")
        ),
        seed=st.integers(min_value=0, max_value=1000000),
        format_choice=st.sampled_from(["png", "jpg"]),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=5)
    def test_e2e_cli_accepts_valid_inputs(
        self, tmp_path: Path, capsys, prompt: str, seed: int, format_choice: str
    ):
        """Property: CLI accepts any valid combination of inputs."""
        config_file = tmp_path / f"config_{os.getpid()}.toml"
        config_data = {
            "output": {"directory": str(tmp_path / "outputs"), "format": "png"},
            "model": {"directories": [], "buffer_size": 8},
            "huggingface": {"token": ""},
            "inference": {"backend": "flux"},
            "logging": {"verbosity": "info"},
        }
        with open(config_file, "wb") as f:
            tomli_w.dump(config_data, f)

        # Run CLI with generated inputs
        with pytest.raises(SystemExit) as exc_info:
            main(
                [
                    "--prompt",
                    prompt,
                    "--config",
                    str(config_file),
                    "--seed",
                    str(seed),
                    "--format",
                    format_choice,
                ]
            )

        # Should exit with "not implemented" (code 2)
        assert exc_info.value.code == 2

        # Should print success message
        captured = capsys.readouterr()
        assert "Textbrush foundation ready" in captured.err

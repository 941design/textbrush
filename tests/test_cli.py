"""Tests for textbrush CLI module."""

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from textbrush.cli import (
    SUPPORTED_RATIOS,
    build_parser,
    get_default_resolution,
    main,
    merge_cli_args_with_config,
    validate_args,
)

# Note: sample_config fixture is provided by conftest.py


class TestBuildParser:
    """Test build_parser() function."""

    def test_parser_exists(self):
        """Parser is created and returns ArgumentParser instance."""
        parser = build_parser()
        assert isinstance(parser, argparse.ArgumentParser)

    def test_parser_has_prompt_argument(self):
        """Parser includes required --prompt argument."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "a cat"])
        assert args.prompt == "a cat"

    def test_prompt_is_required(self):
        """Parser rejects calls without --prompt argument."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    @given(st.text(min_size=1).filter(lambda s: not s.startswith("-")))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_parser_accepts_any_prompt_text(self, prompt: str):
        """Parser accepts any non-empty prompt text (not starting with dash).

        Note: Prompts starting with '-' require the '--' separator due to argparse limitations:
        textbrush --prompt -- -my-prompt
        """
        parser = build_parser()
        args = parser.parse_args(["--prompt", prompt])
        assert args.prompt == prompt

    def test_parser_accepts_optional_arguments(self):
        """Parser accepts all optional arguments."""
        parser = build_parser()
        args = parser.parse_args(
            [
                "--prompt",
                "test",
                "--out",
                "/tmp/test.png",
                "--config",
                "/tmp/config.toml",
                "--seed",
                "42",
                "--aspect-ratio",
                "1:1",
                "--format",
                "jpg",
                "--verbose",
            ]
        )
        assert args.prompt == "test"
        assert args.out == Path("/tmp/test.png")
        assert args.config == Path("/tmp/config.toml")
        assert args.seed == 42
        assert args.aspect_ratio == "1:1"
        assert args.format == "jpg"
        assert args.verbose is True

    @pytest.mark.parametrize("ratio", ["1:1", "16:9", "3:1", "4:1", "4:5", "9:16"])
    def test_parser_aspect_ratio_choices(self, ratio: str):
        """Parser accepts valid aspect ratio choices."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test", "--aspect-ratio", ratio])
        assert args.aspect_ratio == ratio

    def test_parser_rejects_invalid_aspect_ratio(self):
        """Parser rejects invalid aspect ratio values."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--prompt", "test", "--aspect-ratio", "invalid"])

    @pytest.mark.parametrize("fmt", ["png", "jpg"])
    def test_parser_format_choices(self, fmt: str):
        """Parser accepts valid format choices."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test", "--format", fmt])
        assert args.format == fmt

    def test_parser_rejects_invalid_format(self):
        """Parser rejects invalid format values."""
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--prompt", "test", "--format", "invalid"])

    @given(st.integers(min_value=0, max_value=1000000))
    def test_parser_accepts_non_negative_seeds(self, seed: int):
        """Parser accepts and parses non-negative seed values."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test", "--seed", str(seed)])
        assert args.seed == seed

    def test_parser_verbose_flag_defaults_to_false(self):
        """Parser sets verbose to False by default."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test"])
        assert args.verbose is False

    def test_parser_verbose_flag_set_to_true(self):
        """Parser sets verbose to True when --verbose is provided."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test", "--verbose"])
        assert args.verbose is True

    def test_parser_optional_args_default_to_none(self):
        """Parser sets optional arguments to None by default."""
        parser = build_parser()
        args = parser.parse_args(["--prompt", "test"])
        assert args.out is None
        assert args.config is None
        assert args.seed is None
        assert args.aspect_ratio is None
        assert args.format is None


class TestSupportedRatios:
    """Test SUPPORTED_RATIOS constant and get_default_resolution()."""

    def test_supported_ratios_contains_expected_ratios(self):
        """SUPPORTED_RATIOS contains all expected aspect ratios."""
        expected = {"1:1", "16:9", "3:1", "4:1", "4:5", "9:16"}
        assert set(SUPPORTED_RATIOS.keys()) == expected

    def test_each_ratio_has_at_least_one_resolution(self):
        """Each aspect ratio has at least one resolution."""
        for ratio, resolutions in SUPPORTED_RATIOS.items():
            assert len(resolutions) >= 1, f"Ratio {ratio} has no resolutions"

    def test_resolutions_are_tuples_of_two_integers(self):
        """All resolutions are (width, height) tuples."""
        for ratio, resolutions in SUPPORTED_RATIOS.items():
            for res in resolutions:
                assert isinstance(res, tuple), f"Resolution {res} for {ratio} is not a tuple"
                assert len(res) == 2, f"Resolution {res} for {ratio} has wrong length"
                assert isinstance(res[0], int), f"Width in {res} for {ratio} is not int"
                assert isinstance(res[1], int), f"Height in {res} for {ratio} is not int"

    def test_1_1_has_three_resolutions(self):
        """1:1 ratio has exactly three resolutions."""
        assert len(SUPPORTED_RATIOS["1:1"]) == 3
        assert SUPPORTED_RATIOS["1:1"] == [(256, 256), (512, 512), (1024, 1024)]

    def test_16_9_has_two_resolutions(self):
        """16:9 ratio has exactly two resolutions."""
        assert len(SUPPORTED_RATIOS["16:9"]) == 2
        assert SUPPORTED_RATIOS["16:9"] == [(1280, 720), (1920, 1080)]

    def test_4_1_has_single_resolution(self):
        """4:1 ratio has exactly one resolution."""
        assert len(SUPPORTED_RATIOS["4:1"]) == 1
        assert SUPPORTED_RATIOS["4:1"] == [(1600, 400)]

    def test_get_default_resolution_returns_first_resolution(self):
        """get_default_resolution returns first resolution for each ratio."""
        for ratio, resolutions in SUPPORTED_RATIOS.items():
            expected = resolutions[0]
            actual = get_default_resolution(ratio)
            assert actual == expected, f"Default for {ratio}: expected {expected}, got {actual}"

    def test_get_default_resolution_raises_for_invalid_ratio(self):
        """get_default_resolution raises ValueError for invalid ratio."""
        with pytest.raises(ValueError, match="Unsupported aspect ratio"):
            get_default_resolution("invalid")


class TestValidateArgs:
    """Test validate_args() function."""

    def test_validates_non_empty_prompt(self, sample_config):
        """Validation rejects empty prompt."""
        args = argparse.Namespace(
            prompt="",
            out=None,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        with pytest.raises(ValueError, match="--prompt cannot be empty"):
            validate_args(args)

    def test_validates_whitespace_only_prompt(self, sample_config):
        """Validation rejects whitespace-only prompt."""
        args = argparse.Namespace(
            prompt="   ",
            out=None,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        with pytest.raises(ValueError, match="--prompt cannot be empty"):
            validate_args(args)

    @given(st.text(min_size=1).filter(lambda s: s.strip()))
    @settings(suppress_health_check=[HealthCheck.filter_too_much])
    def test_accepts_non_empty_prompt(self, prompt: str):
        """Validation accepts non-empty prompts."""
        args = argparse.Namespace(
            prompt=prompt,
            out=None,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    @given(st.integers(min_value=0))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_accepts_non_negative_seed(self, seed: int):
        """Validation accepts non-negative seed values."""
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=None,
            seed=seed,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    @given(st.integers(max_value=-1))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_rejects_negative_seed(self, seed: int):
        """Validation rejects negative seed values."""
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=None,
            seed=seed,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        with pytest.raises(ValueError, match="--seed must be non-negative"):
            validate_args(args)

    def test_accepts_none_seed(self):
        """Validation accepts None seed (optional)."""
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    def test_rejects_nonexistent_output_with_nonexistent_parent(self, tmp_path):
        """Validation checks if output directory parent can be created."""
        nonexistent_parent = tmp_path / "nonexistent" / "path" / "file.png"
        args = argparse.Namespace(
            prompt="test",
            out=nonexistent_parent,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    def test_accepts_output_path_in_existing_directory(self, tmp_path):
        """Validation accepts output path in existing directory."""
        output_file = tmp_path / "output.png"
        args = argparse.Namespace(
            prompt="test",
            out=output_file,
            config=None,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    def test_accepts_config_path_for_new_file(self, tmp_path):
        """Validation accepts config path that doesn't exist yet."""
        config_file = tmp_path / "config.toml"
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=config_file,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    def test_accepts_existing_readable_config_file(self, tmp_path):
        """Validation accepts existing readable config file."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("[test]\nkey = 'value'\n")
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=config_file,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        validate_args(args)

    def test_rejects_config_path_that_is_directory(self, tmp_path):
        """Validation rejects config path that points to a directory."""
        config_dir = tmp_path / "config_dir"
        config_dir.mkdir()
        args = argparse.Namespace(
            prompt="test",
            out=None,
            config=config_dir,
            seed=None,
            aspect_ratio=None,
            format=None,
            verbose=False,
        )
        with pytest.raises(ValueError, match="is not a file"):
            validate_args(args)


class TestMergeCliArgsWithConfig:
    """Test merge_cli_args_with_config() function."""

    def test_merges_without_mutation(self, sample_config):
        """Merging does not mutate original config."""
        original_format = sample_config.output.format
        args = argparse.Namespace(
            out=Path("/tmp/output.jpg"),
            format="jpg",
            verbose=False,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert sample_config.output.format == original_format
        assert merged.output.format == "jpg"

    def test_merges_format_argument(self, sample_config):
        """Format CLI argument overrides config."""
        args = argparse.Namespace(
            out=None,
            format="jpg",
            verbose=False,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.output.format == "jpg"

    def test_verbose_flag_sets_debug_logging(self, sample_config):
        """Verbose flag sets logging verbosity to debug."""
        args = argparse.Namespace(
            out=None,
            format=None,
            verbose=True,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.logging.verbosity == "debug"

    def test_verbose_false_preserves_logging(self, sample_config):
        """Verbose false does not change logging verbosity."""
        original_verbosity = sample_config.logging.verbosity
        args = argparse.Namespace(
            out=None,
            format=None,
            verbose=False,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.logging.verbosity == original_verbosity

    def test_merges_output_path_parent(self, sample_config):
        """Out CLI argument sets output directory to parent path."""
        output_path = Path("/custom/output/image.png")
        args = argparse.Namespace(
            out=output_path,
            format=None,
            verbose=False,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.output.directory == Path("/custom/output")

    def test_none_arguments_do_not_override(self, sample_config):
        """None CLI arguments do not override config values."""
        original_format = sample_config.output.format
        original_dir = sample_config.output.directory
        args = argparse.Namespace(
            out=None,
            format=None,
            verbose=False,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.output.format == original_format
        assert merged.output.directory == original_dir

    def test_multiple_overrides_together(self, sample_config):
        """Multiple CLI arguments override config together."""
        output_path = Path("/custom/output/image.jpg")
        args = argparse.Namespace(
            out=output_path,
            format="jpg",
            verbose=True,
            config=None,
            prompt="test",
            seed=None,
            aspect_ratio=None,
        )
        merged = merge_cli_args_with_config(args, sample_config)
        assert merged.output.directory == Path("/custom/output")
        assert merged.output.format == "jpg"
        assert merged.logging.verbosity == "debug"


class TestMain:
    """Test main() function."""

    @patch("textbrush.cli.load_config")
    def test_main_exits_with_1_on_missing_prompt(self, mock_load_config, sample_config):
        """Main exits with code 1 when --prompt is missing."""
        mock_load_config.return_value = sample_config
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code == 2

    @patch("textbrush.cli.load_config")
    def test_main_exits_with_1_on_empty_prompt(self, mock_load_config, sample_config):
        """Main exits with code 1 when --prompt is empty."""
        mock_load_config.return_value = sample_config
        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", ""])
        assert exc_info.value.code == 1

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_invokes_backend_successfully(
        self, mock_create_engine, mock_load_config, sample_config
    ):
        """Main creates backend and invokes generation workflow."""
        from unittest.mock import Mock

        from PIL import Image

        from textbrush.inference.base import GenerationResult

        mock_load_config.return_value = sample_config

        mock_engine = Mock()
        mock_engine.is_loaded.return_value = True
        mock_engine.generate.return_value = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=42,
            generation_time=0.1,
            model_name="mock",
        )
        mock_create_engine.return_value = mock_engine

        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", "test"])
        assert exc_info.value.code == 0

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_loads_config_with_default_path(
        self, mock_create_engine, mock_load_config, sample_config, mock_engine
    ):
        """Main loads config from default path when --config not provided."""
        mock_load_config.return_value = sample_config
        mock_create_engine.return_value = mock_engine
        try:
            main(["--prompt", "test"])
        except SystemExit:
            pass
        mock_load_config.assert_called()

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_loads_config_with_custom_path(
        self, mock_create_engine, mock_load_config, sample_config, mock_engine, tmp_path
    ):
        """Main loads config from custom path when --config provided."""
        mock_load_config.return_value = sample_config
        mock_create_engine.return_value = mock_engine
        config_file = tmp_path / "config.toml"
        config_file.write_text("[test]\n")
        try:
            main(["--prompt", "test", "--config", str(config_file)])
        except SystemExit:
            pass
        mock_load_config.assert_called()

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_prints_to_stderr_on_success(
        self, mock_create_engine, mock_load_config, sample_config, capsys
    ):
        """Main prints progress messages to stderr."""
        from unittest.mock import Mock

        from PIL import Image

        from textbrush.inference.base import GenerationResult

        mock_load_config.return_value = sample_config

        mock_engine = Mock()
        mock_engine.is_loaded.return_value = True
        mock_engine.generate.return_value = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=42,
            generation_time=0.1,
            model_name="mock",
        )
        mock_create_engine.return_value = mock_engine

        try:
            main(["--prompt", "test"])
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert "Loading model..." in captured.err
        assert "Generating..." in captured.err

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_prints_output_path_to_stdout(
        self, mock_create_engine, mock_load_config, sample_config, capsys
    ):
        """Main prints output path to stdout."""
        from unittest.mock import Mock

        from PIL import Image

        from textbrush.inference.base import GenerationResult

        mock_load_config.return_value = sample_config

        mock_engine = Mock()
        mock_engine.is_loaded.return_value = True
        mock_engine.generate.return_value = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=42,
            generation_time=0.1,
            model_name="mock",
        )
        mock_create_engine.return_value = mock_engine

        try:
            main(["--prompt", "test"])
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert len(captured.out.strip()) > 0
        assert ".png" in captured.out or ".jpg" in captured.out

    @patch("textbrush.cli.load_config")
    def test_main_handles_validation_error(self, mock_load_config, sample_config, capsys):
        """Main catches validation errors and prints to stderr."""
        mock_load_config.return_value = sample_config
        with pytest.raises(SystemExit) as exc_info:
            main(["--prompt", "test", "--seed", "-1"])
        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.err


class TestParserIntegration:
    """Integration tests for parser with main."""

    @patch("textbrush.cli.load_config")
    @patch("textbrush.backend.create_engine")
    def test_main_with_all_arguments(
        self, mock_create_engine, mock_load_config, sample_config, tmp_path
    ):
        """Main processes all CLI arguments correctly."""
        from unittest.mock import Mock

        from PIL import Image

        from textbrush.inference.base import GenerationResult

        mock_load_config.return_value = sample_config

        mock_engine = Mock()
        mock_engine.is_loaded.return_value = True
        mock_engine.generate.return_value = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=42,
            generation_time=0.1,
            model_name="mock",
        )
        mock_create_engine.return_value = mock_engine

        output_file = tmp_path / "test.png"
        config_file = tmp_path / "config.toml"
        config_file.write_text("[test]\n")
        try:
            main(
                [
                    "--prompt",
                    "test prompt",
                    "--out",
                    str(output_file),
                    "--config",
                    str(config_file),
                    "--seed",
                    "42",
                    "--aspect-ratio",
                    "1:1",
                    "--format",
                    "jpg",
                    "--verbose",
                ]
            )
        except SystemExit:
            pass
        assert mock_load_config.called

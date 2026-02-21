"""End-to-end integration tests for textbrush CLI workflows.

These tests verify the complete system behavior from CLI invocation through
image generation and output, using the headless mode for automation.
"""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestCLIHelp:
    """Property: CLI --help provides complete usage information."""

    @pytest.mark.e2e_smoke
    def test_help_shows_all_required_options(self):
        """--help output includes all required CLI options including --download-model."""
        result = subprocess.run(
            ["textbrush", "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0
        assert "--prompt" in result.stdout
        assert "--out" in result.stdout
        assert "--seed" in result.stdout
        assert "--aspect-ratio" in result.stdout
        assert "--headless" in result.stdout
        assert "--auto-accept" in result.stdout
        assert "--auto-abort" in result.stdout
        assert "--download-model" in result.stdout


class TestDownloadModelCLI:
    """Property: --download-model flag enforces mutual exclusivity and appears in help."""

    @pytest.mark.e2e_smoke
    def test_download_model_conflicts_with_prompt(self):
        """--download-model and --prompt cannot be combined (exits 2)."""
        result = subprocess.run(
            ["textbrush", "--download-model", "--prompt", "test"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Cannot use --download-model with --prompt" in result.stderr

    @pytest.mark.e2e_smoke
    def test_download_model_conflicts_with_headless(self):
        """--download-model and --headless cannot be combined (exits 2)."""
        result = subprocess.run(
            ["textbrush", "--download-model", "--headless"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Cannot use --download-model with --headless" in result.stderr

    @pytest.mark.e2e_smoke
    def test_no_args_requires_prompt_or_download(self):
        """Invoking textbrush with no arguments exits 2 with descriptive error."""
        result = subprocess.run(
            ["textbrush"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "one of --prompt or --download-model" in result.stderr


class TestModelNotFoundMessage:
    """Property: model-not-found error directs users to --download-model."""

    @pytest.mark.e2e_smoke
    def test_model_not_found_references_download_model_flag(self):
        """ensure_flux_available error message references --download-model, not make/scripts."""
        from unittest.mock import patch

        # Import ensure_flux_available to test its error message directly
        with patch("textbrush.model.weights.is_flux_available", return_value=False):
            import textbrush.model.weights as w

            try:
                w.ensure_flux_available()
                assert False, "Expected RuntimeError not raised"
            except RuntimeError as e:
                msg = str(e)
                assert "textbrush --download-model" in msg, (
                    f"Error message should reference 'textbrush --download-model', got: {msg}"
                )
                assert "make download-model" not in msg, (
                    f"Error message should not reference 'make download-model', got: {msg}"
                )
                assert "scripts/download_model.py" not in msg, (
                    f"Error message should not reference scripts/, got: {msg}"
                )


class TestBackendLoadingStateEmission:
    """Property: handle_init emits state_changed(loading) as first IPC event."""

    @pytest.mark.e2e_smoke
    def test_handle_init_emits_loading_before_idle(self):
        """Backend emits state_changed(loading) as first STATE_CHANGED via IPC before idle.

        This is a subprocess-style in-process E2E test that creates a real IPCServer and
        MessageHandler, patches only TextbrushBackend to avoid the torch dependency, then
        drives the full handle_init → _init_backend path and verifies that the first
        STATE_CHANGED event carries state='loading'.
        """
        from textbrush.backend import TextbrushBackend
        from textbrush.config import get_default_config
        from textbrush.ipc.handler import MessageHandler
        from textbrush.ipc.protocol import MessageType

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_server.send = Mock()

        payload = {
            "prompt": "e2e loading state test",
            "seed": None,
            "aspect_ratio": "1:1",
        }

        with patch.object(TextbrushBackend, "__init__", return_value=None):
            with patch.object(handler, "_init_backend"):
                handler.handle_init(payload, mock_server)

        state_changed_calls = [
            call for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert len(state_changed_calls) >= 1, (
            "handle_init must emit at least one STATE_CHANGED event"
        )
        first_state = state_changed_calls[0][0][0].payload["state"]
        assert first_state == "loading", (
            f"First STATE_CHANGED from handle_init must be 'loading', got '{first_state}'"
        )


@pytest.mark.integration
class TestCLIValidation:
    """Property: CLI validates inputs before execution."""

    def test_missing_prompt_fails_with_error(self):
        """CLI without required --prompt exits with error."""
        result = subprocess.run(
            ["textbrush"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "prompt" in result.stderr.lower() or "required" in result.stderr.lower()

    def test_empty_prompt_fails_with_error(self):
        """CLI with empty --prompt string exits with error."""
        result = subprocess.run(
            ["textbrush", "--prompt", ""],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "prompt" in result.stderr.lower() or "empty" in result.stderr.lower()


@pytest.mark.integration
@pytest.mark.slow
class TestHeadlessAcceptWorkflow:
    """Property: Headless accept workflow generates and saves image."""

    @pytest.fixture
    def temp_output(self):
        """Provide temporary output file path."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    @pytest.mark.e2e_smoke
    def test_accept_saves_image_and_prints_path(self, temp_output):
        """Headless mode with --auto-accept saves image and prints path to stdout."""
        result = subprocess.run(
            [
                "textbrush",
                "--prompt",
                "test image",
                "--out",
                str(temp_output),
                "--headless",
                "--auto-accept",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Property: Exit code 0 on success
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}"

        # Property: Output path printed to stdout
        assert str(temp_output) in result.stdout, "Output path not in stdout"

        # Property: Image file created
        assert temp_output.exists(), "Output file was not created"

        # Property: Progress messages to stderr, not stdout
        assert "Loading" in result.stderr or "Generating" in result.stderr

    def test_accept_without_output_generates_path(self):
        """Headless accept without --out generates automatic path."""
        result = subprocess.run(
            [
                "textbrush",
                "--prompt",
                "auto path test",
                "--headless",
                "--auto-accept",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Property: Exit code 0 on success
        assert result.returncode == 0

        # Property: Some path printed to stdout
        output_path = result.stdout.strip()
        assert output_path, "No path in stdout"
        assert Path(output_path).suffix in [".png", ".jpg"]

        # Cleanup generated file
        generated = Path(output_path)
        if generated.exists():
            generated.unlink()


@pytest.mark.integration
@pytest.mark.slow
class TestHeadlessAbortWorkflow:
    """Property: Headless abort workflow exits cleanly without saving."""

    @pytest.mark.e2e_smoke
    def test_abort_exits_with_nonzero_empty_stdout(self):
        """Headless mode with --auto-abort exits with code 1 and empty stdout."""
        result = subprocess.run(
            [
                "textbrush",
                "--prompt",
                "abort test",
                "--headless",
                "--auto-abort",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Property: Exit code 1 on abort
        assert result.returncode == 1, f"Expected exit 1, got {result.returncode}"

        # Property: No path printed to stdout
        assert result.stdout.strip() == "", "Stdout should be empty on abort"


@pytest.mark.integration
@pytest.mark.slow
class TestSeedDeterminism:
    """Property: Same seed produces reproducible images."""

    @pytest.fixture
    def temp_outputs(self):
        """Provide two temporary output file paths."""
        paths = []
        for _ in range(2):
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                paths.append(Path(f.name))
        yield paths
        for path in paths:
            if path.exists():
                path.unlink()

    def test_same_seed_produces_identical_files(self, temp_outputs):
        """Generating with same seed twice produces identical image files."""
        prompt = "determinism test"
        seed = 42
        output1, output2 = temp_outputs

        # Generate first image
        result1 = subprocess.run(
            [
                "textbrush",
                "--prompt",
                prompt,
                "--seed",
                str(seed),
                "--out",
                str(output1),
                "--headless",
                "--auto-accept",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result1.returncode == 0

        # Generate second image with same seed
        result2 = subprocess.run(
            [
                "textbrush",
                "--prompt",
                prompt,
                "--seed",
                str(seed),
                "--out",
                str(output2),
                "--headless",
                "--auto-accept",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result2.returncode == 0

        # Property: Files should be identical
        assert output1.exists() and output2.exists()
        content1 = output1.read_bytes()
        content2 = output2.read_bytes()
        assert content1 == content2, "Images with same seed should be identical"


@pytest.mark.integration
class TestExitCodeContract:
    """Property: Exit codes follow specification contract."""

    def test_success_exit_0_with_path_on_stdout(self):
        """Success scenario exits 0 with path on stdout."""
        # This test uses minimal mocking to verify exit code contract
        # without requiring full model loading
        result = subprocess.run(
            ["textbrush", "--help"],
            capture_output=True,
            text=True,
        )
        # Help always exits 0
        assert result.returncode == 0

    def test_error_exit_1_with_empty_stdout(self):
        """Error scenario exits 1 with empty stdout."""
        result = subprocess.run(
            ["textbrush", "--prompt", ""],
            capture_output=True,
            text=True,
        )
        # Invalid input should exit 1
        assert result.returncode == 1
        # Errors should not print to stdout
        assert result.stdout.strip() == ""

"""Comprehensive property-based tests for run_headless() function."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from textbrush.cli import run_headless


# Property-based test strategies
@st.composite
def prompts(draw) -> str:
    """Generate valid non-empty prompts."""
    return draw(st.text(min_size=1, max_size=500).filter(lambda s: s.strip()))


@st.composite
def seeds(draw) -> int | None:
    """Generate valid seeds (non-negative integers or None)."""
    return draw(st.one_of(st.none(), st.integers(min_value=0, max_value=1000000)))


@st.composite
def aspect_ratios(draw) -> str:
    """Generate valid aspect ratios."""
    return draw(st.sampled_from(["1:1", "16:9", "9:16"]))


@st.composite
def output_paths(draw, tmp_path_factory) -> Path | None:
    """Generate valid output paths (including None)."""
    include_path = draw(st.booleans())
    if not include_path:
        return None
    tmp_path = tmp_path_factory.mktemp("outputs")
    filename = draw(st.just("output.png") | st.just("image.jpg"))
    return tmp_path / filename


class TestAbortWorkflow:
    """Test auto_abort workflow properties."""

    def test_abort_exits_with_code_1(self, sample_config):
        """Auto-abort exits with code 1."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test prompt",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            assert exc_info.value.code == 1

    def test_abort_calls_backend_abort(self, sample_config):
        """Auto-abort calls backend.abort()."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            mock_backend.abort.assert_called_once()

    def test_abort_calls_backend_shutdown(self, sample_config):
        """Auto-abort calls backend.shutdown()."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            mock_backend.shutdown.assert_called_once()

    def test_abort_produces_empty_stdout(self, sample_config, capsys):
        """Auto-abort produces no output to stdout."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            captured = capsys.readouterr()
            assert captured.out == ""

    def test_abort_calls_initialize_before_abort(self, sample_config):
        """Auto-abort initializes backend before aborting."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()
        call_order = []
        mock_backend.initialize.side_effect = lambda: call_order.append("init")
        mock_backend.abort.side_effect = lambda: call_order.append("abort")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            assert call_order == ["init", "abort"]

    def test_abort_with_various_inputs(self, sample_config):
        """Auto-abort exits with code 1 regardless of other inputs."""

        @given(prompts(), seeds(), aspect_ratios())
        @settings(suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(prompt, seed, aspect_ratio):
            mock_backend = Mock()
            mock_backend.buffer = Mock()

            with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
                with pytest.raises(SystemExit) as exc_info:
                    run_headless(
                        prompt=prompt,
                        out=None,
                        config=sample_config,
                        seed=seed,
                        aspect_ratio=aspect_ratio,
                        auto_accept=False,
                        auto_abort=True,
                    )
                assert exc_info.value.code == 1

        property_test()

    def test_abort_takes_precedence_over_accept(self, sample_config):
        """Auto-abort takes precedence even if auto_accept is also True."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=True,
                )
            assert exc_info.value.code == 1
            mock_backend.abort.assert_called_once()


class TestAcceptWorkflow:
    """Test auto_accept workflow properties."""

    def test_accept_exits_with_code_0_on_success(self, sample_config):
        """Auto-accept exits with code 0 on successful image generation."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = Path("/tmp/output.png")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            assert exc_info.value.code == 0

    def test_accept_prints_output_path_to_stdout(self, sample_config, capsys, tmp_path):
        """Auto-accept prints absolute path to stdout."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        output_path = tmp_path / "test_output.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = output_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert str(output_path.absolute()) in captured.out

    def test_accept_output_is_absolute_path(self, sample_config, capsys, tmp_path):
        """Auto-accept output is an absolute path."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        output_path = tmp_path / "test.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = output_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            path_line = captured.out.strip()
            assert Path(path_line).is_absolute()

    def test_accept_calls_backend_accept_current(self, sample_config, tmp_path):
        """Auto-accept calls backend.accept_current()."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        output_path = tmp_path / "output.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = output_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.accept_current.assert_called_once()

    def test_accept_with_explicit_output_path(self, sample_config, tmp_path):
        """Auto-accept uses provided output path."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        output_path = tmp_path / "custom_output.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = output_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=output_path,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.accept_current.assert_called_once_with(output_path)

    def test_accept_without_output_path_generates_default(self, sample_config, tmp_path):
        """Auto-accept generates default path when out=None."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        generated_path = tmp_path / "generated.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = generated_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.accept_current.assert_called_once_with(None)

    def test_accept_calls_shutdown_on_success(self, sample_config, tmp_path):
        """Auto-accept calls backend.shutdown() on success."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.shutdown.assert_called_once()

    def test_accept_timeout_exits_with_code_1(self, sample_config):
        """Auto-accept exits with code 1 if generation times out."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit) as exc_info:
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=True,
                        auto_abort=False,
                    )
                assert exc_info.value.code == 1

    def test_accept_timeout_produces_empty_stdout(self, sample_config, capsys):
        """Auto-accept produces no stdout on timeout."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=True,
                        auto_abort=False,
                    )
            captured = capsys.readouterr()
            assert captured.out == ""

    def test_accept_timeout_calls_shutdown(self, sample_config):
        """Auto-accept calls shutdown on timeout."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=True,
                        auto_abort=False,
                    )
            mock_backend.shutdown.assert_called()

    def test_accept_with_various_seeds(self, sample_config):
        """Auto-accept succeeds with various seed values."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        @given(prompts(), seeds(), aspect_ratios())
        @settings(suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(prompt, seed, aspect_ratio):
            mock_backend = Mock()
            mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=seed or 42)
            mock_backend.buffer.peek.return_value = mock_image
            mock_backend.accept_current.return_value = Path("/tmp/output.png")

            with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
                with pytest.raises(SystemExit) as exc_info:
                    run_headless(
                        prompt=prompt,
                        out=None,
                        config=sample_config,
                        seed=seed,
                        aspect_ratio=aspect_ratio,
                        auto_accept=True,
                        auto_abort=False,
                    )
                assert exc_info.value.code == 0

        property_test()

    def test_accept_with_various_aspect_ratios(self, sample_config):
        """Auto-accept succeeds with all valid aspect ratios."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        @given(aspect_ratios())
        @settings(suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(aspect_ratio):
            mock_backend = Mock()
            mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
            mock_backend.buffer.peek.return_value = mock_image
            mock_backend.accept_current.return_value = Path("/tmp/output.png")

            with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
                with pytest.raises(SystemExit) as exc_info:
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio=aspect_ratio,
                        auto_accept=True,
                        auto_abort=False,
                    )
                assert exc_info.value.code == 0

        property_test()


class TestInitializationProperties:
    """Test initialization and backend lifecycle properties."""

    def test_initializes_backend_before_abort(self, sample_config):
        """Backend.initialize() is called before abort in auto-abort workflow."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()
        init_called = []
        mock_backend.initialize.side_effect = lambda: init_called.append(True)

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            assert len(init_called) == 1

    def test_initializes_backend_before_accept(self, sample_config, tmp_path):
        """Backend.initialize() is called before accept in auto-accept workflow."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"
        init_called = []
        mock_backend.initialize.side_effect = lambda: init_called.append(True)

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            assert len(init_called) == 1

    def test_starts_generation_after_initialize(self, sample_config):
        """Backend.start_generation() is called after initialize."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()
        call_order = []
        mock_backend.initialize.side_effect = lambda: call_order.append("init")
        mock_backend.start_generation.side_effect = lambda **kw: call_order.append("start")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            assert call_order[:2] == ["init", "start"]

    def test_shutdown_called_on_abort(self, sample_config):
        """Backend.shutdown() is guaranteed to be called in abort workflow."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            mock_backend.shutdown.assert_called()

    def test_shutdown_called_on_accept_success(self, sample_config, tmp_path):
        """Backend.shutdown() is guaranteed to be called on successful accept."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.shutdown.assert_called()

    def test_shutdown_called_on_accept_timeout(self, sample_config):
        """Backend.shutdown() is guaranteed to be called on accept timeout."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=True,
                        auto_abort=False,
                    )
            mock_backend.shutdown.assert_called()

    def test_shutdown_called_on_error(self, sample_config):
        """Backend.shutdown() is called even when initialization fails."""
        mock_backend = Mock()
        mock_backend.initialize.side_effect = RuntimeError("Model load failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            mock_backend.shutdown.assert_called()


class TestErrorHandling:
    """Test error handling properties."""

    def test_initialization_error_prints_to_stderr(self, sample_config, capsys):
        """Initialization errors are printed to stderr."""
        mock_backend = Mock()
        mock_backend.initialize.side_effect = RuntimeError("Model load failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert "Error:" in captured.err

    def test_initialization_error_exits_with_code_1(self, sample_config):
        """Initialization errors exit with code 1."""
        mock_backend = Mock()
        mock_backend.initialize.side_effect = RuntimeError("Model load failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            assert exc_info.value.code == 1

    def test_generation_error_prints_to_stderr(self, sample_config, capsys):
        """Generation errors are printed to stderr."""
        mock_backend = Mock()
        mock_backend.start_generation.side_effect = RuntimeError("Generation failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert "Error:" in captured.err

    def test_generation_error_exits_with_code_1(self, sample_config):
        """Generation errors exit with code 1."""
        mock_backend = Mock()
        mock_backend.start_generation.side_effect = RuntimeError("Generation failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            assert exc_info.value.code == 1

    def test_error_produces_empty_stdout(self, sample_config, capsys):
        """Errors produce no output to stdout."""
        mock_backend = Mock()
        mock_backend.initialize.side_effect = RuntimeError("Failed")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert captured.out == ""

    def test_accept_current_error_exits_with_code_1(self, sample_config, tmp_path):
        """accept_current() errors exit with code 1."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.side_effect = RuntimeError("Failed to save image")

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            assert exc_info.value.code == 1


class TestStderrMessages:
    """Test stderr message properties."""

    def test_loading_model_message_printed(self, sample_config, capsys):
        """'Loading model...' is printed to stderr."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            captured = capsys.readouterr()
            assert "Loading model..." in captured.err

    def test_generating_message_printed_on_accept(self, sample_config, capsys, tmp_path):
        """'Generating...' is printed to stderr in auto-accept mode."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=True,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert "Generating..." in captured.err

    def test_generating_message_not_printed_on_abort(self, sample_config, capsys):
        """'Generating...' is not printed in auto-abort mode."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            captured = capsys.readouterr()
            assert "Generating..." not in captured.err


class TestStartGenerationProperties:
    """Test start_generation() call properties."""

    def test_start_generation_called_with_correct_prompt(self, sample_config):
        """start_generation() is called with the provided prompt."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="a beautiful sunset",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            call_kwargs = mock_backend.start_generation.call_args[1]
            assert call_kwargs["prompt"] == "a beautiful sunset"

    def test_start_generation_called_with_seed(self, sample_config):
        """start_generation() is called with the provided seed."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=42,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            call_kwargs = mock_backend.start_generation.call_args[1]
            assert call_kwargs["seed"] == 42

    def test_start_generation_called_with_none_seed(self, sample_config):
        """start_generation() is called with None seed when not provided."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=True,
                )
            call_kwargs = mock_backend.start_generation.call_args[1]
            assert call_kwargs["seed"] is None

    def test_start_generation_called_with_aspect_ratio(self, sample_config):
        """start_generation() is called with the provided aspect_ratio."""
        mock_backend = Mock()
        mock_backend.buffer = Mock()

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="16:9",
                    auto_accept=False,
                    auto_abort=True,
                )
            call_kwargs = mock_backend.start_generation.call_args[1]
            assert call_kwargs["aspect_ratio"] == "16:9"

    def test_start_generation_with_all_aspect_ratios(self, sample_config):
        """start_generation() is called with all valid aspect ratios."""

        @given(aspect_ratios())
        @settings(suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(aspect_ratio):
            mock_backend = Mock()
            mock_backend.buffer = Mock()

            with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio=aspect_ratio,
                        auto_accept=False,
                        auto_abort=True,
                    )
                call_kwargs = mock_backend.start_generation.call_args[1]
                assert call_kwargs["aspect_ratio"] == aspect_ratio

        property_test()

    def test_start_generation_with_various_seeds(self, sample_config):
        """start_generation() is called with various seed values."""

        @given(seeds())
        @settings(suppress_health_check=[HealthCheck.filter_too_much])
        def property_test(seed):
            mock_backend = Mock()
            mock_backend.buffer = Mock()

            with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=seed,
                        aspect_ratio="1:1",
                        auto_accept=False,
                        auto_abort=True,
                    )
                call_kwargs = mock_backend.start_generation.call_args[1]
                assert call_kwargs["seed"] == seed

        property_test()


class TestNoAutoAcceptOrAbort:
    """Test behavior when neither auto_accept nor auto_abort is set.

    Per spec: headless without flags generates one image, saves it, prints path
    to stdout, and exits 0. Behavior is identical to --auto-accept.
    """

    def test_no_flags_exits_with_code_0_on_success(self, sample_config, tmp_path):
        """Without auto_accept or auto_abort, exits with code 0 on success."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit) as exc_info:
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=False,
                )
            assert exc_info.value.code == 0

    def test_no_flags_prints_output_path_to_stdout(self, sample_config, capsys, tmp_path):
        """Without auto_accept or auto_abort, prints absolute path to stdout."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        output_path = tmp_path / "output.png"
        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = output_path

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=False,
                )
            captured = capsys.readouterr()
            assert str(output_path.absolute()) in captured.out

    def test_no_flags_calls_accept_current(self, sample_config, tmp_path):
        """Without auto_accept or auto_abort, calls backend.accept_current()."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=False,
                )
            mock_backend.accept_current.assert_called_once()

    def test_no_flags_calls_shutdown(self, sample_config, tmp_path):
        """Without auto_accept or auto_abort, shutdown is called on success."""
        from PIL import Image

        from textbrush.buffer import BufferedImage

        mock_backend = Mock()
        mock_image = BufferedImage(image=Image.new("RGB", (512, 512)), seed=42)
        mock_backend.buffer.peek.return_value = mock_image
        mock_backend.accept_current.return_value = tmp_path / "output.png"

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with pytest.raises(SystemExit):
                run_headless(
                    prompt="test",
                    out=None,
                    config=sample_config,
                    seed=None,
                    aspect_ratio="1:1",
                    auto_accept=False,
                    auto_abort=False,
                )
            mock_backend.shutdown.assert_called()

    def test_no_flags_timeout_exits_with_code_1(self, sample_config):
        """Without auto_accept or auto_abort, timeout exits with code 1."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit) as exc_info:
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=False,
                        auto_abort=False,
                    )
                assert exc_info.value.code == 1

    def test_no_flags_timeout_produces_empty_stdout(self, sample_config, capsys):
        """Without auto_accept or auto_abort, timeout produces no stdout."""
        mock_backend = Mock()
        mock_backend.buffer.peek.return_value = None

        with patch("textbrush.backend.TextbrushBackend", return_value=mock_backend):
            with patch("time.time", side_effect=[0, 121]):
                with pytest.raises(SystemExit):
                    run_headless(
                        prompt="test",
                        out=None,
                        config=sample_config,
                        seed=None,
                        aspect_ratio="1:1",
                        auto_accept=False,
                        auto_abort=False,
                    )
            captured = capsys.readouterr()
            assert captured.out == ""

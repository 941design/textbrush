"""Property-based tests for TextbrushBackend.start_generation()."""

from unittest.mock import MagicMock, Mock

import hypothesis.strategies as st
from hypothesis import given, settings

from textbrush.backend import TextbrushBackend
from textbrush.config import Config, InferenceConfig, ModelConfig
from textbrush.inference.base import GenerationOptions
from textbrush.worker import GenerationWorker


def create_mock_config():
    """Create a properly structured mock config."""
    mock_config = Mock(spec=Config)
    mock_config.inference = Mock(spec=InferenceConfig)
    mock_config.inference.backend = "flux"
    mock_config.model = Mock(spec=ModelConfig)
    mock_config.model.buffer_size = 8
    return mock_config


@st.composite
def prompts(draw):
    """Generate non-empty prompt strings."""
    return draw(st.text(min_size=1, max_size=500))


@st.composite
def seeds(draw):
    """Generate optional seed values."""
    return draw(st.none() | st.integers(min_value=0, max_value=2**32 - 1))


@st.composite
def aspect_ratios(draw):
    """Generate valid aspect ratio strings."""
    return draw(st.sampled_from(["1:1", "16:9", "9:16"]))


class TestStartGenerationProperties:
    """Property-based tests for start_generation() method."""

    @given(prompt=prompts(), seed=seeds(), aspect_ratio=aspect_ratios())
    @settings(max_examples=10, deadline=None)
    def test_creates_generation_options_with_correct_parameters(self, prompt, seed, aspect_ratio):
        """GenerationOptions created with seed, steps=4, and aspect_ratio."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_options, MagicMock() as mock_gen_worker:
            original_gen_options = GenerationOptions
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationOptions = mock_gen_options
                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, seed, aspect_ratio)

                mock_gen_options.assert_called_once()
                call_kwargs = mock_gen_options.call_args[1]

                assert call_kwargs["seed"] == seed
                assert call_kwargs["steps"] == 4
                assert call_kwargs["aspect_ratio"] == aspect_ratio

            finally:
                textbrush.backend.GenerationOptions = original_gen_options
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts(), seed=seeds(), aspect_ratio=aspect_ratios())
    @settings(max_examples=10, deadline=None)
    def test_creates_generation_worker_with_correct_arguments(self, prompt, seed, aspect_ratio):
        """GenerationWorker created with engine, buffer, prompt, and options."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, seed, aspect_ratio)

                mock_gen_worker.assert_called_once()
                call_kwargs = mock_gen_worker.call_args[1]

                assert call_kwargs["engine"] is backend.engine
                assert call_kwargs["buffer"] is backend.buffer
                assert call_kwargs["prompt"] == prompt
                assert isinstance(call_kwargs["options"], GenerationOptions)
                assert call_kwargs["options"].seed == seed
                assert call_kwargs["options"].steps == 4
                assert call_kwargs["options"].aspect_ratio == aspect_ratio

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts(), seed=seeds(), aspect_ratio=aspect_ratios())
    @settings(max_examples=10, deadline=None)
    def test_worker_started_after_creation(self, prompt, seed, aspect_ratio):
        """Worker.start() called after worker creation."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, seed, aspect_ratio)

                mock_worker_instance.start.assert_called_once()

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts(), seed=seeds(), aspect_ratio=aspect_ratios())
    @settings(max_examples=10, deadline=None)
    def test_worker_stored_in_backend(self, prompt, seed, aspect_ratio):
        """Worker instance stored in backend._worker after start_generation."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, seed, aspect_ratio)

                assert backend._worker is mock_worker_instance

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts())
    @settings(max_examples=50, deadline=None)
    def test_default_aspect_ratio_is_1_to_1(self, prompt):
        """When aspect_ratio not provided, defaults to '1:1'."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt)

                call_kwargs = mock_gen_worker.call_args[1]
                assert call_kwargs["options"].aspect_ratio == "1:1"

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts(), aspect_ratio=aspect_ratios())
    @settings(max_examples=50, deadline=None)
    def test_default_seed_is_none(self, prompt, aspect_ratio):
        """When seed not provided, defaults to None."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, aspect_ratio=aspect_ratio)

                call_kwargs = mock_gen_worker.call_args[1]
                assert call_kwargs["options"].seed is None

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    @given(prompt=prompts(), seed=seeds(), aspect_ratio=aspect_ratios())
    @settings(max_examples=10, deadline=None)
    def test_steps_always_set_to_4(self, prompt, seed, aspect_ratio):
        """GenerationOptions.steps always set to 4 regardless of inputs."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation(prompt, seed, aspect_ratio)

                call_kwargs = mock_gen_worker.call_args[1]
                assert call_kwargs["options"].steps == 4

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker


class TestStartGenerationExamples:
    """Example-based tests for specific scenarios."""

    def test_minimal_call_with_only_prompt(self):
        """Calling with only prompt uses all defaults."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation("test prompt")

                call_kwargs = mock_gen_worker.call_args[1]
                options = call_kwargs["options"]

                assert call_kwargs["prompt"] == "test prompt"
                assert options.seed is None
                assert options.steps == 4
                assert options.aspect_ratio == "1:1"
                assert backend._worker is mock_worker_instance
                mock_worker_instance.start.assert_called_once()

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    def test_explicit_all_parameters(self):
        """Calling with all parameters explicitly set."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)
        backend._worker = None

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                mock_worker_instance = Mock()
                mock_gen_worker.return_value = mock_worker_instance

                backend.start_generation("landscape", seed=42, aspect_ratio="16:9")

                call_kwargs = mock_gen_worker.call_args[1]
                options = call_kwargs["options"]

                assert call_kwargs["prompt"] == "landscape"
                assert options.seed == 42
                assert options.steps == 4
                assert options.aspect_ratio == "16:9"
                assert backend._worker is mock_worker_instance
                mock_worker_instance.start.assert_called_once()

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

    def test_replaces_existing_worker_reference(self):
        """Calling start_generation replaces any existing worker reference."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        old_worker = Mock()
        backend._worker = old_worker

        with MagicMock() as mock_gen_worker:
            original_gen_worker = GenerationWorker

            try:
                import textbrush.backend

                textbrush.backend.GenerationWorker = mock_gen_worker

                new_worker_instance = Mock()
                mock_gen_worker.return_value = new_worker_instance

                backend.start_generation("new prompt")

                assert backend._worker is new_worker_instance
                assert backend._worker is not old_worker

            finally:
                textbrush.backend.GenerationWorker = original_gen_worker

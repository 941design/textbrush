"""Property-based tests for FluxInferenceEngine.generate()."""

from unittest.mock import Mock, patch

import hypothesis.strategies as st
import pytest
import torch
from hypothesis import given, settings
from PIL import Image

from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.inference.flux import FluxInferenceEngine


@st.composite
def generation_options_strategy(draw):
    """Strategy for generating valid GenerationOptions."""
    aspect_ratio = draw(st.sampled_from(["1:1", "16:9", "9:16"]))
    seed = draw(st.one_of(st.none(), st.integers(min_value=0, max_value=2**32 - 1)))
    steps = draw(st.integers(min_value=1, max_value=50))

    return GenerationOptions(
        seed=seed,
        steps=steps,
        aspect_ratio=aspect_ratio,
    )


@st.composite
def prompt_strategy(draw):
    """Strategy for generating valid prompts."""
    return draw(st.text(min_size=1, max_size=500))


class TestGenerateRuntimeChecks:
    """Tests for runtime invariant checks in generate()."""

    def test_not_loaded_raises_runtime_error(self):
        """Calling generate() before load() raises RuntimeError."""
        engine = FluxInferenceEngine()
        options = GenerationOptions()

        with pytest.raises(RuntimeError, match="Engine not loaded"):
            engine.generate("test prompt", options)

    def test_invalid_aspect_ratio_raises_key_error(self):
        """Invalid aspect ratio raises KeyError."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        options = GenerationOptions(aspect_ratio="invalid")

        with pytest.raises(KeyError):
            engine.generate("test prompt", options)


class TestGenerateSeedHandling:
    """Property-based tests for seed handling invariants."""

    @given(seed=st.integers(min_value=0, max_value=2**32 - 1))
    @settings(max_examples=10)
    def test_provided_seed_preserved_in_result(self, seed):
        """Provided seed is returned in result."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(seed=seed)
        result = engine.generate("test", options)

        assert result.seed == seed

    @given(prompt=prompt_strategy())
    @settings(max_examples=10)
    def test_none_seed_generates_valid_seed(self, prompt):
        """None seed generates seed in valid range."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(seed=None)
        result = engine.generate(prompt, options)

        assert 0 <= result.seed < 2**32

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_seed_monotonicity(self, options):
        """If seed provided, use it; else generate random."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        if options.seed is not None:
            assert result.seed == options.seed
        else:
            assert 0 <= result.seed < 2**32


class TestGenerateAspectRatio:
    """Property-based tests for aspect ratio resolution."""

    @given(aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]))
    @settings(max_examples=3)
    def test_aspect_ratio_resolves_to_correct_dimensions(self, aspect_ratio):
        """Aspect ratio maps to correct dimensions."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio=aspect_ratio)
        engine.generate("test", options)

        expected_dims = FluxInferenceEngine.ASPECT_RATIOS[aspect_ratio]

        call_kwargs = engine._pipeline.call_args.kwargs
        assert call_kwargs["width"] == expected_dims[0]
        assert call_kwargs["height"] == expected_dims[1]

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_aspect_ratio_dimensions_used_not_options_dimensions(self, options):
        """Aspect ratio overrides width/height from options."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        engine.generate("test", options)

        expected_dims = FluxInferenceEngine.ASPECT_RATIOS[options.aspect_ratio]

        call_kwargs = engine._pipeline.call_args.kwargs
        assert call_kwargs["width"] == expected_dims[0]
        assert call_kwargs["height"] == expected_dims[1]


class TestGenerateTimingInvariants:
    """Property-based tests for timing invariants."""

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_generation_time_non_negative(self, options):
        """Generation time is always non-negative."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        assert result.generation_time >= 0

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_generation_time_measured_correctly(self, options):
        """Generation time reflects actual pipeline call duration."""
        engine = FluxInferenceEngine()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))

        def slow_pipeline(*args, **kwargs):
            import time

            time.sleep(0.01)
            return Mock(images=[mock_image])

        engine._pipeline = Mock(side_effect=slow_pipeline)

        result = engine.generate("test", options)

        assert result.generation_time >= 0.01


class TestGeneratePipelineInvocation:
    """Property-based tests for pipeline invocation correctness."""

    @given(prompt=prompt_strategy(), options=generation_options_strategy())
    @settings(max_examples=10)
    def test_pipeline_called_with_correct_parameters(self, prompt, options):
        """Pipeline receives correct prompt, dimensions, steps, generator."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        engine.generate(prompt, options)

        call_kwargs = engine._pipeline.call_args.kwargs

        assert call_kwargs["prompt"] == prompt
        assert call_kwargs["num_inference_steps"] == options.steps
        assert isinstance(call_kwargs["generator"], torch.Generator)

        expected_width, expected_height = FluxInferenceEngine.ASPECT_RATIOS[options.aspect_ratio]
        assert call_kwargs["width"] == expected_width
        assert call_kwargs["height"] == expected_height

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_generator_device_matches_engine_device(self, options):
        """torch.Generator device matches engine device."""
        for device in ["cpu", "cuda", "mps"]:
            if device == "cuda" and not torch.cuda.is_available():
                continue
            if device == "mps" and not torch.backends.mps.is_available():
                continue

            engine = FluxInferenceEngine()
            engine._pipeline = Mock()
            engine._device = device

            mock_image = Image.new("RGB", (1024, 1024))
            engine._pipeline.return_value = Mock(images=[mock_image])

            with patch("torch.Generator") as mock_generator_class:
                mock_generator = Mock()
                mock_generator_class.return_value = mock_generator

                engine.generate("test", options)

                mock_generator_class.assert_called_once_with(device)

    @given(seed=st.integers(min_value=0, max_value=2**32 - 1))
    @settings(max_examples=10)
    def test_generator_seed_set_correctly(self, seed):
        """Generator.manual_seed called with correct seed."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(seed=seed)

        with patch("torch.Generator") as mock_generator_class:
            mock_generator = Mock()
            mock_generator_class.return_value = mock_generator

            engine.generate("test", options)

            mock_generator.manual_seed.assert_called_once_with(seed)


class TestGenerateResultInvariants:
    """Property-based tests for GenerationResult invariants."""

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_result_contains_all_required_fields(self, options):
        """Result has image, seed, generation_time, model_name."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        assert isinstance(result, GenerationResult)
        assert isinstance(result.image, Image.Image)
        assert isinstance(result.seed, int)
        assert isinstance(result.generation_time, float)
        assert isinstance(result.model_name, str)

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_result_model_name_correct(self, options):
        """Result model_name matches MODEL_ID."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        assert result.model_name == FluxInferenceEngine.MODEL_ID

    @given(options=generation_options_strategy())
    @settings(max_examples=10)
    def test_result_image_from_pipeline_first_output(self, options):
        """Result image is first image from pipeline output."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (512, 512))
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        assert result.image is mock_image


class TestGenerateDeterminism:
    """Property-based tests for deterministic generation."""

    @given(
        prompt=prompt_strategy(),
        seed=st.integers(min_value=0, max_value=2**32 - 1),
        steps=st.integers(min_value=1, max_value=50),
    )
    @settings(max_examples=10)
    def test_same_seed_same_generator_seed(self, prompt, seed, steps):
        """Same seed produces same generator seed across calls."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(seed=seed, steps=steps)

        seeds_used = []

        def capture_generator_seed(*args, **kwargs):
            generator = kwargs.get("generator")
            if generator:
                seeds_used.append(generator.initial_seed())
            return Mock(images=[mock_image])

        engine._pipeline.side_effect = capture_generator_seed

        engine.generate(prompt, options)
        engine.generate(prompt, options)

        assert len(seeds_used) == 2
        assert seeds_used[0] == seeds_used[1] == seed

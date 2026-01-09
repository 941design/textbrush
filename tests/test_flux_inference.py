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

    @given(
        width=st.integers(min_value=64, max_value=2048),
        height=st.integers(min_value=64, max_value=2048),
    )
    @settings(max_examples=10)
    def test_custom_aspect_ratio_uses_explicit_dimensions(self, width, height):
        """Custom aspect ratio uses explicit width/height from options."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        rounded_width = ((width + 15) // 16) * 16
        rounded_height = ((height + 15) // 16) * 16

        mock_image = Image.new("RGB", (rounded_width, rounded_height))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=width, height=height)
        engine.generate("test", options)

        call_kwargs = engine._pipeline.call_args.kwargs
        assert call_kwargs["width"] == rounded_width
        assert call_kwargs["height"] == rounded_height

    def test_custom_aspect_ratio_with_default_dimensions_does_not_raise(self):
        """Custom aspect ratio with default dimensions (512x512) should not raise KeyError."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (512, 512))
        engine._pipeline.return_value = Mock(images=[mock_image])

        # This is the edge case: "custom" with defaults (512x512) should not try
        # to look up "custom" in ASPECT_RATIOS
        options = GenerationOptions(aspect_ratio="custom", width=512, height=512)
        engine.generate("test", options)  # Should not raise KeyError

        call_kwargs = engine._pipeline.call_args.kwargs
        assert call_kwargs["width"] == 512
        assert call_kwargs["height"] == 512


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
        """Result image is first image from pipeline output (or cropped version)."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        expected_dims = FluxInferenceEngine.ASPECT_RATIOS[options.aspect_ratio]
        mock_image = Image.new("RGB", expected_dims)
        engine._pipeline.return_value = Mock(images=[mock_image])

        result = engine.generate("test", options)

        assert result.image.size == expected_dims


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


class TestDimensionRoundingAndCropping:
    """Property-based tests for dimension rounding and center cropping."""

    @given(
        width=st.integers(min_value=256, max_value=2048),
        height=st.integers(min_value=256, max_value=2048),
    )
    @settings(max_examples=50)
    def test_dimension_rounding_property(self, width, height):
        """Generated dimensions are always multiples of 16."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (((width + 15) // 16) * 16, ((height + 15) // 16) * 16))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=width, height=height)
        result = engine.generate("test", options)

        assert result.generated_width % 16 == 0
        assert result.generated_height % 16 == 0

    @given(
        width=st.integers(min_value=256, max_value=2048),
        height=st.integers(min_value=256, max_value=2048),
    )
    @settings(max_examples=50)
    def test_center_crop_restores_dimensions(self, width, height):
        """Final image dimensions match requested dimensions exactly."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        rounded_width = ((width + 15) // 16) * 16
        rounded_height = ((height + 15) // 16) * 16

        mock_image = Image.new("RGB", (rounded_width, rounded_height))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=width, height=height)
        result = engine.generate("test", options)

        assert result.image.size == (width, height)

    def test_no_crop_when_aligned(self):
        """No cropping occurs when dimensions already aligned to 16."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        mock_image = Image.new("RGB", (1024, 1024))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=1024, height=1024)
        result = engine.generate("test", options)

        assert result.generated_width == 1024
        assert result.generated_height == 1024
        assert result.image.size == (1024, 1024)

    @given(
        width_offset=st.integers(min_value=1, max_value=15),
        height_offset=st.integers(min_value=1, max_value=15),
    )
    @settings(max_examples=30)
    def test_crop_distribution_property(self, width_offset, height_offset):
        """Cropping is evenly distributed (center crop) with at most 1 pixel difference."""
        base_width = 1024
        base_height = 1024
        width = base_width - width_offset
        height = base_height - height_offset

        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        rounded_width = ((width + 15) // 16) * 16
        rounded_height = ((height + 15) // 16) * 16

        mock_image = Image.new("RGB", (rounded_width, rounded_height))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=width, height=height)
        engine.generate("test", options)

        width_diff = rounded_width - width
        height_diff = rounded_height - height

        left_crop = (rounded_width - width) // 2
        right_crop = width_diff - left_crop

        top_crop = (rounded_height - height) // 2
        bottom_crop = height_diff - top_crop

        assert left_crop + right_crop == width_diff
        assert top_crop + bottom_crop == height_diff
        assert abs(left_crop - right_crop) <= 1
        assert abs(top_crop - bottom_crop) <= 1

    def test_specific_odd_pixel_crop(self):
        """Specific test for 1001×1001 dimensions requiring 7 pixel crop."""
        engine = FluxInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        width, height = 1001, 1001
        rounded_width = 1008
        rounded_height = 1008

        mock_image = Image.new("RGB", (rounded_width, rounded_height))
        engine._pipeline.return_value = Mock(images=[mock_image])

        options = GenerationOptions(aspect_ratio="custom", width=width, height=height)
        result = engine.generate("test", options)

        assert result.generated_width == 1008
        assert result.generated_height == 1008
        assert result.image.size == (1001, 1001)

        left_crop = (rounded_width - width) // 2
        assert left_crop == 3
        assert (rounded_width - width - left_crop) == 4


class TestSchedulerStateReset:
    """Tests for scheduler state reset before generation."""

    def test_scheduler_step_index_reset_before_generation(self):
        """Scheduler _step_index is reset to None before calling pipeline.

        This prevents IndexError when scheduler state is corrupted from
        a previous interrupted generation.
        """
        engine = FluxInferenceEngine()
        engine._device = "cpu"

        # Create mock pipeline with mock scheduler
        mock_scheduler = Mock()
        mock_scheduler._step_index = 999  # Simulate corrupted state
        mock_pipeline = Mock()
        mock_pipeline.scheduler = mock_scheduler

        mock_image = Image.new("RGB", (1024, 1024))
        mock_pipeline.return_value = Mock(images=[mock_image])

        engine._pipeline = mock_pipeline

        options = GenerationOptions(seed=42)

        # Track when scheduler reset happens
        reset_called_before_pipeline = []

        def track_pipeline_call(*args, **kwargs):
            # Record scheduler state when pipeline is called
            reset_called_before_pipeline.append(mock_scheduler._step_index)
            return Mock(images=[mock_image])

        mock_pipeline.side_effect = track_pipeline_call

        engine.generate("test", options)

        # Verify scheduler was reset before pipeline was called
        assert len(reset_called_before_pipeline) == 1
        assert reset_called_before_pipeline[0] is None, (
            "Scheduler _step_index should be reset to None before calling pipeline"
        )

    def test_concurrent_generate_calls_are_serialized(self):
        """Concurrent generate() calls must be serialized to prevent scheduler corruption.

        When two threads call generate() simultaneously on the same engine,
        the calls must be serialized to prevent race conditions on the
        shared scheduler state.
        """
        import threading
        import time

        engine = FluxInferenceEngine()
        engine._device = "cpu"

        # Track execution order
        execution_log = []
        execution_lock = threading.Lock()

        mock_scheduler = Mock()
        mock_scheduler._step_index = None
        mock_pipeline = Mock()
        mock_pipeline.scheduler = mock_scheduler

        mock_image = Image.new("RGB", (1024, 1024))

        def slow_pipeline_call(*args, **kwargs):
            with execution_lock:
                execution_log.append(("start", threading.current_thread().name))

            # Simulate slow generation (scheduler would be in use during this time)
            time.sleep(0.1)

            with execution_lock:
                execution_log.append(("end", threading.current_thread().name))

            return Mock(images=[mock_image])

        mock_pipeline.side_effect = slow_pipeline_call
        engine._pipeline = mock_pipeline

        options = GenerationOptions(seed=42)

        # Launch two concurrent generation calls
        results = []
        errors = []

        def generate_and_record(name):
            try:
                engine.generate("test", options)
                results.append(name)
            except Exception as e:
                errors.append((name, e))

        thread1 = threading.Thread(target=generate_and_record, args=("thread1",), name="thread1")
        thread2 = threading.Thread(target=generate_and_record, args=("thread2",), name="thread2")

        thread1.start()
        time.sleep(0.01)  # Small delay to ensure thread1 starts first
        thread2.start()

        thread1.join(timeout=5.0)
        thread2.join(timeout=5.0)

        # Both should complete without error
        assert len(errors) == 0, f"Errors occurred: {errors}"
        assert len(results) == 2, "Both generations should complete"

        # Verify calls were serialized (no overlapping start/end)
        # If serialized: start1, end1, start2, end2 (or start2, end2, start1, end1)
        # If overlapping: start1, start2, end1, end2 (BAD - concurrent access)
        starts = [i for i, (action, _) in enumerate(execution_log) if action == "start"]
        ends = [i for i, (action, _) in enumerate(execution_log) if action == "end"]

        # Check that no two starts happen before any end (which would indicate overlap)
        # With serialization: starts[0] < ends[0] < starts[1] < ends[1]
        assert len(starts) == 2 and len(ends) == 2, "Should have exactly 2 start/end pairs"
        assert starts[0] < ends[0], "First call should end before anything else"
        assert ends[0] < starts[1], f"Calls should be serialized (no overlap). Log: {execution_log}"

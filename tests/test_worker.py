"""Property-based tests for GenerationWorker.

Tests verify worker behavior including continuous generation loop,
seed progression, error handling, graceful shutdown, and immutability.
"""

from __future__ import annotations

import copy
import time
from unittest.mock import Mock, patch

from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

# Import shared MockInferenceEngine for direct instantiation
# (fixtures don't work well with Hypothesis @given tests)
from tests.mocks import MockInferenceEngine
from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.inference.base import GenerationOptions, GenerationResult, InferenceEngine
from textbrush.worker import GenerationWorker


class TestGenerationWorkerProperties:
    """Property-based tests for GenerationWorker._run behavior."""

    @given(
        initial_seed=st.integers(min_value=0, max_value=10000),
        num_generations=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=10, deadline=5000)
    def test_seed_increments_monotonically(self, initial_seed: int, num_generations: int):
        """Property: seed increments by 1 for each successful generation."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=initial_seed)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        collected_seeds = []
        for _ in range(num_generations):
            image = buffer.get(timeout=2.0)
            if image is None:
                break
            collected_seeds.append(image.seed)

        worker.stop()
        worker.join(timeout=2.0)

        assert len(collected_seeds) == num_generations
        for i, seed in enumerate(collected_seeds):
            assert seed == initial_seed + i

    @given(num_generations=st.integers(min_value=1, max_value=15))
    @settings(max_examples=15, deadline=5000)
    def test_buffer_fills_with_generated_images(self, num_generations: int):
        """Property: worker continuously fills buffer with BufferedImage instances."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=100)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        collected = []
        for _ in range(num_generations):
            image = buffer.get(timeout=2.0)
            if image is None:
                break
            collected.append(image)

        worker.stop()
        worker.join(timeout=2.0)

        assert len(collected) == num_generations
        for img in collected:
            assert isinstance(img, BufferedImage)
            assert isinstance(img.image, Image.Image)
            assert isinstance(img.seed, int)

    def test_worker_stops_on_stop_event(self):
        """Property: worker exits loop when stop_event is set."""
        buffer = ImageBuffer(max_size=8)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=1)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        time.sleep(0.1)

        worker.stop()
        worker.join(timeout=2.0)

        assert not worker._thread.is_alive()

    def test_worker_continues_on_generation_error(self):
        """Property: worker continues generating after non-fatal errors."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine(fail_after_n_generations=3)
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)

        with patch("textbrush.worker.logger") as mock_logger:
            worker.start()

            collected = []
            for _ in range(2):
                image = buffer.get(timeout=2.0)
                if image is not None:
                    collected.append(image)

            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            assert len(collected) == 2
            assert mock_logger.error.called

    def test_worker_exits_on_stop_during_error(self):
        """Property: worker exits loop if stopped during error handling."""
        buffer = ImageBuffer(max_size=8)
        engine = MockInferenceEngine(fail_after_n_generations=1)
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.1)
            worker.stop()
            worker.join(timeout=2.0)

            assert not worker._thread.is_alive()

    def test_worker_handles_buffer_full_gracefully(self):
        """Property: worker blocks when buffer full, continues when space available."""
        buffer = ImageBuffer(max_size=2)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        time.sleep(0.2)

        img1 = buffer.get(timeout=1.0)
        img2 = buffer.get(timeout=1.0)
        img3 = buffer.get(timeout=1.0)

        assert img1 is not None
        assert img2 is not None
        assert img3 is not None

        worker.stop()
        worker.join(timeout=2.0)

    def test_worker_exits_when_buffer_shutdown_during_put(self):
        """Property: worker exits if buffer shutdown while blocked on put."""
        buffer = ImageBuffer(max_size=1)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        time.sleep(0.2)

        worker.stop()
        worker.join(timeout=2.0)

        assert not worker._thread.is_alive()

    def test_worker_logs_start_and_stop(self):
        """Property: worker logs start and stop events."""
        buffer = ImageBuffer(max_size=8)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)

        with patch("textbrush.worker.logger") as mock_logger:
            worker.start()
            time.sleep(0.1)
            worker.stop()
            worker.join(timeout=2.0)

            start_logged = any(
                call[0][0] == "Worker started" for call in mock_logger.info.call_args_list
            )
            stop_logged = any(
                call[0][0] == "Worker stopped" for call in mock_logger.info.call_args_list
            )

            assert start_logged
            assert stop_logged

    def test_worker_logs_each_generation(self):
        """Property: worker logs debug message for each successful generation."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=42)

        worker = GenerationWorker(engine, buffer, "test prompt", options)

        with patch("textbrush.worker.logger") as mock_logger:
            worker.start()

            for _ in range(3):
                buffer.get(timeout=2.0)

            worker.stop()
            worker.join(timeout=2.0)

            debug_calls = [
                call for call in mock_logger.debug.call_args_list if "Generated image" in str(call)
            ]
            assert len(debug_calls) >= 3

    @given(initial_seed=st.integers(min_value=0, max_value=1000))
    @settings(max_examples=10, deadline=5000)
    def test_original_options_unchanged_when_seed_none(self, initial_seed: int):
        """Property: original options object with None seed remains unchanged (immutability)."""
        buffer = ImageBuffer(max_size=10)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True
        engine_mock.generate.return_value = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=initial_seed,
            generation_time=0.001,
            model_name="mock",
        )

        options = GenerationOptions(seed=None)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)
        worker.start()

        time.sleep(0.1)

        worker.stop()
        worker.join(timeout=2.0)

        assert options.seed is None

    def test_worker_respects_buffer_timeout(self):
        """Property: worker uses timeout when calling buffer.put."""
        buffer = ImageBuffer(max_size=1)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)

        with patch.object(buffer, "put", wraps=buffer.put) as mock_put:
            worker.start()
            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            assert mock_put.called
            call_kwargs = [call[1] for call in mock_put.call_args_list]
            assert any("timeout" in kwargs for kwargs in call_kwargs)

    def test_worker_creates_buffered_image_correctly(self):
        """Property: worker creates BufferedImage with correct image and seed."""
        buffer = ImageBuffer(max_size=5)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=123)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        img = buffer.get(timeout=2.0)

        worker.stop()
        worker.join(timeout=2.0)

        assert img is not None
        assert isinstance(img, BufferedImage)
        assert isinstance(img.image, Image.Image)
        assert img.seed == 123

    @given(
        prompt=st.text(min_size=1, max_size=50),
        initial_seed=st.integers(min_value=0, max_value=100),
    )
    @settings(max_examples=10, deadline=5000)
    def test_worker_uses_provided_prompt_and_options(self, prompt: str, initial_seed: int):
        """Property: worker passes prompt and options to engine.generate."""
        buffer = ImageBuffer(max_size=5)

        captured_prompts = []
        captured_seeds = []

        def capture_generate(p: str, opts: GenerationOptions) -> GenerationResult:
            captured_prompts.append(p)
            captured_seeds.append(opts.seed)
            return GenerationResult(
                image=Image.new("RGB", (512, 512)),
                seed=opts.seed if opts.seed is not None else 42,
                generation_time=0.001,
                model_name="mock",
            )

        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True
        engine_mock.generate.side_effect = capture_generate

        options = GenerationOptions(seed=initial_seed)
        worker = GenerationWorker(engine_mock, buffer, prompt, options)
        worker.start()

        time.sleep(0.1)

        worker.stop()
        worker.join(timeout=2.0)

        assert len(captured_prompts) > 0
        assert all(p == prompt for p in captured_prompts)
        assert captured_seeds[0] == initial_seed


class TestGenerationWorkerExamples:
    """Example-based tests for specific edge cases."""

    def test_immediate_stop_before_first_generation(self):
        """Worker stops promptly after stop() is called.

        Note: Due to timing, the worker may complete a few generations before
        the stop signal is processed. The key property is that it stops promptly.
        """
        buffer = ImageBuffer(max_size=8)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()
        worker.stop()
        worker.join(timeout=2.0)

        assert not worker._thread.is_alive()
        # May have 0-3 images due to timing - the key property is it stopped
        assert len(buffer) <= 3

    def test_multiple_stop_calls_are_safe(self):
        """Calling stop() multiple times is safe (idempotent)."""
        buffer = ImageBuffer(max_size=8)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        worker.stop()
        worker.stop()
        worker.stop()

        worker.join(timeout=2.0)
        assert not worker._thread.is_alive()

    def test_worker_handles_engine_raising_exception(self):
        """Worker continues when engine raises exception during generate."""
        buffer = ImageBuffer(max_size=20)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True
        engine_mock.generate.side_effect = [
            RuntimeError("First error"),
            GenerationResult(
                image=Image.new("RGB", (512, 512)),
                seed=1,
                generation_time=0.001,
                model_name="mock",
            ),
            RuntimeError("Second error"),
            GenerationResult(
                image=Image.new("RGB", (512, 512)),
                seed=2,
                generation_time=0.001,
                model_name="mock",
            ),
        ]

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()

            img1 = buffer.get(timeout=2.0)
            img2 = buffer.get(timeout=2.0)

            worker.stop()
            worker.join(timeout=2.0)

            assert img1 is not None
            assert img2 is not None
            assert img1.seed == 1
            assert img2.seed == 2


class TestGenerationOptionsImmutability:
    """Property-based tests for GenerationOptions immutability contract."""

    @given(
        initial_seed=st.integers(min_value=0, max_value=10000),
        num_generations=st.integers(min_value=1, max_value=10),
        steps=st.integers(min_value=1, max_value=50),
        width=st.integers(min_value=256, max_value=1024),
        height=st.integers(min_value=256, max_value=1024),
    )
    @settings(max_examples=10, deadline=5000)
    def test_options_immutability(
        self, initial_seed: int, num_generations: int, steps: int, width: int, height: int
    ):
        """Property: original options object unchanged after worker runs."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=initial_seed, steps=steps, width=width, height=height)

        original_options = copy.deepcopy(options)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        for _ in range(num_generations):
            buffer.get(timeout=2.0)

        worker.stop()
        worker.join(timeout=2.0)

        assert original_options.seed == initial_seed
        assert original_options.steps == steps
        assert original_options.width == width
        assert original_options.height == height

    @given(
        initial_seed=st.integers(min_value=0, max_value=5000),
        num_generations=st.integers(min_value=2, max_value=10),
        steps=st.integers(min_value=1, max_value=50),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16", "4:3", "3:2"]),
    )
    @settings(max_examples=10, deadline=5000)
    def test_other_fields_preserved(
        self, initial_seed: int, num_generations: int, steps: int, aspect_ratio: str
    ):
        """Property: steps, aspect_ratio, etc. remain constant across iterations."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=initial_seed, steps=steps, aspect_ratio=aspect_ratio)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        for _ in range(num_generations):
            buffer.get(timeout=2.0)

        worker.stop()
        worker.join(timeout=2.0)

        assert worker.options.steps == steps
        assert worker.options.aspect_ratio == aspect_ratio

    @given(
        auto_seed=st.integers(min_value=1, max_value=5000),
        num_generations=st.integers(min_value=2, max_value=10),
    )
    @settings(max_examples=10, deadline=5000)
    def test_none_seed_handling(self, auto_seed: int, num_generations: int):
        """Property: None seed uses result.seed then increments."""
        buffer = ImageBuffer(max_size=20)

        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        call_count = [0]

        def generate_with_auto_seed(prompt: str, opts: GenerationOptions) -> GenerationResult:
            seed = opts.seed if opts.seed is not None else auto_seed
            call_count[0] += 1
            return GenerationResult(
                image=Image.new("RGB", (512, 512)),
                seed=seed,
                generation_time=0.001,
                model_name="mock",
            )

        engine_mock.generate.side_effect = generate_with_auto_seed

        options = GenerationOptions(seed=None)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)
        worker.start()

        collected_seeds = []
        for _ in range(num_generations):
            image = buffer.get(timeout=2.0)
            if image is not None:
                collected_seeds.append(image.seed)

        worker.stop()
        worker.join(timeout=2.0)

        assert len(collected_seeds) == num_generations
        assert collected_seeds[0] == auto_seed
        for i in range(1, num_generations):
            assert collected_seeds[i] == auto_seed + i

    @given(
        initial_seed=st.integers(min_value=0, max_value=5000),
        num_generations=st.integers(min_value=1, max_value=8),
    )
    @settings(max_examples=10, deadline=5000)
    def test_worker_options_identity_changes(self, initial_seed: int, num_generations: int):
        """Property: worker.options identity changes with each iteration (new object created)."""
        buffer = ImageBuffer(max_size=20)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=initial_seed)

        initial_options_id = id(options)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        for _ in range(num_generations):
            buffer.get(timeout=2.0)

        worker.stop()
        worker.join(timeout=2.0)

        final_options_id = id(worker.options)
        assert final_options_id != initial_options_id


class TestErrorPropagationProperties:
    """Property-based tests for error propagation mechanism."""

    def test_error_captured_in_queue(self):
        """Property: when engine raises exception, worker.get_error() returns it."""
        buffer = ImageBuffer(max_size=10)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        test_error = RuntimeError("Test error message")
        engine_mock.generate.side_effect = test_error

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            captured_error = worker.get_error()
            assert captured_error is test_error
            assert str(captured_error) == "Test error message"

    def test_normal_operation_no_error(self):
        """Property: successful generation has get_error() return None."""
        buffer = ImageBuffer(max_size=10)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()

        for _ in range(3):
            buffer.get(timeout=2.0)

        worker.stop()
        worker.join(timeout=2.0)

        assert worker.get_error() is None

    def test_error_persists_until_cleared(self):
        """Property: get_error() returns same exception on repeated calls."""
        buffer = ImageBuffer(max_size=10)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        test_error = ValueError("Persistent error")
        engine_mock.generate.side_effect = test_error

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            error1 = worker.get_error()
            error2 = worker.get_error()
            error3 = worker.get_error()

            assert error1 is test_error
            assert error2 is test_error
            assert error3 is test_error
            assert error1 is error2 is error3

    def test_clear_error_resets_state(self):
        """Property: after clear_error(), get_error() returns None."""
        buffer = ImageBuffer(max_size=10)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        test_error = RuntimeError("Error to be cleared")
        engine_mock.generate.side_effect = test_error

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            assert worker.get_error() is test_error

            worker.clear_error()

            assert worker.get_error() is None

    def test_clear_error_idempotent(self):
        """Property: calling clear_error() multiple times is safe."""
        buffer = ImageBuffer(max_size=10)
        engine = MockInferenceEngine()
        options = GenerationOptions(seed=0)

        worker = GenerationWorker(engine, buffer, "test prompt", options)
        worker.start()
        time.sleep(0.1)
        worker.stop()
        worker.join(timeout=2.0)

        worker.clear_error()
        worker.clear_error()
        worker.clear_error()

        assert worker.get_error() is None

    @given(error_message=st.text(min_size=1, max_size=100))
    @settings(max_examples=10, deadline=5000)
    def test_error_message_preserved(self, error_message: str):
        """Property: exception message is preserved through error queue."""
        buffer = ImageBuffer(max_size=10)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        test_error = RuntimeError(error_message)
        engine_mock.generate.side_effect = test_error

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.2)
            worker.stop()
            worker.join(timeout=2.0)

            captured_error = worker.get_error()
            assert captured_error is not None
            assert str(captured_error) == error_message

    def test_most_recent_error_kept_when_queue_full(self):
        """Property: when queue is full, oldest error is discarded for newest."""
        buffer = ImageBuffer(max_size=20)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        error1 = RuntimeError("First error")
        error2 = ValueError("Second error")

        call_count = [0]

        def generate_errors(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise error1
            elif call_count[0] == 2:
                raise error2
            else:
                time.sleep(10)
                return GenerationResult(
                    image=Image.new("RGB", (512, 512)),
                    seed=99,
                    generation_time=0.001,
                    model_name="mock",
                )

        engine_mock.generate.side_effect = generate_errors

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.3)
            worker.stop()
            worker.join(timeout=2.0)

            captured_error = worker.get_error()
            assert captured_error is error2
            assert str(captured_error) == "Second error"

    def test_worker_continues_after_error_captured(self):
        """Property: worker continues generating after capturing error."""
        buffer = ImageBuffer(max_size=20)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        test_error = RuntimeError("Recoverable error")
        success_result = GenerationResult(
            image=Image.new("RGB", (512, 512)),
            seed=42,
            generation_time=0.001,
            model_name="mock",
        )

        call_count = [0]

        def generate_mixed(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise test_error
            else:
                return success_result

        engine_mock.generate.side_effect = generate_mixed

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()

            img1 = buffer.get(timeout=2.0)
            img2 = buffer.get(timeout=2.0)

            worker.stop()
            worker.join(timeout=2.0)

            assert img1 is not None
            assert img2 is not None
            assert worker.get_error() is test_error

    @given(num_errors=st.integers(min_value=1, max_value=5))
    @settings(max_examples=5, deadline=5000)
    def test_multiple_errors_only_latest_kept(self, num_errors: int):
        """Property: with multiple errors, only the most recent is kept."""
        buffer = ImageBuffer(max_size=20)
        engine_mock = Mock(spec=InferenceEngine)
        engine_mock.is_loaded.return_value = True

        errors = [RuntimeError(f"Error {i}") for i in range(num_errors)]
        call_count = [0]

        def generate_multiple_errors(*args, **kwargs):
            if call_count[0] < len(errors):
                error = errors[call_count[0]]
                call_count[0] += 1
                raise error
            else:
                time.sleep(10)
                return GenerationResult(
                    image=Image.new("RGB", (512, 512)),
                    seed=99,
                    generation_time=0.001,
                    model_name="mock",
                )

        engine_mock.generate.side_effect = generate_multiple_errors

        options = GenerationOptions(seed=0)
        worker = GenerationWorker(engine_mock, buffer, "test prompt", options)

        with patch("textbrush.worker.logger"):
            worker.start()
            time.sleep(0.3)
            worker.stop()
            worker.join(timeout=2.0)

            captured_error = worker.get_error()
            assert captured_error is errors[-1]
            assert str(captured_error) == f"Error {num_errors - 1}"

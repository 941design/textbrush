"""Shared mock classes for textbrush tests."""

from __future__ import annotations

from PIL import Image

from textbrush.inference.base import GenerationOptions, GenerationResult, InferenceEngine


class MockInferenceEngine(InferenceEngine):
    """Shared mock inference engine for testing.

    This mock engine simulates the inference backend without requiring
    actual model weights or GPU resources.

    Attributes:
        fail_on_load: If True, load() raises RuntimeError.
        fail_on_generate: If True, generate() raises RuntimeError.
        fail_after_n_generations: Fail after N successful generations.
        generation_count: Number of generate() calls made.
        reference_canvas: optional canvas (width, height) reported by
            `reference_input_size`; when None (the default) the mock
            behaves like a text-only engine.
        last_prompt: the most recent prompt passed to `generate()`.
        last_options: the most recent `GenerationOptions` passed to
            `generate()`, including `references` and `sampling_settings`.
    """

    def __init__(
        self,
        *,
        fail_on_load: bool = False,
        fail_on_generate: bool = False,
        fail_after_n_generations: int | None = None,
        reference_canvas: tuple[int, int] | None = None,
    ):
        self._loaded = False
        self._device = "cpu"
        self._fail_on_load = fail_on_load
        self._fail_on_generate = fail_on_generate
        self._fail_after_n_generations = fail_after_n_generations
        self._reference_canvas = reference_canvas
        self.generation_count = 0
        self.last_prompt: str | None = None
        self.last_options: GenerationOptions | None = None

    def load(self) -> None:
        if self._fail_on_load:
            raise RuntimeError("Failed to load model")
        self._loaded = True

    def is_loaded(self) -> bool:
        return self._loaded

    def reference_input_size(self, output_width: int, output_height: int) -> tuple[int, int] | None:
        """Return the configured reference canvas, or None for text-only."""
        return self._reference_canvas

    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        self.generation_count += 1
        self.last_prompt = prompt
        self.last_options = options

        if self._fail_on_generate:
            raise RuntimeError("Failed to generate image")

        if (
            self._fail_after_n_generations is not None
            and self.generation_count >= self._fail_after_n_generations
        ):
            raise RuntimeError("Simulated generation failure after N generations")

        # Follow `options.width/height` so backend tests that drive custom
        # dimensions observe the requested size on the result image.
        width = options.width or 512
        height = options.height or 512
        image = Image.new("RGB", (width, height), color=(128, 128, 128))
        seed = options.seed if options.seed is not None else 42

        return GenerationResult(
            image=image,
            seed=seed,
            generation_time=0.01,
            model_name="mock",
            generated_width=width,
            generated_height=height,
        )

    def unload(self) -> None:
        self._loaded = False

    @property
    def device(self) -> str:
        return self._device

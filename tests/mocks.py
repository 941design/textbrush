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
        """Return the configured reference canvas, or None for text-only.

        When `reference_canvas` is set as a callable, it is invoked with
        the (output_width, output_height) tuple so tests that drive
        different presets observe the canvas each preset would produce
        (a `static (1024, 1024)` mock would mask a preset-driven canvas
        such as portrait-large's 768x1024).
        """
        canvas = self._reference_canvas
        if canvas is None:
            return None
        if callable(canvas):
            return canvas(output_width, output_height)
        return canvas

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

        # Mirror `FluxInferenceEngine`: write the HuggingFace repo id
        # (looked up from the short slug) into `model_name` so PNG /
        # JPEG metadata tests can assert on the closed key set's value
        # (`Model` == `get_repo_id(model_id)`, AC-META-1).
        model_name = self._lookup_repo_id()

        return GenerationResult(
            image=image,
            seed=seed,
            generation_time=0.01,
            model_name=model_name,
            generated_width=width,
            generated_height=height,
        )

    def _lookup_repo_id(self) -> str:
        """Best-effort translation of the active slug to a HuggingFace
        repo id; falls back to "mock" when the slug is not registered
        or not yet attached to the engine (older tests that did not
        opt into the model_id attribute)."""
        model_id = getattr(self, "model_id", None)
        if model_id is None:
            return "mock"
        try:
            from textbrush.model.registry import get_repo_id

            return get_repo_id(model_id)
        except (ValueError, ImportError):
            return model_id

    def unload(self) -> None:
        self._loaded = False

    @property
    def device(self) -> str:
        return self._device

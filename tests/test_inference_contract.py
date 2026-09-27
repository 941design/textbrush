"""Behavioral contract tests for the inference engine reference-input seam.

This suite locks down the per-model engine contract documented in
`specs/epic-multi-reference-flux-image-editing/spec.md` (S5) and the
engine-side decisions in `ralph-plan.md` T04. The test stubs
`engine._pipeline` (per project `CLAUDE.md`: real model weights are gated;
only `tests/conftest.py:64-88` loads them under `--run-slow`) so the
assertions describe what the engine hands each pipeline, not what each
pipeline does internally.

AC coverage (from the T04 step list):
  - AC-MODEL-1 (schnell accepts zero references; per-slug sampling defaults).
  - AC-MODEL-2 (Kontext single reference at canvas size; _auto_resize off;
    max_area neutralised; copy semantics).
  - AC-MODEL-3 (FLUX.2 ordered multi-reference, exact-once delivery, same
    path twice still two list entries -- AC-INPUT-4).
  - AC-MODEL-6 (per-slug sampling defaults; `sampling_settings` override wins).
  - `reference_input_size` table: None for schnell; canvas for editing slugs.

Boundary note: the engine is responsible for asserting that every
`NormalizedReference` it forwards already has the canvas the pipeline
expects; references whose (width, height) do not match are rejected before
the pipeline is called. The size guard test is therefore part of this
contract -- a regression that lets an off-canvas reference through would
silently violate the documented "pipeline-internal resize disabled" rule.
"""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PIL import Image

# The engine's `generate()` imports torch unconditionally for
# `torch.Generator`. Contract tests that call `generate()` therefore
# require torch to be importable; tests that only inspect
# `reference_input_size`, `default_sampling_settings`, or the factory
# dispatch (no `generate()` call) would still need the engine import
# chain to succeed, which also pulls torch via the inference package
# init. The whole module is therefore gated on torch being available
# (matching the existing pattern in `test_flux_inference.py` and
# `test_flux_load.py`). Real model weights are gated separately in
# `tests/conftest.py:64-88` under `--run-slow`; here we only mock
# `_pipeline` (per project `CLAUDE.md`).
pytest.importorskip("torch")

from textbrush.inference.base import DEFAULT_DIMENSIONS, GenerationOptions
from textbrush.inference.factory import create_engine
from textbrush.inference.flux import (
    Flux2KleinInferenceEngine,
    FluxInferenceEngine,
    FluxKontextInferenceEngine,
)
from textbrush.model.registry import (
    FLUX1_KONTEXT_DEV,
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    get_repo_id,
)
from textbrush.references import NormalizedReference
from textbrush.validation import EDITING_PRESETS

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_reference(width: int, height: int, color: tuple[int, int, int]) -> NormalizedReference:
    """Build a NormalizedReference at exactly (width, height) with a solid colour.

    The engine asserts each reference's (width, height) equals its own
    `reference_input_size` canvas before forwarding it, so test fixtures
    must build the reference at that canvas. The colour lets ordering tests
    identify which reference is which by pixel.
    """
    image = Image.new("RGB", (width, height), color=color)
    return NormalizedReference(
        pixel_data=image,
        width=width,
        height=height,
        content_aspect_ratio=width / height,
        fill_value=128,
        decoded_at="1970-01-01T00:00:00+00:00",
    )


def _pipeline_returning(width: int, height: int) -> Mock:
    """A Mock that mimics a diffusers pipeline's `__call__` return shape."""
    mock_image = Image.new("RGB", (width, height), color=(128, 128, 128))
    pipeline = Mock(return_value=Mock(images=[mock_image]))
    return pipeline


# ---------------------------------------------------------------------------
# AC-MODEL-2: Kontext single-reference contract
# ---------------------------------------------------------------------------


class TestKontextSingleReference:
    """AC-MODEL-2: Kontext receives one reference at canvas size with
    `_auto_resize=False`, `max_area` neutralised to the requested canvas,
    and a copy of `pixel_data` (not the same object)."""

    def test_image_is_pil_at_canvas_size(self) -> None:
        """Kontext receives the reference as a PIL image at canvas size."""
        canvas = (768, 576)  # landscape-medium
        engine = FluxKontextInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        image = kwargs["image"]
        assert isinstance(image, Image.Image)
        assert image.size == canvas

    def test_auto_resize_false_and_max_area_neutralised(self) -> None:
        """`_auto_resize=False` and `max_area == gw * gh` so Kontext's
        pipeline-internal resize is provably disabled (T04 step 2: the
        no-op contract)."""
        canvas = (768, 576)
        engine = FluxKontextInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["_auto_resize"] is False
        assert kwargs["max_area"] == canvas[0] * canvas[1]

    def test_per_slug_sampling_defaults(self) -> None:
        """AC-MODEL-6: Kontext receives `num_inference_steps=28`,
        `guidance_scale=2.5` (per T04 design decisions)."""
        canvas = (768, 576)
        engine = FluxKontextInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["num_inference_steps"] == 28
        assert kwargs["guidance_scale"] == 2.5

    def test_image_is_a_copy_not_original(self) -> None:
        """The forwarded image is a copy of the held reference's
        `pixel_data`, not the same object (so an in-place pipeline mutation
        cannot corrupt the acknowledged reference data)."""
        canvas = (768, 576)
        engine = FluxKontextInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        original_pixel_data = reference.pixel_data
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        forwarded = engine._pipeline.call_args.kwargs["image"]
        assert forwarded is not original_pixel_data
        # Sanity: same pixels, different object identity.
        assert forwarded.tobytes() == original_pixel_data.tobytes()

    def test_size_guard_raises_before_pipeline_call(self) -> None:
        """A reference not at canvas size raises ValueError before the
        pipeline is called (T04 step 2 size-guard)."""
        engine = FluxKontextInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        # 700x500 != canvas (768, 576)
        reference = _make_reference(700, 500, (0, 255, 0))
        options = GenerationOptions(
            width=768,
            height=576,
            aspect_ratio="custom",
            references=(reference,),
        )

        with pytest.raises(ValueError, match="reference"):
            engine.generate("test", options)

        engine._pipeline.assert_not_called()


# ---------------------------------------------------------------------------
# AC-MODEL-3: FLUX.2 ordered multi-reference contract (and AC-INPUT-4)
# ---------------------------------------------------------------------------


class TestFlux2KleinMultiReference:
    """AC-MODEL-3: FLUX.2 receives a list of references in order, exact-once
    delivery, with AC-INPUT-4 (same path twice yields two list entries)."""

    def test_image_is_list_with_one_entry(self) -> None:
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        image = engine._pipeline.call_args.kwargs["image"]
        assert isinstance(image, list)
        assert len(image) == 1
        assert image[0].size == canvas

    @pytest.mark.parametrize("count", [1, 2, 3, 4])
    def test_image_list_length_matches_reference_count(self, count: int) -> None:
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        references = tuple(
            _make_reference(canvas[0], canvas[1], (i * 10, 0, 0)) for i in range(count)
        )
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=references,
        )

        engine.generate("test", options)

        image_list = engine._pipeline.call_args.kwargs["image"]
        assert isinstance(image_list, list)
        assert len(image_list) == count

    def test_reference_order_preserved(self) -> None:
        """The list is in the same order as `options.references`; identity
        is checkable by solid-colour pixel value."""
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        colours = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0)]
        references = tuple(_make_reference(canvas[0], canvas[1], c) for c in colours)
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=references,
        )

        engine.generate("test", options)

        image_list = engine._pipeline.call_args.kwargs["image"]
        assert len(image_list) == len(colours)
        for forwarded, expected_colour in zip(image_list, colours, strict=True):
            pixel = forwarded.getpixel((0, 0))
            assert pixel == expected_colour, (
                f"forwarded reference order must match options.references; "
                f"expected {expected_colour} at position, got {pixel}"
            )

    def test_duplicate_paths_yield_two_list_entries(self) -> None:
        """AC-INPUT-4: same path twice in the tuple -> two list entries
        to the pipeline."""
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference, reference),
        )

        engine.generate("test", options)

        image_list = engine._pipeline.call_args.kwargs["image"]
        assert isinstance(image_list, list)
        assert len(image_list) == 2

    def test_per_slug_sampling_defaults(self) -> None:
        """AC-MODEL-6: FLUX.2 klein 4B receives `num_inference_steps=4`,
        `guidance_scale=1.0` (the distilled model values)."""
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["num_inference_steps"] == 4
        assert kwargs["guidance_scale"] == 1.0

    def test_image_entries_are_copies(self) -> None:
        """Each forwarded image is a copy of the held reference, not the
        same object."""
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
        )

        engine.generate("test", options)

        forwarded = engine._pipeline.call_args.kwargs["image"][0]
        assert forwarded is not reference.pixel_data

    def test_size_guard_raises_before_pipeline_call(self) -> None:
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = Mock()
        engine._device = "cpu"

        # One reference correct, one not at canvas
        good = _make_reference(canvas[0], canvas[1], (0, 0, 0))
        bad = _make_reference(700, 500, (0, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(good, bad),
        )

        with pytest.raises(ValueError, match="reference"):
            engine.generate("test", options)

        engine._pipeline.assert_not_called()


# ---------------------------------------------------------------------------
# AC-MODEL-1: Schnell accepts no references
# ---------------------------------------------------------------------------


class TestSchnellNoReferences:
    """AC-MODEL-1: schnell engine with zero references passes no `image`
    kwarg and reports `guidance_scale == 0.0`."""

    def test_schnell_with_no_references_omits_image(self) -> None:
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(1024, 1024)
        engine._device = "cpu"

        options = GenerationOptions(aspect_ratio="1:1", references=())
        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert "image" not in kwargs

    def test_schnell_with_no_references_uses_distilled_defaults(self) -> None:
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(1024, 1024)
        engine._device = "cpu"

        options = GenerationOptions(aspect_ratio="1:1", references=())
        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["num_inference_steps"] == 4
        assert kwargs["guidance_scale"] == 0.0

    def test_schnell_with_references_raises(self) -> None:
        """Schnell is text-only and must refuse a request carrying
        references (T04 step 2: `ValueError` if `options.references` is
        non-empty for schnell)."""
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = Mock()
        engine._device = "cpu"

        reference = _make_reference(1024, 1024, (0, 0, 0))
        options = GenerationOptions(aspect_ratio="1:1", references=(reference,))

        with pytest.raises(ValueError, match="reference"):
            engine.generate("test", options)

        engine._pipeline.assert_not_called()

    def test_aspect_ratios_unchanged(self) -> None:
        """Schnell supports all eight ratios in the shared output-size contract."""
        assert set(FluxInferenceEngine.ASPECT_RATIOS) == {
            "1:1",
            "16:9",
            "4:3",
            "3:4",
            "3:1",
            "4:1",
            "4:5",
            "9:16",
        }


# ---------------------------------------------------------------------------
# AC-MODEL-6: per-slug sampling defaults; sampling_settings override wins
# ---------------------------------------------------------------------------


class TestSamplingSettings:
    """`default_sampling_settings` is per-slug; `options.sampling_settings`
    wins over the default for any matching key."""

    @pytest.mark.parametrize(
        "slug,expected",
        [
            (FLUX1_SCHNELL, {"num_inference_steps": 4, "guidance_scale": 0.0}),
            (FLUX1_KONTEXT_DEV, {"num_inference_steps": 28, "guidance_scale": 2.5}),
            (FLUX2_KLEIN_4B, {"num_inference_steps": 4, "guidance_scale": 1.0}),
        ],
    )
    def test_default_sampling_settings_per_slug(
        self, slug: str, expected: dict[str, float | int]
    ) -> None:
        engine = FluxInferenceEngine(model_id=slug)
        assert engine.default_sampling_settings() == expected

    def test_sampling_settings_override_wins(self) -> None:
        """Caller-supplied `sampling_settings` override the default."""
        canvas = (768, 576)
        engine = FluxKontextInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
            sampling_settings={"num_inference_steps": 10, "guidance_scale": 5.5},
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["num_inference_steps"] == 10
        assert kwargs["guidance_scale"] == 5.5

    def test_sampling_settings_partial_override(self) -> None:
        """A partial override leaves non-overridden defaults intact."""
        canvas = (768, 576)
        engine = Flux2KleinInferenceEngine()
        engine._pipeline = _pipeline_returning(*canvas)
        engine._device = "cpu"

        reference = _make_reference(canvas[0], canvas[1], (255, 0, 0))
        options = GenerationOptions(
            width=canvas[0],
            height=canvas[1],
            aspect_ratio="custom",
            references=(reference,),
            sampling_settings={"guidance_scale": 7.5},
        )

        engine.generate("test", options)

        kwargs = engine._pipeline.call_args.kwargs
        assert kwargs["num_inference_steps"] == 4  # default preserved
        assert kwargs["guidance_scale"] == 7.5  # override applied


# ---------------------------------------------------------------------------
# reference_input_size table (T04 step 2)
# ---------------------------------------------------------------------------


class TestReferenceInputSize:
    """`reference_input_size(output_width, output_height)` returns None
    for text-only schnell and the canvas (multiple of 16) for editing
    slugs. The largest preset canvas (1024x768 = 786_432 px) is below the
    FLUX.2 target area of 1_048_576 px so neither pipeline resizes it."""

    def test_schnell_returns_none(self) -> None:
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        assert engine.reference_input_size(1024, 768) is None

    @pytest.mark.parametrize("preset", sorted(EDITING_PRESETS))
    def test_kontext_returns_canvas(self, preset: str) -> None:
        width, height = EDITING_PRESETS[preset]
        engine = FluxKontextInferenceEngine()
        canvas = engine.reference_input_size(width, height)
        assert canvas is not None
        # Both axes rounded up to a multiple of 16.
        assert canvas[0] % 16 == 0
        assert canvas[1] % 16 == 0

    @pytest.mark.parametrize("preset", sorted(EDITING_PRESETS))
    def test_flux2_returns_canvas(self, preset: str) -> None:
        width, height = EDITING_PRESETS[preset]
        engine = Flux2KleinInferenceEngine()
        canvas = engine.reference_input_size(width, height)
        assert canvas is not None
        assert canvas[0] % 16 == 0
        assert canvas[1] % 16 == 0

    def test_largest_preset_canvas_below_flux2_target_area(self) -> None:
        """T04 design decision: the largest preset canvas (1024x768 =
        786,432 px) is below FLUX.2's 1,048,576 px target area, so the
        pipeline-internal area-based resize is provably a no-op for every
        preset."""
        from textbrush.inference.flux import round16

        engine = Flux2KleinInferenceEngine()
        canvas = engine.reference_input_size(1024, 768)
        assert canvas is not None
        assert canvas == (round16(1024), round16(768))
        assert canvas[0] * canvas[1] <= 1024 * 1024


# ---------------------------------------------------------------------------
# Factory (T04 step 3)
# ---------------------------------------------------------------------------


class TestFactoryDispatch:
    """`create_engine` maps each known slug to the documented concrete class
    and rejects unknown slugs."""

    def test_schnell_maps_to_flux_inference_engine(self) -> None:
        engine = create_engine("flux", model_id=FLUX1_SCHNELL)
        assert type(engine) is FluxInferenceEngine
        assert not isinstance(engine, FluxKontextInferenceEngine)
        assert not isinstance(engine, Flux2KleinInferenceEngine)
        assert engine.model_id == FLUX1_SCHNELL

    def test_kontext_maps_to_flux_kontext_engine(self) -> None:
        engine = create_engine("flux", model_id=FLUX1_KONTEXT_DEV)
        assert type(engine) is FluxKontextInferenceEngine
        assert engine.model_id == FLUX1_KONTEXT_DEV

    def test_klein_maps_to_flux2_klein_engine(self) -> None:
        engine = create_engine("flux", model_id=FLUX2_KLEIN_4B)
        assert type(engine) is Flux2KleinInferenceEngine
        assert engine.model_id == FLUX2_KLEIN_4B

    def test_unknown_backend_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Unknown inference backend"):
            create_engine("not-a-backend", model_id=FLUX1_SCHNELL)


# ---------------------------------------------------------------------------
# GenerationResult: model_name = HuggingFace repo id (AC-META-1 / AC-COMPAT-1)
# ---------------------------------------------------------------------------


class TestModelNameInResult:
    """`GenerationResult.model_name` is the HuggingFace repo id for every
    slug, so the PNG `Model` metadata keeps the repository id for the
    existing schnell path (T04 step 2 / AC-META-1)."""

    @pytest.mark.parametrize(
        "engine_factory,slug",
        [
            (lambda: FluxInferenceEngine(model_id=FLUX1_SCHNELL), FLUX1_SCHNELL),
            (lambda: FluxKontextInferenceEngine(), FLUX1_KONTEXT_DEV),
            (lambda: Flux2KleinInferenceEngine(), FLUX2_KLEIN_4B),
        ],
    )
    def test_model_name_is_repo_id(self, engine_factory, slug: str) -> None:
        engine = engine_factory()
        engine._pipeline = _pipeline_returning(1024, 1024)
        engine._device = "cpu"

        canvas = engine.reference_input_size(1024, 768)
        if canvas is None:
            options = GenerationOptions(
                width=1024,
                height=1024,
                aspect_ratio="custom",
            )
        else:
            width, height = canvas
            reference = _make_reference(width, height, (255, 0, 0))
            options = GenerationOptions(
                width=width,
                height=height,
                aspect_ratio="custom",
                references=(reference,),
            )

        result = engine.generate("test", options)

        assert result.model_name == get_repo_id(slug)


# ---------------------------------------------------------------------------
# Dimension resolution: no sentinel, aspect ratio reachable
# ---------------------------------------------------------------------------


class TestDimensionResolution:
    """`GenerationOptions.width/height` are values, never sentinels.

    Regression for gate-remediation round 7, finding 2: `generate` used to
    read the literal pair (512, 512) as "the caller did not specify
    dimensions", which made `_resolve_dimensions(aspect_ratio)` reachable
    only while every caller happened to default to 512. The moment the
    backend's no-args default moved to 1024 the aspect-ratio branch became
    dead code and `--aspect-ratio 16:9` silently produced a square image.
    """

    @pytest.mark.parametrize("aspect_ratio", sorted(FluxInferenceEngine.ASPECT_RATIOS))
    def test_unspecified_dimensions_resolve_from_aspect_ratio(self, aspect_ratio: str) -> None:
        """width=height=None -> the ASPECT_RATIOS entry, for every ratio."""
        expected = FluxInferenceEngine.ASPECT_RATIOS[aspect_ratio]
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(*expected)
        engine._device = "cpu"

        engine.generate("test", GenerationOptions(aspect_ratio=aspect_ratio))

        kwargs = engine._pipeline.call_args.kwargs
        assert (kwargs["width"], kwargs["height"]) == expected

    def test_explicit_512_is_a_request_not_a_sentinel(self) -> None:
        """An explicit 512x512 with a non-custom ratio is honoured as 512x512.

        Under the old sentinel rule this exact call resolved to the
        aspect-ratio canvas instead -- the caller's dimensions were
        discarded precisely because they happened to equal the sentinel.
        """
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(512, 512)
        engine._device = "cpu"

        engine.generate("test", GenerationOptions(aspect_ratio="1:1", width=512, height=512))

        kwargs = engine._pipeline.call_args.kwargs
        assert (kwargs["width"], kwargs["height"]) == (512, 512)

    def test_explicit_dimensions_beat_the_aspect_ratio(self) -> None:
        """Documented priority: explicit width/height > aspect_ratio lookup."""
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(800, 640)
        engine._device = "cpu"

        engine.generate("test", GenerationOptions(aspect_ratio="16:9", width=800, height=640))

        kwargs = engine._pipeline.call_args.kwargs
        assert (kwargs["width"], kwargs["height"]) == (800, 640)

    def test_custom_without_dimensions_falls_back_to_the_default_canvas(self) -> None:
        """ "custom" claims ownership of the dimensions but supplies none."""
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(*DEFAULT_DIMENSIONS)
        engine._device = "cpu"

        engine.generate("test", GenerationOptions(aspect_ratio="custom"))

        kwargs = engine._pipeline.call_args.kwargs
        assert (kwargs["width"], kwargs["height"]) == DEFAULT_DIMENSIONS

    def test_axes_resolve_independently(self) -> None:
        """One specified axis is kept; the other comes from the ratio."""
        ratio_width, ratio_height = FluxInferenceEngine.ASPECT_RATIOS["16:9"]
        engine = FluxInferenceEngine(model_id=FLUX1_SCHNELL)
        engine._pipeline = _pipeline_returning(640, ratio_height)
        engine._device = "cpu"

        engine.generate("test", GenerationOptions(aspect_ratio="16:9", width=640))

        kwargs = engine._pipeline.call_args.kwargs
        assert (kwargs["width"], kwargs["height"]) == (640, ratio_height)
        assert kwargs["width"] != ratio_width

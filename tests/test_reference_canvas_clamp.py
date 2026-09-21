"""The FLUX.2 reference canvas must land inside the pipeline's no-op area.

`Flux2KleinPipeline` resizes every input image whose area exceeds
1024*1024 and rounds each axis to a multiple of 16. A reference the
backend decoded at one size and the pipeline silently resized is exactly
the reference-identity drift S5-BC-1 forbids, so `reference_input_size`
clamps the canvas into that no-op region itself and the backend decodes
to the clamped size.

Deliberately free of the `torch` import guard the other inference tests
carry: `clamp16_to_area` and `reference_input_size` are pure arithmetic
on the model slug, and this file is the only place the clamp is pinned.
"""

from __future__ import annotations

import pytest

from textbrush.inference.flux import (
    FLUX2_REFERENCE_MAX_AREA,
    FluxInferenceEngine,
    clamp16_to_area,
    round16,
)
from textbrush.model.registry import FLUX1_KONTEXT_DEV, FLUX1_SCHNELL, FLUX2_KLEIN_4B

# Every output size the app offers, plus the extremes of the ladders.
OFFERED_SIZES = [
    (256, 256),
    (512, 512),
    (1024, 1024),
    (640, 360),
    (1280, 720),
    (1920, 1080),
    (512, 384),
    (768, 576),
    (1024, 768),
    (384, 512),
    (576, 768),
    (768, 1024),
    (900, 300),
    (1500, 500),
    (1800, 600),
    (1200, 300),
    (1600, 400),
    (540, 675),
    (1080, 1350),
    (360, 640),
    (1080, 1920),
]


class TestClampArithmetic:
    @pytest.mark.parametrize("width,height", OFFERED_SIZES)
    def test_result_is_inside_the_area_budget_and_on_the_grid(
        self, width: int, height: int
    ) -> None:
        clamped_width, clamped_height = clamp16_to_area(
            round16(width), round16(height), FLUX2_REFERENCE_MAX_AREA
        )
        assert clamped_width * clamped_height <= FLUX2_REFERENCE_MAX_AREA
        assert clamped_width % 16 == 0 and clamped_height % 16 == 0
        assert clamped_width >= 16 and clamped_height >= 16

    def test_a_size_already_inside_the_budget_is_returned_unchanged(self) -> None:
        assert clamp16_to_area(1024, 768, FLUX2_REFERENCE_MAX_AREA) == (1024, 768)
        assert clamp16_to_area(1024, 1024, FLUX2_REFERENCE_MAX_AREA) == (1024, 1024)

    def test_scaling_preserves_the_shape_within_one_grid_step(self) -> None:
        """1920x1080 is 16:9; the clamped canvas must still be about 16:9."""
        width, height = clamp16_to_area(1920, 1080, FLUX2_REFERENCE_MAX_AREA)
        assert abs((width / height) - (1920 / 1080)) < 0.05

    def test_an_extreme_ratio_terminates_and_stays_on_the_grid(self) -> None:
        """A shape whose scaled short axis hits the 16px floor still has to
        come back inside the budget -- the loop that walks the long axis
        down must terminate rather than spin."""
        width, height = clamp16_to_area(16384, 16, FLUX2_REFERENCE_MAX_AREA)
        assert width * height <= FLUX2_REFERENCE_MAX_AREA
        assert width % 16 == 0 and height % 16 == 0


class TestReferenceInputSizePerModel:
    def test_schnell_accepts_no_reference_canvas(self) -> None:
        engine = FluxInferenceEngine(FLUX1_SCHNELL)
        assert engine.reference_input_size(1024, 1024) is None

    @pytest.mark.parametrize("width,height", OFFERED_SIZES)
    def test_klein_never_exceeds_the_pipeline_resize_threshold(
        self, width: int, height: int
    ) -> None:
        engine = FluxInferenceEngine(FLUX2_KLEIN_4B)
        canvas = engine.reference_input_size(width, height)
        assert canvas is not None
        assert canvas[0] * canvas[1] <= FLUX2_REFERENCE_MAX_AREA

    def test_kontext_is_not_clamped(self) -> None:
        """Kontext is called with `_auto_resize=False` and an explicit
        `max_area`, so its canvas is the generation canvas -- rounded up
        onto the multiple-of-16 grid exactly as `generate` rounds it, and
        never area-clamped however large it gets."""
        engine = FluxInferenceEngine(FLUX1_KONTEXT_DEV)
        assert engine.reference_input_size(1920, 1080) == (round16(1920), round16(1080))
        assert round16(1920) * round16(1080) > FLUX2_REFERENCE_MAX_AREA

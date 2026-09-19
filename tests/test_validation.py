"""Tests for textbrush/validation.py.

This module owns cardinality and preset rules shared by both composition
roots (`textbrush.cli` and `textbrush.ipc.handler`); see
specs/epic-multi-reference-flux-image-editing/architecture.md "Why
`validation` is a module rather than duplicated logic." Anything that
asserts behavior across (model_id, reference_count, preset, aspect_ratio)
cells belongs here; anything that asserts a particular composition root's
plumbing of those calls (CLI exit codes, IPC wire envelope) belongs in
the per-root test suite, not here.

AC coverage:
  - AC-MODEL-4 (validation message names both model and rule text),
  - AC-INPUT-4 (duplicate paths are counted, not deduplicated),
  - AC-PRESET-1 (preset dimensions table is canonical),
  - S4 leaf-boundary contract (`validation` imports nothing above `model`).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.test_config import _internal_imports
from textbrush.model.registry import (
    FLUX1_KONTEXT_DEV,
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    ModelSpec,
    get_model_spec,
    iter_model_slugs,
)
from textbrush.validation import (
    DEFAULT_EDITING_PRESET,
    EDITING_PRESETS,
    TEXT_ASPECT_RATIOS,
    ValidationVerdict,
    editing_preset_dimensions,
    is_editing_model,
    resolve_preset,
    validate_selection,
)

# ---------------------------------------------------------------------------
# Per-model expected `required_model` table for invalid cardinality cells.
#
# Computed from the spec §5.1 / §7.3 rule set documented in the T03 step-2
# table; kept here as a literal table (not derived) so a test failure points
# to a concrete (model, count) cell rather than to "the rule changed."
# ---------------------------------------------------------------------------


def _expected_required_model(model_id: str, count: int) -> str | None:
    """Hand-derived mirror of the validate_selection `required_model` table.

    Only meaningful for cells where cardinality fails; for valid cells the
    helper returns None and the verdict itself carries `valid=True` with no
    recommendation.
    """
    spec = get_model_spec(model_id)
    is_valid = spec.min_references <= count <= spec.max_references
    if is_valid:
        return None
    max_supported = max(get_model_spec(slug).max_references for slug in iter_model_slugs())
    if count > max_supported:
        return None
    if 2 <= count <= max_supported:
        return FLUX2_KLEIN_4B
    if count == 1 and model_id == FLUX1_SCHNELL:
        return FLUX2_KLEIN_4B
    if count == 0 and spec.max_references > 0:
        return FLUX1_SCHNELL
    return None


def _expected_rule_text(spec: ModelSpec) -> str:
    """Hand-derived mirror of the validate_selection rule-text generator."""
    if spec.min_references == spec.max_references == 0:
        return "accepts no reference images"
    if spec.min_references == spec.max_references:
        return f"requires exactly {spec.min_references} reference image"
    return f"requires between {spec.min_references} and {spec.max_references} reference images"


# ---------------------------------------------------------------------------
# Cardinality: every (model, count) cell for counts 0..5
# ---------------------------------------------------------------------------


class TestCardinalityTable:
    """One test per cell of the (model, reference_count) grid.

    Counts 0..5 cover all five currently-supported bands (0, 1, 2, 3, 4)
    plus one cell above the FLUX.2 max that exercises the documented
    no-model path. Every known slug participates in every row.
    """

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_SCHNELL, FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5])
    def test_each_cell_validity(self, model_id: str, count: int) -> None:
        """Validity matches the spec's per-model cardinality band."""
        spec = get_model_spec(model_id)
        expected_valid = spec.min_references <= count <= spec.max_references

        verdict = validate_selection(model_id, count)

        assert verdict.valid is expected_valid, (
            f"validate_selection({model_id!r}, {count}) returned valid="
            f"{verdict.valid}; spec band is [{spec.min_references}, "
            f"{spec.max_references}]"
        )

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_SCHNELL, FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5])
    def test_each_invalid_cell_messages_name_model_and_rule(
        self, model_id: str, count: int
    ) -> None:
        """Every invalid cell's reason names both the model and the rule
        text (AC-MODEL-4). The literal reason is checked, not a derived
        one, so a generic message like "1-4 references required" cannot
        satisfy this contract (VQ-S4-007)."""
        spec = get_model_spec(model_id)
        is_valid = spec.min_references <= count <= spec.max_references
        if is_valid:
            pytest.skip("valid cell; reason assertions do not apply")

        verdict = validate_selection(model_id, count)

        assert verdict.valid is False
        assert verdict.reason is not None
        assert spec.slug in verdict.reason, (
            f"reason must name the slug {spec.slug!r}; got {verdict.reason!r}"
        )
        assert spec.display_name in verdict.reason, (
            f"reason must name the display_name {spec.display_name!r}; got {verdict.reason!r}"
        )
        assert _expected_rule_text(spec) in verdict.reason, (
            f"reason must contain the exact rule text "
            f"{_expected_rule_text(spec)!r}; got {verdict.reason!r}"
        )
        assert f"got {count}" in verdict.reason, (
            f"reason must include the offending count; got {verdict.reason!r}"
        )

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_SCHNELL, FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("count", [0, 1, 2, 3, 4, 5])
    def test_each_cell_required_model(self, model_id: str, count: int) -> None:
        """required_model matches the recommendation table for every cell."""
        expected = _expected_required_model(model_id, count)

        verdict = validate_selection(model_id, count)

        assert verdict.required_model == expected, (
            f"validate_selection({model_id!r}, {count}).required_model="
            f"{verdict.required_model!r}; expected {expected!r}"
        )

    def test_no_model_supports_more_than_four_references(self) -> None:
        """The "no supported model accepts more than N" tail is appended
        exactly for the >_MAX_SUPPORTED case, naming the bound the
        registry exposes today."""
        verdict = validate_selection(FLUX2_KLEIN_4B, 5)

        assert verdict.valid is False
        assert verdict.required_model is None
        assert verdict.reason is not None
        max_supported = max(get_model_spec(slug).max_references for slug in iter_model_slugs())
        assert f"no supported model accepts more than {max_supported}" in verdict.reason

    def test_range_spanning_generic_message_does_not_satisfy_rule(self) -> None:
        """VQ-S4-007: a generic "1-4 references required" message does not
        satisfy AC-MODEL-4 -- the message must name the model and its
        EXACT rule. The FLUX.2 cell for count=0 carries "between 1 and 4"
        because that is the model-specific band, and the slug/display_name
        prefixes are what disambiguate which model's band is meant."""
        verdict = validate_selection(FLUX2_KLEIN_4B, 0)

        assert verdict.valid is False
        assert verdict.reason is not None
        assert FLUX2_KLEIN_4B in verdict.reason
        assert "FLUX.2 [klein] 4B" in verdict.reason
        assert "between 1 and 4 reference images" in verdict.reason
        # Negative assertion: a bare "1-4 references required" (without
        # model name) would NOT satisfy AC-MODEL-4 because it doesn't name
        # the model. Verify that such a bare phrase is absent here so a
        # regression toward a generic message would be caught.
        assert not re.search(r"^\s*1-4 references required", verdict.reason)


# ---------------------------------------------------------------------------
# Unknown slug
# ---------------------------------------------------------------------------


class TestUnknownSlug:
    """Unknown model slugs short-circuit to a verdict whose reason names
    the unknown id (AC-MODEL-4: "unknown model: ..."); required_model is
    None because no recommendation is meaningful without a resolved spec."""

    def test_unknown_slug_is_invalid(self) -> None:
        verdict = validate_selection("flux3-megatron", 0)

        assert verdict.valid is False
        assert verdict.reason == "unknown model: flux3-megatron"
        assert verdict.required_model is None


# ---------------------------------------------------------------------------
# Bidirectional preset and aspect-ratio rules
# ---------------------------------------------------------------------------


class TestBidirectionalPresetRules:
    """Editing preset direction 1 (preset in EDITING_PRESETS on a text
    model): invalid. Aspect-ratio direction (text ratio on editing model):
    invalid. Editing preset on editing model with valid cardinality: valid."""

    @pytest.mark.parametrize("preset", sorted(EDITING_PRESETS))
    def test_editing_preset_on_schnell_with_zero_references_is_invalid(self, preset: str) -> None:
        """Schnell + 0 references + any editing preset: cardinality passes
        (schnell wants 0), but the preset direction 1 rule rejects the
        preset because schnell is not editing-capable."""
        verdict = validate_selection(FLUX1_SCHNELL, 0, preset=preset)

        assert verdict.valid is False
        assert verdict.reason == (f"editing preset {preset} requires an editing-capable model")

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize(
        "aspect_ratio",
        sorted(TEXT_ASPECT_RATIOS),
    )
    def test_text_aspect_ratio_on_editing_model_is_invalid(
        self, model_id: str, aspect_ratio: str
    ) -> None:
        """Editing-capable model + valid cardinality + a text-only aspect
        ratio: the aspect-ratio rule rejects the ratio and points the
        caller at the editing-preset alternatives. Cardinality is set to
        1 (Kontext) or 1 (FLUX.2 lower bound) so this test isolates the
        aspect-ratio check, not the cardinality check."""
        verdict = validate_selection(model_id, 1, aspect_ratio=aspect_ratio)

        assert verdict.valid is False
        assert verdict.reason is not None
        assert (
            f"text-only aspect ratio {aspect_ratio} is not valid for "
            f"editing model {model_id}" in verdict.reason
        )
        assert "choose one of " in verdict.reason
        # The list of editing presets is included verbatim so the UI can
        # surface them without re-importing EDITING_PRESETS.
        for preset in EDITING_PRESETS:
            assert preset in verdict.reason

    def test_aspect_ratio_custom_is_accepted_on_editing_model(self) -> None:
        """`aspect_ratio="custom"` is the bridge for editing models that
        pair width/height (T10 wires the UI to send this). It must NOT
        trip the aspect-ratio rule -- otherwise the only legal aspect
        ratio on editing models would be the literal text ratios."""
        verdict = validate_selection(FLUX1_KONTEXT_DEV, 1, aspect_ratio="custom")

        assert verdict.valid is True

    def test_aspect_ratio_none_is_accepted_on_editing_model(self) -> None:
        """`aspect_ratio=None` (the default, and the only value callers
        currently pass before T08) must not trip the aspect-ratio rule."""
        verdict = validate_selection(FLUX1_KONTEXT_DEV, 1, aspect_ratio=None)

        assert verdict.valid is True

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("preset", sorted(EDITING_PRESETS))
    def test_editing_preset_on_editing_model_with_valid_cardinality_is_valid(
        self, model_id: str, preset: str
    ) -> None:
        """Editing-capable model + valid cardinality + a recognised
        editing preset: valid. The cardinality here is 1 (the lower bound
        for both Kontext and FLUX.2) so the test does not also exercise a
        cardinality mismatch."""
        verdict = validate_selection(model_id, 1, preset=preset)

        assert verdict.valid is True

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("preset", sorted(EDITING_PRESETS))
    def test_editing_preset_on_editing_model_with_invalid_cardinality_is_invalid(
        self, model_id: str, preset: str
    ) -> None:
        """Editing-capable model + invalid cardinality + a recognised
        editing preset: cardinality is the first-failure rule, so the
        preset value never reaches the preset-direction check. The
        reason therefore names the cardinality band, not the preset."""
        verdict = validate_selection(model_id, 0, preset=preset)

        assert verdict.valid is False
        assert "reference" in (verdict.reason or "")
        # The preset-direction message would be a tell that ordering
        # broke; absence here proves cardinality runs first.
        assert "editing preset" not in (verdict.reason or "")

    def test_unknown_editing_preset_is_rejected(self) -> None:
        """A preset value that is not in EDITING_PRESETS is rejected via
        the preset direction 2 rule, naming the offending value."""
        verdict = validate_selection(FLUX1_KONTEXT_DEV, 1, preset="square-huge")

        assert verdict.valid is False
        assert verdict.reason == "unknown editing preset: square-huge"

    def test_unknown_editing_preset_is_rejected_on_text_model(self) -> None:
        """Direction 2 (unknown preset identifier) runs after direction 1
        (preset-in-EDITING_PRESETS-on-text-model), so a bogus preset name
        on FLUX.1 schnell still surfaces as 'unknown editing preset',
        not 'editing preset X requires an editing-capable model' -- both
        are correct, but direction 2 has the more useful reason for an
        unrecognised identifier."""
        verdict = validate_selection(FLUX1_SCHNELL, 0, preset="square-huge")

        assert verdict.valid is False
        assert verdict.reason == "unknown editing preset: square-huge"


# ---------------------------------------------------------------------------
# Duplicate-path semantics (AC-INPUT-4)
# ---------------------------------------------------------------------------


class TestDuplicatePathSemantics:
    """`validate_selection` takes a count, not paths, so it cannot and
    must not deduplicate. The same file path counted twice is still two
    occurrences."""

    def test_flux2_with_two_references_is_valid(self) -> None:
        """FLUX.2 accepts 1-4 references; 2 is in band, regardless of
        whether the caller would later supply the same path twice."""
        verdict = validate_selection(FLUX2_KLEIN_4B, 2)

        assert verdict.valid is True

    def test_kontext_with_two_references_is_invalid_even_if_same_path_twice(
        self,
    ) -> None:
        """Kontext wants exactly 1 reference; 2 is out of band even when
        the caller would pass the same path twice -- the validator must
        count occurrences, not distinct paths."""
        verdict = validate_selection(FLUX1_KONTEXT_DEV, 2)

        assert verdict.valid is False
        assert verdict.reason is not None
        assert "requires exactly 1 reference image" in verdict.reason


# ---------------------------------------------------------------------------
# editing_preset_dimensions table
# ---------------------------------------------------------------------------


class TestEditingPresetDimensions:
    """The preset identifier -> (width, height) table is the contract the
    backend reads when normalising references to the engine canvas (S6)
    and the contract the UI reads when sizing previews. architecture.md
    "Preset lexicon" lists exactly the six entries below; a seventh or
    a remapping would silently break both consumers."""

    EXPECTED_TABLE: dict[str, tuple[int, int]] = {
        "landscape-small": (512, 384),
        "landscape-medium": (768, 576),
        "landscape-large": (1024, 768),
        "portrait-small": (384, 512),
        "portrait-medium": (576, 768),
        "portrait-large": (768, 1024),
    }

    def test_six_entries(self) -> None:
        assert len(EDITING_PRESETS) == 6
        assert set(EDITING_PRESETS) == set(self.EXPECTED_TABLE)

    @pytest.mark.parametrize("preset", sorted(EXPECTED_TABLE))
    def test_each_preset_dimension(self, preset: str) -> None:
        assert editing_preset_dimensions(preset) == self.EXPECTED_TABLE[preset]

    def test_unknown_preset_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown editing preset: not-a-real-preset"):
            editing_preset_dimensions("not-a-real-preset")


# ---------------------------------------------------------------------------
# TEXT_ASPECT_RATIOS table
# ---------------------------------------------------------------------------


class TestTextAspectRatiosTable:
    """The text-only aspect-ratio vocabulary must be exactly the six
    keys of cli.py's SUPPORTED_RATIOS, in the order cli.py declares them.
    validation is the canonical owner of "what is text-only"; cli keeps
    the resolution choices but does NOT redefine the vocabulary."""

    def test_six_entries(self) -> None:
        assert len(TEXT_ASPECT_RATIOS) == 6

    def test_matches_cli_supported_ratios(self) -> None:
        # Imported lazily so the leaf-boundary test below does not falsely
        # see a top-level cli import from the validation module.
        from textbrush.cli import SUPPORTED_RATIOS

        assert tuple(SUPPORTED_RATIOS.keys()) == TEXT_ASPECT_RATIOS


# ---------------------------------------------------------------------------
# is_editing_model
# ---------------------------------------------------------------------------


class TestIsEditingModel:
    """`is_editing_model` derives from `ModelSpec.max_references > 0` so
    that adding a future editing model touches the registry, not this
    module. Tests below cover both editing-capable and text-only slugs
    plus the negative path (an unknown slug raises -- by construction,
    not by silent fallback to False)."""

    def test_kontext_is_editing(self) -> None:
        assert is_editing_model(FLUX1_KONTEXT_DEV) is True

    def test_klein_is_editing(self) -> None:
        assert is_editing_model(FLUX2_KLEIN_4B) is True

    def test_schnell_is_not_editing(self) -> None:
        assert is_editing_model(FLUX1_SCHNELL) is False

    def test_unknown_slug_raises(self) -> None:
        # The leaf validator contract is that an unknown model id is a
        # hard error, not a silent False -- callers handle it upstream
        # via validate_selection. is_editing_model is a thin convenience
        # wrapper and inherits the registry's ValueError.
        with pytest.raises(ValueError):
            is_editing_model("not-a-real-model")


# ---------------------------------------------------------------------------
# resolve_preset
# ---------------------------------------------------------------------------


class TestResolvePreset:
    """`resolve_preset` centralises the explicit-else-default rule so
    callers (backend, CLI, IPC handler) do not each restate it. The
    contract is: explicit preset wins; else the configured default applies
    to an editing-capable model; else None. Schnell + default returns
    None because schnell does not consume an editing preset."""

    def test_explicit_preset_wins_over_default(self) -> None:
        result = resolve_preset(FLUX1_KONTEXT_DEV, "portrait-large", "landscape-medium")

        assert result == "portrait-large"

    def test_editing_model_uses_default_when_preset_none(self) -> None:
        result = resolve_preset(FLUX1_KONTEXT_DEV, None, "landscape-medium")

        assert result == "landscape-medium"

    def test_schnell_returns_none_when_preset_none(self) -> None:
        result = resolve_preset(FLUX1_SCHNELL, None, "landscape-medium")

        assert result is None

    def test_explicit_none_value_still_resolves_to_none(self) -> None:
        """An explicit `preset=None` is the same as "not given" -- the
        function does not distinguish the two; the result is still the
        default-or-None outcome."""
        result = resolve_preset(FLUX1_SCHNELL, None, "landscape-small")

        assert result is None

    def test_explicit_preset_wins_for_schnell(self) -> None:
        """An explicit preset on a text model is still returned verbatim
        by resolve_preset; the cross-direction rejection is validate_selection's
        job, not this resolver's (separating the two keeps each function
        single-purpose)."""
        result = resolve_preset(FLUX1_SCHNELL, "landscape-medium", "landscape-medium")

        assert result == "landscape-medium"

    def test_custom_default_preset_propagates(self) -> None:
        """A non-canonical default (e.g. set via TEXTBRUSH_EDITING_DEFAULT_PRESET)
        propagates through unchanged when the caller passed no explicit preset."""
        result = resolve_preset(FLUX2_KLEIN_4B, None, "portrait-small")

        assert result == "portrait-small"


# ---------------------------------------------------------------------------
# Verdict contract: valid=False always carries reason; never partially populated
# ---------------------------------------------------------------------------


class TestVerdictContract:
    """AC-MODEL-4: `valid=False` always carries `reason` populated; no
    partially-populated verdicts leak to callers."""

    @pytest.mark.parametrize(
        "model_id",
        [FLUX1_SCHNELL, FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B],
    )
    @pytest.mark.parametrize("count", [0, 1, 2, 5])
    def test_invalid_verdict_always_has_reason(self, model_id: str, count: int) -> None:
        spec = get_model_spec(model_id)
        is_valid = spec.min_references <= count <= spec.max_references
        if is_valid:
            pytest.skip("valid cell; reason assertions do not apply")

        verdict = validate_selection(model_id, count)

        assert verdict.valid is False
        assert verdict.reason is not None
        assert verdict.reason != ""

    def test_unknown_model_invalid_verdict_has_reason(self) -> None:
        verdict = validate_selection("not-a-real-model", 0)

        assert verdict.valid is False
        assert verdict.reason == "unknown model: not-a-real-model"

    def test_invalid_preset_verdict_has_reason(self) -> None:
        verdict = validate_selection(FLUX1_KONTEXT_DEV, 1, preset="square-huge")

        assert verdict.valid is False
        assert verdict.reason is not None


# ---------------------------------------------------------------------------
# Structural / leaf-module contract
# ---------------------------------------------------------------------------


class TestValidationLeafBoundary:
    """architecture.md boundary rule 2 + VQ-S4-002: `validation` is a leaf
    module and must not import backend/worker/ipc/inference. The only
    internal (textbrush.*) dependency permitted is textbrush.model.registry
    -- which `validation` needs for the per-model cardinality and the
    `_MAX_SUPPORTED` bound."""

    EXPECTED_INTERNAL_IMPORTS = {"textbrush.model.registry"}

    def test_validation_module_imports_only_model_registry(self) -> None:
        import textbrush.validation as validation_module

        source = Path(validation_module.__file__).read_text()
        internal_imports = _internal_imports(source)

        assert internal_imports <= self.EXPECTED_INTERNAL_IMPORTS, (
            f"validation.py must import only textbrush.model.registry "
            f"internally; found {internal_imports}"
        )

    def test_validation_module_no_forbidden_internal_imports(self) -> None:
        import textbrush.validation as validation_module

        source = Path(validation_module.__file__).read_text()
        internal_imports = _internal_imports(source)

        forbidden = {
            "textbrush.backend",
            "textbrush.worker",
            "textbrush.ipc",
            "textbrush.inference",
            "textbrush.config",
            "textbrush.cli",
            "textbrush.references",
        }
        violations = {
            i for i in internal_imports if any(i == f or i.startswith(f + ".") for f in forbidden)
        }
        assert not violations, (
            f"validation.py must not import any of {sorted(forbidden)}; found {violations}"
        )


class TestNoCardinalityLiteralFour:
    """The `> _MAX_SUPPORTED` no-model branch is the ONLY place that may
    encode an upper cardinality bound; everywhere else upper bounds come
    from the per-model spec. This forbids `reference_count > 4` literals
    so the next FLUX.2-style model with `max_references=5` does not need
    a second grep + edit to validation.py."""

    def test_no_reference_count_literal_4_comparison(self) -> None:
        import textbrush.validation as validation_module

        source = Path(validation_module.__file__).read_text()

        # Forbidden: literal `4` in a cardinality comparison. Whitelist
        # `> _MAX_SUPPORTED` (which expands to `max(...)` at module load
        # time and uses no literal `4`).
        forbidden_patterns = [
            r"reference_count\s*>\s*4\b",
            r"reference_count\s*>=\s*4\b",
            r"reference_count\s*==\s*4\b",
            r"reference_count\s*!=\s*4\b",
            r"reference_count\s*<\s*4\b",
            r"reference_count\s*<=\s*4\b",
        ]
        for pattern in forbidden_patterns:
            match = re.search(pattern, source)
            assert match is None, (
                f"validation.py must not use a literal 4 in a "
                f"reference_count comparison; found {match.group()!r}. "
                f"Use _MAX_SUPPORTED (max over ModelSpec.max_references) "
                f"instead so the bound follows the registry."
            )

    def test_module_uses_max_supported_constant(self) -> None:
        """The `_MAX_SUPPORTED` constant is computed from the registry
        rather than a literal, so a future model with a larger bound
        automatically extends the "no supported model accepts more than N"
        tail message."""
        import textbrush.validation as validation_module

        source = Path(validation_module.__file__).read_text()

        assert "_MAX_SUPPORTED" in source, (
            "validation.py must compute _MAX_SUPPORTED from the registry "
            "rather than hardcoding an upper cardinality bound"
        )
        assert "max(" in source, "_MAX_SUPPORTED must be derived via max() over the registry"


# ---------------------------------------------------------------------------
# ValidationVerdict dataclass surface
# ---------------------------------------------------------------------------


class TestValidationVerdictDataclass:
    """The verdict dataclass is part of the public surface; its field
    set is what callers read (see `backend.apply_configuration` in T06).
    Adding a field would silently pass through every test that only
    asserts `valid` and `reason`; these tests guard against accidental
    shape drift."""

    def test_is_dataclass(self) -> None:
        import dataclasses

        assert dataclasses.is_dataclass(ValidationVerdict)

    def test_is_frozen(self) -> None:
        import dataclasses

        assert dataclasses.fields(ValidationVerdict) is not None
        # frozen=True makes assignment raise FrozenInstanceError rather
        # than silently mutate the verdict (which callers pass through
        # without expecting mutation).
        verdict = ValidationVerdict(valid=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            verdict.valid = False  # type: ignore[misc]

    def test_fields(self) -> None:
        import dataclasses

        field_names = {f.name for f in dataclasses.fields(ValidationVerdict)}
        assert field_names == {"valid", "reason", "required_model"}

    def test_valid_true_has_no_required_model_by_default(self) -> None:
        verdict = ValidationVerdict(valid=True)

        assert verdict.required_model is None
        assert verdict.reason is None

    def test_valid_true_with_explicit_reason_is_allowed(self) -> None:
        """A `valid=True` verdict with an explanatory reason is permitted
        by the dataclass (no runtime check forbids it); callers decide
        whether to surface it. validate_selection itself never produces
        one, so this is a dataclass-shape test only."""
        verdict = ValidationVerdict(valid=True, reason="informational")

        assert verdict.reason == "informational"


# ---------------------------------------------------------------------------
# Default editing preset constant
# ---------------------------------------------------------------------------


class TestDefaultEditingPreset:
    """`DEFAULT_EDITING_PRESET` is the canonical fallback. The
    `config.editing.default_preset` field (which the user can override)
    is separate from this constant -- this one is the built-in default
    the field starts from and the value the resolver falls back to when
    nothing else applies."""

    def test_default_editing_preset_is_a_known_preset(self) -> None:
        assert DEFAULT_EDITING_PRESET in EDITING_PRESETS

    def test_default_editing_preset_dimensions_resolve(self) -> None:
        # No exception means the default is itself a valid key in the
        # preset table -- a regression where the constant and the table
        # drift apart would surface here.
        assert editing_preset_dimensions(DEFAULT_EDITING_PRESET) is not None

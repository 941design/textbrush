"""Shared, side-effect-free model, reference, and preset validation.

This module is the single owner of cardinality and preset rules shared
by both composition roots (`textbrush.cli` and `textbrush.ipc.handler`).
architecture.md boundary rule 2: `validation` is a leaf and must not
import `backend`, `worker`, `ipc`, `inference`, `config`, `cli`, or
`references`. Its only internal dependency is `textbrush.model.registry`,
which owns the per-model cardinality and identity data it consumes.

Public surface (this module's seam contract, mirrored in the composition
roots and the desktop UI):

- `EDITING_PRESETS`, `DEFAULT_EDITING_PRESET`: the canonical identifier
  -> (width, height) table for editing outputs and its built-in default.
  Owned here so config, cli, ipc, and desktop-ui all agree on the
  spelling (architecture.md "Preset lexicon"). The `landscape-medium`
  identifier reproduces pre-epic FLUX.1 schnell text-to-image behavior
  so config files predating this epic load unchanged (AC-COMPAT-1).

- `TEXT_ASPECT_RATIOS`: the aspect-ratio vocabulary, copied here from
  `cli.py`'s `SUPPORTED_RATIOS` keys so validation owns the set of
  identifiers that exist. Every model accepts every one of them; the
  name is historical (see the table's own comment). The CLI resolution
  table (`SUPPORTED_RATIOS`) stays in `cli.py` -- this module owns the
  *vocabulary*, not the resolutions.

- `ValidationVerdict`: the verdict dataclass. `valid=False` always
  carries `reason` (AC-MODEL-4); `required_model` is populated only
  when a different model would have made the selection compatible.

- `validate_selection(model_id, reference_count, preset=None,
  aspect_ratio=None)`: the rule engine. First-failure-wins ordering;
  cardinality runs before preset/aspect-ratio so a request that fails
  cardinality surfaces a cardinality message, not a preset one.

- `resolve_preset(model_id, preset, default_preset) -> str | None`:
  centralised preset-default resolution; explicit preset wins, else
  the configured default applies for editing-capable models, else None.

- `is_editing_model(model_id) -> bool`: `ModelSpec.max_references > 0`,
  the canonical definition of "editing-capable" used throughout the
  codebase.

- `editing_preset_dimensions(preset) -> tuple[int, int]`: lookup helper
  for the preset table, and `preset_for_dimensions(width, height) ->
  str | None`, its inverse, for callers that carry explicit pixel
  dimensions and want the identifier naming them (if any).

`validation` is a leaf, but it does depend on `textbrush.model.registry`
(S2). Per architecture.md boundary rule 2, that is the one legal
internal dependency for this module; tests/test_validation.py enforces
this in `TestValidationLeafBoundary`.

Determinism (AC-PROCESS-2): this module performs no IO and no
randomness. Its outputs depend only on its inputs and the static
`ModelSpec` table.
"""

from __future__ import annotations

from dataclasses import dataclass

from textbrush.model.registry import (
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    get_model_spec,
    iter_model_slugs,
)

EDITING_PRESETS: dict[str, tuple[int, int]] = {
    "landscape-small": (512, 384),
    "landscape-medium": (768, 576),
    "landscape-large": (1024, 768),
    "portrait-small": (384, 512),
    "portrait-medium": (576, 768),
    "portrait-large": (768, 1024),
}
DEFAULT_EDITING_PRESET = "landscape-medium"

# The aspect-ratio vocabulary. Order and contents mirror `cli.py`'s
# `SUPPORTED_RATIOS` keys exactly -- this module owns the vocabulary
# (which identifiers exist), cli owns the per-ratio resolution choices.
# They cannot drift without a deliberate edit because
# `tests/test_validation.py::TestTextAspectRatiosTable` compares the two
# and fails if either is reordered or extended without the other.
#
# The name is historical: these ratios were once refused for editing-
# capable models, which had to use `EDITING_PRESETS` instead. They no
# longer are -- the desktop UI offers one output-size group to every
# model (4:3 and 3:4 are the same ladders the landscape-* / portrait-*
# presets name) and always sends explicit pixel dimensions alongside the
# ratio, so there is nothing left for a per-mode ratio rule to protect.
#
# Order is height/width ascending -- widest first, tallest last; see
# `cli.SUPPORTED_RATIOS` for why.
TEXT_ASPECT_RATIOS: tuple[str, ...] = (
    "4:1",
    "3:1",
    "16:9",
    "4:3",
    "1:1",
    "4:5",
    "3:4",
    "9:16",
)

# Computed once at module load from the per-model registry so the upper
# cardinality bound follows the registry, not a literal in this file.
# Used by `validate_selection` for the documented "no supported model
# accepts more than N" tail message and for the FLUX.2 recommendation
# band. If a future model raises `max_references` above the current
# value, this constant updates automatically.
_MAX_SUPPORTED = max(get_model_spec(slug).max_references for slug in iter_model_slugs())


@dataclass(frozen=True)
class ValidationVerdict:
    """Outcome of a single validation call.

    CONTRACT:
      Invariants:
        - When `valid` is False, `reason` is a non-empty string naming
          both the offending model (slug + display_name) and the exact
          cardinality or preset rule that failed (AC-MODEL-4). A generic
          range-spanning message (e.g. "1-4 references required") does
          NOT satisfy this contract; the message must identify the
          specific model and rule that produced the verdict.
        - `required_model` is populated only on cardinality failure, and
          only when a different model would have made the selection
          compatible. It is `None` on success, on unknown-model
          failures (no recommendation is meaningful without a resolved
          spec), and on no-model-supported failures (reference_count
          exceeds every registered model).
        - `reason` is `None` only when `valid` is True.
    """

    valid: bool
    reason: str | None = None
    required_model: str | None = None


def is_editing_model(model_id: str) -> bool:
    """True when `model_id` is an editing-capable registered model.

    A model is editing-capable iff it accepts at least one reference
    image, i.e. `ModelSpec.max_references > 0`. The definition lives
    here (not in callers) so adding a future editing model touches the
    registry, not every conditional in the codebase.

    CONTRACT:
      Inputs:
        model_id: a short slug from `iter_model_slugs()`.
      Outputs:
        True iff `model_id` is editing-capable.
      Raises:
        ValueError: model_id is not a known registry slug (delegated
          from `get_model_spec`); a silent False would mask typos in
          composition-root code.
    """
    return get_model_spec(model_id).max_references > 0


def editing_preset_dimensions(preset: str) -> tuple[int, int]:
    """Return the (width, height) for a recognised editing preset.

    CONTRACT:
      Inputs:
        preset: a key in `EDITING_PRESETS`.
      Outputs:
        The (width, height) tuple registered for that preset.
      Raises:
        ValueError: preset is not a known editing preset.
    """
    try:
        return EDITING_PRESETS[preset]
    except KeyError as exc:
        raise ValueError(f"unknown editing preset: {preset}") from exc


def preset_for_dimensions(width: int, height: int) -> str | None:
    """Return the preset identifier naming exactly `(width, height)`.

    The inverse of `editing_preset_dimensions`. Callers that carry
    explicit pixel dimensions (the desktop UI sends them for every
    output-size choice) use this to label an acknowledged canvas with
    the preset identifier config files and `--preset` speak, and get
    None for a size no preset names -- which is not an error, only the
    absence of a name.

    CONTRACT:
      Inputs:
        width, height: pixel dimensions.
      Outputs:
        The matching key of `EDITING_PRESETS`, or None when no preset
        names those dimensions. The first match wins; `EDITING_PRESETS`
        holds no duplicate dimension pairs.
    """
    for identifier, dimensions in EDITING_PRESETS.items():
        if dimensions == (width, height):
            return identifier
    return None


def resolve_preset(model_id: str, preset: str | None, default_preset: str) -> str | None:
    """Resolve the active editing preset for a (model, requested preset) pair.

    Centralises the explicit-else-default rule so callers (backend, CLI,
    IPC handler) do not each restate it.

    CONTRACT:
      Inputs:
        model_id: a short slug from `iter_model_slugs()`.
        preset: the caller's explicit preset value, or None when the
          caller has no override.
        default_preset: the configured default (typically
          `config.editing.default_preset`).
      Outputs:
        - `preset` when the caller gave one (verbatim, even if it is
          later rejected by `validate_selection` -- separation of
          concerns: this resolver picks a value to try, validation
          decides whether it is acceptable).
        - `default_preset` when no explicit preset and the model is
          editing-capable.
        - None when no explicit preset and the model is text-only
          (schnell), since text models do not consume an editing preset.
    """
    if preset is not None:
        return preset
    if is_editing_model(model_id):
        return default_preset
    return None


def validate_selection(
    model_id: str,
    reference_count: int,
    preset: str | None = None,
    aspect_ratio: str | None = None,
) -> ValidationVerdict:
    """Validate a (model, reference_count, preset, aspect_ratio) selection.

    First-failure-wins ordering: unknown slug, then cardinality, then
    preset direction 1 (preset-in-EDITING_PRESETS-on-text-model),
    then preset direction 2 (unknown preset identifier), then valid.
    Cardinality runs before the preset checks so a request that fails
    cardinality surfaces a cardinality message, not a confusing preset
    message (VQ-S4-005). `aspect_ratio` carries no rule of its own any
    more -- see the final step of the implementation for why.

    CONTRACT:
      Inputs:
        model_id: a short slug from `iter_model_slugs()`. Any other
          string produces an `unknown model` verdict (AC-MODEL-4).
        reference_count: a non-negative integer count of references the
          caller intends to supply. Validation counts occurrences, not
          distinct paths -- the same file path passed twice is still
          two occurrences (AC-INPUT-4).
        preset: an explicit editing-preset identifier, or None to use
          the default. Cross-direction rejections (preset in
          EDITING_PRESETS on a text model, preset identifier not in
          EDITING_PRESETS) are reported here so callers do not need to
          re-implement the rule (architecture.md "Why `validation` is a
          module rather than duplicated logic").
        aspect_ratio: an aspect-ratio identifier from
          `TEXT_ASPECT_RATIOS`, or None, or the literal "custom".
          Accepted for every model: the desktop UI offers one
          output-size group to all of them and sends explicit pixel
          dimensions alongside the ratio.

      Outputs:
        ValidationVerdict.

      Invariants:
        - For every (model_id, reference_count) pair, `valid` matches
          `spec.min_references <= reference_count <= spec.max_references`.
        - On `valid=False`, `reason` is non-empty, names the slug and
          display_name of the offending model, includes the exact
          cardinality rule text (or the specific preset/aspect-ratio
          message), and includes the offending count.
        - `required_model` follows the documented table: FLUX.2 when
          2 <= count <= _MAX_SUPPORTED; FLUX.2 when count == 1 and the
          selected model is FLUX.1 schnell (spec §5.1 prefers FLUX.2);
          FLUX.1 schnell when count == 0 and the selected model is
          editing-capable; None when count exceeds every registered
          model's capacity.

      Properties:
        - Pure: no IO, no randomness; same inputs always produce the
          same verdict (AC-PROCESS-2).
        - Cardinality band is read from `ModelSpec`, not restated in
          this module, so a future editing model extends it
          automatically.
        - The `_MAX_SUPPORTED` constant is computed from the registry at
          module load; the upper cardinality bound follows the registry,
          not a literal in this file.
    """
    try:
        spec = get_model_spec(model_id)
    except ValueError:
        return ValidationVerdict(False, f"unknown model: {model_id}")

    editing_capable = spec.max_references > 0

    # Cardinality: first-failure rule. Runs before preset/aspect-ratio so
    # those messages do not mask a cardinality mismatch (VQ-S4-005).
    if reference_count < spec.min_references or reference_count > spec.max_references:
        if spec.min_references == spec.max_references == 0:
            rule = "accepts no reference images"
        elif spec.min_references == spec.max_references:
            rule = f"requires exactly {spec.min_references} reference image"
        else:
            rule = (
                f"requires between {spec.min_references} and {spec.max_references} reference images"
            )
        reason = f"{spec.slug} ({spec.display_name}) {rule}; got {reference_count}"

        required_model = _recommended_model(
            reference_count, spec=spec, editing_capable=editing_capable
        )
        if required_model is None and reference_count > _MAX_SUPPORTED:
            # No supported model accepts this many references; the rule
            # text alone does not communicate that, so the reason tail
            # makes it explicit. Bound is read from the registry rather
            # than a literal here (see `_MAX_SUPPORTED`).
            reason += f"; no supported model accepts more than {_MAX_SUPPORTED}"

        return ValidationVerdict(False, reason, required_model)

    # Preset direction 1: editing preset on a text-only model. Checked
    # before direction 2 so a known preset on a text model surfaces
    # the more specific "requires an editing-capable model" message.
    if preset is not None and preset in EDITING_PRESETS and not editing_capable:
        return ValidationVerdict(
            False,
            f"editing preset {preset} requires an editing-capable model",
        )

    # Preset direction 2: preset identifier not in EDITING_PRESETS.
    if preset is not None and preset not in EDITING_PRESETS:
        return ValidationVerdict(False, f"unknown editing preset: {preset}")

    # Aspect ratio: no per-mode rule. Every registered model accepts every
    # ratio in TEXT_ASPECT_RATIOS as well as the literal "custom", because
    # the callers that pass a ratio for an editing-capable model also pass
    # the explicit pixel dimensions that size its canvas. `aspect_ratio` is
    # kept in the signature: it is part of the documented selection tuple
    # and a future model with a genuine ratio restriction would be
    # rejected here rather than in each composition root.
    return ValidationVerdict(True)


def _recommended_model(reference_count: int, *, spec: object, editing_capable: bool) -> str | None:
    """Pick the model to recommend when cardinality fails.

    The table mirrors `validate_selection`'s step-2 rule; extracted so
    the cardinality branch reads as a linear rule sequence rather than
    a nested `if/elif` tree. The literal-1 / literal-0 / literal-2
    comparison values are spelled out exactly as the spec dictates --
    they are not arbitrary bounds but per-rule recommendation cutoffs
    (1 reference -> FLUX.2 preferred per spec §5.1; 0 references ->
    schnell for any editing model), and the structural test in
    `TestNoCardinalityLiteralFour` guards only the upper bound (4)
    which the spec names as `_MAX_SUPPORTED` rather than a literal.
    """
    # Above all registered models' capacity: no recommendation possible.
    if reference_count > _MAX_SUPPORTED:
        return None
    # 2.._MAX_SUPPORTED references: FLUX.2 is the only registered model
    # that accepts this band.
    if 2 <= reference_count <= _MAX_SUPPORTED:
        return FLUX2_KLEIN_4B
    # 1 reference but the selected model is schnell: spec §5.1 prefers
    # FLUX.2 over Kontext for the single-reference case.
    if reference_count == 1 and spec is get_model_spec(FLUX1_SCHNELL):
        return FLUX2_KLEIN_4B
    # 0 references but the selected model is editing-capable: schnell
    # accepts 0 references and reproduces pre-epic text behavior.
    if reference_count == 0 and editing_capable:
        return FLUX1_SCHNELL
    return None

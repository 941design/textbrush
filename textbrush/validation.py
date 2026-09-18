"""Shared, side-effect-free model, reference, and preset validation."""

from __future__ import annotations

from dataclasses import dataclass

from textbrush.model.registry import FLUX1_SCHNELL, FLUX2_KLEIN_4B, get_model_spec

EDITING_PRESETS: dict[str, tuple[int, int]] = {
    "landscape-small": (512, 384), "landscape-medium": (768, 576),
    "landscape-large": (1024, 768), "portrait-small": (384, 512),
    "portrait-medium": (576, 768), "portrait-large": (768, 1024),
}
DEFAULT_EDITING_PRESET = "landscape-medium"

@dataclass(frozen=True)
class ValidationVerdict:
    valid: bool
    reason: str | None = None
    required_model: str | None = None

def validate_selection(model_id: str, reference_count: int, preset: str | None = None) -> ValidationVerdict:
    """Validate without changing the user's selected model, files, or preset."""
    try:
        spec = get_model_spec(model_id)
    except ValueError:
        return ValidationVerdict(False, f"unknown model: {model_id}")
    if reference_count < spec.min_references or reference_count > spec.max_references:
        required = FLUX2_KLEIN_4B if reference_count > 1 else None
        return ValidationVerdict(False, f"{spec.display_name} accepts {spec.min_references}–{spec.max_references} reference images; got {reference_count}", required)
    if preset is not None:
        editing = preset in EDITING_PRESETS
        if model_id == FLUX1_SCHNELL and editing:
            return ValidationVerdict(False, "editing presets require an editing-capable model")
        if model_id != FLUX1_SCHNELL and not editing:
            return ValidationVerdict(False, "text-only aspect ratios are not valid for an editing model")
    return ValidationVerdict(True)

def editing_preset_dimensions(preset: str) -> tuple[int, int]:
    try:
        return EDITING_PRESETS[preset]
    except KeyError as exc:
        raise ValueError(f"unknown editing preset: {preset}") from exc

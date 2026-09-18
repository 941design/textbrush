"""Shared filesystem fixtures for exercising the per-model registry's
discovery completeness check (AC-DISCOVERY-1) without downloading real
weights.

Not a test module itself (no `test_` prefix) -- imported by
`tests/test_weights.py` and `tests/test_model_weights.py`.
"""

from __future__ import annotations

import json
from pathlib import Path

from textbrush.model.registry import ModelSpec, get_model_spec


def _index_content(spec: ModelSpec) -> dict:
    """Build a model_index.json payload declaring every one of `spec`'s
    components as a diffusers-style `[library_name, class_name]` entry, plus
    the non-component `_class_name` key real checkpoints also carry.

    Discovery (`textbrush.model.weights._declared_components`) reads the
    checkpoint's *own* index to decide which components exist -- it does not
    trust `spec.components` directly -- so a fixture must declare the same
    names in the index it writes, exactly as a real checkpoint would.

    `_class_name` is sourced from `spec.expected_class_name` when the
    registry pins one (gate-remediation round 5, finding 4 added identity
    checking against this key). Previously this was hardcoded to
    "FluxPipeline" regardless of which model was being written, which broke
    silently the moment `_directory_identity_matches` started reading
    `_class_name`: `write_complete_snapshot(dir, FLUX2_KLEIN_4B)` would
    declare schnell's class name while being checked against klein's pinned
    "Flux2KleinPipeline", a confirmed-foreign-identity mismatch that made
    every generic fixture usage for a non-schnell model rejected outright.
    Falls back to a neutral, unrecognised placeholder for a model with no
    pinned `expected_class_name` (e.g. FLUX1_KONTEXT_DEV) -- unrecognised is
    always treated as ambiguous, never a mismatch, so this stays safe.
    """
    index: dict = {"_class_name": spec.expected_class_name or "Placeholder"}
    for component in spec.components:
        index[component.name] = ["diffusers", "Placeholder"]
    return index


def write_complete_snapshot(root: Path, model_id: str = "flux1-schnell") -> ModelSpec:
    """Populate `root` with a minimal-but-complete snapshot for `model_id`:
    the top-level index file (declaring every component by name) plus every
    declared component's configuration file and, where the component
    declares one, a file matching its weight glob. Returns the ModelSpec used.

    Gate-remediation round 6, finding 3: a tokenizer component (name prefix
    "tokenizer") additionally needs at least one real vocabulary asset --
    `check_model_availability` now requires this (see
    `textbrush.model.weights._tokenizer_has_vocab_assets`), because a
    tokenizer cannot actually be loaded from its config file alone. This
    fixture writes `tokenizer.json`, the one asset format every registered
    tokenizer type (CLIP's BPE, T5's SentencePiece) can load from -- so
    "complete" here stays complete under the strengthened check without this
    generic fixture needing to know which specific tokenizer class each
    named component is.
    """
    spec = get_model_spec(model_id)
    root.mkdir(parents=True, exist_ok=True)
    (root / spec.index_filename).write_text(json.dumps(_index_content(spec)))
    for component in spec.components:
        comp_dir = root / component.name
        comp_dir.mkdir(parents=True, exist_ok=True)
        (comp_dir / component.config_filename).write_text("{}")
        if component.name.startswith("tokenizer"):
            (comp_dir / "tokenizer.json").write_text("{}")
        if component.weight_glob is not None:
            weight_name = component.weight_glob.replace("*", "weights")
            (comp_dir / weight_name).write_bytes(b"\x00")
    return spec


def write_index_only(root: Path, model_id: str = "flux1-schnell") -> ModelSpec:
    """Populate `root` with only the top-level index file (still declaring
    every component by name, as a real checkpoint's index would): the exact
    'incomplete' shape AC-DISCOVERY-1 calls out -- a marker present, but none
    of the declared component files.
    """
    spec = get_model_spec(model_id)
    root.mkdir(parents=True, exist_ok=True)
    (root / spec.index_filename).write_text(json.dumps(_index_content(spec)))
    return spec


def remove_component_weights(root: Path, model_id: str, component_name: str) -> None:
    """Delete one component's weight file(s) under an otherwise-complete
    snapshot, leaving its config file in place. Constructs a targeted
    'incomplete' case: index present, one component's weights missing.
    """
    spec = get_model_spec(model_id)
    component = next(c for c in spec.components if c.name == component_name)
    comp_dir = root / component.name
    if component.weight_glob is not None:
        for f in comp_dir.glob(component.weight_glob):
            f.unlink()

"""Utilities for managing model weights in HuggingFace cache.

Models are stored in HuggingFace's global cache (~/.cache/huggingface/hub by default).
The cache location can be customized via HF_HOME or HF_HUB_CACHE environment variables.

Per-model identity (short slug <-> HuggingFace repo id) and cardinality metadata
live in `textbrush.model.registry` -- this module owns discovery (local-only,
cause-classified per spec.md sec 8 / AC-DISCOVERY-1), download, and local-only
loading, all keyed by the slugs that module defines.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from huggingface_hub import snapshot_download, try_to_load_from_cache
from huggingface_hub.utils import GatedRepoError, HfHubHTTPError, RepositoryNotFoundError

from textbrush.model.registry import (
    FLUX1_SCHNELL,
    MODEL_REGISTRY,
    AvailabilityReport,
    DiscoveryCause,
    ModelComponent,
    ModelSpec,
    get_model_spec,
)


class TokenRequiredError(Exception):
    """Raised when a HuggingFace token is required but not available or invalid.

    Triggered when:
    - No HF_TOKEN environment variable is set before attempting a download
      (cause: DiscoveryCause.CREDENTIALS_MISSING).
    - The download attempt returns a 401 (Unauthorized) or 403 (Forbidden)
      response, or the Hub reports a GatedRepoError, indicating the token is
      missing, invalid, or the user has not accepted the model license
      (cause: DiscoveryCause.LICENSE_ACCESS_MISSING).

    `cause` carries the DiscoveryCause this failure corresponds to (spec.md
    sec 8). This is the ONLY place DiscoveryCause.LICENSE_ACCESS_MISSING is
    ever produced: it is only observable by attempting a download and having
    the Hub refuse it as unauthorized/forbidden -- `check_model_availability`
    is local-only and cannot distinguish "not yet downloaded" from "access
    refused" without making that network request itself.
    """

    def __init__(self, message: str, *, cause: DiscoveryCause = DiscoveryCause.CREDENTIALS_MISSING):
        super().__init__(message)
        self.cause = cause


def _mask_token(token: str | None) -> str:
    """Mask HuggingFace token for safe display in error messages.

    Args:
        token: Token string to mask, or None.

    Returns:
        Masked token string showing first 4 and last 4 characters, or "None".
    """
    if token is None:
        return "None"
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-4:]}"


# Filter patterns: download only safetensors + config files. Shared across
# every registered model -- these describe file *types* to keep/skip, not
# per-model identity, so they are not part of ModelSpec.
ALLOW_PATTERNS: list[str] = [
    "*.json",  # Root-level config (model_index.json)
    "**/*.safetensors",
    "**/*.json",
    "**/tokenizer*",
    "**/*.txt",
    "**/*.md",
    "**/*.model",  # For T5 tokenizer
]

IGNORE_PATTERNS: list[str] = [
    "*.bin",
    "*.onnx",
    "*.onnx_data",
    "*.msgpack",
    "openvino*",
    "*.pb",
    "flax*",
]


class CacheInfo(TypedDict):
    """Information about the HuggingFace cache location."""

    cache_dir: Path
    custom_location: bool
    env_var: str | None


def get_cache_info() -> CacheInfo:
    """Get information about the HuggingFace cache location.

    Returns:
        CacheInfo with cache directory path and whether it's customized.
    """
    # Check for custom cache location
    hf_home = os.environ.get("HF_HOME")
    hf_hub_cache = os.environ.get("HF_HUB_CACHE")

    if hf_hub_cache:
        return CacheInfo(
            cache_dir=Path(hf_hub_cache),
            custom_location=True,
            env_var="HF_HUB_CACHE",
        )
    elif hf_home:
        return CacheInfo(
            cache_dir=Path(hf_home) / "hub",
            custom_location=True,
            env_var="HF_HOME",
        )
    else:
        # Default location
        return CacheInfo(
            cache_dir=Path.home() / ".cache" / "huggingface" / "hub",
            custom_location=False,
            env_var=None,
        )


def _declared_class_name(spec: ModelSpec, root: Path) -> str | None:
    """Return the checkpoint's own declared `_class_name` (the diffusers
    pipeline class, e.g. "FluxPipeline"), or None if the index is missing,
    unparseable, or does not carry a string `_class_name` key.

    Read independently from `_declared_components` (a scalar key, not a
    component) purely to feed the identity check in
    `_directory_identity_matches` -- gate-remediation round 5, finding 4.
    """
    try:
        data = json.loads((root / spec.index_filename).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    class_name = data.get("_class_name")
    return class_name if isinstance(class_name, str) else None


def _known_identity_class_names() -> dict[str, str]:
    """Reverse map of every registered model's confidently-pinned diffusers
    pipeline class name (`ModelSpec.expected_class_name`) to its slug.

    Gate-remediation round 5, finding 4: used to reject a directory whose
    declared `_class_name` is positively known to be a DIFFERENT model's
    identity, without needing the requested model's own class name to be
    pinned. Built from confirmed values only -- a model with
    `expected_class_name=None` (not independently verified, e.g. a gated
    repo this environment cannot fetch without a token -- see
    FLUX1_KONTEXT_DEV in registry.py) never appears here, so it can neither
    be used to reject a foreign directory nor be mistaken as a match.
    """
    return {
        spec.expected_class_name: spec.slug
        for spec in MODEL_REGISTRY.values()
        if spec.expected_class_name is not None
    }


def _directory_identity_matches(spec: ModelSpec, directory: Path) -> bool:
    """Return whether a candidate directory's own model_index.json is
    plausibly a checkpoint for `spec`, rather than a complete-but-wrong
    installation of a *different* registered model handed to us via
    `config.model.directories` (gate-remediation C1).

    Judgment call, recorded here because it is not obvious: every registered
    model shares the same top-level marker filename (`model_index.json`), so
    the marker's mere presence is not identity evidence -- a directory
    is user-supplied and may point at any checkpoint at all. Verified
    concretely: a complete 7-component FLUX.1 schnell directory handed to a
    `flux2-klein-4b` request reported `available=True` before this fix.

    Two independent, positive-evidence-only signals are used, in order:

    1. Declared `_class_name` (gate-remediation round 5, finding 4). FLUX.1
       schnell and FLUX.1 Kontext-dev share the exact same
       `identity_components` name set (signal 2 below cannot tell them
       apart in either direction), so a second signal is required. A
       directory is rejected here if EITHER:
         (a) `spec.expected_class_name` is pinned and the directory's
             declared class name differs from it -- i.e. we know for a
             fact what this model's real class name is, and the directory
             doesn't have it; or
         (b) the directory's declared class name is pinned as some OTHER
             model's identity in `_known_identity_class_names()` -- i.e. we
             don't need to know `spec`'s own class name to recognize that
             this directory is confirmed to be a *different*, specific
             model.
       Together, (a) and (b) resolve the schnell/Kontext ambiguity in BOTH
       directions using only schnell's and klein's independently-pinned
       values (see registry.py) -- neither direction requires
       FLUX1_KONTEXT_DEV's own `expected_class_name`, which is deliberately
       left unpinned (this environment could not fetch that gated repo's
       model_index.json without a token). An unrecognised class name (not
       equal to `spec`'s own pinned value when pinned, and not equal to any
       OTHER model's pinned value either) is treated as AMBIGUOUS, not a
       mismatch -- it never rejects a directory by itself; it only falls
       through to signal 2.

    2. The *set of component names the index positively declares* (via
       `_declared_components`, which already filters diffusers' `[None,
       None]` "unpopulated slot" convention -- see that function's
       docstring). If that set contains any name absent from
       `spec.identity_components` (the per-model identity name set,
       declared independently in registry.py -- e.g. `text_encoder_2`/
       `tokenizer_2`, present only in the FLUX.1 family's 7-component
       layout, never in FLUX.2's 5-component one), the directory declares a
       component the requested model does not have at all. That is strong,
       positive evidence it is a *different* model's checkpoint, not an
       incomplete installation of this one -- so it is rejected as a
       candidate for `spec` here (the search continues to the next
       candidate; see `_find_available_root`) rather than surfaced as
       INCOMPLETE.

    Deliberately tolerant of ambiguity: an EMPTY declared component set
    (e.g. a bare `{"_class_name": "..."}` marker from an interrupted
    download), or a declared set that is a *subset* of
    `spec.identity_components` (e.g. a genuinely-incomplete checkpoint of
    the right model, or -- the narrower, known-and-accepted gap signal 2
    alone cannot close -- a complete FLUX.2 5-component directory checked
    against a FLUX.1 request, whose 5 names are all also names FLUX.1 has),
    is not rejected by signal 2: it is not positive evidence of a different
    model, and must still surface as INCOMPLETE via the existing
    completeness check rather than being silently skipped.

    Invariant this function upholds: never a false `available=True` for a
    directory that is a *different, identifiable* model -- "identifiable"
    meaning either its component-name set is a strict superset of `spec`'s
    (signal 2), or its declared class name is confirmed (signal 1) to
    belong to `spec` or to some other pinned model. A directory that is
    ambiguous under BOTH signals (e.g. an unpinned-class-name model whose
    component names happen to be an exact or subset match, such as the
    Kontext-vs-schnell case when checked in the direction that only has
    schnell's or klein's pinned values available) can still, in principle,
    produce a false match -- gate-remediation round 5 closes the two
    concretely reported directions of that gap, not every conceivable one.
    """
    declared_class_name = _declared_class_name(spec, directory)
    if declared_class_name is not None:
        if spec.expected_class_name is not None and declared_class_name != spec.expected_class_name:
            return False
        owner = _known_identity_class_names().get(declared_class_name)
        if owner is not None and owner != spec.slug:
            return False

    declared = _declared_components(spec, directory)
    if not declared:
        return True
    expected_names = spec.identity_components
    if not expected_names:
        # Unreachable in practice: ModelSpec.__post_init__ refuses to
        # construct a spec with an empty identity_components set
        # (gate-remediation round 5, finding 1). Kept as a loud failure
        # rather than a permissive fallback in case that invariant is ever
        # bypassed (e.g. a future dataclasses.replace() call) -- an empty
        # identity set must never silently make every directory match.
        raise AssertionError(
            f"{spec.slug!r}: identity_components is empty at check time; "
            "ModelSpec.__post_init__ should have made this impossible to "
            "construct. Refusing to treat this as 'every directory matches'."
        )
    declared_names = {component.name for component in declared}
    return declared_names <= expected_names


@dataclass(frozen=True)
class _RootSearchResult:
    """Outcome of `_find_available_root`.

    Attributes:
      root: the resolved candidate directory -- a complete root if one was
        found; otherwise the most informative incomplete root (fewest
        missing components, tie-broken by priority order -- gate-
        remediation round 5, finding 6); or None if nothing at all was
        found (no directory carrying the marker file, identity-matched, or
        cached).
      missing: `_missing_components(spec, root)`, precomputed here so the
        caller does not recompute it on the winning candidate (gate-
        remediation round 5, finding 6's optional efficiency note --
        previously computed up to N+1 times: once per candidate here, once
        more by the caller). None when `root` is None, or when `root`'s own
        inspection failed (same meaning `_missing_components` itself uses,
        surfaces as DiscoveryCause.UNKNOWN).
      rejected_identity_path: the first custom directory that carried the
        top-level marker but was rejected by `_directory_identity_matches`
        (gate-remediation round 5, finding 5), or None if no such rejection
        occurred. Lets a caller reporting ABSENT distinguish "nothing was
        found at all" from "something was found but it declared a
        different model's identity", instead of collapsing both into the
        same misleading "no local marker found" detail message.
    """

    root: Path | None
    missing: list[str] | None
    rejected_identity_path: Path | None


def _find_available_root(spec: ModelSpec, custom_dirs: list[Path] | None) -> _RootSearchResult:
    """Locate the best candidate directory holding a model's top-level index
    file and declared component files.

    Checks every `custom_dirs` entry, in order, then the HuggingFace cache
    via `try_to_load_from_cache` -- a lookup against the cache's local
    reference database that involves no network access. try_to_load_from_
    cache is itself keyed by `spec.repo_id`, so the HF-cache candidate's
    identity is unambiguous by construction (the Hub's own cache path shape,
    `models--<org>--<repo>/snapshots/...`, already disambiguates it) --
    unlike a `custom_dirs` entry, which is user-supplied and may point at
    any checkpoint at all, the cache candidate is never run through
    `_directory_identity_matches` (gate-remediation round 5, finding 4).
    A `custom_dirs` candidate must pass `_directory_identity_matches`
    (gate-remediation C1): a directory that positively declares identity
    evidence for a different registered model is skipped, not accepted as
    a broken install of this one.

    Gate-remediation C2: a directory is no longer accepted merely for being
    first in priority order -- completeness is checked. As soon as a
    *complete* candidate is found (all of the checkpoint's own declared
    components present), it is returned immediately, and no lower-priority
    candidate (including the HF cache) is even consulted -- this preserves
    the existing precedence that a complete custom directory wins over the
    cache. If no candidate found so far is complete, the search keeps going
    rather than stopping at the first non-empty match, so an incomplete
    custom directory can no longer shadow a complete HF cache install (or
    vice versa).

    Gate-remediation round 5, finding 6: if nothing found anywhere is
    complete, the candidate reported is the one missing the FEWEST
    components (a candidate whose own inspection failed, i.e. `missing is
    None`, always sorts last -- an unreadable candidate is never more
    informative than one that could actually be inspected), tie-broken by
    priority order. This makes the eventual failure genuinely the most
    actionable one, rather than merely the first one encountered.

    Gate-remediation round 6, finding 1 (P2 crash): `try_to_load_from_cache`
    has THREE possible outcomes, not two -- verified against the installed
    huggingface_hub 0.36.0's own docstring and source
    (`huggingface_hub/file_download.py`): the exact path (`str`) if cached,
    `None` if never cached, or the sentinel `_CACHED_NO_EXIST` if the file's
    *absence* was itself cached (an ordinary state: a prior lookup for this
    exact repo/revision/filename found nothing and the Hub client recorded
    that fact to avoid re-checking). The prior `if cached is not None:`
    treated the sentinel as a path and crashed inside `Path(cached)` with a
    `TypeError` the moment a cache recorded a prior miss -- reachable in any
    ordinary cache, not a contrived state.

    Fixed with `isinstance(cached, str)` rather than importing
    `_CACHED_NO_EXIST` (from `huggingface_hub.file_download`, not
    `huggingface_hub.constants` -- checked) and comparing identity against
    it. Both are correct today, but the type check is strictly more robust:
    the function's own return-type contract guarantees the only "found"
    outcome is a `str` (confirmed by reading `try_to_load_from_cache`'s
    source: the success path always returns `os.path.join(...)`, which is a
    `str`), and this is the exact pattern the library's own docstring
    recommends (`if isinstance(filepath, str): # file exists and is
    cached`). It also requires no import of a private symbol at all --
    immune to that symbol being renamed or moved in a future release, with
    no fallback branch needed to degrade gracefully.
    """
    candidates: list[tuple[Path, list[str] | None]] = []
    rejected_identity_path: Path | None = None

    if custom_dirs:
        for directory in custom_dirs:
            directory = Path(directory)
            if not directory.is_dir():
                continue
            if not (directory / spec.index_filename).exists():
                continue
            if not _directory_identity_matches(spec, directory):
                if rejected_identity_path is None:
                    rejected_identity_path = directory
                continue
            missing = _missing_components(spec, directory)
            if missing == []:
                return _RootSearchResult(directory, missing, rejected_identity_path)
            candidates.append((directory, missing))

    cached = try_to_load_from_cache(spec.repo_id, filename=spec.index_filename)
    if isinstance(cached, str):
        cache_root = Path(cached).parent
        missing = _missing_components(spec, cache_root)
        if missing == []:
            return _RootSearchResult(cache_root, missing, rejected_identity_path)
        candidates.append((cache_root, missing))

    if not candidates:
        return _RootSearchResult(None, None, rejected_identity_path)

    def _sort_key(item: tuple[Path, list[str] | None]) -> tuple[bool, int]:
        _, item_missing = item
        return (item_missing is None, len(item_missing) if item_missing is not None else 0)

    best_root, best_missing = min(candidates, key=_sort_key)
    return _RootSearchResult(best_root, best_missing, rejected_identity_path)


def _infer_component_metadata(name: str) -> ModelComponent:
    """Infer a declared component's config filename / weight glob from its
    name, for a component the index declares that has no entry in
    `spec.components` (the override table). Mirrors the naming convention
    every diffusers FluxPipeline component already follows: schedulers and
    tokenizers carry no weight files of their own.
    """
    if name == "scheduler":
        return ModelComponent(name=name, config_filename="scheduler_config.json", weight_glob=None)
    if name.startswith("tokenizer"):
        return ModelComponent(name=name, config_filename="tokenizer_config.json", weight_glob=None)
    return ModelComponent(name=name)


def _declared_components(spec: ModelSpec, root: Path) -> list[ModelComponent] | None:
    """Return the components the checkpoint's own top-level index declares
    (spec.md sec 8: "for each component the index declares"), not a static
    per-model list. The index is parsed for its own component set; `Model
    Spec.components` is consulted only as an optional per-name override
    supplying a non-default config filename / weight glob, never as the
    source of which components exist.

    Diffusers' model_index.json format: every key that does not start with
    "_" and whose value is a list (`[library_name, class_name]`) names one
    loaded pipeline sub-component; scalar keys (`_class_name`,
    `_diffusers_version`, feature flags such as `is_distilled`) are not
    components. A list value of `[None, None]` (diffusers' convention for a
    pipeline slot that exists in the class signature but is deliberately
    unpopulated, e.g. an omitted `safety_checker`) is a list too, but it does
    not name a real component -- skip any entry whose list has no non-None
    member, or a genuinely-optional, absent slot would be reported as a
    missing required component (gate-remediation finding 2).

    Returns None if the index is missing or cannot be parsed as a JSON
    object (surfaces as DiscoveryCause.UNKNOWN, alongside the other
    filesystem-inspection failures below).
    """
    try:
        data = json.loads((root / spec.index_filename).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    overrides = {component.name: component for component in spec.components}
    declared: list[ModelComponent] = []
    for key, value in data.items():
        if key.startswith("_") or not isinstance(value, list):
            continue
        # Diffusers declares a component as [library_name, class_name]; both are
        # strings (or None for an unpopulated slot). A list of anything else is a
        # flag, not a component, and must not become a phantom required file.
        if not all(v is None or isinstance(v, str) for v in value):
            continue
        if not any(item is not None for item in value):
            continue
        declared.append(overrides.get(key) or _infer_component_metadata(key))
    return declared


# Sentinel returned by `_missing_components` when the index parses cleanly
# but declares zero components. Gate-remediation finding 1: an empty
# declared set previously made `if missing:` falsy, so a bare
# `{"_class_name": "FluxPipeline"}` marker -- exactly the "top-level marker
# alone" state AC-DISCOVERY-1 forbids -- fell through to `available=True`.
# Reachable in practice from an interrupted download of model_index.json, a
# hand-assembled `config.model.directories` entry, or any index whose
# component values are not JSON lists.
_NO_COMPONENTS_DECLARED = "(index declares zero components)"


# Matches diffusers' sharded-weight filename convention, e.g.
# "diffusion_pytorch_model-00001-of-00003.safetensors". Used by
# `_missing_shards`'s no-index fallback (gate-remediation round 5, finding
# 2) to recognize a sharded component even before its weight-index file has
# been written.
_SHARD_SUFFIX_RE = re.compile(r"-(\d+)-of-(\d+)\.safetensors$")

# Sentinel prefix `_missing_shards` returns (as the sole element of its
# result list) when a `*.safetensors.index.json` file exists but cannot be
# trusted -- unparseable JSON, not an object, or no usable `weight_map`.
# Gate-remediation round 5, finding 2: a malformed index must be treated as
# INCOMPLETE, not silently downgraded to the weaker no-index fallback check
# (a broken index is itself evidence of an interrupted or corrupted
# download, not evidence that this component isn't sharded at all).
_MALFORMED_INDEX_PREFIX = "(malformed weight index: "

# Sentinel prefix `_missing_shards` appends (to the no-index fallback
# branch's return list) for the weight-index file itself, when shard-suffixed
# filenames are found but no `*.safetensors.index.json` accompanies them.
# Gate-remediation round 6, finding 2 (P2): every shard named by a sharded
# component being physically present is NOT sufficient for that component to
# be loadable. Verified against the installed diffusers 0.36.0
# (`diffusers/models/modeling_utils.py::from_pretrained`, via
# `model_loading_utils._fetch_index_file`): for a local path, `is_sharded`
# is set True only when the *actual* `<prefix>.safetensors.index.json` file
# `.is_file()` -- diffusers does not reconstruct the shard-to-parameter
# mapping from shard filenames. When that index file is absent, `is_sharded`
# stays False and the loader instead looks for a single plain
# `diffusion_pytorch_model.safetensors` file, which does not exist for a
# sharded checkpoint -- the load fails outright, regardless of how many
# correctly-named shard files sit on disk. The round-5 fallback signal (shard-
# suffixed filenames, used when the index hasn't been written yet) correctly
# detects an INTERRUPTED download when shards are missing, but incorrectly
# reported COMPLETE once every named shard was present, because it never
# required the index file's own existence -- exactly the fixture this
# constant makes fail first (see
# TestShardedWeightCompletenessWithoutIndexFile
# .test_all_shards_present_with_no_index_file_reports_incomplete).
_MISSING_SHARD_INDEX_PREFIX = "(missing weight index file: "


def _missing_shards(component_dir: Path, weight_glob: str) -> list[str] | None:
    """Return the shard filenames a sharded component requires that are not
    present (as a resolvable file) under `component_dir`, or None if this
    component shows NEITHER of the two independent signals of being sharded
    at all -- in which case the caller falls back to its pre-existing "at
    least one glob match" check for a genuinely single-file component.

    Gate-remediation C3 (round 1): `*.safetensors` matches ANY single
    matching file, so an interrupted sharded download leaving only
    `diffusion_pytorch_model-00001-of-00003.safetensors` on disk reported
    available. Diffusers writes an index file alongside a sharded
    component -- `diffusion_pytorch_model.safetensors.index.json` for
    diffusers-format components (transformer, vae) or
    `model.safetensors.index.json` for transformers-format components
    (text_encoder) -- whose `weight_map` maps every parameter name to the
    shard file that holds it; the set of unique values is exactly the set of
    shard files that must exist.

    Gate-remediation round 5, finding 2: `snapshot_download` fetches shard
    files and the index file concurrently with no ordering guarantee, so
    "one shard written, index.json not yet written" is an ordinary
    interruption state, not a hypothetical -- and the round-1 fix above only
    engages once an index file exists, so this exact state fell through to
    the weak single-glob-match check and reported available. This function
    now recognizes a second, independent signal when no index file is
    present: any file matching `weight_glob` whose name carries the
    `-NNNNN-of-NNNNN` shard suffix. When found, the largest total shard
    count named by any matching file (grouped by filename prefix, in case
    more than one sharded prefix is present under one component -- not
    expected in practice, but not assumed away either) is taken as
    authoritative, and every shard index 1..total is required to resolve to
    a real file -- not merely to have matched the glob, so a broken
    HF-cache symlink (see below) is still correctly caught even though its
    name matches.

    A component directory carrying more than one `*.safetensors.index.json`
    is not arbitrarily reduced to "the first one glob() happens to return"
    (a prior version of this function read `index_files[0]`): every index
    file's `weight_map` is parsed and their required-shard sets are unioned,
    so a shard only a second index file names cannot go undetected. Any
    index file that is unparseable, not a JSON object, or has no usable
    `weight_map` makes the whole component INCOMPLETE (a non-empty sentinel
    list is returned) rather than silently falling back to the weaker
    no-index check -- a broken index is evidence of a corrupted or
    interrupted download, not evidence "not sharded".

    Existence is checked with `Path.exists()`, which follows symlinks: in an
    HF cache layout, files inside a snapshot directory are symlinks into a
    shared `blobs/` store, and a blob that was never fully downloaded leaves
    a symlink whose target does not exist. `exists()` correctly reports
    False for that broken-symlink case (it does not merely check that a
    directory entry with that name exists), so an interrupted cache download
    is not mistaken for a present shard.

    Gate-remediation round 6, finding 2 (P2): the no-index fallback branch
    below previously returned an empty list (falsy -> "component complete")
    once every shard it could name from filenames alone was present on disk.
    That is necessary but not sufficient: diffusers loads a sharded
    checkpoint by reading the actual `*.safetensors.index.json` file, never
    by reconstructing the shard map from filenames (verified against
    installed diffusers 0.36.0 -- see `_MISSING_SHARD_INDEX_PREFIX`'s
    comment). So the fallback branch's return is now ALWAYS non-empty:
    it reports every missing shard it can detect from filenames, AND -- since
    by construction this branch never found an index file at all -- the
    index file's own absence, every time this branch runs at all. The
    happy-path "no signal of sharding whatsoever" case (`matches` empty)
    is unaffected and still returns None, deferring to the caller's
    single-file glob check.
    """
    index_files = sorted(component_dir.glob("*.safetensors.index.json"))
    if index_files:
        shard_names: set[str] = set()
        for index_file in index_files:
            try:
                data = json.loads(index_file.read_text())
            except (OSError, ValueError):
                return [f"{_MALFORMED_INDEX_PREFIX}{index_file.name})"]
            weight_map = data.get("weight_map") if isinstance(data, dict) else None
            if not isinstance(weight_map, dict):
                return [f"{_MALFORMED_INDEX_PREFIX}{index_file.name})"]
            names = {name for name in weight_map.values() if isinstance(name, str)}
            if not names:
                return [f"{_MALFORMED_INDEX_PREFIX}{index_file.name})"]
            shard_names |= names
        return sorted(name for name in shard_names if not (component_dir / name).exists())

    # No index file at all. Look for a shard-suffixed filename among the
    # ordinary weight_glob matches -- the state an interrupted download can
    # leave before the index file itself is written.
    matches = [p for p in component_dir.glob(weight_glob) if _SHARD_SUFFIX_RE.search(p.name)]
    if not matches:
        return None

    groups: dict[str, dict[str, object]] = {}
    for path in matches:
        match = _SHARD_SUFFIX_RE.search(path.name)
        assert match is not None  # guaranteed by the filter above
        prefix = path.name[: match.start()]
        index, total = int(match.group(1)), int(match.group(2))
        width = len(match.group(2))
        group = groups.setdefault(prefix, {"total": 0, "width": width, "seen": set()})
        group["total"] = max(int(group["total"]), total)  # type: ignore[arg-type]
        group["seen"].add(index)  # type: ignore[union-attr]

    missing: list[str] = []
    for prefix, group in groups.items():
        total = int(group["total"])  # type: ignore[arg-type]
        width = int(group["width"])  # type: ignore[arg-type]
        for shard_index in range(1, total + 1):
            name = f"{prefix}-{shard_index:0{width}d}-of-{total:0{width}d}.safetensors"
            if not (component_dir / name).exists():
                missing.append(name)
        # The shard files alone are never sufficient (gate-remediation round
        # 6, finding 2): diffusers requires the weight-index file itself to
        # map parameters to shards, and this branch runs only when no such
        # index file exists at all. Reported unconditionally, independent of
        # whether any individual shard is also missing, so this branch's
        # result is never mistaken for "component complete".
        missing.append(f"{_MISSING_SHARD_INDEX_PREFIX}{prefix}.safetensors.index.json)")
    return sorted(missing)


# The realistic set of vocabulary asset filenames a HuggingFace tokenizer
# component may carry. Gate-remediation round 6, finding 3 (P2): a tokenizer
# component declares `weight_glob=None` (it has no *weight* files), which
# previously meant NOTHING under its directory was ever checked beyond the
# config file -- a directory containing only `tokenizer_config.json` reported
# available, but transformers cannot actually build a usable tokenizer from
# that file alone. Verified against the installed transformers 4.57.3:
# - `transformers/models/clip/tokenization_clip.py::VOCAB_FILES_NAMES` pins
#   CLIP's (BPE) slow-tokenizer files to "vocab.json" + "merges.txt".
# - `transformers/models/t5/tokenization_t5.py::VOCAB_FILES_NAMES` pins T5's
#   (SentencePiece) slow-tokenizer file to "spiece.model".
# - `transformers/tokenization_utils_base.py` (`FULL_TOKENIZER_FILE =
#   "tokenizer.json"`, consulted alongside the slow-format vocab files in
#   `PreTrainedTokenizerBase.from_pretrained`) additionally accepts a single
#   fast-tokenizer `tokenizer.json` in place of either slow-format asset --
#   this is the unified format both CLIPTokenizerFast and T5TokenizerFast can
#   load from.
# schnell/Kontext-dev's `tokenizer` (CLIP) and `tokenizer_2` (T5) therefore
# need different slow-format filenames; rather than hardcode which named
# component is which tokenizer type (fragile, and not this module's
# business -- `model` stays a leaf, so no transformers import here either),
# accept the union of every realistic asset set. A component carrying ANY
# one of them is accepted; a bare `tokenizer_config.json` with none of them
# is not.
_TOKENIZER_SINGLE_FILE_VOCAB_ASSETS: tuple[str, ...] = ("tokenizer.json", "spiece.model")
_TOKENIZER_BPE_VOCAB_PAIR: tuple[str, str] = ("vocab.json", "merges.txt")


def _tokenizer_has_vocab_assets(component_dir: Path) -> bool:
    """Return whether `component_dir` carries at least one recognised
    tokenizer vocabulary asset (see `_TOKENIZER_SINGLE_FILE_VOCAB_ASSETS` /
    `_TOKENIZER_BPE_VOCAB_PAIR` above for the verified, real-world set and
    its grounding). `tokenizer_config.json` alone is deliberately not
    sufficient -- it carries the tokenizer's class and settings, never its
    vocabulary.
    """
    if any((component_dir / name).exists() for name in _TOKENIZER_SINGLE_FILE_VOCAB_ASSETS):
        return True
    vocab_file, merges_file = _TOKENIZER_BPE_VOCAB_PAIR
    return (component_dir / vocab_file).exists() and (component_dir / merges_file).exists()


def _missing_components(spec: ModelSpec, root: Path) -> list[str] | None:
    """Return declared components missing their config or weight files under
    `root`, or None if the index could not be parsed, or the filesystem
    inspection itself failed, in a way that doesn't map to a specific cause
    (surfaces as DiscoveryCause.UNKNOWN).

    A zero-length declared set is treated as INCOMPLETE, not vacuously
    available: an index that names no components is not evidence that every
    declared component's files are present, it is evidence that the index
    itself is not (yet, or ever) a valid diffusers checkpoint manifest.

    Gate-remediation round 6, finding 3: a component whose name identifies it
    as a tokenizer (checked the same way `_infer_component_metadata` already
    recognizes one -- by name prefix, since every registered tokenizer
    component declares `weight_glob=None`) additionally requires at least
    one real vocabulary asset (`_tokenizer_has_vocab_assets`); its config
    file alone is not a usable tokenizer.
    """
    declared = _declared_components(spec, root)
    if declared is None:
        return None
    if not declared:
        return [_NO_COMPONENTS_DECLARED]

    missing: list[str] = []
    try:
        for component in declared:
            component_dir = root / component.name
            if not (component_dir / component.config_filename).exists():
                missing.append(component.name)
                continue
            if component.name.startswith("tokenizer") and not _tokenizer_has_vocab_assets(
                component_dir
            ):
                missing.append(component.name)
                continue
            if component.weight_glob is None:
                continue
            shard_status = _missing_shards(component_dir, component.weight_glob)
            if shard_status is not None:
                # A weight index exists: this component is sharded, and
                # completeness means every shard it names is present -- not
                # merely that one matching file exists (gate-remediation C3).
                if shard_status:
                    missing.append(component.name)
                continue
            # No weight index -- not sharded (or not yet downloaded enough
            # to have one). Fall back to the pre-existing check, but require
            # the match to actually resolve (not a broken HF-cache symlink)
            # rather than merely matching a filename.
            if not any(p.exists() for p in component_dir.glob(component.weight_glob)):
                missing.append(component.name)
    except OSError:
        return None
    return missing


def _has_hf_token() -> bool:
    return bool(os.environ.get("HF_TOKEN"))


def check_model_availability(
    model_id: str, *, custom_dirs: list[Path] | None = None
) -> AvailabilityReport:
    """Discover whether a model is available for local, offline loading.

    CONTRACT:
      Inputs:
        model_id: a short slug from `textbrush.model.registry.MODEL_REGISTRY`.
        custom_dirs: optional directories to check before the HuggingFace
          cache (e.g. `config.model.directories`).
      Outputs:
        AvailabilityReport. available=True only once the top-level index AND
        every declared component's configuration and weight files are
        present (spec.md sec 8; AC-DISCOVERY-1) -- a top-level marker alone
        is not sufficient evidence of availability.
      Invariants:
        - Performs no network access. try_to_load_from_cache and every
          filesystem check here are local-only by construction; this is the
          local-only discovery half of AC-LOCAL-1 (the load half is
          `load_local_only` below).
        - Whenever available=False, cause is one of ABSENT,
          CREDENTIALS_MISSING, INCOMPLETE, or UNKNOWN from this function.
          LICENSE_ACCESS_MISSING and UNLOADABLE are never reported here --
          see below.
        - LICENSE_ACCESS_MISSING is reported only by the download path
          (`TokenRequiredError.cause`, raised from `download_model_weights`
          / `download_flux_weights` on a GatedRepoError or an HTTP 401/403).
          "Access refused as unauthorized or forbidden" (spec.md sec 8) is
          observable only by attempting a request; this function is local-
          only by contract and cannot distinguish "not yet downloaded" from
          "access refused" without making that request itself. A gated
          model with no local root and a token configured is therefore
          classified ABSENT here -- local facts alone cannot tell it apart
          from LICENSE_ACCESS_MISSING, and ABSENT is the classification that
          correctly routes it into the download flow (spec.md sec 8) rather
          than away from it.
        - UNLOADABLE is reported only by an actual load attempt (see
          `load_local_only`), never by this function.
        - UNKNOWN is reached only when the filesystem inspection itself
          fails in a way none of the other three causes describe -- never a
          default classification for an ordinary "not found" case.
      Algorithm:
        0. An index that parses as a JSON object but declares no components
           is INCOMPLETE -- not UNKNOWN and never available. spec.md sec 8
           warns against collapsing enumerated causes into "unknown", and
           the operational cause (a partial or interrupted index fetch) is
           resolved by completing the download, which is what incomplete
           routes the user to.
        1. Locate the best candidate snapshot root across custom_dirs, then
           the HF cache (`_find_available_root`): each custom directory must
           also identify as this model (`_directory_identity_matches`,
           gate-remediation C1) to be considered at all, and the search
           prefers the first *complete* candidate over merely the first
           candidate found, so an incomplete custom directory can no longer
           shadow a complete cache install or vice versa (gate-remediation
           C2) -- a complete custom directory still wins over the cache.
        2. If no root is found: gated and no HF token configured ->
           credentials_missing; otherwise (not gated, OR gated with a token
           configured -- local facts cannot further distinguish "not yet
           downloaded" from "access refused") -> absent. If a custom
           directory was found but rejected on identity grounds (gate-
           remediation round 5, finding 5), the absent detail names it
           rather than claiming no marker was found at all.
        3. If a root is found, check every component the checkpoint's own
           model_index.json declares. Any missing component file ->
           incomplete. All present -> available, and the resolved root is
           carried on `AvailabilityReport.root` (gate-remediation round 5,
           finding 3) so a caller can load from that exact directory rather
           than from a repo id that only resolves within the HF cache.
    """
    spec = get_model_spec(model_id)
    result = _find_available_root(spec, custom_dirs)

    if result.root is None:
        if spec.gated and not _has_hf_token():
            return AvailabilityReport(
                False,
                DiscoveryCause.CREDENTIALS_MISSING,
                "model is gated and no HF_TOKEN is configured",
            )
        if result.rejected_identity_path is not None:
            return AvailabilityReport(
                False,
                DiscoveryCause.ABSENT,
                f"a local checkpoint was found at {result.rejected_identity_path} but "
                "declares components this model does not have; it appears to be a "
                "different model",
            )
        return AvailabilityReport(False, DiscoveryCause.ABSENT, "no local marker found")

    missing = result.missing
    if missing is None:
        return AvailabilityReport(
            False, DiscoveryCause.UNKNOWN, "error while inspecting local snapshot"
        )
    if missing == [_NO_COMPONENTS_DECLARED]:
        return AvailabilityReport(
            False,
            DiscoveryCause.INCOMPLETE,
            "index declares no components; snapshot is not a usable checkpoint manifest",
        )
    if missing:
        return AvailabilityReport(
            False, DiscoveryCause.INCOMPLETE, f"missing component(s): {', '.join(missing)}"
        )
    return AvailabilityReport(True, None, "all declared files present", root=result.root)


def is_model_available(model_id: str, *, custom_dirs: list[Path] | None = None) -> bool:
    """Boolean convenience wrapper over `check_model_availability`."""
    return check_model_availability(model_id, custom_dirs=custom_dirs).available


def is_flux_available(custom_dirs: list[Path] | None = None) -> bool:
    """Check if FLUX.1 Schnell is available for local, offline loading.

    Preserved (name and signature) for existing callers
    (`textbrush/ipc/handler.py`, `textbrush/cli.py`). Delegates to
    `check_model_availability`, so this now applies the same strengthened
    completeness check as every other registered model: previously this only
    probed for a top-level `model_index.json` marker file. AC-DISCOVERY-1
    calls this out explicitly as a real strengthening, not a restatement.

    Args:
        custom_dirs: Optional list of directories to check before the HuggingFace
            cache. Each directory is checked for the model's declared files.

    Returns:
        True if the model appears to be available.
    """
    return is_model_available(FLUX1_SCHNELL, custom_dirs=custom_dirs)


def ensure_flux_available() -> None:
    """Ensure FLUX.1 Schnell is available, raising a helpful error if not.

    Preserved (name and signature) for existing callers. Delegates to
    `ensure_model_available`: the only externally-observed contract on this
    function's wording is that the raised message references
    "textbrush --download-model" (asserted by
    `tests/e2e/test_full_workflow.py`), which `ensure_model_available`'s
    message satisfies.

    Raises:
        RuntimeError: If the model is not cached, with instructions to download.
    """
    ensure_model_available(FLUX1_SCHNELL)


def ensure_model_available(model_id: str, *, custom_dirs: list[Path] | None = None) -> None:
    """Ensure a registered model is available, raising a cause-specific error if not.

    Generic implementation shared by every registered model, including
    `flux1-schnell` via `ensure_flux_available`.

    CONTRACT:
      Raises:
        RuntimeError: if the model is not available, naming the model and the
          discovery cause (AC-DISCOVERY-1) with a pointer to the download flow.
    """
    report = check_model_availability(model_id, custom_dirs=custom_dirs)
    if report.available:
        return
    spec = get_model_spec(model_id)
    cache_info = get_cache_info()
    cause = report.cause.value if report.cause else DiscoveryCause.UNKNOWN.value
    raise RuntimeError(
        f"{spec.display_name} model not found or not usable (cause: {cause}).\n"
        f"Cache location: {cache_info['cache_dir']}\n"
        f"\n"
        f"To download the model, run:\n"
        f"  textbrush --download-model\n"
    )


def download_flux_weights(*, force: bool = False) -> Path:
    """Download FLUX.1 Schnell weights to HuggingFace cache.

    Preserved (name and signature) for existing callers
    (`textbrush/cli.py`). Thin delegation to `download_model_weights`, the
    generic implementation every registered model (including schnell) uses.

    Args:
        force: If True, re-download even if already cached.

    Returns:
        Path to the HuggingFace snapshot directory for the downloaded model.

    Raises:
        TokenRequiredError: If HF_TOKEN is not set, or if the download returns
            a 401/403 auth error (token invalid or license not accepted).
        RuntimeError: If download fails for other reasons (network, disk space, etc.).
    """
    return download_model_weights(FLUX1_SCHNELL, force=force)


def download_model_weights(model_id: str, *, force: bool = False) -> Path:
    """Download a registered model's weights to the HuggingFace cache.

    Generic implementation shared by every registry entry, including
    `flux1-schnell` via `download_flux_weights`.

    CONTRACT:
        Inputs:
            model_id: a short slug from `textbrush.model.registry.MODEL_REGISTRY`.
            force: If True, re-download even if already cached.
        Outputs:
            Path: Absolute path to the HuggingFace snapshot directory.
        Invariants:
            - HF_TOKEN is only required when actually downloading (not for cached reads).
            - The pre-flight token guard (step 2) applies only when
              `spec.gated` is true (gate-remediation C4). schnell and
              Kontext-dev are both gated (`auto`) and still require a
              token pre-flight; klein-4B is verified ungated and must be
              downloadable anonymously -- requiring a token for every model
              regardless of `spec.gated` left the registry's `gated` field
              half-wired (round 2 wired it into discovery's
              CREDENTIALS_MISSING classification, but the downloader never
              read it). A 401/403 the Hub returns anyway on an ungated repo
              (e.g. `gated` drifting stale) is still mapped to
              TokenRequiredError(cause=LICENSE_ACCESS_MISSING) by the
              exception handling in steps 4 below, which is not conditioned
              on `spec.gated` -- only the pre-flight guard is.
        Algorithm:
            1. If already available (per check_model_availability) and not force:
               return the cached snapshot path (no token needed).
            2. Guard against a missing token, but only for a gated model
               (check `spec.gated` and the HF_TOKEN env var).
            3. Call snapshot_download(); return Path to snapshot directory.
            4. On auth/gated-repo errors, raise TokenRequiredError.
            5. On all other errors, raise RuntimeError with actionable message.

    Raises:
        TokenRequiredError: If HF_TOKEN is not set, or if the download returns
            a 401/403 auth error (token invalid or license not accepted).
        RuntimeError: If download fails for other reasons (network, disk space, etc.).
    """
    spec = get_model_spec(model_id)
    repo_id = spec.repo_id

    if not force and is_model_available(model_id):
        cache_info = get_cache_info()
        hub_cache = cache_info["cache_dir"]
        model_dir = hub_cache / f"models--{repo_id.replace('/', '--')}"
        snapshots_dir = model_dir / "snapshots"
        if snapshots_dir.is_dir():
            snapshots = sorted(snapshots_dir.iterdir())
            if snapshots:
                return snapshots[-1]
        return hub_cache

    if spec.gated and not os.environ.get("HF_TOKEN"):
        raise TokenRequiredError(
            "HF_TOKEN environment variable is not set. "
            "A valid HuggingFace token is required to download model weights.",
            cause=DiscoveryCause.CREDENTIALS_MISSING,
        )

    try:
        snapshot_path = snapshot_download(
            repo_id,
            allow_patterns=ALLOW_PATTERNS,
            ignore_patterns=IGNORE_PATTERNS,
            force_download=force,
        )
        return Path(snapshot_path)
    except (GatedRepoError, RepositoryNotFoundError) as e:
        raise TokenRequiredError(
            f"Access denied when downloading {repo_id}. "
            "Ensure your HF_TOKEN is valid and you have accepted the model license at "
            f"{spec.license_url}",
            cause=DiscoveryCause.LICENSE_ACCESS_MISSING,
        ) from e
    except HfHubHTTPError as e:
        if e.response is not None and e.response.status_code in (401, 403):
            raise TokenRequiredError(
                f"Authentication failed when downloading {repo_id} "
                f"(HTTP {e.response.status_code}). "
                "Ensure your HF_TOKEN is valid and you have accepted the model license at "
                f"{spec.license_url}",
                cause=DiscoveryCause.LICENSE_ACCESS_MISSING,
            ) from e
        cache_info = get_cache_info()
        raise RuntimeError(
            f"Failed to download {spec.display_name} model.\n"
            f"Error: {e}\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"Common issues:\n"
            f"  - Network timeout or connection error\n"
            f"  - Insufficient disk space\n"
        ) from e
    except Exception as e:
        error_msg = str(e)
        if "401" in error_msg or "403" in error_msg:
            raise TokenRequiredError(
                f"Authentication failed when downloading {repo_id}. "
                "Ensure your HF_TOKEN is valid and you have accepted "
                "the model license at "
                f"{spec.license_url}",
                cause=DiscoveryCause.LICENSE_ACCESS_MISSING,
            ) from e
        cache_info = get_cache_info()
        raise RuntimeError(
            f"Failed to download {spec.display_name} model.\n"
            f"Error: {e}\n"
            f"Cache location: {cache_info['cache_dir']}\n"
            f"\n"
            f"Common issues:\n"
            f"  - Network timeout or connection error\n"
            f"  - Insufficient disk space\n"
        ) from e


def load_local_only(
    pipeline_factory: Callable[..., object],
    model_id: str,
    *,
    root: Path | None = None,
    **kwargs: object,
) -> object:
    """Load a pipeline from local files only, never revalidating against a
    remote host (spec.md sec 8; AC-LOCAL-1).

    CONTRACT:
      Inputs:
        pipeline_factory: a callable such as `FluxPipeline.from_pretrained`,
          invoked as `pipeline_factory(target, local_files_only=True,
          **kwargs)`, where `target` is `root` (stringified) when given,
          else `spec.repo_id`.
        model_id: a short slug from `textbrush.model.registry.MODEL_REGISTRY`.
        root: optional resolved local snapshot directory, typically
          `AvailabilityReport.root` from a prior `check_model_availability`
          call (gate-remediation round 5, finding 3). When given,
          `pipeline_factory` is invoked with `str(root)` in place of
          `spec.repo_id` as its first positional argument. This closes a
          real gap: `pipeline_factory(spec.repo_id, local_files_only=True)`
          only ever consults the ordinary HuggingFace cache (that is what
          `local_files_only=True` means to `from_pretrained` when given a
          repo id) -- it never sees a `config.model.directories` custom
          directory discovery just validated. A model available only via a
          custom directory previously reported `available=True` and then
          failed to load at all, classified UNLOADABLE at the worst
          possible time (mid-launch), even though discovery had already
          done the work of finding and validating the right directory.
        kwargs: forwarded verbatim (e.g. torch_dtype).
      Outputs:
        Whatever `pipeline_factory` returns.
      Invariants:
        - Always passes local_files_only=True; a model that discovery reports
          as available is therefore loaded with no remote revalidation round
          trip, regardless of what pipeline_factory would otherwise default to.
        - This function performs no availability check of its own -- it does
          not know and does not assert whether discovery ever reported this
          model available. Callers that want that guarantee must call
          `check_model_availability` first; a model that is actually ABSENT
          (never downloaded) and is loaded through this function anyway will
          still be reported UNLOADABLE, not ABSENT, because that is the only
          fact this function is in a position to observe.
        - Omitting `root` reproduces the exact prior behavior (loads by repo
          id, HF cache only) -- every existing caller that does not pass
          `root` is unaffected.
      Raises:
        RuntimeError: pipeline_factory raised for any reason, classified
          DiscoveryCause.UNLOADABLE per spec.md sec 8. The original exception
          is preserved via `__cause__` (`raised.__cause__`) rather than only
          its message, so a spec sec 11 classifier can distinguish e.g. an
          out-of-memory or unsupported-hardware failure from any other
          load-time error without this function needing to special-case it.
    """
    spec = get_model_spec(model_id)
    target = str(root) if root is not None else spec.repo_id
    try:
        return pipeline_factory(target, local_files_only=True, **kwargs)
    except Exception as exc:
        raise RuntimeError(
            f"{spec.display_name} ({spec.repo_id}) failed to load locally "
            f"(cause: {DiscoveryCause.UNLOADABLE.value}): {exc}"
        ) from exc

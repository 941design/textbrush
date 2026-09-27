"""Per-model registry: identity, cardinality metadata, and launch-time
default-model resolution.

This module is pure data and pure functions -- it performs no filesystem or
network IO. `textbrush/model/weights.py` (discovery/download, HuggingFace Hub
IO) and `textbrush/inference/flux.py` (pipeline loading) consume it. Keeping
this split lets `registry` stay a dependency-free leaf that any layer above
`model` can import without dragging in `huggingface_hub`.

BLOCKING CONDITION S2-BC-1 (see specs/epic-multi-reference-flux-image-editing
/stories.json): two model-identity vocabularies coexist --

- short slugs (this module's `MODEL_REGISTRY` keys / `FLUX1_SCHNELL` etc.),
  fixed by the `GenerationRequest` seam contract and already used by
  `textbrush/config.py`;
- HuggingFace repo ids (`ModelSpec.repo_id`), the vocabulary the Hub and
  `diffusers` understand.

This module is the single owner of the mapping between them. Every other
module -- `textbrush/inference/flux.py` included -- must call `get_repo_id()`
rather than hardcoding a repo id string of its own.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# ---------------------------------------------------------------------------
# Short-slug identity (the GenerationRequest.model_id vocabulary)
# ---------------------------------------------------------------------------

FLUX1_SCHNELL = "flux1-schnell"
FLUX1_KONTEXT_DEV = "flux1-kontext-dev"
FLUX2_KLEIN_4B = "flux2-klein-4b"


@dataclass(frozen=True)
class ModelComponent:
    """One declared sub-component of a diffusers-style pipeline snapshot.

    A component lives at `<snapshot_root>/<name>/` and is "present" once its
    config file exists and, if `weight_glob` is not None, at least one file
    under the component directory matches that glob. `weight_glob` is None
    for components that carry no weight files of their own (schedulers,
    tokenizers).
    """

    name: str
    config_filename: str = "config.json"
    weight_glob: str | None = "*.safetensors"


# This table has exactly ONE job: an optional per-name config-filename/
# weight-glob override for a component whose real layout disagrees with
# `_infer_component_metadata`'s name-based default (e.g. a scheduler or
# tokenizer needing a non-default config filename or no weight glob at
# all). `check_model_availability` (textbrush/model/weights.py) does NOT
# read this table for completeness membership -- it derives the component
# set to check from each checkpoint's own model_index.json at discovery
# time (spec.md sec 8: "for each component the index declares"). A name
# absent from this table is not "unchecked" for completeness -- it is
# checked using the inferred default.
#
# It is a SEPARATE matter, and gate-remediation round 4 got this wrong,
# that `ModelSpec.identity_components` below -- a distinct, independently-
# declared field, NOT derived from this table at each model's registration
# -- IS load-bearing for cross-model identity matching
# (`_directory_identity_matches` in weights.py, gate-remediation C1).
# Emptying or otherwise "cleaning up" this override table has zero effect
# on identity checking; see `identity_components` for that contract, and
# `ModelSpec.__post_init__` for the loud-failure guard that makes an empty
# identity set for a registered model a build-time error, not a silent
# permissive fallback.
#
# Measured 2026-09-18: every entry below is byte-identical to what
# `_infer_component_metadata` derives from the name alone (0 of 19 entries
# differ, across all three registered models) -- so today this table is
# provably redundant with the inference default for its ONE job
# (filename/glob overrides). It earns its place, rather than being deleted
# outright, only via
# `tests/test_model_weights.py::TestComponentOverrideTableAgreesWithInference`,
# which fails the moment an entry is added that actually diverges from the
# inferred default without a deliberate justifying comment. Do not add an
# override here to "document" a real layout -- discovery no longer reads
# this table for completeness membership, only for filename/glob
# overrides, so a stale or wrong entry here silently misdescribes what
# discovery actually checks.
_STANDARD_FLUX_COMPONENTS: tuple[ModelComponent, ...] = (
    ModelComponent(name="scheduler", config_filename="scheduler_config.json", weight_glob=None),
    ModelComponent(name="text_encoder"),
    ModelComponent(name="text_encoder_2"),
    ModelComponent(name="tokenizer", config_filename="tokenizer_config.json", weight_glob=None),
    ModelComponent(name="tokenizer_2", config_filename="tokenizer_config.json", weight_glob=None),
    ModelComponent(name="transformer"),
    ModelComponent(name="vae"),
)

# Override entries for FLUX.2-klein-4B. Membership here is irrelevant to
# *completeness*: discovery reads the checkpoint's own model_index.json to
# decide which components exist. It is irrelevant to *identity* too --
# see the module-level comment above `_STANDARD_FLUX_COMPONENTS`.
# Retained only so the two tuples stay parallel; every entry currently equals the
# inferred default (pinned by TestComponentOverrideTableAgreesWithInference).
_FLUX2_COMPONENTS: tuple[ModelComponent, ...] = (
    ModelComponent(name="scheduler", config_filename="scheduler_config.json", weight_glob=None),
    ModelComponent(name="text_encoder"),
    ModelComponent(name="tokenizer", config_filename="tokenizer_config.json", weight_glob=None),
    ModelComponent(name="transformer"),
    ModelComponent(name="vae"),
)


@dataclass(frozen=True)
class ModelSpec:
    """Identity and cardinality metadata for one supported model.

    `min_references`/`max_references` are the single source of "how many
    references this model accepts" (spec.md sec 5.1). They are descriptive
    identity data about the model, owned here alongside `repo_id`; the
    *validation* that an active selection matches a request's actual
    reference count is a separate concern (spec.md sec 7.2, owned by the
    `validation` module once it exists) that should read this same field
    rather than restating the bounds.
    """

    slug: str
    repo_id: str
    display_name: str
    min_references: int
    max_references: int
    gated: bool
    index_filename: str = "model_index.json"
    components: tuple[ModelComponent, ...] = ()
    # Gate-remediation round 5, finding 1 (BLOCKER): the set of component
    # *names* used for cross-model identity matching
    # (`_directory_identity_matches` in weights.py, gate-remediation C1).
    # Deliberately a SEPARATE field from `components` above, not derived
    # from it by default at each MODEL_REGISTRY entry (every entry below
    # sets this explicitly, independent of `components`) -- round 4's bug
    # was reading `{c.name for c in spec.components}` for identity, which
    # meant that table's own round-3 comment ("provably redundant... does
    # NOT determine which components are checked") was true for
    # completeness but had silently become false for identity: emptying
    # `components` (exactly what the round-3 comment invited a future
    # maintainer to do) also emptied identity, and the `not
    # expected_names: return True` escape hatch then made every directory
    # match every model. Keeping this as its own field means the override
    # table can be edited, pruned, or deleted for its one real job
    # (filename/glob overrides) without touching identity at all.
    identity_components: frozenset[str] = field(default_factory=frozenset)
    # Gate-remediation round 5, finding 4: the checkpoint's own declared
    # `_class_name` (diffusers pipeline class, e.g. "FluxPipeline"), used as
    # a second, independent identity signal in `_directory_identity_matches`
    # because FLUX.1 schnell and FLUX.1 Kontext-dev share the exact same
    # `identity_components` name set (both use `_STANDARD_FLUX_COMPONENTS`)
    # and are therefore mutually indistinguishable by component names alone.
    # None means "not pinned" -- deliberately left unset for a model this
    # registry cannot independently verify (see FLUX1_KONTEXT_DEV below) --
    # and a None value is never used to reject anything; see
    # `_directory_identity_matches`'s docstring in weights.py for exactly
    # how an unpinned value stays fail-safe.
    expected_class_name: str | None = None
    license_url: str = ""
    # Tokenizers used through apply_chat_template need a default template
    # in addition to their vocabulary, even when tokenizer construction succeeds.
    chat_template_components: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Default `license_url` from `repo_id`, and enforce that
        `identity_components` is never empty for a constructed spec.

        S2-BC-1 extends to license URLs: a URL embedding a repo id is the
        slug<->repo-id mapping restated in a different wrapper, and drifts
        the same way a hardcoded repo id would. Every caller that needs a
        per-model license URL must read `ModelSpec.license_url` rather than
        formatting `repo_id` into a URL of its own.

        Gate-remediation round 5, finding 1: an empty `identity_components`
        would silently disable identity matching for this model (every
        directory's component-name set is trivially a subset of the empty
        set... no -- worse, `_directory_identity_matches` would have
        nothing positive to check against). Rather than let that surface
        later as a silent, permissive runtime fallback, it is a loud,
        immediate construction-time failure: a registered model MUST name
        its identity component set explicitly (see `identity_components`
        above), and the only convenience allowed is deriving it from
        `components` when the caller left both unset in a hand-built
        `ModelSpec` (e.g. in a test) -- deriving from an EMPTY `components`
        is exactly the round-4 regression, so that specific case still
        raises.
        """
        if not self.identity_components:
            derived = frozenset(component.name for component in self.components)
            if not derived:
                raise ValueError(
                    f"{self.slug!r}: ModelSpec.identity_components must not be "
                    "empty. Either declare it explicitly (the name set used for "
                    "cross-model identity matching) or supply a non-empty "
                    "`components` tuple to derive it from. An empty identity set "
                    "would silently disable identity checking for this model "
                    "(gate-remediation round 4 regression) -- this is refused at "
                    "construction time rather than allowed to fail open later."
                )
            object.__setattr__(self, "identity_components", derived)
        if not self.license_url:
            object.__setattr__(self, "license_url", f"https://huggingface.co/{self.repo_id}")


MODEL_REGISTRY: dict[str, ModelSpec] = {
    # gated: verified 2026-09-18 against https://huggingface.co/api/models/<repo_id>
    # ("gated" field). schnell and Kontext-dev both report "auto" (gated with
    # automatic approval -- still requires an accepted licence and an
    # authenticated request); klein-4B reports `false` (not gated).
    FLUX1_SCHNELL: ModelSpec(
        slug=FLUX1_SCHNELL,
        repo_id="black-forest-labs/FLUX.1-schnell",
        display_name="FLUX.1 schnell",
        min_references=0,
        max_references=0,
        gated=True,
        components=_STANDARD_FLUX_COMPONENTS,
        # Declared independently of `components` above (gate-remediation
        # round 5, finding 1) -- this literal name set is what
        # `_directory_identity_matches` checks a candidate directory
        # against, and it stays intact even if `components` is later
        # pruned or emptied for its own (unrelated) filename/glob-override
        # purpose.
        identity_components=frozenset(
            {
                "scheduler",
                "text_encoder",
                "text_encoder_2",
                "tokenizer",
                "tokenizer_2",
                "transformer",
                "vae",
            }
        ),
        # Gated repo: an unauthenticated fetch of model_index.json returns
        # HTTP 401 (verified 2026-09-18 attempting exactly that during this
        # round), so this is not independently Hub-verified this round.
        # "FluxPipeline" is nonetheless pinned with high confidence: it is
        # the standard diffusers class for the base FLUX text-to-image
        # pipeline, and every literal test fixture across this story
        # (written independently, in prior rounds) already assumes this
        # exact value for schnell.
        expected_class_name="FluxPipeline",
    ),
    FLUX1_KONTEXT_DEV: ModelSpec(
        slug=FLUX1_KONTEXT_DEV,
        repo_id="black-forest-labs/FLUX.1-Kontext-dev",
        display_name="FLUX.1 Kontext [dev]",
        min_references=1,
        max_references=1,
        gated=True,
        components=_STANDARD_FLUX_COMPONENTS,
        identity_components=frozenset(
            {
                "scheduler",
                "text_encoder",
                "text_encoder_2",
                "tokenizer",
                "tokenizer_2",
                "transformer",
                "vae",
            }
        ),
        # Deliberately left unpinned (None). Same gating problem as schnell
        # above -- an unauthenticated fetch of this repo's model_index.json
        # also returns HTTP 401 -- but unlike schnell, no prior test fixture
        # in this codebase already commits to a specific value, so pinning
        # one here would be a guess with no corroborating evidence at all.
        # `_directory_identity_matches` in weights.py is fail-safe for this:
        # an unpinned `expected_class_name` is never used to reject a
        # directory outright, and the concrete gate-remediation finding 4
        # defect (schnell/Kontext mutual false-positive) is fully resolved
        # by schnell's and klein's pinned values alone -- see that
        # function's docstring for the two-direction argument.
        expected_class_name=None,
    ),
    FLUX2_KLEIN_4B: ModelSpec(
        slug=FLUX2_KLEIN_4B,
        repo_id="black-forest-labs/FLUX.2-klein-4B",
        display_name="FLUX.2 [klein] 4B",
        # min_references=0: FLUX.2 klein is a text-to-image model that
        # ALSO accepts 1-4 references; references are optional, not a
        # precondition. `max_references > 0` (the `is_editing_model`
        # predicate) therefore means "accepts references", never
        # "requires them" -- every consumer that needs the stricter
        # question must read `min_references` itself. The engine-side
        # guard in `textbrush/inference/flux.py` does exactly that.
        min_references=0,
        max_references=4,
        gated=False,
        components=_FLUX2_COMPONENTS,
        identity_components=frozenset(
            {"scheduler", "text_encoder", "tokenizer", "transformer", "vae"}
        ),
        # Ungated repo: live-verified 2026-09-18 by fetching
        # https://huggingface.co/black-forest-labs/FLUX.2-klein-4B/raw/main/model_index.json
        # directly (no token required) and reading its `_class_name` key.
        expected_class_name="Flux2KleinPipeline",
        chat_template_components=("tokenizer",),
    ),
}


def get_model_spec(model_id: str) -> ModelSpec:
    """Look up a model's registry entry.

    CONTRACT:
      Inputs:
        model_id: a short slug (e.g. "flux1-schnell").
      Outputs:
        The ModelSpec for that slug.
      Raises:
        ValueError: model_id is not a known registry slug.
    """
    try:
        return MODEL_REGISTRY[model_id]
    except KeyError:
        raise ValueError(
            f"unknown model id {model_id!r}; known ids: {sorted(MODEL_REGISTRY)}"
        ) from None


def get_repo_id(model_id: str) -> str:
    """Return the HuggingFace repo id for a short slug.

    CONTRACT:
      Inputs:
        model_id: a short slug (e.g. "flux1-schnell").
      Outputs:
        The HuggingFace Hub repo id (e.g. "black-forest-labs/FLUX.1-schnell").
      Invariants:
        This is the ONLY place the slug<->repo-id mapping is defined
        (S2-BC-1). Callers -- including `textbrush.inference.flux` -- must
        consume this rather than hardcoding a repo id of their own.
      Raises:
        ValueError: model_id is not a known registry slug.
    """
    return get_model_spec(model_id).repo_id


def iter_model_slugs() -> tuple[str, ...]:
    """Return every known short slug, in registry declaration order."""
    return tuple(MODEL_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Discovery cause enumeration (spec.md sec 8, AC-DISCOVERY-1)
# ---------------------------------------------------------------------------


class DiscoveryCause(str, Enum):
    """Why a model is not available, or why availability could not be
    determined more specifically.

    `UNKNOWN` is a true fallback: it is reachable only when a failure does
    not match any of the other four (see `check_model_availability` in
    `textbrush.model.weights`), never a default classification.
    """

    ABSENT = "absent"
    CREDENTIALS_MISSING = "credentials_missing"
    LICENSE_ACCESS_MISSING = "license_access_missing"
    INCOMPLETE = "incomplete"
    UNLOADABLE = "unloadable"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class AvailabilityReport:
    """Outcome of a discovery check for one model.

    CONTRACT:
      Invariants:
        - available is True iff cause is None.
        - cause is populated whenever available is False.
        - `root`, when not None, is the local snapshot directory discovery
          actually validated (gate-remediation round 5, finding 3): a
          composition root that loads a pipeline after seeing
          `available=True` should pass THIS path to
          `textbrush.model.weights.load_local_only` (its `root` kwarg)
          rather than relying on `from_pretrained`'s own repo-id/HF-cache
          resolution, which never sees a `config.model.directories` custom
          directory at all. Populated only on the `available=True` return
          from `check_model_availability` -- not on INCOMPLETE/ABSENT/etc,
          where there is nothing a loader should be pointed at.
    """

    available: bool
    cause: DiscoveryCause | None
    detail: str = ""
    root: Path | None = None

    def __post_init__(self) -> None:
        if self.available and self.cause is not None:
            raise ValueError("AvailabilityReport.cause must be None when available is True")
        if not self.available and self.cause is None:
            raise ValueError("AvailabilityReport.cause must be set when available is False")


AvailabilityLookup = Callable[[str], AvailabilityReport]


# ---------------------------------------------------------------------------
# Launch-time-only default-model resolution (spec.md sec 5.1, 7.3; AC-MODEL-5)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelResolution:
    """Outcome of resolving which model should be active at launch.

    CONTRACT:
      Invariants:
        - model_id is not None iff blocked is False.
        - blocked=True always carries `reason`.
        - An explicitly requested model is never replaced by a different one:
          the branch that handles `selected_id is not None` only ever returns
          that same id (blocked=False) or blocks (model_id=None) -- it never
          substitutes a different model_id.
    """

    model_id: str | None
    blocked: bool
    reason: str | None = None
    required_model: str | None = None
    cause: DiscoveryCause | None = None


def resolve_model_selection(
    *,
    selected_id: str | None,
    reference_count: int,
    availability: AvailabilityLookup,
) -> ModelResolution:
    """Resolve which model should be active, once, at launch.

    This is the single authored implementation of spec.md sec 5.1 + 7.3,
    intended to be called by both composition roots (`cli.py` and
    `textbrush/ipc/handler.py`) at their respective launch points -- neither
    should reimplement this algorithm. See architecture.json for the
    ownership rationale (this function lives in `model`, not the not-yet-
    existing `validation` module, because both composition roots already
    depend on `model` and it already holds the availability data the
    algorithm needs).

    CONTRACT:
      Inputs:
        selected_id: `config.model.selected_id` verbatim -- None means no
          explicit choice was made (architecture.md "Selected-model
          representation"); any other value is an explicit user choice.
        reference_count: number of references supplied at launch, 0-4.
        availability: a pure lookup from short slug to AvailabilityReport.
          Callers bind this to real discovery (e.g.
          `textbrush.model.weights.check_model_availability`) with whatever
          custom directories apply; this function performs no IO itself so
          that "resolution happens once, at launch" is enforced by call
          discipline in the composition roots, not by hidden state here.
      Outputs:
        ModelResolution.
      Invariants:
        - selected_id, when not None, is honored verbatim or the request is
          blocked -- it is NEVER silently replaced by a different model
          (spec.md sec 5.1).
        - reference_count == 0 always resolves to flux1-schnell, regardless
          of availability (spec.md sec 7.3 item 3; this release has no other
          text-to-image model to fall through to).
        - reference_count in [2, 4] never resolves to flux1-schnell or
          flux1-kontext-dev (spec.md sec 7.3 item 1).
        - This function must be called at most once per launch by each
          composition root; it does not itself detect or prevent re-
          invocation mid-session -- that discipline belongs to the callers
          (S8, S9), consistent with "runs only at launch" being a call-site
          property, not a property this pure function can enforce alone.
      Properties:
        - The 0 / 1 / 2-4 reference-count bands are derived from each
          ModelSpec's min_references/max_references rather than restated as
          a second set of literals, so a future cardinality-owning module
          can share MODEL_REGISTRY instead of duplicating the bounds.
      Raises:
        ValueError: selected_id is not None and not a known registry slug,
          or reference_count is outside 0-4.
    """
    if not 0 <= reference_count <= 4:
        raise ValueError(f"reference_count must be between 0 and 4, got {reference_count}")

    if selected_id is not None:
        spec = get_model_spec(selected_id)  # raises ValueError for an unknown slug
        report = availability(selected_id)
        if report.available:
            return ModelResolution(model_id=selected_id, blocked=False)
        return ModelResolution(
            model_id=None,
            blocked=True,
            reason=(
                f"{spec.display_name} was explicitly selected but is not available "
                f"(cause: {report.cause.value if report.cause else 'unknown'})."
            ),
            required_model=selected_id,
            cause=report.cause,
        )

    if reference_count == 0:
        return ModelResolution(model_id=FLUX1_SCHNELL, blocked=False)

    candidates = [
        slug
        for slug, spec in MODEL_REGISTRY.items()
        if slug != FLUX1_SCHNELL and spec.min_references <= reference_count <= spec.max_references
    ]
    # spec.md sec 7.3: FLUX.2 is preferred whenever it is eligible; Kontext is
    # only ever a fallback for the single-reference case.
    candidates.sort(key=lambda slug: 0 if slug == FLUX2_KLEIN_4B else 1)

    for slug in candidates:
        if availability(slug).available:
            return ModelResolution(model_id=slug, blocked=False)

    preferred = candidates[0] if candidates else None
    preferred_name = get_model_spec(preferred).display_name if preferred else "a compatible model"
    return ModelResolution(
        model_id=None,
        blocked=True,
        reason=(
            f"No locally available model supports {reference_count} reference(s); "
            f"install {preferred_name}."
        ),
        required_model=preferred,
    )

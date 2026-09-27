"""Tests for the per-model registry, discovery, and launch-time default-model
resolution introduced by epic multi-reference-flux-image-editing, story S2.

Covers:
  - AC-DISCOVERY-1: the five enumerated discovery causes, each constructed
    from literal on-disk/env state, plus the "incomplete" gap the current
    (pre-epic) is_flux_available() cannot detect.
  - AC-MODEL-5: launch-time-only default-model resolution, the full
    availability-permutation table from spec.md sec 7.3, and the "explicit
    selection is never silently replaced" guarantee.
  - AC-LOCAL-1: local-only loading with zero network access.
  - S2-BC-1: the short-slug <-> HuggingFace-repo-id mapping has exactly one
    owner (this registry); textbrush.inference.flux consumes it rather than
    restating it.
"""

from __future__ import annotations

import dataclasses
import json
import os
import socket
from pathlib import Path
from unittest.mock import patch

import pytest
from huggingface_hub import _CACHED_NO_EXIST

from tests.model_fixtures import (
    remove_component_weights,
    write_complete_snapshot,
    write_index_only,
)
from tests.test_config import _internal_imports
from textbrush.model.registry import (
    FLUX1_KONTEXT_DEV,
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    MODEL_REGISTRY,
    AvailabilityReport,
    DiscoveryCause,
    ModelResolution,
    ModelSpec,
    get_model_spec,
    get_repo_id,
    iter_model_slugs,
    resolve_model_selection,
)
from textbrush.model.weights import (
    _directory_identity_matches,
    check_model_availability,
    download_model_weights,
    is_model_available,
    load_local_only,
)


class TestLeafBoundary:
    """architecture.md boundary rule 1: `model` is a leaf and must not import
    backend, worker, ipc, or inference."""

    def test_registry_and_weights_have_no_forbidden_internal_imports(self):
        import textbrush.model.registry as registry_module
        import textbrush.model.weights as weights_module

        forbidden = {
            "textbrush.backend",
            "textbrush.worker",
            "textbrush.ipc",
            "textbrush.inference",
        }
        for module in (registry_module, weights_module):
            source = Path(module.__file__).read_text()
            internal_imports = _internal_imports(source)
            violations = {
                i
                for i in internal_imports
                if any(i == f or i.startswith(f + ".") for f in forbidden)
            }
            assert not violations, f"{module.__name__} must not import {forbidden}: {violations}"


class TestRegistryIdentity:
    """S2-BC-1: the registry is the single owner of slug<->repo-id."""

    def test_all_three_models_registered(self):
        assert set(iter_model_slugs()) == {FLUX1_SCHNELL, FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B}

    def test_repo_ids_are_distinct(self):
        repo_ids = [get_repo_id(slug) for slug in iter_model_slugs()]
        assert len(repo_ids) == len(set(repo_ids))

    def test_unknown_slug_raises_value_error(self):
        with pytest.raises(ValueError):
            get_model_spec("not-a-real-model")

    def test_inference_flux_consumes_registry_mapping_not_a_second_spelling(self):
        """S2-BC-1: FluxInferenceEngine.MODEL_ID must equal the registry's
        mapping for flux1-schnell rather than a separately hardcoded repo id
        literal living in textbrush/inference/flux.py."""
        from textbrush.inference.flux import FluxInferenceEngine

        assert FluxInferenceEngine.MODEL_ID == get_repo_id(FLUX1_SCHNELL)


class TestCardinalityMetadata:
    """Descriptive per-model reference-count bounds (spec.md sec 5.1), the
    single source resolve_model_selection reads instead of restating bands."""

    def test_schnell_accepts_zero_references_only(self):
        spec = get_model_spec(FLUX1_SCHNELL)
        assert (spec.min_references, spec.max_references) == (0, 0)

    def test_kontext_requires_exactly_one_reference(self):
        spec = get_model_spec(FLUX1_KONTEXT_DEV)
        assert (spec.min_references, spec.max_references) == (1, 1)

    def test_klein_accepts_zero_to_four_references(self):
        """References are OPTIONAL for FLUX.2 klein: it is a text-to-image
        model that also accepts up to four references, so its lower bound
        is zero, not one."""
        spec = get_model_spec(FLUX2_KLEIN_4B)
        assert (spec.min_references, spec.max_references) == (0, 4)


class TestComponentOverrideTableAgreesWithInference:
    """Gate-remediation round 3, finding 3: `ModelSpec.components` is no
    longer the source of which components discovery checks (that's the
    checkpoint's own model_index.json, via `_declared_components` in
    weights.py) -- it now serves only as an optional per-name
    config-filename/weight-glob override for a component whose real layout
    disagrees with `_infer_component_metadata`'s name-based default.

    This test is what makes the override table "earn its place" rather than
    being silently vestigial: it fails the moment an entry is added that
    diverges from the inferred default, forcing that divergence to be a
    deliberate, visible exception (with its own justifying comment) instead
    of a stale or wrong entry nobody notices because nothing reads it for
    membership anymore. As of 2026-09-18 every entry agrees (0 of 19 differ,
    across both component tuples) -- this test pins that fact so a future,
    genuinely-diverging override is a conscious choice, not an accident."""

    def test_every_override_table_entry_matches_the_inferred_default(self):
        from textbrush.model.weights import _infer_component_metadata

        for spec in MODEL_REGISTRY.values():
            for component in spec.components:
                inferred = _infer_component_metadata(component.name)
                assert component == inferred, (
                    f"{spec.slug}: override for {component.name!r} "
                    f"({component}) diverges from the inferred default "
                    f"({inferred}). If this divergence is real and "
                    f"intentional (the actual on-disk layout truly needs a "
                    f"non-default config filename or weight glob), justify "
                    f"it with a comment on the override table entry rather "
                    f"than adjusting this assertion to ignore it."
                )


class TestIdentityComponentsIndependentOfOverrideTable:
    """Gate-remediation round 5, finding 1 (BLOCKER): round 4's identity fix
    read `{c.name for c in spec.components}` -- the SAME override table
    round 3's own comment declared "provably redundant" and safe to prune --
    as the authoritative membership set for identity. Verified concretely
    before this fix: setting `MODEL_REGISTRY[FLUX2_KLEIN_4B].components = ()`
    made a complete schnell directory pass as FLUX.2 again, with a green
    suite (`TestComponentOverrideTableAgreesWithInference` is satisfied
    vacuously by an empty tuple). `ModelSpec.identity_components` is now a
    separate field, declared independently at each MODEL_REGISTRY entry, so
    pruning or emptying `components` cannot affect identity at all.
    """

    def test_every_registered_model_declares_its_real_component_name_set(self):
        """The literal 7/7/5 name sets discovery must be able to
        distinguish models by -- pinned here independent of `components`,
        so this test would catch a divergence even if `components` were
        edited or emptied for its own (filename/glob-override) purpose."""
        standard_flux_names = {
            "scheduler",
            "text_encoder",
            "text_encoder_2",
            "tokenizer",
            "tokenizer_2",
            "transformer",
            "vae",
        }
        flux2_names = {"scheduler", "text_encoder", "tokenizer", "transformer", "vae"}

        assert get_model_spec(FLUX1_SCHNELL).identity_components == standard_flux_names
        assert get_model_spec(FLUX1_KONTEXT_DEV).identity_components == standard_flux_names
        assert get_model_spec(FLUX2_KLEIN_4B).identity_components == flux2_names

    def test_emptying_components_table_does_not_disable_identity_matching(self):
        """Regression test for the concretely-verified round-4 defect:
        simulate a maintainer following round-3's own comment ("provably
        redundant... does NOT determine which components are checked") to
        its conclusion and pruning `components` to `()`. Identity matching
        must be unaffected, because it now reads `identity_components`, a
        field that is never derived from `components` when both are already
        set on a constructed `ModelSpec` (only the empty-both-fields case in
        `__post_init__` derives one from the other, and that case is a
        registry-construction failure, not a live mutation path)."""
        klein_spec = get_model_spec(FLUX2_KLEIN_4B)
        pruned_klein_spec = dataclasses.replace(klein_spec, components=())
        assert pruned_klein_spec.identity_components == klein_spec.identity_components

    def test_pruned_components_table_still_rejects_a_foreign_complete_directory(self, tmp_path):
        """End-to-end version of the above: a `ModelSpec` whose `components`
        override table has been emptied must still reject a complete,
        differently-shaped (7-component, schnell-identity) directory for a
        FLUX.2 (5-component) request -- i.e. identity checking cannot be
        silently switched off by pruning the override table."""
        klein_spec = get_model_spec(FLUX2_KLEIN_4B)
        pruned_klein_spec = dataclasses.replace(klein_spec, components=())

        model_dir = tmp_path / "actually-schnell"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )

        assert _directory_identity_matches(pruned_klein_spec, model_dir) is False, (
            "emptying the components override table must not silently disable identity matching"
        )

    def test_constructing_a_spec_with_no_identity_and_no_components_fails_loudly(self):
        """Gate-remediation round 5, finding 1: turning the previous
        permissive `if not expected_names: return True` escape into a loud,
        construction-time failure. A `ModelSpec` that declares neither
        `identity_components` nor a non-empty `components` tuple to derive
        it from must never be constructible -- an empty identity set must
        never be allowed to silently mean "every directory matches"."""
        with pytest.raises(ValueError):
            ModelSpec(
                slug="hypothetical",
                repo_id="org/repo",
                display_name="Hypothetical Model",
                min_references=0,
                max_references=0,
                gated=False,
                components=(),
            )


class TestAvailabilityReportInvariant:
    def test_available_true_requires_no_cause(self):
        with pytest.raises(ValueError):
            AvailabilityReport(True, DiscoveryCause.ABSENT)

    def test_available_false_requires_a_cause(self):
        with pytest.raises(ValueError):
            AvailabilityReport(False, None)


class TestDiscoveryCauseEnumeration:
    """AC-DISCOVERY-1: causes constructed from literal on-disk/env state (not
    a mocked helper return value), except LICENSE_ACCESS_MISSING, which is
    only observable from the download path (see
    tests/test_weights.py::TestTokenRequiredError -- e.g.
    test_raises_token_required_on_gated_repo_error -- for that cause's
    construction and assertion)."""

    def test_absent_when_no_local_marker_for_ungated_model(self, tmp_path):
        # klein-4b is the only ungated model in the registry (verified
        # against the Hub 2026-09-18: gated=false).
        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[tmp_path / "nope"])

        assert report.available is False
        assert report.cause == DiscoveryCause.ABSENT

    def test_credentials_missing_when_gated_model_absent_and_no_token(self, tmp_path):
        env = {k: v for k, v in os.environ.items() if k != "HF_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
                report = check_model_availability(
                    FLUX1_KONTEXT_DEV, custom_dirs=[tmp_path / "nope"]
                )

        assert report.available is False
        assert report.cause == DiscoveryCause.CREDENTIALS_MISSING

    def test_absent_when_gated_model_no_local_root_but_token_present(self, tmp_path):
        """Gate-remediation fix (finding B): a gated model with no local root
        and a token configured is ABSENT, not LICENSE_ACCESS_MISSING --
        local, static facts (no root found; a token is configured) cannot
        distinguish "not yet downloaded" from "access refused"; only an
        actual download attempt can (see TestTokenRequiredError in
        tests/test_weights.py). Reporting LICENSE_ACCESS_MISSING here, as a
        prior version of this test asserted, made DiscoveryCause.ABSENT
        unreachable for every gated model and routed a user who simply
        hadn't downloaded yet away from the download flow spec.md sec 8
        requires."""
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
                report = check_model_availability(
                    FLUX1_KONTEXT_DEV, custom_dirs=[tmp_path / "nope"]
                )

        assert report.available is False
        assert report.cause == DiscoveryCause.ABSENT

    def test_incomplete_when_index_present_but_one_component_weight_missing(self, tmp_path):
        """The exact gap AC-DISCOVERY-1 calls out: a top-level index alone is
        not sufficient evidence of availability."""
        model_dir = tmp_path / "flux2-partial"
        write_complete_snapshot(model_dir, FLUX2_KLEIN_4B)
        remove_component_weights(model_dir, FLUX2_KLEIN_4B, "transformer")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE

    def test_incomplete_when_index_present_with_no_component_files_at_all(self, tmp_path):
        """`write_index_only` writes a *full* index (every component named,
        per `spec.components`) with none of the per-component directories --
        "no component *files*", not "no components *declared*". That second,
        distinct state (an index that itself declares zero components -- the
        literal bare-marker case AC-DISCOVERY-1 forbids reporting as
        available) is covered separately by
        `TestDiscoveryCauseEnumeration.test_incomplete_when_index_declares_zero_components`
        below (gate-remediation round 3, finding 1)."""
        model_dir = tmp_path / "flux1-kontext-index-only"
        write_index_only(model_dir, FLUX1_KONTEXT_DEV)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE

    def test_incomplete_when_index_declares_zero_components(self, tmp_path):
        """Gate-remediation round 3, finding 1 (severity 8 regression): an
        index that parses as a JSON object but declares no components at all
        -- e.g. a bare `{"_class_name": "FluxPipeline"}` marker left behind
        by an interrupted download, or any index whose component values
        aren't JSON lists -- previously made `_declared_components` return
        `[]`, `_missing_components` return `[]`, and `if missing:` fall
        through to `available=True`. This is verbatim the state
        AC-DISCOVERY-1 forbids ("a top-level marker alone is not sufficient
        evidence of availability"); it must report INCOMPLETE, not
        available, and must never be silently treated as "every declared
        component present" merely because there were zero of them."""
        for case_index, index in enumerate(
            (
                {},
                {"_class_name": "FluxPipeline"},
                {"_class_name": "FluxPipeline", "is_distilled": True},
            )
        ):
            model_dir = tmp_path / f"bare-{case_index}"
            model_dir.mkdir()
            (model_dir / "model_index.json").write_text(json.dumps(index))

            with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
                report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

            assert report.available is False, (index, report)
            assert report.cause == DiscoveryCause.INCOMPLETE, (index, report)

    def test_available_when_index_and_every_component_present(self, tmp_path):
        model_dir = tmp_path / "flux1-kontext-complete"
        write_complete_snapshot(model_dir, FLUX1_KONTEXT_DEV)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])

        assert report.available is True
        assert report.cause is None

    def test_unloadable_is_a_load_time_classification_not_a_discovery_outcome(self, tmp_path):
        """spec.md sec 8: 'unloadable -- discovery succeeds but loading raises
        on the current system'. check_model_availability() never reports it;
        only an actual load attempt (load_local_only) does."""
        model_dir = tmp_path / "flux1-kontext-complete"
        write_complete_snapshot(model_dir, FLUX1_KONTEXT_DEV)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])
        assert report.available is True

        def failing_factory(repo_id, **kwargs):
            raise OSError("simulated pipeline construction failure")

        with pytest.raises(RuntimeError) as exc_info:
            load_local_only(failing_factory, FLUX1_KONTEXT_DEV)
        assert DiscoveryCause.UNLOADABLE.value in str(exc_info.value)

    def test_unknown_is_a_true_fallback_reached_only_when_inspection_itself_fails(self, tmp_path):
        """unknown must never be a default classification for an ordinary
        'not found' case -- it is reached only when the filesystem inspection
        fails in a way none of the other four causes describe."""
        model_dir = tmp_path / "flux1-kontext-complete"
        write_complete_snapshot(model_dir, FLUX1_KONTEXT_DEV)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            with patch("pathlib.Path.glob", side_effect=OSError("simulated fs error")):
                report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.UNKNOWN

    def test_all_five_causes_are_distinct(self):
        causes = {
            DiscoveryCause.ABSENT,
            DiscoveryCause.CREDENTIALS_MISSING,
            DiscoveryCause.LICENSE_ACCESS_MISSING,
            DiscoveryCause.INCOMPLETE,
            DiscoveryCause.UNLOADABLE,
        }
        assert len(causes) == 5
        assert DiscoveryCause.UNKNOWN not in causes


class TestLoadLocalOnly:
    """AC-LOCAL-1: a model discovery reports as available must load local-only,
    with no remote revalidation round trip."""

    def test_passes_local_files_only_true(self):
        calls: dict[str, object] = {}

        def factory(repo_id, **kwargs):
            calls["repo_id"] = repo_id
            calls["kwargs"] = kwargs
            return "pipeline-object"

        result = load_local_only(factory, FLUX1_SCHNELL, torch_dtype="bf16")

        assert result == "pipeline-object"
        assert calls["repo_id"] == get_repo_id(FLUX1_SCHNELL)
        assert calls["kwargs"]["local_files_only"] is True
        assert calls["kwargs"]["torch_dtype"] == "bf16"

    def test_factory_failure_raises_runtime_error_classified_unloadable(self):
        def failing_factory(repo_id, **kwargs):
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError) as exc_info:
            load_local_only(failing_factory, FLUX1_KONTEXT_DEV)
        assert "unloadable" in str(exc_info.value)

    def test_root_kwarg_is_passed_in_place_of_repo_id(self, tmp_path):
        """Gate-remediation round 5, finding 3: a model available only via
        `config.model.directories` (never the HF cache) previously reported
        available and then failed to load, because
        `pipeline_factory(repo_id, local_files_only=True)` only ever
        consults the HF cache -- it never sees a custom directory discovery
        just validated. Passing `root` must route `pipeline_factory` to
        that exact directory instead."""
        calls: dict[str, object] = {}
        resolved_root = tmp_path / "custom-install"

        def factory(target, **kwargs):
            calls["target"] = target
            calls["kwargs"] = kwargs
            return "pipeline-object"

        result = load_local_only(factory, FLUX1_SCHNELL, root=resolved_root, torch_dtype="bf16")

        assert result == "pipeline-object"
        assert calls["target"] == str(resolved_root)
        assert calls["kwargs"]["local_files_only"] is True

    def test_omitting_root_reproduces_prior_repo_id_behavior(self):
        """Omitting `root` (the default) must be indistinguishable from
        calling `load_local_only` before this parameter existed -- every
        existing caller that never passes `root` is unaffected."""
        calls: dict[str, object] = {}

        def factory(target, **kwargs):
            calls["target"] = target
            return "pipeline-object"

        load_local_only(factory, FLUX1_SCHNELL)

        assert calls["target"] == get_repo_id(FLUX1_SCHNELL)

    def test_availability_report_root_can_be_threaded_straight_through(self, tmp_path):
        """End-to-end: `check_model_availability`'s returned `root` (finding
        3's other half) plugs directly into `load_local_only`'s `root`
        kwarg with no extra translation."""
        model_dir = tmp_path / "custom-install"
        write_complete_snapshot(model_dir, FLUX1_SCHNELL)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.root == model_dir

        calls: dict[str, object] = {}

        def factory(target, **kwargs):
            calls["target"] = target
            return "pipeline-object"

        load_local_only(factory, FLUX1_SCHNELL, root=report.root)

        assert calls["target"] == str(model_dir)


class TestZeroNetworkLocalLoad:
    """AC-LOCAL-1 end to end: with outbound connections refused at the socket
    layer and a populated local cache, discovery and load complete with zero
    network access. The socket block is real (monkeypatches socket.socket.connect
    itself), not a mock of a specific HF Hub client method -- any new code
    path that tried to open a real connection would fail this test, not
    silently pass it.
    """

    def test_discovery_and_load_succeed_with_sockets_blocked(self, tmp_path, monkeypatch):
        cache_dir = tmp_path / "hf_cache"
        write_complete_snapshot(cache_dir, FLUX1_KONTEXT_DEV)

        network_attempts: list[object] = []

        def blocked_connect(self, address, *args, **kwargs):
            network_attempts.append(address)
            raise OSError("network access disabled for this test (AC-LOCAL-1)")

        monkeypatch.setattr(socket.socket, "connect", blocked_connect)

        # custom_dirs is checked before the HF cache, so try_to_load_from_cache
        # (itself a local-only lookup) is never reached here -- discovery is
        # pure filesystem stat calls against a real on-disk snapshot.
        report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[cache_dir])
        assert report.available is True
        assert report.cause is None

        def local_pipeline_factory(repo_id, **kwargs):
            assert kwargs.get("local_files_only") is True
            return object()

        pipeline = load_local_only(local_pipeline_factory, FLUX1_KONTEXT_DEV)
        assert pipeline is not None

        assert network_attempts == [], (
            "discovery and local-only load must complete without attempting "
            f"any socket connection; attempted: {network_attempts}"
        )

    def test_discovery_succeeds_via_real_hf_cache_lookup_with_sockets_blocked(
        self, tmp_path, monkeypatch
    ):
        """Gate-remediation fix (finding G): the previous version of this
        test always passed custom_dirs, so try_to_load_from_cache (the real
        HF-cache lookup component) never actually ran under the socket
        block -- it exercised only the custom_dirs half of discovery. This
        variant leaves custom_dirs unset and instead populates a real
        on-disk HF cache layout (`models--<org>--<repo>/snapshots/main/...`)
        via HF_HUB_CACHE, so `try_to_load_from_cache` itself executes for
        real, still under the same socket block.

        The diffusers `FluxPipeline.from_pretrained` half is intentionally
        still stubbed here (`local_pipeline_factory`) rather than exercised
        for real -- that belongs to the spec.md sec 15 gated smoke test, not
        this unit test.
        """
        import huggingface_hub.constants as hf_constants

        cache_dir = tmp_path / "hf_cache"
        spec = get_model_spec(FLUX1_KONTEXT_DEV)
        snapshot_dir = (
            cache_dir / f"models--{spec.repo_id.replace('/', '--')}" / "snapshots" / "main"
        )
        write_complete_snapshot(snapshot_dir, FLUX1_KONTEXT_DEV)
        # huggingface_hub reads HF_HUB_CACHE into this module constant once at
        # import time, so setting the env var alone has no effect on an
        # already-imported process -- the constant itself must be patched for
        # try_to_load_from_cache's default `cache_dir=constants.HF_HUB_CACHE`
        # lookup to see our fixture.
        monkeypatch.setattr(hf_constants, "HF_HUB_CACHE", str(cache_dir))

        network_attempts: list[object] = []

        def blocked_connect(self, address, *args, **kwargs):
            network_attempts.append(address)
            raise OSError("network access disabled for this test (AC-LOCAL-1)")

        monkeypatch.setattr(socket.socket, "connect", blocked_connect)

        # custom_dirs=None: discovery must fall through to the real HF-cache
        # lookup (try_to_load_from_cache), not a mocked/patched one.
        report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=None)
        assert report.available is True
        assert report.cause is None

        def local_pipeline_factory(repo_id, **kwargs):
            assert kwargs.get("local_files_only") is True
            return object()

        pipeline = load_local_only(local_pipeline_factory, FLUX1_KONTEXT_DEV)
        assert pipeline is not None

        assert network_attempts == [], (
            "discovery via the real HF-cache lookup and local-only load must "
            f"complete without attempting any socket connection; attempted: {network_attempts}"
        )


class TestTryToLoadFromCacheCachedAbsenceSentinel:
    """Gate-remediation round 6, finding 1 (P2 crash): `try_to_load_from_cache`
    has THREE possible return values, not two -- verified against installed
    huggingface_hub 0.36.0's own docstring and source
    (`huggingface_hub/file_download.py::try_to_load_from_cache`): the cached
    path (`str`) if found, `None` if never cached, or the sentinel
    `_CACHED_NO_EXIST` if a prior lookup already established the file does
    not exist at this revision and the Hub client cached THAT fact. The
    third outcome is an ordinary state -- reachable any time discovery runs
    twice against the same repo/revision/filename after the first lookup
    found nothing -- not a contrived edge case. Before this fix,
    `_find_available_root` treated any non-`None` return (including the
    sentinel) as a cache hit and called `Path(cached)` on it directly,
    crashing with a `TypeError` (verified live: "argument should be a str or
    an os.PathLike object ... not 'object'") instead of correctly treating
    it as "not cached"."""

    def test_check_model_availability_does_not_crash_on_cached_absence_sentinel(self):
        # klein-4b is ungated, so the classification below is deterministic
        # regardless of whether HF_TOKEN happens to be set in the test env.
        with patch(
            "textbrush.model.weights.try_to_load_from_cache",
            return_value=_CACHED_NO_EXIST,
        ):
            report = check_model_availability(FLUX2_KLEIN_4B)

        assert report.available is False
        assert report.cause == DiscoveryCause.ABSENT

    def test_download_model_weights_does_not_crash_on_cached_absence_sentinel(self):
        """The same sentinel reaches `download_model_weights`'s pre-flight
        `is_model_available` check via the identical `_find_available_root`
        code path. `snapshot_download` is mocked purely to keep this test
        network-free; the point under test is that the sentinel is handled
        before ever reaching it, not what happens after."""
        with (
            patch(
                "textbrush.model.weights.try_to_load_from_cache",
                return_value=_CACHED_NO_EXIST,
            ),
            patch("textbrush.model.weights.snapshot_download") as mock_download,
        ):
            mock_download.return_value = "/fake/snapshot/path"
            result = download_model_weights(FLUX2_KLEIN_4B)

        assert str(result) == "/fake/snapshot/path"
        mock_download.assert_called_once()


class TestIndexDrivenDiscoveryLiteralFixtures:
    """Gate-remediation fix (finding C): tests/model_fixtures.py builds
    snapshots FROM spec.components, so every other discovery test constructs
    precisely what the registry expects and then asserts discovery finds it
    -- self-consistency, not correctness. These fixtures are instead written
    by hand, independent of ModelSpec.components, so a mismatch between the
    registry's expectations and a real checkpoint layout could actually be
    caught by a test.
    """

    def test_flux2_shaped_five_component_fixture_reports_available(self, tmp_path):
        """A checkpoint whose model_index.json declares FLUX.2's real
        five-component layout (no text_encoder_2, no tokenizer_2 -- verified
        against the Hub 2026-09-18) reports available. Written literally: no
        loop over spec.components, so this cannot pass merely because the
        registry and the fixture agree by construction."""
        model_dir = tmp_path / "flux2-literal"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "_diffusers_version": "0.37.0.dev0",
                    "is_distilled": True,
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        (model_dir / "scheduler").mkdir()
        (model_dir / "scheduler" / "scheduler_config.json").write_text("{}")
        (model_dir / "text_encoder").mkdir()
        (model_dir / "text_encoder" / "config.json").write_text("{}")
        (model_dir / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (model_dir / "tokenizer").mkdir()
        (model_dir / "tokenizer" / "tokenizer_config.json").write_text("{}")
        (model_dir / "tokenizer" / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (model_dir / "tokenizer" / "tokenizer.json").write_text("{}")
        (model_dir / "transformer").mkdir()
        (model_dir / "transformer" / "config.json").write_text("{}")
        (model_dir / "transformer" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        (model_dir / "vae").mkdir()
        (model_dir / "vae" / "config.json").write_text("{}")
        (model_dir / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        # Deliberately no text_encoder_2/ or tokenizer_2/ directories at all
        # -- FLUX.2 genuinely has none, and this must not be reported missing.

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_literal_fixture_missing_a_declared_component_reports_incomplete(self, tmp_path):
        """The mirror case: a literal, hand-written index that disagrees with
        an on-disk layout must be caught -- proving the two fixtures above
        aren't passing by construction."""
        model_dir = tmp_path / "flux2-literal-incomplete"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        # transformer/ directory intentionally omitted entirely.

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail

    def test_null_null_slot_is_not_a_required_component(self, tmp_path):
        """Gate-remediation round 3, finding 2: diffusers' convention for a
        pipeline slot that exists in the class signature but is deliberately
        unpopulated is `"name": [null, null]` -- which `isinstance(value,
        list)` accepts, so a naive parse reports it missing. An otherwise-
        complete checkpoint carrying `"safety_checker": [null, null]` must
        report available; `safety_checker` must not be required, and must
        not appear in `report.detail` if it ever were."""
        model_dir = tmp_path / "flux2-literal-null-slot"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                    "safety_checker": [None, None],
                }
            )
        )
        (model_dir / "scheduler").mkdir()
        (model_dir / "scheduler" / "scheduler_config.json").write_text("{}")
        (model_dir / "text_encoder").mkdir()
        (model_dir / "text_encoder" / "config.json").write_text("{}")
        (model_dir / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (model_dir / "tokenizer").mkdir()
        (model_dir / "tokenizer" / "tokenizer_config.json").write_text("{}")
        (model_dir / "tokenizer" / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (model_dir / "tokenizer" / "tokenizer.json").write_text("{}")
        (model_dir / "transformer").mkdir()
        (model_dir / "transformer" / "config.json").write_text("{}")
        (model_dir / "transformer" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        (model_dir / "vae").mkdir()
        (model_dir / "vae" / "config.json").write_text("{}")
        (model_dir / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        # Deliberately no safety_checker/ directory at all -- [null, null]
        # means the slot is unpopulated by design, not missing.

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None


class TestSchnellCompatibility:
    """Gate-remediation fix (finding F3): AC-DISCOVERY-1's strengthening from
    a top-level-marker-only probe to a full per-component check could break
    a real, previously-working FLUX.1 schnell installation (spec.md sec 13:
    "Existing FLUX.1 schnell installations continue to work"). This fixture
    mirrors a real schnell snapshot literally -- sharded transformer/
    text_encoder_2 weights (each with its own real `*.safetensors.index.json`
    -- gate-remediation round 6, finding 2 added these; their earlier absence
    here was itself an under-specification this fixture is now corrected to
    not repeat), a CLIP tokenizer's `tokenizer.json`, and a T5 tokenizer's
    `spiece.model` alongside `tokenizer_config.json` (round 6, finding 3) --
    and is independent of tests/model_fixtures.py.
    """

    def test_sharded_weights_and_t5_spiece_model_report_available(self, tmp_path):
        model_dir = tmp_path / "schnell-real-shape"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )
        (model_dir / "scheduler").mkdir()
        (model_dir / "scheduler" / "scheduler_config.json").write_text("{}")
        (model_dir / "text_encoder").mkdir()
        (model_dir / "text_encoder" / "config.json").write_text("{}")
        (model_dir / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (model_dir / "text_encoder_2").mkdir()
        (model_dir / "text_encoder_2" / "config.json").write_text("{}")
        # Real schnell text_encoder_2 (T5) weights are sharded; *.safetensors
        # matches any suffix-matching filename regardless of the shard prefix,
        # so this is not a gap -- it is confirmed working, not assumed.
        # gate-remediation round 6, finding 2: a real sharded checkpoint also
        # ships the transformers-format weight-index file
        # ("model.safetensors.index.json") alongside its shards -- diffusers/
        # transformers read THAT file to map parameters to shards; they do
        # not reconstruct the mapping from shard filenames (verified against
        # installed transformers 4.57.3). This fixture previously omitted it
        # (round 5 finding 2 only proved shard-suffix detection worked, not
        # that the checkpoint was actually loadable without an index) --
        # omitting it was itself an under-specification of what a real
        # schnell install looks like, now corrected.
        (model_dir / "text_encoder_2" / "model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "weight_map": {
                        "layer.0.weight": "model-00001-of-00002.safetensors",
                        "layer.1.weight": "model-00002-of-00002.safetensors",
                    }
                }
            )
        )
        for shard in ("00001-of-00002", "00002-of-00002"):
            (model_dir / "text_encoder_2" / f"model-{shard}.safetensors").write_bytes(b"\x00")
        (model_dir / "tokenizer").mkdir()
        (model_dir / "tokenizer" / "tokenizer_config.json").write_text("{}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (model_dir / "tokenizer" / "tokenizer.json").write_text("{}")
        (model_dir / "tokenizer_2").mkdir()
        (model_dir / "tokenizer_2" / "tokenizer_config.json").write_text("{}")
        # spiece.model is real T5-tokenizer baggage with no weight_glob check
        # of its own (tokenizer_2 declares weight_glob=None) -- its presence
        # must not be required, and must not break anything either.
        (model_dir / "tokenizer_2" / "spiece.model").write_bytes(b"\x00")
        (model_dir / "transformer").mkdir()
        (model_dir / "transformer" / "config.json").write_text("{}")
        # gate-remediation round 6, finding 2: see the text_encoder_2 comment
        # above -- the diffusers-format weight-index filename differs
        # ("diffusion_pytorch_model.safetensors.index.json").
        (model_dir / "transformer" / "diffusion_pytorch_model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "weight_map": {
                        "layer.0.weight": "diffusion_pytorch_model-00001-of-00003.safetensors",
                        "layer.1.weight": "diffusion_pytorch_model-00002-of-00003.safetensors",
                        "layer.2.weight": "diffusion_pytorch_model-00003-of-00003.safetensors",
                    }
                }
            )
        )
        for shard in ("00001-of-00003", "00002-of-00003", "00003-of-00003"):
            (
                model_dir / "transformer" / f"diffusion_pytorch_model-{shard}.safetensors"
            ).write_bytes(b"\x00")
        (model_dir / "vae").mkdir()
        (model_dir / "vae" / "config.json").write_text("{}")
        (model_dir / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None


class TestTokenizerVocabAssetCompleteness:
    """Gate-remediation round 6, finding 3 (P2): a tokenizer component
    declares `weight_glob=None`, so before this fix nothing under its
    directory was ever checked beyond `tokenizer_config.json` -- a directory
    containing only that config file reported available, but transformers
    cannot build a usable tokenizer from it alone. Verified against the
    installed transformers 4.57.3: CLIP's (BPE) slow tokenizer needs
    `vocab.json` + `merges.txt`
    (`transformers/models/clip/tokenization_clip.py::VOCAB_FILES_NAMES`); T5's
    (SentencePiece) slow tokenizer needs `spiece.model`
    (`transformers/models/t5/tokenization_t5.py::VOCAB_FILES_NAMES`); either
    can instead be loaded from a single fast-format `tokenizer.json`
    (`transformers/tokenization_utils_base.py::FULL_TOKENIZER_FILE`, read
    alongside the slow-format files in `PreTrainedTokenizerBase.
    from_pretrained`). Fixtures are literal, independent of
    tests/model_fixtures.py, per the same discipline as
    TestIndexDrivenDiscoveryLiteralFixtures / TestSchnellCompatibility.
    """

    @staticmethod
    def _write_flux2_literal_with_tokenizer_files(
        root: Path, tokenizer_files: dict[str, str]
    ) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        (root / "scheduler").mkdir()
        (root / "scheduler" / "scheduler_config.json").write_text("{}")
        (root / "text_encoder").mkdir()
        (root / "text_encoder" / "config.json").write_text("{}")
        (root / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (root / "transformer").mkdir()
        (root / "transformer" / "config.json").write_text("{}")
        (root / "transformer" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        (root / "vae").mkdir()
        (root / "vae" / "config.json").write_text("{}")
        (root / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        tokenizer_dir = root / "tokenizer"
        tokenizer_dir.mkdir()
        (tokenizer_dir / "tokenizer_config.json").write_text("{}")
        (tokenizer_dir / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        for filename, content in tokenizer_files.items():
            (tokenizer_dir / filename).write_text(content)

    def test_bare_tokenizer_config_alone_reports_incomplete(self, tmp_path):
        """The exact gap this finding names: a tokenizer directory carrying
        only its class/settings config, no vocabulary asset at all."""
        model_dir = tmp_path / "flux2-bare-tokenizer-config"
        self._write_flux2_literal_with_tokenizer_files(model_dir, {})

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"tokenizer_config.json alone must not be sufficient for a usable "
            f"tokenizer; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "tokenizer" in report.detail

    def test_fast_tokenizer_json_alone_is_sufficient(self, tmp_path):
        """A single `tokenizer.json` (the unified fast-tokenizer format both
        CLIPTokenizerFast and T5TokenizerFast can load from) is accepted on
        its own -- the realistic set is a union, not a single filename."""
        model_dir = tmp_path / "flux2-fast-tokenizer"
        self._write_flux2_literal_with_tokenizer_files(model_dir, {"tokenizer.json": "{}"})

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_sentencepiece_spiece_model_alone_is_sufficient(self, tmp_path):
        """T5's SentencePiece vocabulary file, on its own, is accepted."""
        model_dir = tmp_path / "flux2-sentencepiece-tokenizer"
        self._write_flux2_literal_with_tokenizer_files(model_dir, {"spiece.model": ""})

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_bpe_vocab_and_merges_pair_is_sufficient(self, tmp_path):
        """CLIP's BPE slow-tokenizer pair, both present, is accepted."""
        model_dir = tmp_path / "flux2-bpe-tokenizer"
        self._write_flux2_literal_with_tokenizer_files(
            model_dir, {"vocab.json": "{}", "merges.txt": "#version: 0.2"}
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_vocab_json_without_merges_txt_reports_incomplete(self, tmp_path):
        """The BPE pair is required together -- `vocab.json` alone (without
        its paired `merges.txt`, and with neither a fast `tokenizer.json`
        nor a SentencePiece `spiece.model` present either) is not a usable
        CLIP tokenizer, and must not be silently accepted as one."""
        model_dir = tmp_path / "flux2-half-bpe-tokenizer"
        self._write_flux2_literal_with_tokenizer_files(model_dir, {"vocab.json": "{}"})

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"vocab.json without its paired merges.txt must not report available; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "tokenizer" in report.detail


class TestCustomDirIdentityMismatch:
    """Gate-remediation C1: `custom_dirs` never checked *which model* a
    directory contains -- every registered model shares the same top-level
    marker filename, so any directory carrying `model_index.json` was
    accepted for any requested model. Verified before this fix: a complete
    7-component FLUX.1 schnell directory handed to
    `check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[...])` reported
    `available=True`. Written literally (real diffusers class names, no loop
    over `spec.components`), independent of tests/model_fixtures.py, per the
    same discipline as TestIndexDrivenDiscoveryLiteralFixtures /
    TestSchnellCompatibility.
    """

    def test_complete_flux1_shaped_dir_rejected_for_flux2_request(self, tmp_path):
        """A real, fully-populated FLUX.1 schnell-shaped directory (7
        components, including text_encoder_2/tokenizer_2 -- names FLUX.2
        does not have at all) must not be accepted as a FLUX.2 install, even
        though it carries the same marker filename and is itself complete."""
        model_dir = tmp_path / "actually-schnell"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )
        for name, config_filename in (
            ("scheduler", "scheduler_config.json"),
            ("text_encoder", "config.json"),
            ("text_encoder_2", "config.json"),
            ("tokenizer", "tokenizer_config.json"),
            ("tokenizer_2", "tokenizer_config.json"),
            ("transformer", "config.json"),
            ("vae", "config.json"),
        ):
            comp_dir = model_dir / name
            comp_dir.mkdir()
            (comp_dir / config_filename).write_text("{}")
            if config_filename.startswith("tokenizer"):
                # gate-remediation round 6, finding 3: a real vocab asset.
                (comp_dir / "tokenizer.json").write_text("{}")
            if config_filename != "scheduler_config.json" and not config_filename.startswith(
                "tokenizer"
            ):
                (comp_dir / "model.safetensors").write_bytes(b"\x00")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            "a complete FLUX.1-shaped directory must never be reported as an "
            f"available FLUX.2 install; got {report}"
        )
        assert report.cause == DiscoveryCause.ABSENT

    def test_same_directory_is_correctly_accepted_for_the_model_it_actually_is(self, tmp_path):
        """Control case proving the rejection above is identity-based, not a
        blanket regression: the identical directory, requested as what it
        actually is (flux1-schnell), must still report available."""
        model_dir = tmp_path / "actually-schnell"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )
        for name, config_filename in (
            ("scheduler", "scheduler_config.json"),
            ("text_encoder", "config.json"),
            ("text_encoder_2", "config.json"),
            ("tokenizer", "tokenizer_config.json"),
            ("tokenizer_2", "tokenizer_config.json"),
            ("transformer", "config.json"),
            ("vae", "config.json"),
        ):
            comp_dir = model_dir / name
            comp_dir.mkdir()
            (comp_dir / config_filename).write_text("{}")
            if config_filename.startswith("tokenizer"):
                # gate-remediation round 6, finding 3: a real vocab asset.
                (comp_dir / "tokenizer.json").write_text("{}")
            if config_filename != "scheduler_config.json" and not config_filename.startswith(
                "tokenizer"
            ):
                (comp_dir / "model.safetensors").write_bytes(b"\x00")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None


class TestIncompleteCustomDirDoesNotShadowCompleteCache:
    """Gate-remediation C2: `_find_available_root` returned the *first*
    directory carrying the marker file regardless of completeness, so a
    partial custom directory could shadow a perfectly good HuggingFace
    cache. Verified before this fix: an incomplete custom dir + a complete
    HF cache reported `available=False, INCOMPLETE`, offering a multi-
    gigabyte re-download while a working copy sat in the cache -- violating
    spec.md sec 13 ("Existing installations continue to work"). Fixtures are
    literal and independent of tests/model_fixtures.py.
    """

    @staticmethod
    def _write_flux2_literal(root: Path, *, omit_vae_weights: bool) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        (root / "scheduler").mkdir()
        (root / "scheduler" / "scheduler_config.json").write_text("{}")
        (root / "text_encoder").mkdir()
        (root / "text_encoder" / "config.json").write_text("{}")
        (root / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (root / "tokenizer").mkdir()
        (root / "tokenizer" / "tokenizer_config.json").write_text("{}")
        (root / "tokenizer" / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (root / "tokenizer" / "tokenizer.json").write_text("{}")
        (root / "transformer").mkdir()
        (root / "transformer" / "config.json").write_text("{}")
        (root / "transformer" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")
        (root / "vae").mkdir()
        (root / "vae" / "config.json").write_text("{}")
        if not omit_vae_weights:
            (root / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")

    def test_incomplete_custom_dir_falls_back_to_complete_cache(self, tmp_path):
        custom_dir = tmp_path / "partial-custom-dir"
        self._write_flux2_literal(custom_dir, omit_vae_weights=True)

        cache_root = tmp_path / "hf_cache_snapshot"
        self._write_flux2_literal(cache_root, omit_vae_weights=False)

        with patch(
            "textbrush.model.weights.try_to_load_from_cache",
            return_value=str(cache_root / "model_index.json"),
        ):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[custom_dir])

        assert report.available is True, (
            "a complete HF cache install must be found even when a "
            f"higher-priority custom dir is incomplete; got {report}"
        )
        assert report.cause is None

    def test_complete_custom_dir_still_wins_over_cache(self, tmp_path):
        """Precedence preserved: when the custom directory IS complete, the
        cache must not be consulted at all (mirrors
        TestIsFluxAvailableCustomDirs.test_custom_dirs_checked_before_hf_cache
        for this new literal-fixture pattern)."""
        custom_dir = tmp_path / "complete-custom-dir"
        self._write_flux2_literal(custom_dir, omit_vae_weights=False)

        with patch("textbrush.model.weights.try_to_load_from_cache") as mock_try_load:
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[custom_dir])

        assert report.available is True, report.detail
        mock_try_load.assert_not_called()


class TestShardedWeightCompleteness:
    """Gate-remediation C3: a component's weight check accepted any single
    matching `.safetensors` file, so one shard of a multi-shard component
    (an interrupted download) reported available. Verified before this fix:
    a transformer with only shard 1 of 3 present reported
    `available=True, cause=None`. Diffusers writes a
    `*.safetensors.index.json` whose `weight_map` names every shard file;
    completeness now means every referenced shard resolves to a real file
    (broken HF-cache symlinks -- a blob that never finished downloading --
    do not count as present, since `Path.exists()` follows the symlink).
    Written literally, independent of tests/model_fixtures.py.
    """

    @staticmethod
    def _index_and_non_transformer_components(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        (root / "scheduler").mkdir()
        (root / "scheduler" / "scheduler_config.json").write_text("{}")
        (root / "text_encoder").mkdir()
        (root / "text_encoder" / "config.json").write_text("{}")
        (root / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (root / "tokenizer").mkdir()
        (root / "tokenizer" / "tokenizer_config.json").write_text("{}")
        (root / "tokenizer" / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (root / "tokenizer" / "tokenizer.json").write_text("{}")
        (root / "vae").mkdir()
        (root / "vae" / "config.json").write_text("{}")
        (root / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")

    def test_one_of_three_shards_reports_incomplete(self, tmp_path):
        model_dir = tmp_path / "flux2-one-shard-of-three"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        (transformer_dir / "diffusion_pytorch_model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "metadata": {"total_size": 3},
                    "weight_map": {
                        "layer.0.weight": "diffusion_pytorch_model-00001-of-00003.safetensors",
                        "layer.1.weight": "diffusion_pytorch_model-00002-of-00003.safetensors",
                        "layer.2.weight": "diffusion_pytorch_model-00003-of-00003.safetensors",
                    },
                }
            )
        )
        # Only shard 1 of 3 actually downloaded.
        (transformer_dir / "diffusion_pytorch_model-00001-of-00003.safetensors").write_bytes(
            b"\x00"
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"one shard of three present must not report available; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail

    def test_all_shards_present_reports_available(self, tmp_path):
        """Control case: the same sharded layout, fully downloaded, must
        still report available -- proving the check verifies completeness
        rather than merely rejecting anything sharded."""
        model_dir = tmp_path / "flux2-all-shards"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        (transformer_dir / "diffusion_pytorch_model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "metadata": {"total_size": 3},
                    "weight_map": {
                        "layer.0.weight": "diffusion_pytorch_model-00001-of-00003.safetensors",
                        "layer.1.weight": "diffusion_pytorch_model-00002-of-00003.safetensors",
                        "layer.2.weight": "diffusion_pytorch_model-00003-of-00003.safetensors",
                    },
                }
            )
        )
        for shard in ("00001-of-00003", "00002-of-00003", "00003-of-00003"):
            (transformer_dir / f"diffusion_pytorch_model-{shard}.safetensors").write_bytes(b"\x00")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_broken_symlink_shard_does_not_count_as_present(self, tmp_path):
        """HF-cache layouts store blobs as symlinks; a blob that never
        finished downloading leaves a symlink whose target is missing. That
        must not count as a present shard."""
        model_dir = tmp_path / "flux2-broken-symlink-shard"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        (transformer_dir / "diffusion_pytorch_model.safetensors.index.json").write_text(
            json.dumps(
                {
                    "metadata": {"total_size": 2},
                    "weight_map": {
                        "layer.0.weight": "diffusion_pytorch_model-00001-of-00002.safetensors",
                        "layer.1.weight": "diffusion_pytorch_model-00002-of-00002.safetensors",
                    },
                }
            )
        )
        (transformer_dir / "diffusion_pytorch_model-00001-of-00002.safetensors").write_bytes(
            b"\x00"
        )
        broken_target = tmp_path / "blobs" / "missing-blob"
        (transformer_dir / "diffusion_pytorch_model-00002-of-00002.safetensors").symlink_to(
            broken_target
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail


class TestShardedWeightCompletenessWithoutIndexFile:
    """Gate-remediation round 5, finding 2 (BLOCKER): C3 was only fixed in
    the branch where a `*.safetensors.index.json` file exists.
    `_missing_shards` returned None when no index file was present, and the
    caller fell back to "at least one resolving glob match" -- the ORIGINAL
    C3 defect, still reachable. Verified before this fix:

        transformer/, 1 of 3 shards, NO index.json   -> available=True   (bug)
        transformer/, 1 of 3 shards, WITH index.json -> INCOMPLETE (fixed)

    `snapshot_download` fetches shard files and the index file concurrently
    with no ordering guarantee between them, so "one shard written, index
    not yet written" is an ordinary interruption state, not a hypothetical.

    Gate-remediation round 6, finding 2 (P2) supersedes this class's original
    "all shards present, no index -> available" control case (see
    `test_all_shards_present_with_no_index_file_reports_incomplete` below,
    renamed and re-asserted from its round-5 form). That prior assertion
    described the OLD, WRONG behavior: verified against the installed
    diffusers 0.36.0 (`diffusers/models/modeling_utils.py`, via
    `model_loading_utils._fetch_index_file`), a local load only treats a
    component as sharded (`is_sharded = True`) when the actual
    `*.safetensors.index.json` file exists on disk -- diffusers never
    reconstructs the shard-to-parameter mapping from shard filenames alone.
    Without that file, the loader looks for a single plain
    `diffusion_pytorch_model.safetensors` instead, which does not exist for
    a sharded checkpoint, and the load fails outright regardless of how many
    correctly-named shard files are present. So "every shard present, no
    index file" is genuinely unloadable and must report INCOMPLETE, not
    available; the round-5 fixture that asserted the opposite was itself
    under-specified (it proved the shard-COUNT heuristic worked without
    verifying the checkpoint could actually be loaded that way).
    """

    @staticmethod
    def _index_and_non_transformer_components(root: Path) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "Flux2KleinPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "Qwen3ForCausalLM"],
                    "tokenizer": ["transformers", "Qwen2TokenizerFast"],
                    "transformer": ["diffusers", "Flux2Transformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKLFlux2"],
                }
            )
        )
        (root / "scheduler").mkdir()
        (root / "scheduler" / "scheduler_config.json").write_text("{}")
        (root / "text_encoder").mkdir()
        (root / "text_encoder" / "config.json").write_text("{}")
        (root / "text_encoder" / "model.safetensors").write_bytes(b"\x00")
        (root / "tokenizer").mkdir()
        (root / "tokenizer" / "tokenizer_config.json").write_text("{}")
        (root / "tokenizer" / "chat_template.jinja").write_text("{{ messages[0]['content'] }}")
        # gate-remediation round 6, finding 3: a tokenizer needs a real vocab asset.
        (root / "tokenizer" / "tokenizer.json").write_text("{}")
        (root / "vae").mkdir()
        (root / "vae" / "config.json").write_text("{}")
        (root / "vae" / "diffusion_pytorch_model.safetensors").write_bytes(b"\x00")

    def test_one_of_three_shards_with_no_index_file_reports_incomplete(self, tmp_path):
        """The exact reachable case the finding names literally: one shard
        of three, no index.json at all."""
        model_dir = tmp_path / "flux2-one-shard-no-index"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        # NO diffusion_pytorch_model.safetensors.index.json written -- the
        # ordinary "index not yet written" interruption state.
        (transformer_dir / "diffusion_pytorch_model-00001-of-00003.safetensors").write_bytes(
            b"\x00"
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"one shard of three, with no index.json, must not report available; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail

    def test_all_shards_present_with_no_index_file_reports_incomplete(self, tmp_path):
        """Gate-remediation round 6, finding 2: renamed and re-asserted from
        this class's original round-5 "control case", which claimed the
        opposite (available=True) on the theory that verifying shard COUNT
        from filenames alone was sufficient. It wasn't: diffusers requires
        the actual weight-index file to load a sharded checkpoint at all
        (verified against installed diffusers 0.36.0 -- see this class's
        docstring), so every shard being present without that file is still
        genuinely unloadable, hence INCOMPLETE. The still-valid "not a
        blanket sharded-is-always-incomplete regression" control lives in
        `TestShardedWeightCompleteness.test_all_shards_present_reports_available`,
        which is the same state but WITH the index file present."""
        model_dir = tmp_path / "flux2-all-shards-no-index"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        for shard in ("00001-of-00003", "00002-of-00003", "00003-of-00003"):
            (transformer_dir / f"diffusion_pytorch_model-{shard}.safetensors").write_bytes(b"\x00")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"every shard present but no weight-index file must not report "
            f"available -- diffusers cannot load it without that file; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail

    def test_malformed_index_json_reports_incomplete_not_weak_fallback(self, tmp_path):
        """A malformed/unparseable index.json must be treated as INCOMPLETE
        directly, not silently downgraded to the weaker no-index fallback
        check (which a single present shard would then satisfy)."""
        model_dir = tmp_path / "flux2-malformed-index"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        (transformer_dir / "diffusion_pytorch_model.safetensors.index.json").write_text(
            "not valid json {{{"
        )
        # Only one shard present -- if the malformed index were treated as
        # "no index" (fallback), this single glob match would (wrongly)
        # satisfy the weak "at least one match" check.
        (transformer_dir / "diffusion_pytorch_model-00001-of-00003.safetensors").write_bytes(
            b"\x00"
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail

    def test_second_index_file_shards_are_not_ignored(self, tmp_path):
        """Gate-remediation round 5, finding 2: a prior version of
        `_missing_shards` read `index_files[0]` arbitrarily. A component
        directory carrying more than one `*.safetensors.index.json` must
        have every index file's required shards honoured -- not just
        whichever one glob() happens to list first."""
        model_dir = tmp_path / "flux2-two-index-files"
        self._index_and_non_transformer_components(model_dir)

        transformer_dir = model_dir / "transformer"
        transformer_dir.mkdir()
        (transformer_dir / "config.json").write_text("{}")
        (transformer_dir / "diffusion_pytorch_model.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"layer.0.weight": "shard-00001-of-00002.safetensors"}})
        )
        (transformer_dir / "extra.safetensors.index.json").write_text(
            json.dumps({"weight_map": {"layer.1.weight": "shard-00002-of-00002.safetensors"}})
        )
        (transformer_dir / "shard-00001-of-00002.safetensors").write_bytes(b"\x00")
        # shard-00002-of-00002.safetensors, required only by the SECOND
        # index file, is deliberately absent.

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False, (
            f"a shard required only by a second index file must not be ignored; got {report}"
        )
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "transformer" in report.detail


class TestSchnellKontextClassNameDisambiguation:
    """Gate-remediation round 5, finding 4: FLUX.1 schnell and FLUX.1
    Kontext-dev both use `_STANDARD_FLUX_COMPONENTS`, so their
    `identity_components` name sets are identical -- the component-name
    subset check (signal 2 of `_directory_identity_matches`) holds in BOTH
    directions and cannot tell them apart. Verified before this fix: a
    complete Kontext-shaped directory reported available for a schnell
    request, and a complete schnell-shaped directory reported available for
    a Kontext request. `_class_name` (signal 1) now resolves both
    directions using only schnell's and klein's independently-pinned
    `expected_class_name` values -- Kontext's own value is deliberately left
    unpinned (see registry.py) and is not needed for either direction.
    """

    @staticmethod
    def _write_seven_component_dir(root: Path, class_name: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": class_name,
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )
        for name, config_filename in (
            ("scheduler", "scheduler_config.json"),
            ("text_encoder", "config.json"),
            ("text_encoder_2", "config.json"),
            ("tokenizer", "tokenizer_config.json"),
            ("tokenizer_2", "tokenizer_config.json"),
            ("transformer", "config.json"),
            ("vae", "config.json"),
        ):
            comp_dir = root / name
            comp_dir.mkdir()
            (comp_dir / config_filename).write_text("{}")
            if config_filename.startswith("tokenizer"):
                # gate-remediation round 6, finding 3: a real vocab asset.
                (comp_dir / "tokenizer.json").write_text("{}")
            if config_filename != "scheduler_config.json" and not config_filename.startswith(
                "tokenizer"
            ):
                (comp_dir / "model.safetensors").write_bytes(b"\x00")

    def test_kontext_shaped_dir_rejected_for_schnell_request(self, tmp_path):
        """Direction 1: schnell's OWN `expected_class_name` ("FluxPipeline")
        is pinned, so a directory whose declared class name differs from it
        is rejected outright -- regardless of what that foreign value
        actually is, and without needing Kontext's real value at all."""
        model_dir = tmp_path / "actually-kontext"
        self._write_seven_component_dir(model_dir, class_name="FluxKontextPipeline")

        # Both schnell and Kontext are gated; a token must be configured so
        # the ABSENT-vs-CREDENTIALS_MISSING branch doesn't mask the identity
        # rejection this test targets.
        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
                report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

        assert report.available is False, (
            "a differently-classed 7-component directory must never satisfy a "
            f"schnell request merely because the component names match; got {report}"
        )
        assert report.cause == DiscoveryCause.ABSENT

    def test_schnell_shaped_dir_rejected_for_kontext_request(self, tmp_path):
        """Direction 2 (the harder one): Kontext's `expected_class_name` is
        UNPINNED (None), so this relies entirely on the reverse-map signal --
        the directory's declared "FluxPipeline" is recognised as schnell's
        confirmed identity, and schnell != the requested spec (Kontext)."""
        model_dir = tmp_path / "actually-schnell"
        self._write_seven_component_dir(model_dir, class_name="FluxPipeline")

        with patch.dict(os.environ, {"HF_TOKEN": "hf_test_token"}):
            with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
                report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])

        assert report.available is False, (
            "a real schnell directory must never satisfy a Kontext request merely "
            f"because the component names match; got {report}"
        )
        assert report.cause == DiscoveryCause.ABSENT

    def test_matching_class_name_is_still_accepted_for_its_own_request(self, tmp_path):
        """Control case: a directory correctly declaring its own model's
        pinned class name must still be accepted for that model's request --
        proving the two rejections above are identity-based, not a blanket
        regression."""
        model_dir = tmp_path / "actually-schnell"
        self._write_seven_component_dir(model_dir, class_name="FluxPipeline")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_SCHNELL, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None

    def test_unrecognised_class_name_is_ambiguous_not_a_mismatch(self, tmp_path):
        """A class name that is neither the requested spec's own pinned
        value nor any other model's pinned value must not be rejected by
        the class-name signal at all -- it falls through to the component-
        name check (signal 2), which still correctly accepts a genuine
        Kontext installation (whose real, unverified class name this
        registry does not pin) for a Kontext request."""
        model_dir = tmp_path / "actually-kontext"
        self._write_seven_component_dir(model_dir, class_name="FluxKontextPipeline")

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[model_dir])

        assert report.available is True, report.detail
        assert report.cause is None


class TestIdentityMismatchDetailIsAccurate:
    """Gate-remediation round 5, finding 5: an identity mismatch previously
    reported the ABSENT detail "no local marker found" -- false, since a
    marker WAS found, parsed, and deliberately skipped. A user who
    configured `model.directories` was told nothing was there, with no hint
    the mismatch was the reason."""

    def test_absent_detail_names_the_rejected_path_and_the_reason(self, tmp_path):
        model_dir = tmp_path / "actually-schnell"
        model_dir.mkdir()
        (model_dir / "model_index.json").write_text(
            json.dumps(
                {
                    "_class_name": "FluxPipeline",
                    "scheduler": ["diffusers", "FlowMatchEulerDiscreteScheduler"],
                    "text_encoder": ["transformers", "CLIPTextModel"],
                    "text_encoder_2": ["transformers", "T5EncoderModel"],
                    "tokenizer": ["transformers", "CLIPTokenizer"],
                    "tokenizer_2": ["transformers", "T5TokenizerFast"],
                    "transformer": ["diffusers", "FluxTransformer2DModel"],
                    "vae": ["diffusers", "AutoencoderKL"],
                }
            )
        )

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(FLUX2_KLEIN_4B, custom_dirs=[model_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.ABSENT
        assert str(model_dir) in report.detail, report.detail
        assert "no local marker found" not in report.detail, (
            "a marker WAS found and parsed -- the detail must not claim otherwise"
        )

    def test_genuinely_absent_still_reports_the_generic_detail(self, tmp_path):
        """Control case: when nothing at all is found, the original generic
        detail is unchanged."""
        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            report = check_model_availability(
                FLUX2_KLEIN_4B, custom_dirs=[tmp_path / "does-not-exist"]
            )

        assert report.available is False
        assert report.cause == DiscoveryCause.ABSENT
        assert report.detail == "no local marker found"


class TestMostInformativeIncompleteRootSelection:
    """Gate-remediation round 5, finding 6: `_find_available_root`'s
    docstring claimed its no-complete-candidate fallback returned "the most
    informative root", but it actually returned the first candidate in
    priority order. Verified before this fix: a custom dir missing seven
    components, ahead of a cache install missing only one, reported all
    seven missing -- the cache's near-complete state was strictly more
    actionable and was never surfaced."""

    def test_reports_the_candidate_missing_the_fewest_components(self, tmp_path):
        custom_dir = tmp_path / "custom-missing-everything"
        write_index_only(custom_dir, FLUX1_KONTEXT_DEV)  # index only: all 7 missing

        cache_dir = tmp_path / "cache-missing-one"
        write_complete_snapshot(cache_dir, FLUX1_KONTEXT_DEV)
        remove_component_weights(cache_dir, FLUX1_KONTEXT_DEV, "vae")

        with patch(
            "textbrush.model.weights.try_to_load_from_cache",
            return_value=str(cache_dir / "model_index.json"),
        ):
            report = check_model_availability(FLUX1_KONTEXT_DEV, custom_dirs=[custom_dir])

        assert report.available is False
        assert report.cause == DiscoveryCause.INCOMPLETE
        assert "vae" in report.detail
        # The 7-missing custom dir must not be what's reported.
        assert "scheduler" not in report.detail


class TestResolveModelSelectionExplicit:
    """AC-MODEL-5: an explicit model selection is never silently replaced."""

    def test_explicit_selection_available_is_honored_verbatim(self):
        result = resolve_model_selection(
            selected_id=FLUX1_KONTEXT_DEV,
            reference_count=1,
            availability=lambda slug: AvailabilityReport(True, None),
        )
        assert result == ModelResolution(model_id=FLUX1_KONTEXT_DEV, blocked=False)

    def test_explicit_selection_unavailable_blocks_rather_than_substitutes(self):
        """VQ-S2-008: an explicitly requested unavailable model blocks with a
        clear, actionable reason -- it is never silently replaced."""

        def availability(slug: str) -> AvailabilityReport:
            return AvailabilityReport(False, DiscoveryCause.ABSENT)

        result = resolve_model_selection(
            selected_id=FLUX1_KONTEXT_DEV, reference_count=1, availability=availability
        )

        assert result.blocked is True
        assert result.model_id is None
        assert result.required_model == FLUX1_KONTEXT_DEV
        assert result.cause == DiscoveryCause.ABSENT
        assert result.reason

    def test_explicit_selection_unavailable_never_falls_through_to_another_model(self):
        """Even when a *different* model is fully available, an explicit but
        unavailable selection must not be silently swapped for it."""

        def availability(slug: str) -> AvailabilityReport:
            if slug == FLUX1_KONTEXT_DEV:
                return AvailabilityReport(False, DiscoveryCause.ABSENT)
            return AvailabilityReport(True, None)

        result = resolve_model_selection(
            selected_id=FLUX1_KONTEXT_DEV, reference_count=1, availability=availability
        )

        assert result.blocked is True
        assert result.model_id is None
        assert result.model_id != FLUX2_KLEIN_4B

    def test_explicit_schnell_selection_unavailable_blocks_with_cause_attached(self):
        """Gate-remediation pin (finding F1): resolve_model_selection with an
        explicit selected_id=flux1-schnell and schnell unavailable blocks
        (model_id=None), same as any other explicit selection -- it does NOT
        fall back to the implicit reference_count==0 default (which always
        resolves to schnell regardless of availability). This asymmetry
        between the explicit and implicit paths is intentional and pre-
        existing (spec.md sec 7.3 item 3 vs sec 7.2): the implicit default
        defers the availability question entirely to the load/download flow,
        while an explicit selection surfaces it immediately via `cause`.
        This test pins today's explicit-path contract (blocked=True,
        cause attached, required_model=selected_id) so a future composition
        root (S8/S9) that decides how to route each cause is changing that
        decision deliberately, not discovering an untested regression.
        """
        result = resolve_model_selection(
            selected_id=FLUX1_SCHNELL,
            reference_count=0,
            availability=lambda slug: AvailabilityReport(False, DiscoveryCause.ABSENT),
        )

        assert result.blocked is True
        assert result.model_id is None
        assert result.required_model == FLUX1_SCHNELL
        assert result.cause == DiscoveryCause.ABSENT
        assert result.reason

    def test_unknown_selected_id_raises(self):
        with pytest.raises(ValueError):
            resolve_model_selection(
                selected_id="not-a-model",
                reference_count=0,
                availability=lambda slug: AvailabilityReport(True, None),
            )

    def test_reference_count_out_of_range_raises(self):
        with pytest.raises(ValueError):
            resolve_model_selection(
                selected_id=None,
                reference_count=5,
                availability=lambda slug: AvailabilityReport(True, None),
            )
        with pytest.raises(ValueError):
            resolve_model_selection(
                selected_id=None,
                reference_count=-1,
                availability=lambda slug: AvailabilityReport(True, None),
            )


class TestDefaultResolutionPermutationTable:
    """spec.md sec 7.3, full permutation table: 0 / 1 / 2-4 references x
    FLUX.2 available/unavailable x Kontext available/unavailable."""

    @staticmethod
    def _availability(flux2_available: bool, kontext_available: bool):
        def lookup(slug: str) -> AvailabilityReport:
            if slug == FLUX2_KLEIN_4B:
                return AvailabilityReport(
                    flux2_available, None if flux2_available else DiscoveryCause.ABSENT
                )
            if slug == FLUX1_KONTEXT_DEV:
                return AvailabilityReport(
                    kontext_available, None if kontext_available else DiscoveryCause.ABSENT
                )
            return AvailabilityReport(True, None)

        return lookup

    @pytest.mark.parametrize(
        "reference_count,flux2_available,kontext_available,expected_model,expected_blocked",
        [
            # 0 references: always schnell, regardless of editing-model availability.
            (0, True, True, FLUX1_SCHNELL, False),
            (0, True, False, FLUX1_SCHNELL, False),
            (0, False, True, FLUX1_SCHNELL, False),
            (0, False, False, FLUX1_SCHNELL, False),
            # 1 reference: FLUX.2 preferred, Kontext fallback, else block.
            (1, True, True, FLUX2_KLEIN_4B, False),
            (1, True, False, FLUX2_KLEIN_4B, False),
            (1, False, True, FLUX1_KONTEXT_DEV, False),
            (1, False, False, None, True),
            # 2-4 references: FLUX.2 only, never Kontext, never schnell.
            (2, True, True, FLUX2_KLEIN_4B, False),
            (2, True, False, FLUX2_KLEIN_4B, False),
            (2, False, True, None, True),
            (2, False, False, None, True),
            (3, True, False, FLUX2_KLEIN_4B, False),
            (4, False, False, None, True),
        ],
    )
    def test_permutation_table(
        self,
        reference_count,
        flux2_available,
        kontext_available,
        expected_model,
        expected_blocked,
    ):
        result = resolve_model_selection(
            selected_id=None,
            reference_count=reference_count,
            availability=self._availability(flux2_available, kontext_available),
        )

        assert result.blocked is expected_blocked
        assert result.model_id == expected_model
        if expected_blocked:
            assert result.reason
            assert result.required_model is not None

    @pytest.mark.parametrize("reference_count", [2, 3, 4])
    def test_two_to_four_references_never_fall_back_to_flux1(self, reference_count):
        result = resolve_model_selection(
            selected_id=None,
            reference_count=reference_count,
            availability=lambda slug: AvailabilityReport(True, None),
        )
        assert result.model_id == FLUX2_KLEIN_4B
        assert result.model_id not in (FLUX1_SCHNELL, FLUX1_KONTEXT_DEV)


class TestResolutionRunsOnlyAtLaunch:
    """AC-MODEL-5 / VQ-S2-005: resolution must run only at launch, never
    mid-session. resolve_model_selection is a pure, IO-free function of its
    arguments with no cached/memoized state of its own -- the "only at
    launch" guarantee is therefore a call-site discipline the composition
    roots (S8, S9) must uphold by invoking it exactly once per launch; this
    test proves the function itself has no hidden state that could either
    violate that discipline on its own or prevent a caller from upholding it
    correctly (e.g. no memoization that would make a second call at a later
    point in the session silently return a stale first answer instead of a
    fresh, correct one if a caller ever needed to recompute for a *new*
    launch).
    """

    def test_pure_function_reflects_only_its_current_arguments(self):
        call_log: list[str] = []

        def availability(slug: str) -> AvailabilityReport:
            call_log.append(slug)
            return AvailabilityReport(True, None)

        first = resolve_model_selection(
            selected_id=None, reference_count=1, availability=availability
        )
        second = resolve_model_selection(
            selected_id=None, reference_count=2, availability=availability
        )

        # No caching across calls: the function consults `availability` fresh
        # every time (call_log grows), and reflects each call's own arguments
        # rather than the previous call's result.
        assert first.model_id == FLUX2_KLEIN_4B
        assert second.model_id == FLUX2_KLEIN_4B
        assert len(call_log) >= 2

    def test_adding_a_reference_mid_session_would_require_a_fresh_call_to_change_anything(self):
        """Nothing in this module observes a reference being added; only a
        caller explicitly invoking resolve_model_selection again would ever
        get a different answer. Composition roots must not do so mid-session
        (spec.md sec 5.1): the desktop never auto-switches the selected model
        in response to a reference change."""
        one_ref = resolve_model_selection(
            selected_id=None,
            reference_count=1,
            availability=lambda slug: AvailabilityReport(slug == FLUX1_KONTEXT_DEV, None)
            if slug == FLUX1_KONTEXT_DEV
            else AvailabilityReport(False, DiscoveryCause.ABSENT),
        )
        assert one_ref.model_id == FLUX1_KONTEXT_DEV

        # A caller that (incorrectly) re-ran resolution after a reference was
        # added mid-session would get a different model -- which is exactly
        # why S8/S9 must call this once, at launch, and never again.
        two_refs = resolve_model_selection(
            selected_id=None,
            reference_count=2,
            availability=lambda slug: AvailabilityReport(slug == FLUX1_KONTEXT_DEV, None)
            if slug == FLUX1_KONTEXT_DEV
            else AvailabilityReport(False, DiscoveryCause.ABSENT),
        )
        assert two_refs.blocked is True
        assert two_refs.model_id != one_ref.model_id


class TestIsModelAvailableConvenienceWrapper:
    def test_matches_check_model_availability(self, tmp_path):
        model_dir = tmp_path / "complete"
        write_complete_snapshot(model_dir, FLUX1_SCHNELL)

        with patch("textbrush.model.weights.try_to_load_from_cache", return_value=None):
            assert is_model_available(FLUX1_SCHNELL, custom_dirs=[model_dir]) is True
            assert is_model_available(FLUX1_SCHNELL, custom_dirs=[tmp_path / "missing"]) is False

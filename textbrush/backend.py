"""Backend coordinator for textbrush image generation.

Orchestrates model loading, generation workflow, and image buffer management.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.config import Config
from textbrush.inference.base import DEFAULT_DIMENSIONS, GenerationOptions
from textbrush.inference.factory import create_engine
from textbrush.model.registry import (
    FLUX1_SCHNELL,
    DiscoveryCause,
)
from textbrush.model.weights import check_model_availability
from textbrush.references import (
    NormalizedReference,
    ReferenceImageError,
    normalize,
)
from textbrush.validation import (
    EDITING_PRESETS,
    editing_preset_dimensions,
    is_editing_model,
    preset_for_dimensions,
    resolve_preset,
    validate_selection,
)
from textbrush.worker import GenerationWorker, OnGenerationStartCallback

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Engine-swap exceptions (T06 design decision)
# ---------------------------------------------------------------------------


class ModelUnavailableError(Exception):
    """The requested model is not available on disk; engine is untouched.

    Distinct from `ModelSwitchError`: here the candidate engine was
    never created because `check_model_availability` reported a non-
    available result before the unload+load dance began. `cause` is
    the `DiscoveryCause` returned by the availability check; callers
    in `ipc` and `cli` map these to user-facing messages."""

    def __init__(
        self,
        cause: DiscoveryCause,
        detail: str = "",
        model_id: str | None = None,
    ) -> None:
        self.cause = cause
        self.detail = detail
        self.model_id = model_id
        super().__init__(
            f"model {model_id!r} unavailable: cause={cause.value if cause else 'unknown'}, "
            f"detail={detail!r}"
        )


class AcceptanceError(OSError):
    """A batch stopped after zero or more committed saves; retry the same images."""

    def __init__(self, cause: Exception, completed_paths: list[Path]):
        self.completed_paths = completed_paths
        super().__init__(str(cause))


class ModelSwitchError(Exception):
    """The engine swap failed and was recovered by reloading the previous
    engine. The backend's active model is unchanged; the new engine's
    load() was the failing step."""

    def __init__(
        self,
        message: str,
        *,
        recoverable: bool = True,
        original_cause: BaseException | None = None,
        model_id: str | None = None,
    ) -> None:
        self.recoverable = recoverable
        self.original_cause = original_cause
        self.model_id = model_id
        super().__init__(message)


class ConfigurationRejectedError(ModelSwitchError, ValueError):
    """`apply_configuration` refused the request before touching any state.

    Raised when the caller named an identifier that does not exist: a
    model id that is not a registry slug, or an editing preset that is
    not in `validation.EDITING_PRESETS`. Both used to escape as a bare
    `ValueError` from `is_editing_model` / `editing_preset_dimensions`
    BEFORE `validate_selection` could turn them into a verdict, so the
    IPC handler -- which recognises only the typed rejections -- reported
    a generic loop error and emitted no `config_ack`, leaving the UI's
    idea of the configuration permanently out of step with the backend's
    (gate-remediation round 7, finding 5).

    Base classes, both deliberate:
      - `ModelSwitchError`: it puts this rejection in the set the IPC
        handler already catches and answers with a rollback
        `config_ack`. The shared promise is the one that matters here --
        the request was refused and the backend's acknowledged state is
        byte-for-byte unchanged. Unlike a plain `ModelSwitchError`
        nothing was unloaded or reloaded: the refusal happens before the
        engine is touched at all.
      - `ValueError`: an unknown identifier was a `ValueError` before
        this class existed, and the CLI's `except (ValueError,
        RuntimeError)` paths still classify it as a bad argument.

    `recoverable` is always True: there is nothing to recover from.
    """

    def __init__(self, message: str, *, model_id: str | None = None) -> None:
        super().__init__(message, recoverable=True, model_id=model_id)


class FatalModelError(Exception):
    """Engine release or recovery failed; the session cannot safely resume."""

    def __init__(
        self,
        message: str,
        *,
        model_id: str | None = None,
        original_cause: BaseException | None = None,
        recovery_cause: BaseException | None = None,
    ) -> None:
        self.model_id = model_id
        self.original_cause = original_cause
        self.recovery_cause = recovery_cause
        super().__init__(message)


# ---------------------------------------------------------------------------
# ConfigurationAck: the return value of apply_configuration
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConfigurationAck:
    """Outcome of one `apply_configuration` call.

    Attributes:
        model_id: short slug of the model whose configuration has been
            acknowledged (e.g. ``"flux2-klein-4b"``).
        reference_count: number of references held after this
            acknowledgement (0..4).
        reference_paths: paths as the caller supplied them, in order;
            used by the IPC handler for acknowledgement reporting only.
            Decoded pixel data lives in `backend.references` (the
            NormalizedReference tuple), not here.
        preset: editing preset the backend applied (None for text mode).
        compatible: True iff `validate_selection` accepts the (model,
            count, preset) tuple; False means resume is refused (T07).
        incompatibility_reason: human-readable reason when
            `compatible` is False; None otherwise.
        required_model: a different model that would have made the
            selection compatible (per `validate_selection.required_model`);
            None when no recommendation is meaningful.
    """

    model_id: str
    reference_count: int
    reference_paths: tuple[str, ...]
    preset: str | None
    compatible: bool
    incompatibility_reason: str | None = None
    required_model: str | None = None


class TextbrushBackend:
    """High-level coordinator for inference backend.

    Manages model lifecycle, worker threads, and image buffer.
    """

    def __init__(self, config: Config):
        """Initialize backend with configuration.

        CONTRACT:
          Inputs:
            - config: Config object with inference and model settings
              (the composition root sets `config.model.selected_id`
              from the model resolver before constructing the backend;
              S7 keeps that contract -- `config.model.selected_id` may
              be None, in which case the backend falls back to
              `FLUX1_SCHNELL` for the initial engine selection).

          Outputs: none (constructs instance)

          Invariants:
            - Engine is created but not loaded
            - Buffer is created with config.model.buffer_size
            - Worker is not started
            - Backend holds the acknowledged model id, references
              tuple, preset, per-mode preset memory used by
              `apply_configuration`, and the snapshot directory the
              active engine was loaded from (None until `initialize`)

          Properties:
            - Lazy loading: model is not loaded until initialize()
            - Configuration immutable: config is stored, not modified
        """
        self.config = config
        self.model_id: str = config.model.selected_id or FLUX1_SCHNELL
        self.engine = create_engine(config.inference.backend, self.model_id)
        self.references: tuple[NormalizedReference, ...] = ()
        self.reference_paths: tuple[str, ...] = ()
        self.reference_ids: tuple[str, ...] = ()
        self.preset: str | None = None
        # Per-mode preset memory (spec §5.5): the last acknowledged
        # preset for an editing-capable model, used to restore the
        # editing preset when the user switches back from text mode.
        # None at construction (no editing acknowledgement yet).
        self._last_editing_preset: str | None = None
        # The local snapshot directory discovery validated for the
        # currently-active engine (`AvailabilityReport.root`), or None
        # when the weights resolve by repo id out of the HuggingFace
        # cache. Kept so the engine swap can reload the PREVIOUS engine
        # from the root that was validated for the PREVIOUS model when
        # the incoming load fails.
        self._engine_root: Path | None = None
        # The acknowledged output canvas in pixels, or None before the
        # first acknowledgement. References are decoded against it, so a
        # change to it must re-decode them exactly as a model change does
        # -- `preset` alone no longer answers "did the canvas move?" now
        # that callers may name any size directly.
        self.canvas: tuple[int, int] | None = None
        self.buffer = ImageBuffer(max_size=config.model.buffer_size)
        self._worker: GenerationWorker | None = None

    def initialize(self) -> None:
        """Load model - call before starting generation.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After initialize(), engine.is_loaded() = True
            - Model is ready for inference
            - The engine is loaded from the snapshot directory discovery
              validated for `self.model_id`, so a model present only in a
              `config.model.directories` entry loads from there instead of
              being looked up by repo id in the HuggingFace cache, where
              it is not (gate-remediation round 7, finding 3).

          Properties:
            - Blocking: waits for model to load completely
            - Idempotent: safe to call multiple times (engine handles it)
            - Must be called before start_generation()
            - Does NOT enforce availability. Discovery is consulted here
              only to LOCATE the weights; the authoritative availability
              gate is `resolve_model_selection` in the composition roots,
              which runs before the backend is constructed. A discovery
              pass that reports unavailable, or fails outright, therefore
              falls back to `root=None` -- exactly the behavior this
              method had before it consulted discovery at all -- rather
              than turning a loadable model into a launch failure.

          Algorithm:
            1. Resolve the validated snapshot root for the active model
            2. Call engine.load_from(root)
        """
        self._engine_root = self._discover_root(self.model_id)
        self.engine.load_from(self._engine_root)

    def _discover_root(self, slug: str) -> Path | None:
        """Best-effort lookup of the validated snapshot directory for `slug`.

        Returns `AvailabilityReport.root` when discovery reports the model
        available, else None. Never raises: a discovery failure degrades to
        "resolve by repo id", the pre-existing load behavior. Used only by
        `initialize`, where availability is not this method's to enforce;
        `_swap_engine` consults discovery directly because there the
        availability verdict IS load-bearing.
        """
        try:
            report = self._check_availability(slug)
        except Exception:
            logger.exception("model discovery failed for %r; loading by repo id", slug)
            return None
        return report.root if report.available else None

    # ------------------------------------------------------------------
    # T06: acknowledged-configuration seam
    # ------------------------------------------------------------------

    def _check_availability(self, slug: str):
        """Thin wrapper over `textbrush.model.weights.check_model_availability`
        bound to the configured custom directories; exists so tests can
        patch it (the production call passes `config.model.directories`)."""
        return check_model_availability(slug, custom_dirs=self.config.model.directories)

    def apply_configuration(
        self,
        *,
        model_id: str | None = None,
        reference_paths: list[str] | tuple[str, ...] | None = None,
        preset: str | None = None,
        width: int | None = None,
        height: int | None = None,
    ) -> ConfigurationAck:
        """Acknowledge a (model, references, preset) configuration.

        This is the single authoritative seam for configuration changes
        (spec §5.4 / AC-STATE-3, AC-STATE-4). Decodes reference paths
        exactly once at acknowledgement (AC-PROCESS-3), swaps the
        engine on a model change with reload-on-failure (AC-RECOVERY-1),
        records the per-mode preset so switching modes preserves the
        user's last editing choice (spec §5.5), and -- when a worker
        is alive -- commits the new snapshot to it via `update_config`
        and clears the buffer (any in-flight result is from a now-
        superseded configuration).

        The method never mutates state until every precondition passes.
        A failure in any step (engine swap, decode, model-side guards)
        leaves `self.*` untouched and propagates the exception
        (the caller reports the message; T07 maps each to a wire event).

        CONTRACT:
          Inputs:
            - model_id: optional short slug (None keeps the current model)
            - reference_paths: optional list/tuple of paths (None keeps
              the currently decoded references; an empty list explicitly
              drops them)
            - preset: optional editing preset identifier (None keeps the
              current preset, with mode-switch preset semantics per
              spec §5.5)
            - width/height: optional explicit output canvas in pixels.
              When BOTH are given they are authoritative: they size the
              canvas directly and `preset` is re-derived from them (the
              identifier naming exactly those dimensions, or None when
              no preset names them). This is the path the desktop UI
              takes -- it offers one output-size group to every model,
              so most of its sizes have no preset name at all. When
              either is None the preset decides, as before.

          Outputs:
            - ConfigurationAck with the acknowledged state.

          Raises:
            - ConfigurationRejectedError: `model_id` is not a registry
              slug, or the resolved preset is not a known editing preset.
              Raised before anything is touched, and typed so the IPC
              handler answers with a rollback `config_ack` instead of a
              generic loop error (gate-remediation round 7, finding 5).
            - ModelUnavailableError / ModelSwitchError / FatalModelError:
              from the engine swap; see `_swap_engine`.
            - ReferenceImageError: a reference path failed to decode.

          Invariants:
            - Requires either no worker, or a settled (paused) worker:
              a configuration change while generating is refused.
            - A rejected configuration restores the previous engine; failed
              restoration is fatal even if the candidate can still load.
            - On success, `references` holds the decoded tuple and
              `reference_ids` is the same length in the same order
              (session-local uuids).
            - Reference retention, by branch:
              * explicit `reference_paths` -> decoded from those paths;
              * target model is text-only -> dropped (a text engine
                reports `reference_input_size() is None` and MUST be
                given an empty tuple);
              * model or canvas changed -> the held PATHS are re-decoded,
                because the engine's reference canvas moved with them;
              * otherwise (the no-change case) -> the already-decoded
                references, their paths AND their ids are retained
                verbatim. Nothing that determines the canvas changed, so
                a re-decode could only reproduce the same pixels, and
                dropping them (the pre-round-7 behavior) contradicted
                both the documented "None keeps the currently decoded
                references" and idempotency: re-acknowledging the active
                model wiped the references and answered `compatible=False`.

          Properties:
            - Non-blocking (the only IO is one `normalize()` per
              reference path, which is fast, and none at all in the
              retain branch).
            - Idempotent on identical input: re-acknowledging the active
              configuration is a no-op down to the reference ids.
        """
        # a. Precondition: no worker, or a settled worker.
        if self._worker is not None and not self._worker.is_settled():
            raise RuntimeError("configuration changes require a settled, paused worker")

        # b. Resolve candidate model + preset. Spec §5.5: when the
        # caller did not give an explicit preset and the mode changed,
        # drop the old-mode preset (text mode -> None, editing mode ->
        # the last editing preset we acknowledged, or the configured
        # default if we never acknowledged one).
        candidate_model = model_id or self.model_id
        target_is_editing = self._require_known_model(candidate_model)
        explicit_preset = preset if preset is not None else self.preset
        mode_changed = target_is_editing != self._require_known_model(self.model_id)
        if preset is None and mode_changed:
            # No explicit preset from caller and mode switch in progress:
            # drop the old-mode preset (spec §5.5).
            candidate_preset: str | None = self._last_editing_preset if target_is_editing else None
            if candidate_preset is None and target_is_editing:
                candidate_preset = self.config.editing.default_preset
        elif preset is not None:
            candidate_preset = preset
        else:
            # No preset, no mode change -- keep the current preset
            # (None for text mode, last editing preset for editing mode).
            candidate_preset = explicit_preset

        # Explicit dimensions win over the preset resolution above: the
        # caller named the canvas in pixels, so the preset becomes a
        # label for it rather than its source (and is None for a size no
        # preset names). Resolved before the unknown-preset guard so a
        # caller that sends dimensions can never be rejected over a
        # preset identifier it did not choose.
        if width is not None and height is not None:
            candidate_preset = preset_for_dimensions(width, height)

        # Reject an unknown preset identifier here, while nothing has been
        # touched yet, and through the same typed channel as the other
        # rejections. `_canvas_dimensions` would otherwise discover it
        # below via `editing_preset_dimensions`, as a bare ValueError,
        # after a model swap may already have happened.
        if candidate_preset is not None and candidate_preset not in EDITING_PRESETS:
            raise ConfigurationRejectedError(
                f"unknown editing preset: {candidate_preset}", model_id=candidate_model
            )

        # The canvas every later step uses: references are decoded to it,
        # the worker generates at it, and the commit remembers it.
        if width is not None and height is not None:
            candidate_canvas = (width, height)
        else:
            candidate_canvas = self._canvas_dimensions(candidate_preset)

        # c. Engine swap (if the model changed).
        swapped = candidate_model != self.model_id
        if swapped:
            self._swap_engine(candidate_model)

        # d. Decide what the acknowledged references are. The candidate
        # engine decides whether references are valid at all: a text-only
        # engine (schnell) reports None for `reference_input_size` and
        # MUST receive an empty tuple. `retained_references` is not None
        # only in the no-change branch, where the already-decoded
        # references stay as they are (see the contract above).
        retained_references: tuple[NormalizedReference, ...] | None = None
        if reference_paths is not None:
            paths_to_decode = tuple(reference_paths)
        elif not target_is_editing:
            # Mode switch to text: the held references are invalid
            # against a text engine, so they are dropped entirely.
            paths_to_decode = ()
        elif candidate_model != self.model_id and self.reference_paths:
            # New model: its reference canvas may differ, so re-decode.
            paths_to_decode = self.reference_paths
        elif candidate_canvas != self.canvas and self.reference_paths:
            # New canvas: references are normalised to it, so re-decode.
            # Compared on the dimensions rather than on the preset
            # identifier: a caller sending explicit pixel sizes moves the
            # canvas between two sizes that both have preset None, and a
            # preset-identity test would miss exactly that change.
            paths_to_decode = self.reference_paths
        else:
            # Nothing that determines the reference canvas changed.
            # Keep what is already decoded -- including the ids, so
            # re-acknowledging the active configuration is a true no-op.
            paths_to_decode = self.reference_paths
            retained_references = self.references

        canvas = self.engine.reference_input_size(*candidate_canvas)
        if retained_references is not None:
            decoded_references = retained_references
            reference_ids = self.reference_ids
        elif paths_to_decode:
            if canvas is None:
                error = ValueError(
                    f"engine {candidate_model!r} accepts no references but "
                    f"{len(paths_to_decode)} path(s) were supplied"
                )
                if swapped:
                    self._restore_engine_after_rejection(error)
                raise error
            try:
                decoded_references = tuple(
                    normalize(Path(p), target_size=canvas) for p in paths_to_decode
                )
            except ReferenceImageError as exc:
                # Decode failed; revert any swap we did so the
                # backend's `engine` is left untouched (AC-RECOVERY-1,
                # and the "state untouched on failure" invariant of
                # apply_configuration).
                if swapped:
                    self._restore_engine_after_rejection(exc)
                raise
            reference_ids = tuple(
                f"{uuid.uuid4().hex}:{position}" for position in range(len(decoded_references))
            )
        else:
            decoded_references = ()
            reference_ids = ()

        # e. Validate the (model, count, preset) tuple.
        verdict = validate_selection(candidate_model, len(decoded_references), candidate_preset)

        # f. Commit state. The commit happens unconditionally once the
        # preconditions (swap, decode, verdict) succeed; an
        # incompatible verdict is still acknowledged (T07 will refuse
        # resume against the post-acknowledge state).
        self.model_id = candidate_model
        self.references = decoded_references
        self.reference_paths = paths_to_decode
        self.reference_ids = reference_ids
        self.preset = candidate_preset
        self.canvas = candidate_canvas
        # Per-mode preset memory (spec §5.5) is the memory of the last
        # EDITING preset. A preset acknowledged against a text-only model
        # is not one: the verdict below reports it incompatible but the
        # commit still happens, and remembering it here would hand the
        # user a preset they never chose the next time they switch to an
        # editing model (gate-remediation round 7, finding 6).
        if candidate_preset is not None and target_is_editing:
            self._last_editing_preset = candidate_preset

        if self._worker is not None:
            canvas_width, canvas_height = candidate_canvas
            sampling = dict(self.engine.default_sampling_settings())
            options = GenerationOptions(
                seed=None,
                width=canvas_width,
                height=canvas_height,
                aspect_ratio="custom",
                references=decoded_references,
                model_id=candidate_model,
                sampling_settings=sampling,
            )
            self._worker.engine = self.engine
            self._worker.update_config(
                self._worker.prompt,
                options,
                model_id=candidate_model,
                reference_ids=self.reference_ids,
            )

        # g. Return the ack.
        return ConfigurationAck(
            model_id=candidate_model,
            reference_count=len(decoded_references),
            reference_paths=paths_to_decode,
            preset=candidate_preset,
            compatible=verdict.valid,
            incompatibility_reason=verdict.reason,
            required_model=verdict.required_model,
        )

    def _require_known_model(self, slug: str) -> bool:
        """Return whether `slug` is editing-capable, rejecting unknown slugs.

        `is_editing_model` raises a bare `ValueError` for a slug that is
        not in the registry. That escapes `apply_configuration` before
        `validate_selection` can turn it into an "unknown model" verdict,
        and the IPC handler does not recognise it, so the UI never gets
        its rollback ack. Translating it here keeps every rejection from
        `apply_configuration` inside the typed, recoverable channel.
        """
        try:
            return is_editing_model(slug)
        except ValueError as exc:
            raise ConfigurationRejectedError(f"unknown model: {slug}", model_id=slug) from exc

    def _swap_engine(self, candidate_model: str) -> None:
        """Swap a settled worker's engine with at most one resident pipeline.

        Check availability before unloading. A partially loaded candidate must be
        released before restoring the previous engine from its validated root.
        Unload failures are fatal: continuing could load two full models at once.
        """
        # (1) availability check. Nothing is unloaded until this passes.
        report = self._check_availability(candidate_model)
        if not report.available:
            raise ModelUnavailableError(
                cause=report.cause or DiscoveryCause.UNKNOWN,
                detail=report.detail,
                model_id=candidate_model,
            )

        # Capture the previous engine and the root it was loaded from so
        # we can reload it if the incoming load fails. Constructing the
        # incoming engine is cheap (no weights are touched) and can still
        # raise for an unknown backend, so it happens before the unload.
        previous_engine = self.engine
        previous_root = self._engine_root
        next_engine = create_engine(self.config.inference.backend, candidate_model)

        try:
            previous_engine.unload()
        except Exception as exc:
            raise FatalModelError(
                "previous engine could not be released; candidate was not loaded",
                model_id=candidate_model,
                original_cause=exc,
            ) from exc

        # (3) load the new engine.
        try:
            next_engine.load_from(report.root)
        except Exception as exc:
            try:
                next_engine.unload()
            except Exception as cleanup_exc:
                raise FatalModelError(
                    "failed candidate could not be released; recovery was not attempted",
                    model_id=candidate_model,
                    original_cause=exc,
                    recovery_cause=cleanup_exc,
                ) from cleanup_exc
            # Exception tracebacks can themselves retain a pipeline in load()/to()
            # locals. Preserve the exception chain and stack locations, but release
            # inactive frame locals before allocating the previous model again.
            import traceback

            pending = [exc]
            seen = set()
            while pending:
                cause = pending.pop()
                if id(cause) in seen:
                    continue
                seen.add(id(cause))
                if cause.__traceback__ is not None:
                    traceback.clear_frames(cause.__traceback__)
                pending.extend(
                    linked for linked in (cause.__cause__, cause.__context__) if linked is not None
                )
            try:
                previous_engine.load_from(previous_root)
            except Exception as recovery_exc:
                raise FatalModelError(
                    f"engine swap to {candidate_model!r} failed AND recovery "
                    f"of the previous engine failed; backend is in an "
                    f"indeterminate state",
                    model_id=candidate_model,
                    original_cause=exc,
                    recovery_cause=recovery_exc,
                ) from recovery_exc
            raise ModelSwitchError(
                f"engine swap to {candidate_model!r} failed; previous engine reloaded successfully",
                recoverable=True,
                original_cause=exc,
                model_id=candidate_model,
            ) from exc

        self.engine = next_engine
        self._engine_root = report.root
        if self._worker is not None:
            self._worker.engine = next_engine

    def _restore_engine_after_rejection(self, cause: Exception) -> None:
        """A failed rollback is fatal even if its inner swap recovers the candidate."""
        try:
            self._swap_engine(self.model_id)
        except Exception as recovery_exc:
            raise FatalModelError(
                "configuration was rejected and the previous model could not be restored",
                model_id=self.model_id,
                original_cause=cause,
                recovery_cause=recovery_exc,
            ) from recovery_exc

    def _canvas_dimensions(self, preset: str | None) -> tuple[int, int]:
        """Return the (width, height) the engine canvas will use for the
        next generation.

        Editing preset wins when supplied -- which is the only case that
        matters, because this value exists to size the reference canvas
        and only editing models take references. With no preset it falls
        back to the worker's acknowledged dimensions, per axis, and then
        to `DEFAULT_DIMENSIONS`; the worker's axes are `None` whenever
        the caller left them to an aspect ratio, and that ratio is the
        engine's to resolve, not this method's.
        """
        if preset is not None:
            return editing_preset_dimensions(preset)
        default_width, default_height = DEFAULT_DIMENSIONS
        if self._worker is not None:
            opts = self._worker.options
            return (
                opts.width if opts.width is not None else default_width,
                opts.height if opts.height is not None else default_height,
            )
        return DEFAULT_DIMENSIONS

    def start_generation(
        self,
        prompt: str,
        seed: int | None = None,
        aspect_ratio: str = "custom",
        width: int | None = None,
        height: int | None = None,
        on_generation_start: OnGenerationStartCallback | None = None,
        start_paused: bool = False,
    ) -> None:
        """Begin background image generation.

        T06 contract: the caller is expected to have acknowledged the
        desired (model, references, preset) configuration via
        `apply_configuration` first; this method reads the
        acknowledged state off `self` rather than re-decoding paths or
        re-resolving a preset. The `model_id`/`references`/`preset`
        keyword arguments that 47f6151 added are removed: decode lives
        in the backend (`apply_configuration`), not in the call site.

        CONTRACT:
          Inputs:
            - prompt: non-empty string, text description
            - seed: optional integer seed (None = auto-generate)
            - aspect_ratio: aspect-ratio string. Default is "custom",
              which means "the explicit width/height own the canvas".
              Any of `cli.py`'s `SUPPORTED_RATIOS` keys is accepted for
              any model.
            - width: optional int, image width in pixels. Explicit
              dimensions win over the resolved preset for every model;
              the preset sizes the canvas only when neither axis was
              given. None means "not specified" and is forwarded to the
              engine as None, so `aspect_ratio` decides the axis.
            - height: optional int, image height in pixels (same).
            - on_generation_start: optional callback invoked before each
              generation with (seed, queue_position) args.
            - start_paused: if True, worker starts in paused state.

          Outputs: none (modifies internal state)

          Invariants:
            - Engine must be loaded (initialize() called) before start_generation()
            - Validates the acknowledged state; raises `ValueError` if
              the (model, references, preset) tuple is incompatible.
            - Editing-capable models take width/height from the preset
              only when the caller named neither axis.
            - For text mode this method applies NO dimension default of
              its own. `aspect_ratio` is meaningful only for an axis the
              caller left unspecified, so substituting a number here
              would silently disable it (round 7, finding 2). The engine
              owns both the ratio table and the final fallback.
            - Creates GenerationWorker with prompt and options
            - Starts worker thread

          Properties:
            - Non-blocking: returns immediately, generation runs in background
            - Prerequisites: initialize() must be called first (raises RuntimeError if not)
            - Worker lifecycle: creates new worker (any existing worker should be stopped first)
            - Buffer reset: resets shutdown state to allow new images to be delivered

          Algorithm:
            1. Check engine.is_loaded(), raise RuntimeError if not loaded
            2. Resolve active preset via `resolve_preset` (explicit else
               default-else-None, per the `validation` module).
            3. If the caller named neither axis and the preset is
               editing-capable: width/height from the preset; otherwise
               the caller's arguments verbatim (None included -- the
               engine resolves those from aspect_ratio).
            4. Validate the resolved tuple; raise ValueError if invalid.
            5. Build GenerationOptions with references, model_id, and
               sampling_settings from the engine's defaults.
            6. Create the GenerationWorker and start it.
        """
        if not self.engine.is_loaded():
            raise RuntimeError("Engine not loaded. Call initialize() before start_generation().")

        self.buffer.reset_shutdown()

        active_model = self.model_id
        active_preset = resolve_preset(
            active_model, self.preset, self.config.editing.default_preset
        )
        if (
            width is None
            and height is None
            and active_preset is not None
            and is_editing_model(active_model)
        ):
            # The preset sizes the canvas only when the caller named
            # neither axis. Explicit dimensions win: the desktop UI sends
            # them for every output size it offers, and most of those
            # sizes have no preset name at all, so letting the resolved
            # default preset overwrite them would silently collapse the
            # whole output-size group onto `editing.default_preset`.
            width, height = editing_preset_dimensions(active_preset)
        if width is not None and height is not None:
            # Remember the canvas this generation runs at, so a later
            # `apply_configuration` can tell whether the canvas moved.
            self.canvas = (width, height)
        # Otherwise width/height travel to the engine exactly as the
        # caller gave them, INCLUDING None. Defaulting them here (which
        # this method did, to 1024x1024) made `--aspect-ratio` a no-op:
        # the engine can only honour a ratio for an axis nobody asked
        # for, and a defaulted axis is indistinguishable from a
        # requested one once it carries a number.

        verdict = validate_selection(active_model, len(self.references), active_preset)
        if not verdict.valid:
            raise ValueError(verdict.reason)

        sampling = dict(self.engine.default_sampling_settings())
        options = GenerationOptions(
            seed=seed,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            references=self.references,
            model_id=active_model,
            sampling_settings=sampling,
        )
        self._worker = GenerationWorker(
            engine=self.engine,
            buffer=self.buffer,
            prompt=prompt,
            options=options,
            on_generation_start=on_generation_start,
            start_paused=start_paused,
        )
        self._worker.start()

    def get_next_image(self, timeout: float | None = 30.0) -> BufferedImage | None:
        """Get next generated image (blocks if buffer empty).

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely, default 30.0)

          Outputs:
            - BufferedImage if available, None if buffer shutdown or timeout

          Invariants:
            - Removes and returns oldest image from buffer
            - Blocks until image available, buffer shutdown, or timeout

          Properties:
            - Blocking: waits for image if buffer empty
            - FIFO: returns images in generation order
            - Thread-safe: can be called while worker is generating
            - Timeout protection: returns None if timeout expires

          Algorithm:
            1. Call buffer.get(timeout) and return result
        """
        return self.buffer.get(timeout=timeout)

    def skip_current(self, timeout: float | None = 30.0) -> BufferedImage | None:
        """Skip current image and get next.

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely, default 30.0)

          Outputs:
            - BufferedImage (next image), or None if buffer shutdown or timeout

          Invariants:
            - Discards current image (calls buffer.get())
            - Returns next image in queue

          Properties:
            - Blocking: waits for image if buffer empty
            - Discard: current image is removed and not saved
            - Timeout protection: returns None if timeout expires

          Algorithm:
            1. Delegate to get_next_image(timeout) for implementation
        """
        return self.get_next_image(timeout=timeout)

    def accept_current(self, output_path: Path | None = None) -> Path:
        """Save current image and return path.

        CONTRACT:
          Inputs:
            - output_path: optional Path to save image (None = auto-generate)

          Outputs:
            - Path: absolute path where image was saved

          Invariants:
            - Current image (from buffer.peek()) is saved to disk
            - Image remains in buffer (use get_next_image() to advance)
            - If output_path is None, generates path based on seed or timestamp
            - PNG metadata includes aspect ratio and dimensions; JPEG has no custom metadata

          Properties:
            - Non-blocking: returns after save completes
            - Side effect: writes file to disk
            - Error: raises RuntimeError if no image to accept

          Algorithm:
            1. Peek at current image
            2. If no image: raise RuntimeError
            3. If output_path is None: generate path using _generate_output_path()
            4. Commit output without overwriting an existing destination
            5. Return output_path
        """
        current = self.buffer.peek()
        if not current:
            raise RuntimeError("No image to accept")

        if output_path is None:
            output_path = self._generate_output_path()

        if current.temp_path is None and current.accepted_path is None:
            self.save_to_preview(current)
        return self.accept_from_preview(current, output_path)

    def _save_with_metadata(self, buffered_image: BufferedImage, output_path: Path) -> None:
        """Save PNG metadata or encode JPEG without custom metadata.

        CONTRACT:
          Inputs:
            - buffered_image: BufferedImage with image and metadata
            - output_path: Path where image should be saved

          Outputs: none (writes file to disk)

          Invariants:
            - Image is saved to output_path
            - PNG metadata includes: aspect_ratio, width, height, prompt, model, seed
            - If generated_width/generated_height present, also stored in PNG tEXt chunks
            - Width/Height in metadata = image.size (final dimensions)
            - GeneratedWidth/GeneratedHeight = dimensions passed to model (if present)
            - `BufferedImage.model_id` and `BufferedImage.reference_ids`
              are session-local provenance (T05) and MUST NEVER be written
              into the output file. AC-META-1: the PNG key set is closed
              and contains no reference paths, ids, hashes, or bytes.

          Properties:
            - PNG: metadata stored in tEXt chunks
            - JPEG: no custom metadata is written
            - Backward compatibility: GeneratedWidth/GeneratedHeight optional
            - If generated dimensions absent (None), Width/Height fields sufficient

          Algorithm:
            1. Extract image, width, height from buffered_image
            2. Determine format from output_path extension
            3. If PNG:
               a. Create PngInfo object
               b. Add standard metadata: AspectRatio, Width, Height, Prompt, Model, Seed
               c. If generated_width is not None: add GeneratedWidth
               d. If generated_height is not None: add GeneratedHeight
               e. Save with pnginfo
            4. Else (JPEG, etc.):
               a. Save without custom metadata (piexif not available)
        """
        from PIL import PngImagePlugin

        image = buffered_image.image
        width, height = image.size
        aspect_ratio = buffered_image.aspect_ratio

        # Determine format from extension
        ext = output_path.suffix.lower()

        if ext == ".png":
            # Use PNG tEXt chunks for metadata
            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("AspectRatio", aspect_ratio)
            pnginfo.add_text("Width", str(width))
            pnginfo.add_text("Height", str(height))
            pnginfo.add_text("Prompt", buffered_image.prompt)
            pnginfo.add_text("Model", buffered_image.model_name)
            pnginfo.add_text("Seed", str(buffered_image.seed))
            if buffered_image.generated_width is not None:
                pnginfo.add_text("GeneratedWidth", str(buffered_image.generated_width))
            if buffered_image.generated_height is not None:
                pnginfo.add_text("GeneratedHeight", str(buffered_image.generated_height))
            image.save(output_path, pnginfo=pnginfo)
        elif ext in (".jpg", ".jpeg"):
            # JPEG has no custom metadata. It cannot encode alpha/palette modes.
            if image.mode in ("RGB", "L", "CMYK"):
                image.save(output_path, format="JPEG")
            else:
                with image.convert("RGB") as converted:
                    converted.save(output_path, format="JPEG")
        else:
            raise ValueError("Output filename must end in .png, .jpg, or .jpeg")

    def abort(self) -> None:
        """Stop generation and discard all images.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Worker is stopped
            - Buffer is cleared
            - After abort(), no generation is happening
            - All temp files from discarded images are deleted
            - `references` and `reference_ids` are released (AC-PROCESS-3):
              an aborted configuration's decoded data does not outlive
              the abort

          Properties:
            - Blocking without a deadline: waits for in-flight inference to finish
            - Cleanup: discards all buffered images and deletes temp files
            - Idempotent: safe to call multiple times

          Algorithm:
            1. If worker exists: stop worker and join until inference has returned
            2. Clear buffer (which calls cleanup() on all items)
            3. Release decoded references (set references, reference_ids,
               reference_paths to empty)
        """
        if self._worker:
            self._worker.stop()
            self._worker.join()
        self.buffer.clear()
        self.references = ()
        self.reference_paths = ()
        self.reference_ids = ()

    def shutdown(self) -> None:
        """Clean shutdown of backend.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - Worker is stopped
            - Buffer is cleared
            - Model is unloaded
            - `references` and `reference_ids` are released (AC-PROCESS-3)

          Properties:
            - Blocking: waits for worker and unload to complete
            - Cleanup: releases all resources
            - Idempotent: safe to call multiple times

          Algorithm:
            1. Call abort() to stop worker and clear buffer
            2. Call engine.unload()
        """
        self.abort()
        self.engine.unload()

    def check_worker_error(self) -> Exception | None:
        """Check if worker has encountered an error.

        CONTRACT:
          Inputs: none

          Outputs:
            - Exception if worker encountered an error, None otherwise

          Invariants:
            - Non-destructive: error state persists in worker
            - Returns None if no worker exists

          Properties:
            - Non-blocking: returns immediately
            - Delegates to worker.get_error()
            - Thread-safe: can be called while worker is running

          Algorithm:
            1. If worker exists: return worker.get_error()
            2. Otherwise: return None
        """
        if self._worker:
            return self._worker.get_error()
        return None

    def pause_generation(self, on_settled: Callable[[], None] | None = None) -> None:
        """Pause image generation without stopping.

        CONTRACT:
          Inputs:
            - on_settled: optional zero-arg callable invoked (on the
              worker thread) the first time the worker enters the
              pause-wait state after this pause. Forwarded to the
              worker via `set_on_settled`. Re-arms on the next resume.

          Outputs: none (modifies internal state)

          Invariants:
            - If worker exists: worker.pause() is called
            - Current generation completes before pause takes effect
            - is_paused() returns True after this call (if worker exists)

          Properties:
            - Non-blocking: returns immediately
            - Graceful: current generation completes
            - Idempotent: safe to call multiple times
            - No-op if no worker exists
        """
        if self._worker:
            self._worker.set_on_settled(on_settled)
            self._worker.pause()

    def resume_generation(self) -> None:
        """Resume paused image generation.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - If worker exists: worker.resume() is called
            - is_paused() returns False after this call (if worker exists)

          Properties:
            - Non-blocking: returns immediately
            - Idempotent: safe to call multiple times
            - No-op if no worker exists
        """
        if self._worker:
            self._worker.resume()

    def is_paused(self) -> bool:
        """Check if generation is paused.

        CONTRACT:
          Inputs: none

          Outputs:
            - True if paused, False if running or no worker

          Properties:
            - Thread-safe: can be called from any thread
            - Non-blocking: returns immediately
        """
        if self._worker:
            return self._worker.is_paused()
        return False

    def is_settled(self) -> bool:
        """True when the worker is paused AND settled (T05/T07).

        CONTRACT:
          Inputs: none

          Outputs:
            - True when there is no worker (no generation in flight)
              or when the worker has reached quiescence.
            - False when the worker exists but is not settled
              (running or paused-but-still-in-flight).

          Properties:
            - Thread-safe: can be called from any thread.
            - Non-blocking: returns immediately.
        """
        if self._worker is None:
            return True
        return self._worker.is_settled()

    def wait_settled(self, timeout: float | None) -> bool:
        """Block until the worker is paused and settled (T07 gate).

        CONTRACT:
          Inputs:
            - timeout: seconds to wait; None means wait indefinitely.

          Outputs:
            - True if the worker settled within the timeout (or there
              was no worker to wait for).
            - False on timeout.

          Properties:
            - Thread-safe: can be called from any thread.
            - Non-blocking when no worker exists.
        """
        if self._worker is None:
            return True
        return self._worker.wait_settled(timeout)

    def update_config(
        self,
        prompt: str,
        aspect_ratio: str = "custom",
        width: int | None = None,
        height: int | None = None,
        on_generation_start: OnGenerationStartCallback | None = None,
    ) -> None:
        """Update the prompt and (optionally) explicit dimensions without
        changing the acknowledged model, references, or preset.

        T06 contract: editing field changes go through
        `apply_configuration`; this method is a prompt-only update that
        leaves `self.model_id / self.references / self.preset / sampling
        settings` untouched. As a side effect, the worker's epoch bumps
        (any in-flight result is from a now-superseded configuration;
        see `GenerationWorker.update_config` and T05 step 2).

        CONTRACT:
          Inputs:
            - prompt: non-empty string, text description
            - aspect_ratio: aspect-ratio string (default "custom").
            - width: optional int, and authoritative when given --
              EXCEPT while references are held, where the acknowledged
              canvas wins (a canvas move needs the re-decode only
              `apply_configuration` does). With neither axis given, an
              editing-capable model falls back to its preset. None
              leaves the axis to aspect_ratio; no default is
              substituted here.
            - height: same as width.
            - on_generation_start: optional callback; if None the
              existing callback is kept.

          Outputs: none (modifies internal state)

          Invariants:
            - Worker must exist (start_generation() called before)
            - Worker thread continues running (not stopped/restarted)
            - Buffer is cleared (old images are stale)
            - Pause state is preserved
            - The acknowledged (model, references, preset) tuple is
              unchanged; this method does not re-run validation

          Properties:
            - Non-blocking: returns immediately
            - Thread-safe: can be called while worker is paused or running
            - Buffer cleared: existing images discarded since the prompt
              changed

          Algorithm:
            1. Resolve dimensions (acknowledged canvas wins while
               references are held; else explicit axes; else preset).
            2. Build a new GenerationOptions with the resolved
               dimensions and the existing acknowledged state.
            3. Call worker.update_config(prompt, options,
               on_generation_start), which atomically clears old buffered output.
        """
        if not self._worker:
            raise RuntimeError("No worker to update. Call start_generation() first.")

        active_preset = resolve_preset(
            self.model_id, self.preset, self.config.editing.default_preset
        )
        if self.references and self.canvas is not None:
            # References are decoded against the acknowledged canvas, and
            # the engine refuses an off-canvas reference rather than
            # resizing it. Moving the canvas therefore requires a
            # re-decode, which only `apply_configuration` performs -- so
            # this prompt-only path keeps the acknowledged canvas instead
            # of honouring dimensions that would fail at generate() time.
            resolved_width, resolved_height = self.canvas
        elif (
            width is None
            and height is None
            and active_preset is not None
            and is_editing_model(self.model_id)
        ):
            resolved_width, resolved_height = editing_preset_dimensions(active_preset)
        else:
            # Pass the caller's axes through untouched, None included, so
            # `aspect_ratio` still governs any axis nobody specified
            # (see `start_generation` for why defaulting here is wrong).
            resolved_width, resolved_height = width, height

        sampling = dict(self.engine.default_sampling_settings())
        options = GenerationOptions(
            seed=None,
            width=resolved_width,
            height=resolved_height,
            aspect_ratio=aspect_ratio,
            references=self.references,
            model_id=self.model_id,
            sampling_settings=sampling,
        )
        if resolved_width is not None and resolved_height is not None:
            # Record the canvas this path resolved, exactly as
            # `start_generation` and `apply_configuration` do. Leaving it
            # behind let `self.canvas` describe a canvas the worker had
            # already moved off, which a later rollback `config_ack`
            # would then report to the UI as the current output size.
            self.canvas = (resolved_width, resolved_height)
        self._worker.update_config(
            prompt,
            options,
            on_generation_start,
            model_id=self.model_id,
            reference_ids=self.reference_ids,
        )

    def _generate_output_path(self) -> Path:
        """Generate output path for accepted image.

        CONTRACT:
          Inputs: none

          Outputs:
            - Path: absolute path in config.output.directory with generated filename

          Invariants:
            - Path is in config.output.directory
            - Filename is a UUID
            - Extension matches config.output.format

          Properties:
            - Unique: generates unique UUID filename for each call
            - Deterministic structure: uses config settings

          Algorithm:
            1. Get config.output.directory
            2. Generate UUID filename
            3. Add extension from config.output.format
            4. Return Path object
        """
        import uuid

        output_dir = self.config.output.directory
        output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{uuid.uuid4()}.{self.config.output.format}"

        return output_dir / filename

    def _get_preview_dir(self) -> Path:
        """Get or create the preview directory for temporary images.

        CONTRACT:
          Inputs: none

          Outputs:
            - Path: absolute path to preview directory (.preview/ under output dir)

          Invariants:
            - Preview directory exists after call
            - Preview directory is a subdirectory of output directory

          Properties:
            - Creates directory if it doesn't exist
            - Deterministic: always returns same path for same config

          Algorithm:
            1. Get config.output.directory
            2. Create .preview subdirectory path
            3. Create directory if it doesn't exist
            4. Return path
        """
        preview_dir = self.config.output.directory / ".preview"
        preview_dir.mkdir(parents=True, exist_ok=True)
        return preview_dir

    def save_to_preview(self, buffered_image: BufferedImage) -> Path:
        """Save image to preview directory with metadata, set temp_path.

        CONTRACT:
          Inputs:
            - buffered_image: BufferedImage with image and metadata

          Outputs:
            - Path: absolute path to saved preview file

          Invariants:
            - Image is saved to preview directory with PNG metadata
            - buffered_image.temp_path is set to the saved file path
            - File can be moved to output on accept or deleted on skip

          Properties:
            - Side effect: writes file to disk
            - Side effect: modifies buffered_image.temp_path
            - Unique filename: uses UUID

          Algorithm:
            1. Get preview directory
            2. Generate unique UUID filename
            3. Save image with metadata using _save_with_metadata
            4. Set buffered_image.temp_path
            5. Return path
        """
        import uuid

        preview_dir = self._get_preview_dir()
        filename = f"{uuid.uuid4()}.png"
        preview_path = preview_dir / filename

        try:
            self._save_with_metadata(buffered_image, preview_path)
        except Exception:
            preview_path.unlink(missing_ok=True)
            raise
        buffered_image.temp_path = preview_path

        return preview_path

    @staticmethod
    def _publish_output(source: Path, destination: Path) -> None:
        """Publish complete bytes without overwriting an existing destination.

        A hard link avoids copying PNG previews on the same filesystem. On a
        filesystem without linking, exclusive creation still protects collisions;
        any failed copy removes only the file created by this operation.
        """
        import errno
        import os
        import shutil

        try:
            os.link(source, destination)
        except OSError as exc:
            if exc.errno not in (errno.EXDEV, errno.EPERM, errno.ENOTSUP):
                raise
            target = destination.open("xb")
            try:
                with target:
                    with source.open("rb") as original:
                        shutil.copyfileobj(original, target)
                    target.flush()
                    os.fsync(target.fileno())
            except BaseException:
                destination.unlink(missing_ok=True)
                raise

    def accept_from_preview(
        self,
        buffered_image: BufferedImage,
        output_path: Path | None = None,
        *,
        retain_preview: bool = False,
    ) -> Path:
        """Commit one image, retaining a checkpoint if preview cleanup fails.

        A completed save is never repeated on retry. Existing destinations are
        rejected. PNG preview bytes and metadata are preserved; JPEG is encoded
        in the destination directory before publication, without custom metadata.
        The preview survives any encoding/publication failure.
        """
        import tempfile

        if buffered_image.accepted_path is None:
            preview = buffered_image.temp_path
            if preview is None or not preview.exists():
                raise RuntimeError("No preview file to accept")
            destination = (output_path or self._generate_output_path()).absolute()
            if destination.suffix.lower() not in (".png", ".jpg", ".jpeg"):
                raise ValueError("Output filename must end in .png, .jpg, or .jpeg")
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.suffix.lower() == ".png":
                self._publish_output(preview, destination)
            else:
                with tempfile.NamedTemporaryFile(
                    prefix=".textbrush-",
                    suffix=destination.suffix,
                    dir=destination.parent,
                    delete=False,
                ) as temporary:
                    staging = Path(temporary.name)
                try:
                    self._save_with_metadata(buffered_image, staging)
                    self._publish_output(staging, destination)
                finally:
                    staging.unlink(missing_ok=True)
            # Commit before cleanup. A failed unlink must not cause a duplicate save.
            buffered_image.accepted_path = destination

        if not retain_preview and buffered_image.temp_path is not None:
            buffered_image.temp_path.unlink(missing_ok=True)
            buffered_image.temp_path = None
        return buffered_image.accepted_path

    def accept_all(
        self,
        images: list[BufferedImage],
        output_dir: Path | None = None,
        *,
        output_path: Path | None = None,
    ) -> list[Path]:
        """Save in delivery order, checkpointing every successful image.

        An explicit filename names the first output. Further images receive
        -002, -003, ... before its extension; existing files are never replaced.
        Retries reuse each image's committed path, including after partial failure.
        """
        import uuid

        if output_dir is not None and output_path is not None:
            raise ValueError("Specify an output directory or filename, not both")
        directory = output_dir if output_dir is not None else self.config.output.directory
        paths: list[Path] = []
        try:
            for position, image in enumerate(images, start=1):
                if output_path is None:
                    destination = directory / f"{uuid.uuid4()}.{self.config.output.format}"
                elif position == 1:
                    destination = output_path
                else:
                    destination = output_path.with_name(
                        f"{output_path.stem}-{position:03d}{output_path.suffix}"
                    )
                if image.planned_output_path is None:
                    image.planned_output_path = destination
                paths.append(
                    self.accept_from_preview(image, image.planned_output_path, retain_preview=True)
                )
            # Retain every preview across partial save failure so review/retry
            # still has usable images. Cleanup only after all output commits.
            for image in images:
                image.cleanup()
                image.temp_path = None
        except Exception as exc:
            completed = [image.accepted_path for image in images if image.accepted_path is not None]
            raise AcceptanceError(exc, completed) from exc
        return paths

    def delete_preview(self, buffered_image: BufferedImage) -> None:
        """Delete preview file for skipped image.

        CONTRACT:
          Inputs:
            - buffered_image: BufferedImage with temp_path set to preview file

          Outputs: none (deletes file)

          Invariants:
            - Preview file is deleted if it exists
            - buffered_image.temp_path is cleared (set to None)

          Properties:
            - Safe: no error if file doesn't exist
            - Idempotent: safe to call multiple times

          Algorithm:
            1. If temp_path is None: return
            2. Delete file if it exists
            3. Clear temp_path
        """
        if buffered_image.temp_path is not None:
            buffered_image.temp_path.unlink(missing_ok=True)
            buffered_image.temp_path = None

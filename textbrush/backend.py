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
from textbrush.inference.base import GenerationOptions
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
    editing_preset_dimensions,
    is_editing_model,
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


class FatalModelError(Exception):
    """Both the new engine's load() and the recovery load() of the
    previous engine failed. Backend is in an indeterminate state."""

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
              tuple, preset, and per-mode preset memory used by
              `apply_configuration`

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

          Properties:
            - Blocking: waits for model to load completely
            - Idempotent: safe to call multiple times (engine handles it)
            - Must be called before start_generation()

          Algorithm:
            1. Call engine.load()
        """
        self.engine.load()

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

          Outputs:
            - ConfigurationAck with the acknowledged state.

          Invariants:
            - Requires either no worker, or a settled (paused) worker:
              a configuration change while generating is refused.
            - At most one engine swap per call. Failure rolls back to the
              previous engine (recoverable) or surfaces a fatal error
              (when recovery also fails).
            - On success, `references` is the freshly decoded tuple;
              `reference_ids` is the same length in the same order
              (session-local uuids).

          Properties:
            - Non-blocking (the only IO is one `normalize()` per
              reference path, which is fast).
            - Idempotent on identical input.
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
        explicit_preset = preset if preset is not None else self.preset
        mode_changed = is_editing_model(candidate_model) != is_editing_model(self.model_id)
        if preset is None and mode_changed:
            # No explicit preset from caller and mode switch in progress:
            # drop the old-mode preset (spec §5.5).
            candidate_preset: str | None = (
                self._last_editing_preset if is_editing_model(candidate_model) else None
            )
            if candidate_preset is None and is_editing_model(candidate_model):
                candidate_preset = self.config.editing.default_preset
        elif preset is not None:
            candidate_preset = preset
        else:
            # No preset, no mode change -- keep the current preset
            # (None for text mode, last editing preset for editing mode).
            candidate_preset = explicit_preset

        # c. Engine swap (if the model changed).
        swapped = candidate_model != self.model_id
        if swapped:
            self._swap_engine(candidate_model)

        # d. Decode references. The candidate engine decides whether
        # references are valid: a text-only engine (schnell) reports
        # None for `reference_input_size` and MUST receive an empty
        # `paths_to_decode`. So when the new mode is text, we drop
        # the previously-held references entirely (they would be
        # invalid against a text engine); otherwise the same re-
        # normalization rules as before apply.
        target_is_editing = is_editing_model(candidate_model)
        if reference_paths is not None:
            paths_to_decode = tuple(reference_paths)
        elif not target_is_editing:
            paths_to_decode = ()
        elif candidate_model != self.model_id and self.reference_paths:
            paths_to_decode = self.reference_paths
        elif candidate_preset != self.preset and target_is_editing and self.reference_paths:
            paths_to_decode = self.reference_paths
        else:
            paths_to_decode = ()

        canvas = self.engine.reference_input_size(*self._canvas_dimensions(candidate_preset))
        if paths_to_decode:
            if canvas is None:
                # Revert any swap we did for this candidate.
                if swapped:
                    self._swap_engine(self.model_id)
                raise ValueError(
                    f"engine {self.model_id!r} accepts no references but "
                    f"{len(paths_to_decode)} path(s) were supplied"
                )
            try:
                decoded_references = tuple(
                    normalize(Path(p), target_size=canvas) for p in paths_to_decode
                )
            except ReferenceImageError:
                # Decode failed; revert any swap we did so the
                # backend's `engine` is left untouched (AC-RECOVERY-1,
                # and the "state untouched on failure" invariant of
                # apply_configuration).
                if swapped:
                    self._swap_engine(self.model_id)
                raise
        else:
            decoded_references = ()

        # e. Validate the (model, count, preset) tuple.
        verdict = validate_selection(candidate_model, len(decoded_references), candidate_preset)

        # f. Commit state. The commit happens unconditionally once the
        # preconditions (swap, decode, verdict) succeed; an
        # incompatible verdict is still acknowledged (T07 will refuse
        # resume against the post-acknowledge state).
        self.model_id = candidate_model
        self.references = decoded_references
        self.reference_paths = paths_to_decode
        self.reference_ids = tuple(
            f"{uuid.uuid4().hex}:{position}" for position in range(len(decoded_references))
        )
        self.preset = candidate_preset
        if candidate_preset is not None:
            self._last_editing_preset = candidate_preset

        if self._worker is not None:
            width, height = self._canvas_dimensions(candidate_preset)
            sampling = dict(self.engine.default_sampling_settings())
            options = GenerationOptions(
                seed=None,
                width=width,
                height=height,
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
            self.buffer.clear()

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

    def _swap_engine(self, candidate_model: str) -> None:
        """Atomically swap the loaded engine for `candidate_model`.

        Order per T06 design decision: (1) check availability; (2)
        unload the previous engine; (3) load the new engine; (4) on
        exception, attempt to reload the previous engine; if that
        succeeds raise `ModelSwitchError(recoverable=True, ...)`; if
        that also fails raise `FatalModelError`.

        On any failure path, `self.engine` and `self.model_id` remain
        unchanged: the swap is atomic from the caller's perspective.
        """
        # (1) availability check.
        report = self._check_availability(candidate_model)
        if not report.available:
            raise ModelUnavailableError(
                cause=report.cause or DiscoveryCause.UNKNOWN,
                detail=report.detail,
                model_id=candidate_model,
            )

        # (2) capture previous engine before unload so we can attempt
        # reload-on-failure.
        previous_engine = self.engine
        # (3) create and load the new engine.
        try:
            next_engine = create_engine(self.config.inference.backend, candidate_model)
            next_engine.load()
        except Exception as exc:
            # Attempt to reload the previous engine so the backend stays
            # usable.
            try:
                previous_engine.load()
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

        # Successful swap: unload the previous engine (it was already
        # not in use; we just held a reference).
        try:
            previous_engine.unload()
        except Exception:
            logger.exception("previous engine unload raised after successful swap")
        self.engine = next_engine

    def _canvas_dimensions(self, preset: str | None) -> tuple[int, int]:
        """Return the (width, height) the engine canvas will use for the
        next generation. Editing preset wins when supplied; otherwise
        the previously-acknowledged width/height fall back to the
        1024x1024 default used by `start_generation`'s no-args path."""
        if preset is not None:
            return editing_preset_dimensions(preset)
        if self._worker is not None:
            opts = self._worker.options
            return (opts.width, opts.height)
        return (1024, 1024)

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
            - aspect_ratio: aspect-ratio string. Default is "custom";
              editing models always use "custom" (the preset owns the
              dimensions). For text mode the caller can pass any of
              `cli.py`'s `SUPPORTED_RATIOS` keys.
            - width: optional int, image width in pixels (ignored for
              editing-capable models; for text mode overrides
              aspect_ratio).
            - height: optional int, image height in pixels (same).
            - on_generation_start: optional callback invoked before each
              generation with (seed, queue_position) args.
            - start_paused: if True, worker starts in paused state.

          Outputs: none (modifies internal state)

          Invariants:
            - Engine must be loaded (initialize() called) before start_generation()
            - Validates the acknowledged state; raises `ValueError` if
              the (model, references, preset) tuple is incompatible.
            - Editing-capable models force width/height from the preset.
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
            3. If the preset is editing-capable: width/height from the
               preset; otherwise from the caller's arguments or default
               1024x1024.
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
        if active_preset is not None and is_editing_model(active_model):
            width, height = editing_preset_dimensions(active_preset)
        else:
            width = width if width is not None else 1024
            height = height if height is not None else 1024

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
            - EXIF metadata includes aspect ratio and dimensions

          Properties:
            - Non-blocking: returns after save completes
            - Side effect: writes file to disk
            - Error: raises RuntimeError if no image to accept

          Algorithm:
            1. Peek at current image
            2. If no image: raise RuntimeError
            3. If output_path is None: generate path using _generate_output_path()
            4. Save image to output_path with EXIF metadata
            5. Return output_path
        """
        current = self.buffer.peek()
        if not current:
            raise RuntimeError("No image to accept")

        if output_path is None:
            output_path = self._generate_output_path()

        # Save with EXIF metadata
        self._save_with_metadata(current, output_path)
        return output_path

    def _save_with_metadata(self, buffered_image: BufferedImage, output_path: Path) -> None:
        """Save image with EXIF metadata including dimensions and generated dimensions.

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
            - JPEG: metadata stored in EXIF UserComment (TODO: not yet implemented)
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
        else:
            # For JPEG and other formats, save without custom metadata
            # (EXIF requires piexif which is not a dependency)
            image.save(output_path)
            # TODO: Add EXIF support for JPEG when piexif is added as dependency

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
            - Blocking: waits for worker to stop (with timeout)
            - Cleanup: discards all buffered images and deletes temp files
            - Idempotent: safe to call multiple times

          Algorithm:
            1. If worker exists: stop worker and join with timeout
            2. Clear buffer (which calls cleanup() on all items)
            3. Release decoded references (set references, reference_ids,
               reference_paths to empty)
        """
        if self._worker:
            self._worker.stop()
            self._worker.join(timeout=5.0)
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
            - aspect_ratio: aspect-ratio string (default "custom";
              editing models keep their preset dimensions regardless).
            - width: optional int; for editing-capable models the
              preset's width wins. For text mode this overrides
              aspect_ratio when supplied.
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
            1. Resolve dimensions (preset wins for editing models).
            2. Build a new GenerationOptions with the resolved
               dimensions and the existing acknowledged state.
            3. Call worker.update_config(prompt, options,
               on_generation_start).
            4. Clear the buffer.
        """
        if not self._worker:
            raise RuntimeError("No worker to update. Call start_generation() first.")

        active_preset = resolve_preset(
            self.model_id, self.preset, self.config.editing.default_preset
        )
        if active_preset is not None and is_editing_model(self.model_id):
            resolved_width, resolved_height = editing_preset_dimensions(active_preset)
        else:
            resolved_width = width if width is not None else 1024
            resolved_height = height if height is not None else 1024

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
        self._worker.update_config(
            prompt,
            options,
            on_generation_start,
            model_id=self.model_id,
            reference_ids=self.reference_ids,
        )
        self.buffer.clear()

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

        self._save_with_metadata(buffered_image, preview_path)
        buffered_image.temp_path = preview_path

        return preview_path

    def accept_from_preview(
        self, buffered_image: BufferedImage, output_path: Path | None = None
    ) -> Path:
        """Move image from preview to output directory.

        CONTRACT:
          Inputs:
            - buffered_image: BufferedImage with temp_path set to preview file
            - output_path: optional Path for final location (None = auto-generate)

          Outputs:
            - Path: absolute path where image was moved

          Invariants:
            - File is moved from preview to output directory
            - Preview file no longer exists after call
            - buffered_image.temp_path is cleared (set to None)

          Properties:
            - Atomic on same filesystem: uses rename
            - Falls back to copy+delete if rename fails
            - Raises RuntimeError if no temp_path set

          Algorithm:
            1. Check buffered_image.temp_path exists
            2. If output_path is None: generate path using _generate_output_path
            3. Move file from temp_path to output_path
            4. Clear buffered_image.temp_path
            5. Return output_path
        """
        import shutil

        if buffered_image.temp_path is None or not buffered_image.temp_path.exists():
            raise RuntimeError("No preview file to accept")

        if output_path is None:
            output_path = self._generate_output_path()

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Move file (rename or copy+delete)
        try:
            buffered_image.temp_path.rename(output_path)
        except OSError:
            # Cross-filesystem move: copy then delete
            shutil.copy2(buffered_image.temp_path, output_path)
            buffered_image.temp_path.unlink()

        buffered_image.temp_path = None
        return output_path

    def accept_all(self, images: list[BufferedImage], output_dir: Path | None = None) -> list[Path]:
        """Move all delivered images from preview to output directory.

        CONTRACT:
          Inputs:
            - images: collection of BufferedImage, each with temp_path set to preview file
            - output_dir: optional Path to output directory (None = use config.output.directory)

          Outputs:
            - collection of Path: absolute paths where images were moved, in same order as inputs

          Invariants:
            - len(output paths) equals len(images)
            - All preview files are moved to output directory
            - All preview files no longer exist after call
            - All buffered_image.temp_path fields are cleared (set to None)
            - Order preservation: output_paths[i] corresponds to images[i]

          Properties:
            - Batch operation: moves all images in sequence
            - Error handling: if any move fails, raises exception (partial state possible)
            - Auto-naming: generates unique filename for each image
            - Directory creation: ensures output directory exists

          Algorithm:
            1. Determine output_dir (use parameter or config.output.directory)
            2. Ensure output_dir exists
            3. Initialize empty output_paths list
            4. For each buffered_image in images (in order):
               a. Call accept_from_preview(buffered_image, output_path=None)
                  - This auto-generates unique path in output_dir
               b. Append returned path to output_paths
            5. Return output_paths list
        """
        if output_dir is None:
            output_dir = self.config.output.directory

        output_dir.mkdir(parents=True, exist_ok=True)

        output_paths: list[Path] = []
        for buffered_image in images:
            # accept_from_preview will auto-generate unique path
            path = self.accept_from_preview(buffered_image, output_path=None)
            output_paths.append(path)

        return output_paths

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

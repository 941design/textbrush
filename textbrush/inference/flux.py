"""FLUX.1 Schnell inference engine implementation."""

from __future__ import annotations

import logging
import random
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from textbrush.inference.base import GenerationOptions, GenerationResult, InferenceEngine
from textbrush.model.registry import FLUX1_KONTEXT_DEV, FLUX1_SCHNELL, FLUX2_KLEIN_4B, get_repo_id
from textbrush.model.weights import load_local_only

if TYPE_CHECKING:
    from textbrush.references import NormalizedReference

logger = logging.getLogger(__name__)


def round16(x: int) -> int:
    """Round `x` up to the next multiple of 16 (FLUX VAE multiple-of-16 floor).

    Single source of the rounding helper used by `FluxInferenceEngine.generate()`
    and `reference_input_size()`. Both axes of the generation canvas and both
    axes of the reference canvas must be multiples of 16 so the pipeline's
    internal `_auto_resize=False` / area-floor / `preprocess(..., resize_mode)`
    steps are provably no-ops (T04 design decision).
    """
    return ((x + 15) // 16) * 16


class FluxInferenceEngine(InferenceEngine):
    """FLUX.1 Schnell implementation of InferenceEngine.

    Uses the model registered under the "flux1-schnell" short slug
    (`textbrush.model.registry`) on HuggingFace.
    """

    # Sourced from the registry rather than hardcoded (S2-BC-1): the
    # short-slug <-> HuggingFace-repo-id mapping has exactly one owner,
    # `textbrush.model.registry`, and this class consumes it rather than
    # restating it.
    MODEL_ID = get_repo_id(FLUX1_SCHNELL)

    # Aspect ratio to dimensions mapping (default resolutions for each ratio)
    # Values must be divisible by 16 (FLUX model requirement)
    ASPECT_RATIOS = {
        "1:1": (1024, 1024),
        "16:9": (1280, 720),
        "3:1": (1536, 512),
        "4:1": (1600, 400),
        "4:5": (1024, 1280),
        "9:16": (720, 1280),
    }

    @staticmethod
    def _resolve_dimensions(aspect_ratio: str) -> tuple[int, int]:
        """Resolve aspect ratio string to dimensions.

        CONTRACT:
          Inputs:
            - aspect_ratio: string, one of "1:1", "16:9", "3:1", "4:1", "4:5", "9:16"

          Outputs:
            - tuple of two integers (width, height)

          Invariants:
            - aspect_ratio must be valid key in ASPECT_RATIOS

          Properties:
            - Lookup: returns dimensions from ASPECT_RATIOS dict
            - KeyError: raises if aspect_ratio not recognized

          Algorithm:
            1. Look up aspect_ratio in ASPECT_RATIOS
            2. Return corresponding (width, height) tuple
        """
        return FluxInferenceEngine.ASPECT_RATIOS[aspect_ratio]

    def __init__(self, model_id: str = FLUX1_SCHNELL):
        """Initialize FLUX engine in unloaded state.

        CONTRACT:
          Inputs: none

          Outputs: none (constructs instance)

          Invariants:
            - Engine starts unloaded
            - is_loaded() returns False
            - device is None

          Properties:
            - Lightweight: no model loading in constructor
            - Thread-safe: includes lock for serializing generate() calls
        """
        self._pipeline = None
        self.model_id = model_id
        self._device = None
        self._dtype = None
        self._generate_lock = threading.Lock()

    def reference_input_size(self, output_width: int, output_height: int) -> tuple[int, int] | None:
        """Return the per-reference canvas for editing-capable slugs, None otherwise.

        Pipeline facts (recorded 2026-09-19 against diffusers 0.39.0; see
        `Flux2KleinInferenceEngine` docstring for the FLUX.2 source paths and
        `pipelines/flux/pipeline_flux_kontext.py` for Kontext):

        - Schnell accepts no references -> None.
        - Kontext accepts one reference at the generation canvas. With
          `_auto_resize=False` and `max_area = gw * gh`, both already multiples
          of 16, the pipeline-internal resize is provably a no-op.
        - FLUX.2 klein 4B accepts 1-4 references at the generation canvas.
          The pipeline applies an unconditional area-based resize above
          `1024 * 1024` and rounds each axis to a multiple of 16; the
          no-op contract is `width * height <= 1024 * 1024` AND both axes
          multiples of 16. The largest preset canvas (1024x768) is below
          `1024 * 1024`, so this is satisfied for every preset.
        """
        if self.model_id == FLUX1_SCHNELL:
            return None
        return (round16(output_width), round16(output_height))

    def default_sampling_settings(self) -> dict[str, float | int]:
        """Per-slug sampling baseline (T04 design decision).

        - Schnell: distilled `num_inference_steps=4`, `guidance_scale=0.0`
          (no classifier-free guidance for the distilled model).
        - Kontext: `num_inference_steps=28`, `guidance_scale=2.5`
          (matches the documented dev-mode defaults).
        - FLUX.2 klein 4B (distilled): `num_inference_steps=4`,
          `guidance_scale=1.0`.

        Caller-supplied `options.sampling_settings` override this baseline
        key by key (AC-MODEL-6).
        """
        if self.model_id == FLUX1_SCHNELL:
            return {"num_inference_steps": 4, "guidance_scale": 0.0}
        if self.model_id == FLUX1_KONTEXT_DEV:
            return {"num_inference_steps": 28, "guidance_scale": 2.5}
        return {"num_inference_steps": 4, "guidance_scale": 1.0}

    def load(self, *, root: Path | None = None) -> None:
        """Load FLUX model into memory.

        CONTRACT:
          Inputs:
            - root: optional resolved local snapshot directory (typically
              `AvailabilityReport.root` from
              `textbrush.model.weights.check_model_availability`), threaded
              through to `load_local_only` (gate-remediation round 5,
              finding 3). When omitted, behavior is unchanged: the pipeline
              loads by repo id from the ordinary HuggingFace cache only.
              Wiring a caller's `config.model.directories` root into this
              parameter is out of scope here -- `model` (S2) only owns
              making the plumbing available; the composition roots that own
              custom-directory wiring end to end are S7/S8/S9.

          Outputs: none (modifies internal state)

          Invariants:
            - After successful load, is_loaded() returns True
            - Device is selected (CUDA > MPS > CPU priority)
            - Model pipeline is initialized and ready for inference

          Properties:
            - Idempotent: calling load() multiple times is safe (no-op if already loaded)
            - State transition: unloaded → loaded
            - Device auto-detection: CUDA > MPS > CPU

          Algorithm:
            1. If already loaded: return (idempotent)
            2. Auto-detect available device:
               - If torch.cuda.is_available(): device = "cuda", dtype = torch.bfloat16
               - Else if torch.backends.mps.is_available(): device = "mps", dtype = torch.float32
               - Else: device = "cpu", dtype = torch.float32, log warning
            3. Load pipeline from MODEL_ID with torch_dtype, local files only
               (AC-LOCAL-1: a model discovery reports as available must load
               with no remote revalidation round trip)
            4. Apply device-specific optimization:
               - If CUDA: enable_model_cpu_offload()
               - Else: to(device)
            5. Mark engine as loaded
        """
        if self.is_loaded():
            return

        import torch
        from diffusers import FluxPipeline

        if torch.cuda.is_available():
            self._device = "cuda"
            self._dtype = torch.bfloat16
        elif torch.backends.mps.is_available():
            self._device = "mps"
            self._dtype = torch.float32
        else:
            self._device = "cpu"
            self._dtype = torch.float32
            logger.warning("Running on CPU - inference will be slow")

        # local_files_only=True (AC-LOCAL-1): a model that discovery has
        # already reported as available must not trigger a remote
        # revalidation round trip on every load.
        pipeline_class = FluxPipeline
        if self.model_id == FLUX1_KONTEXT_DEV:
            from diffusers import FluxKontextPipeline

            pipeline_class = FluxKontextPipeline
        elif self.model_id == FLUX2_KLEIN_4B:
            from diffusers import Flux2KleinPipeline

            pipeline_class = Flux2KleinPipeline
        self._pipeline = load_local_only(
            pipeline_class.from_pretrained, self.model_id, root=root, torch_dtype=self._dtype
        )

        if self._device == "cuda":
            self._pipeline.enable_model_cpu_offload()
        else:
            self._pipeline = self._pipeline.to(self._device)

    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        """Generate image using FLUX.1 Schnell with dimension alignment.

        CONTRACT:
          Inputs:
            - prompt: text description, non-empty string
            - options: GenerationOptions with seed, steps, aspect_ratio, width, height

          Outputs:
            - GenerationResult containing image, seed, time, model_name
            - Returned image dimensions exactly match options.width × options.height
            - If requested dimensions not divisible by 16, image generated at rounded-up
              dimensions and cropped back to requested size

          Invariants:
            - is_loaded() must be True before calling (else RuntimeError)
            - Returned seed matches options.seed if provided, else is auto-generated
            - final_width, final_height: requested dimensions (from options)
            - generated_width, generated_height: rounded-up dimensions passed to pipeline
            - Final image size = (final_width, final_height) exactly
            - generation_time is non-negative

          Properties:
            - Dimension rounding: generated_dim = ((requested_dim + 15) // 16) * 16
            - Rounding idempotent: if requested_dim divisible by 16, generated_dim = requested_dim
            - Rounding direction: always rounds UP, never down
            - Center cropping: left_offset = (generated_width - final_width) // 2
                              top_offset = (generated_height - final_height) // 2
            - Crop bounds: (left, top, left + final_width, top + final_height)
            - Deterministic: same prompt + seed → same image (within numerical precision)
            - Seed handling: use options.seed if provided, else random.randint(0, 2**32 - 1)
            - Dimension priority: "custom" or explicit width/height > aspect_ratio lookup

          Algorithm:
            1. Check is_loaded(), raise RuntimeError if not loaded
            2. Determine final (requested) dimensions:
               - If aspect_ratio is "custom", use options.width/height directly
               - If options.width != 512 or options.height != 512, use those
               - Otherwise resolve from options.aspect_ratio using ASPECT_RATIOS
            3. Round dimensions to multiples of 16:
               - generated_width = ((final_width + 15) // 16) * 16
               - generated_height = ((final_height + 15) // 16) * 16
            4. Create torch.Generator(self._device)
            5. Determine seed: options.seed if not None, else random.randint(0, 2**32 - 1)
            6. Set generator.manual_seed(seed)
            7. Acquire _generate_lock (thread safety)
            8. Reset scheduler state if present
            9. Record start time
            10. Call self._pipeline(prompt, generated_width, generated_height, steps, generator)
            11. Record elapsed time
            12. If generated dimensions differ from final dimensions:
                a. Calculate crop offsets (center crop):
                   - left = (generated_width - final_width) // 2
                   - top = (generated_height - final_height) // 2
                b. Crop image: result.images[0].crop((left, top, left + final_width,
                                                       top + final_height))
            13. Return GenerationResult with (cropped) image, seed, elapsed, MODEL_ID

        IMPLEMENTATION NOTE:
        The dimension alignment logic must be implemented between step 2 and step 10.
        Steps 1-2 and 4-9 already exist in the current implementation.
        New steps: 3 (rounding), 12 (cropping).
        """
        if not self.is_loaded():
            raise RuntimeError("Engine not loaded. Call load() before generate().")

        # Use explicit dimensions if "custom" aspect ratio or dimensions differ from defaults
        if options.aspect_ratio == "custom" or options.width != 512 or options.height != 512:
            final_width, final_height = options.width, options.height
        else:
            final_width, final_height = self._resolve_dimensions(options.aspect_ratio)

        # Round dimensions to multiples of 16 (required by FLUX model).
        generated_width = round16(final_width)
        generated_height = round16(final_height)

        logger.info(
            f"Generating image: prompt='{prompt}', "
            f"seed={options.seed}, steps={options.steps}, "
            f"final_dimensions={final_width}×{final_height}, "
            f"generated_dimensions={generated_width}×{generated_height}"
        )

        import torch

        generator = torch.Generator(self._device)
        seed = options.seed if options.seed is not None else random.randint(0, 2**32 - 1)
        generator.manual_seed(seed)

        # Acquire lock to prevent concurrent pipeline access (scheduler state corruption)
        with self._generate_lock:
            # Reset scheduler state to prevent IndexError from corrupted state
            # (e.g., when previous generation was interrupted mid-step)
            if hasattr(self._pipeline, "scheduler"):
                self._pipeline.scheduler._step_index = None

            start_time = time.perf_counter()
            settings = {**self.default_sampling_settings(), **options.sampling_settings}
            steps = int(settings.pop("num_inference_steps", options.steps))
            kwargs = dict(
                prompt=prompt,
                width=generated_width,
                height=generated_height,
                num_inference_steps=steps,
                generator=generator,
                **settings,
            )

            # Reference handling per slug. The model-boundary guard (T04
            # step 2): every reference forwarded to an editing pipeline
            # must already be at the engine's `reference_input_size` canvas.
            # The backend (S7) is the single decode site and normalizes to
            # that canvas at acknowledgement time, so an off-canvas
            # reference here means the engine is being called outside the
            # documented contract and must fail loudly (a silent resize
            # would violate the "no reference identity drift" guarantee of
            # S5-BC-1).
            canvas = self.reference_input_size(generated_width, generated_height)
            references: tuple[NormalizedReference, ...] = options.references
            if canvas is None:
                if references:
                    raise ValueError(
                        f"references provided but engine {self.model_id!r} accepts none; "
                        f"schnell is a text-to-image pipeline"
                    )
            elif not references:
                raise ValueError(
                    f"engine {self.model_id!r} requires at least one reference image; "
                    f"a cardinality check upstream of this engine should have rejected "
                    f"the request before generate() was called"
                )
            else:
                gw, gh = canvas
                for index, reference in enumerate(references):
                    if (reference.width, reference.height) != (gw, gh):
                        raise ValueError(
                            f"reference {index} has size "
                            f"({reference.width}, {reference.height}); "
                            f"engine {self.model_id!r} requires "
                            f"({gw}, {gh}) (normalize via "
                            f"references.normalize(target_size={gw, gh}) before "
                            f"calling generate())"
                        )
                if self.model_id == FLUX1_KONTEXT_DEV:
                    # Kontext is single-reference and accepts one PIL
                    # image; the pipeline unwraps a list itself, but T04
                    # commits to forwarding a one-element list for
                    # consistency with the FLUX.2 path and because
                    # `pixel_data.copy()` belongs to the engine, not the
                    # caller.
                    kwargs["image"] = references[0].pixel_data.copy()
                    kwargs["_auto_resize"] = False
                    kwargs["max_area"] = generated_width * generated_height
                else:
                    # FLUX.2 klein accepts a list of PIL images.
                    kwargs["image"] = [r.pixel_data.copy() for r in references]

            result = self._pipeline(**kwargs)
            generation_time = time.perf_counter() - start_time

        # Apply center cropping if dimensions were rounded
        image = result.images[0]
        if generated_width != final_width or generated_height != final_height:
            left = (generated_width - final_width) // 2
            top = (generated_height - final_height) // 2
            right = left + final_width
            bottom = top + final_height
            image = image.crop((left, top, right, bottom))

        return GenerationResult(
            image=image,
            seed=seed,
            generation_time=generation_time,
            model_name=get_repo_id(self.model_id),
            generated_width=generated_width,
            generated_height=generated_height,
        )

    def is_loaded(self) -> bool:
        """Check if FLUX model is loaded.

        CONTRACT:
          Inputs: none

          Outputs:
            - boolean: True if model loaded and ready, False otherwise

          Invariants:
            - Returns False before load() is called
            - Returns True after successful load()
            - Returns False after unload() is called

          Properties:
            - Pure query: does not modify state
            - Synchronous: returns immediately
        """
        return self._pipeline is not None

    def unload(self) -> None:
        """Unload FLUX model from memory.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After unload(), is_loaded() returns False
            - Memory occupied by model is released

          Properties:
            - Idempotent: calling unload() multiple times is safe
            - State transition: loaded → unloaded
            - Cleanup: releases GPU/CPU memory

          Algorithm:
            1. Set self._pipeline = None
            2. Set self._device = None
            3. Set self._dtype = None
        """
        self._pipeline = None
        self._device = None
        self._dtype = None

    @property
    def device(self) -> str:
        """Return device being used for inference.

        CONTRACT:
          Inputs: none

          Outputs:
            - string: "cuda", "mps", or "cpu", or empty string if not loaded

          Invariants:
            - Returns empty string before load()
            - Returns device string after load()
            - Device string is one of: "cuda", "mps", "cpu"

          Properties:
            - Pure query: does not modify state
            - Reflects actual hardware in use
        """
        return self._device or ""


class FluxKontextInferenceEngine(FluxInferenceEngine):
    """FLUX.1 Kontext [dev] single-reference editing engine."""

    def __init__(self) -> None:
        super().__init__(FLUX1_KONTEXT_DEV)


class Flux2KleinInferenceEngine(FluxInferenceEngine):
    """FLUX.2 [klein] 4B ordered multi-reference editing engine.

    Pipeline facts (recorded 2026-09-19 against diffusers 0.39.0,
    ``diffusers/pipelines/flux2/pipeline_flux2_klein.py``):

    - ``image`` parameter accepts ``list[PIL.Image.Image] | PIL.Image.Image | None``
      (``pipeline_flux2_klein.py:616``); the engine forwards a list.
    - Per-reference preprocessing (lines 770-779): if
      ``image_width * image_height > 1024 * 1024``, the image is uniformly scaled by
      ``_resize_to_target_area(img, 1024 * 1024)`` to that target area; otherwise the
      image is left at its native size. Each axis is then floored to a multiple of
      ``self.vae_scale_factor * 2`` (= 16 for FLUX VAE), and finally
      ``self.image_processor.preprocess(img, height=image_height, width=image_width,
      resize_mode="crop")`` is called.
    - There is no ``_auto_resize``-style flag on this pipeline; the resize happens
      unconditionally whenever pixel area exceeds ``1024 * 1024``. The contract
      for a no-op preprocessing path is therefore: width and height already
      multiples of 16 AND ``width * height <= 1024 * 1024``.
    - ``num_inference_steps: int = 50`` (line 620), ``guidance_scale: float = 4.0``
      (line 622). The project overrides these per
      ``FluxInferenceEngine.default_sampling_settings`` (``num_inference_steps=4``,
      ``guidance_scale=1.0`` for the klein 4B distilled model).
    """

    def __init__(self) -> None:
        super().__init__(FLUX2_KLEIN_4B)

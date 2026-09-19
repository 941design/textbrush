"""Base interface for inference engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from textbrush.references import NormalizedReference

# The canvas used when neither the caller nor an aspect ratio determines a
# dimension: `aspect_ratio == "custom"` (the caller owns the dimensions)
# with one or both axes left unspecified. Owned here rather than restated
# as a literal in `flux.py` and `backend.py` so the "default resolution"
# decision has exactly one site. It is deliberately NOT a sentinel: a
# caller that did not specify a dimension passes None, not this value, so
# an explicit `aspect_ratio` always wins over a defaulted dimension.
DEFAULT_DIMENSIONS: tuple[int, int] = (1024, 1024)


@dataclass
class GenerationResult:
    """Result from a single image generation.

    Attributes:
        image: Generated PIL image.
        seed: Random seed used for generation.
        generation_time: Time taken to generate in seconds.
        model_name: Identifier of the model used.
        generated_width: Width passed to model (multiple of 16), or None.
        generated_height: Height passed to model (multiple of 16), or None.

    CONTRACT (generated dimension fields):
      Invariants:
        - If generated_width is not None, it is divisible by 16
        - If generated_height is not None, it is divisible by 16
        - If generated dimensions differ from image.size, image was cropped after generation
        - If generated dimensions equal image.size, no cropping occurred
        - If generated dimensions are None, image not subject to dimension alignment

      Properties:
        - Backward compatibility: None means "no dimension alignment performed"
        - Optional: default to None for engines without dimension alignment
        - Semantic: None indicates legacy behavior or non-FLUX engines
    """

    image: Image.Image
    seed: int
    generation_time: float
    model_name: str
    generated_width: int | None = None
    generated_height: int | None = None


@dataclass
class GenerationOptions:
    """Options for image generation.

    Attributes:
        seed: Random seed for reproducibility (None = auto-generate).
        width: Image width in pixels, or None when the caller did not
            specify one. None is the honest representation of "no explicit
            width": the engine then resolves that axis from `aspect_ratio`
            (or from `DEFAULT_DIMENSIONS` when `aspect_ratio` is "custom",
            which means the caller owns the dimensions but supplied none).
            An int -- ANY int -- is an explicit request and wins over the
            aspect-ratio lookup.
        height: Image height in pixels, or None. Same rules as `width`;
            the two axes are resolved independently.
        steps: Number of inference steps.
        aspect_ratio: Aspect ratio string (1:1, 16:9, 9:16, ... or the
            literal "custom" meaning "the caller owns width/height").

    CONTRACT (dimension fields):
      Invariants:
        - `width`/`height` are never sentinels. Before
          gate-remediation round 7 the pair (512, 512) doubled as "caller
          did not specify", which silently disabled the aspect-ratio
          lookup the moment a caller defaulted them to anything else
          (a real regression: `--aspect-ratio 16:9` became a no-op).
          None carries that meaning now and cannot collide with a
          legitimately requested resolution.
      Properties:
        - Priority: explicit width/height > aspect_ratio lookup >
          DEFAULT_DIMENSIONS.
    """

    seed: int | None = None
    width: int | None = None
    height: int | None = None
    steps: int = 4
    aspect_ratio: str = "1:1"
    references: tuple[NormalizedReference, ...] = ()
    model_id: str = "flux1-schnell"
    sampling_settings: dict[str, float | int] = field(default_factory=dict)


class InferenceEngine(ABC):
    """Abstract base class for inference backends.

    Defines the interface that all inference engines must implement.
    """

    @abstractmethod
    def load(self) -> None:
        """Load model into memory.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies internal state)

          Invariants:
            - After successful load, is_loaded() returns True
            - Device is selected (CUDA > MPS > CPU priority)
            - Model pipeline is initialized and ready for inference

          Properties:
            - Idempotent: calling load() multiple times is safe (no-op if already loaded)
            - State transition: unloaded → loaded
            - Must detect hardware (torch.cuda.is_available, torch.backends.mps.is_available)
            - Reusable after unload(): unload() → load() reloads the engine
              from scratch. The backend's engine swap depends on this (it
              unloads the outgoing engine BEFORE loading the incoming one
              and reloads it if the incoming load fails).

          Algorithm:
            1. Auto-detect available device (CUDA, MPS, or CPU)
            2. Select appropriate dtype based on device (bfloat16 for CUDA, float32 otherwise)
            3. Load model pipeline from HuggingFace
            4. Apply device-specific optimizations (CPU offload for CUDA, to(device) otherwise)
            5. Mark engine as loaded
        """
        pass

    def load_from(self, root: Path | None) -> None:
        """Load this engine, preferring an already-validated snapshot directory.

        CONTRACT:
          Inputs:
            - root: a local snapshot directory a discovery pass has already
              validated for this engine's model (typically
              `AvailabilityReport.root` from
              `textbrush.model.weights.check_model_availability`), or None
              meaning "resolve the weights the ordinary way".

          Outputs: none (modifies internal state)

          Invariants:
            - Equivalent to `load()` in every respect except WHERE the
              weights are read from; all of `load()`'s invariants and
              properties (idempotency, device selection, reusability after
              unload) hold unchanged.
            - `load_from(None)` is exactly `load()`.

          Properties:
            - This is the seam a composition root uses to honour
              `config.model.directories`. `load()` alone cannot: a
              repo-id-plus-HF-cache lookup never sees a custom directory,
              so a model discovery validated in one would report available
              and then fail to load (the gap `load_local_only`'s `root`
              kwarg closes).
            - Default implementation ignores `root` and delegates to
              `load()`. That is the correct behavior for an engine with no
              on-disk snapshot to be pointed at (a test double, a remote
              engine). An engine that CAN consume a resolved snapshot
              directory overrides this method -- see
              `FluxInferenceEngine.load_from`. The capability is declared
              here as an optional, defaulted seam rather than as a `root`
              keyword on the abstract `load()` so that implementations are
              not silently required to grow a parameter they cannot use.
        """
        self.load()

    @abstractmethod
    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        """Generate a single image from prompt.

        CONTRACT:
          Inputs:
            - prompt: text description, non-empty string
            - options: GenerationOptions with seed, dimensions, steps, aspect_ratio,
              references, model_id, and sampling_settings. Explicit (non-None)
              width/height win over the aspect_ratio lookup; a None axis is
              resolved from aspect_ratio, or from DEFAULT_DIMENSIONS when
              aspect_ratio is "custom". `options.references` (already at this
              engine's `reference_input_size` canvas, when present) are forwarded
              to the pipeline in tuple order.

          Outputs:
            - GenerationResult containing image, seed, time, model_name

          Invariants:
            - is_loaded() must be True before calling (else error)
            - Returned seed matches options.seed if provided, else is auto-generated
            - Returned image has dimensions matching aspect_ratio mapping:
              * 1:1 → 1024×1024
              * 16:9 → 1344×768
              * 9:16 → 768×1344
            - generation_time is non-negative
            - Reference-bearing engines (Kontext, FLUX.2 klein) refuse a request
              whose `references` are not at this engine's `reference_input_size`
              canvas (the model-boundary guard documented in S5-BC-1).

          Properties:
            - Deterministic: same prompt + seed → same image (within numerical precision)
            - Seed monotonic: if options.seed is provided, use it; else generate random seed
            - Dimension priority: an explicitly supplied (non-None) width/height
              takes precedence over the aspect_ratio lookup, per axis. There is
              no magic dimension value: "unspecified" is None, so an engine can
              never mistake a requested resolution for an absent one.
            - Reference handling: references are forwarded in tuple order; same
              path twice yields two list entries to the pipeline (AC-INPUT-4)

          Algorithm:
            1. Resolve dimensions per axis: options.width/height when not None,
               else the aspect_ratio lookup, else DEFAULT_DIMENSIONS
            2. Round dimensions to multiples of 16
            3. Build sampling settings from `default_sampling_settings()` overridden
               by `options.sampling_settings`
            4. For each reference (when this engine accepts them), assert its size
               matches the engine's canvas; pass pixel_data through (copies are the
               engine's responsibility, not the caller's)
            5. Create torch.Generator with device and seed (auto-generate if None)
            6. Call pipeline with prompt, dimensions, steps, references (if any),
               and the merged sampling settings
            7. Measure generation time
            8. Crop the pipeline output back to the requested dimensions if the
               rounded generation canvas was larger
            9. Return GenerationResult with image, seed, time, model_name
        """
        pass

    def reference_input_size(self, output_width: int, output_height: int) -> tuple[int, int] | None:
        """Return the (width, height) canvas this engine expects references at.

        CONTRACT:
          Inputs:
            - output_width: requested generation output width in pixels
            - output_height: requested generation output height in pixels

          Outputs:
            - tuple of two ints: the canvas a `NormalizedReference` must already
              have at the moment the engine forwards it to its pipeline, or
            - None: this engine accepts no references; `options.references`
              must be empty when calling `generate()`.

          Invariants:
            - The single source of "what canvas references must be at" for this
              engine (stories.json S5-BC-1). A backend pass-through consumer
              reads this value and passes it to `references.normalize()` so
              the engine never has to scale references itself.

          Properties:
            - Default implementation returns None (text-only engine). Editing
              engines override to return the generation canvas rounded to a
              multiple of 16.
            - Pure: deterministic for the same output dimensions.
        """
        return None

    def default_sampling_settings(self) -> dict[str, float | int]:
        """Return the per-engine baseline sampling settings.

        CONTRACT:
          Inputs: none.

          Outputs:
            - dict of str -> (int | float): the per-engine sampling baseline.
              Recognised keys: `num_inference_steps` (int), `guidance_scale`
              (float). The engine pops `num_inference_steps` and forwards the
              rest as keyword arguments to the pipeline.

          Invariants:
            - Caller-supplied `options.sampling_settings` override this
              baseline, key by key (AC-MODEL-6: per-slug defaults, with a
              caller-visible override path).

          Properties:
            - Default implementation returns `{}` (no overrides; the pipeline's
              own signature defaults apply). Editing engines override to
              return the distilled / production defaults documented in T04.
            - Pure: no IO, no randomness; same engine always returns the same
              dict.
        """
        return {}

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is ready for inference.

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
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release model from memory.

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
            1. Release pipeline reference
            2. Clear device reference
            3. Mark engine as unloaded
        """
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        """Return device being used for inference.

        CONTRACT:
          Inputs: none

          Outputs:
            - string: "cuda", "mps", or "cpu"

          Invariants:
            - Returns None or empty before load()
            - Returns device string after load()
            - Device string is one of: "cuda", "mps", "cpu"

          Properties:
            - Pure query: does not modify state
            - Reflects actual hardware in use
        """
        pass

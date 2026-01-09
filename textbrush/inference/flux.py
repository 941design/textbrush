"""FLUX.1 Schnell inference engine implementation."""

from __future__ import annotations

import logging
import random
import threading
import time

import torch
from diffusers import FluxPipeline

from textbrush.inference.base import GenerationOptions, GenerationResult, InferenceEngine

logger = logging.getLogger(__name__)


class FluxInferenceEngine(InferenceEngine):
    """FLUX.1 Schnell implementation of InferenceEngine.

    Uses black-forest-labs/FLUX.1-schnell model from HuggingFace.
    """

    MODEL_ID = "black-forest-labs/FLUX.1-schnell"

    # Aspect ratio to dimensions mapping
    ASPECT_RATIOS = {
        "1:1": (1024, 1024),
        "16:9": (1344, 768),
        "9:16": (768, 1344),
    }

    @staticmethod
    def _resolve_dimensions(aspect_ratio: str) -> tuple[int, int]:
        """Resolve aspect ratio string to dimensions.

        CONTRACT:
          Inputs:
            - aspect_ratio: string, one of "1:1", "16:9", "9:16"

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

    def __init__(self):
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
        self._device = None
        self._dtype = None
        self._generate_lock = threading.Lock()

    def load(self) -> None:
        """Load FLUX model into memory.

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
            - Device auto-detection: CUDA > MPS > CPU

          Algorithm:
            1. If already loaded: return (idempotent)
            2. Auto-detect available device:
               - If torch.cuda.is_available(): device = "cuda", dtype = torch.bfloat16
               - Else if torch.backends.mps.is_available(): device = "mps", dtype = torch.float32
               - Else: device = "cpu", dtype = torch.float32, log warning
            3. Load pipeline from MODEL_ID with torch_dtype
            4. Apply device-specific optimization:
               - If CUDA: enable_model_cpu_offload()
               - Else: to(device)
            5. Mark engine as loaded
        """
        if self.is_loaded():
            return

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

        self._pipeline = FluxPipeline.from_pretrained(self.MODEL_ID, torch_dtype=self._dtype)

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

        # Round dimensions to multiples of 16 (required by FLUX model)
        generated_width = ((final_width + 15) // 16) * 16
        generated_height = ((final_height + 15) // 16) * 16

        logger.info(
            f"Generating image: prompt='{prompt}', "
            f"seed={options.seed}, steps={options.steps}, "
            f"final_dimensions={final_width}×{final_height}, "
            f"generated_dimensions={generated_width}×{generated_height}"
        )

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
            result = self._pipeline(
                prompt=prompt,
                width=generated_width,
                height=generated_height,
                num_inference_steps=options.steps,
                generator=generator,
            )
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
            model_name=self.MODEL_ID,
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

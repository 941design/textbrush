"""FLUX.1 Schnell inference engine implementation."""

from __future__ import annotations

import logging
import random
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
        """
        self._pipeline = None
        self._device = None
        self._dtype = None

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
        """Generate image using FLUX.1 Schnell.

        CONTRACT:
          Inputs:
            - prompt: text description, non-empty string
            - options: GenerationOptions with seed, steps, aspect_ratio

          Outputs:
            - GenerationResult containing image, seed, time, model_name

          Invariants:
            - is_loaded() must be True before calling (else RuntimeError)
            - Returned seed matches options.seed if provided, else is auto-generated
            - Returned image has dimensions matching aspect_ratio from ASPECT_RATIOS
            - generation_time is non-negative

          Properties:
            - Deterministic: same prompt + seed → same image (within numerical precision)
            - Seed handling: use options.seed if provided, else random.randint(0, 2**32 - 1)
            - Aspect ratio mapping: uses ASPECT_RATIOS dict to resolve dimensions

          Algorithm:
            1. Check is_loaded(), raise RuntimeError if not loaded
            2. Resolve width, height from options.aspect_ratio using ASPECT_RATIOS
            3. Create torch.Generator(self._device)
            4. Determine seed: options.seed if not None, else random.randint(0, 2**32 - 1)
            5. Set generator.manual_seed(seed)
            6. Record start time
            7. Call self._pipeline(prompt, width, height, num_inference_steps, generator)
            8. Record elapsed time
            9. Return GenerationResult with result.images[0], seed, elapsed, MODEL_ID
        """
        if not self.is_loaded():
            raise RuntimeError("Engine not loaded. Call load() before generate().")

        logger.info(
            f"Generating image: prompt='{prompt}', "
            f"seed={options.seed}, steps={options.steps}, aspect_ratio={options.aspect_ratio}"
        )

        width, height = self._resolve_dimensions(options.aspect_ratio)

        generator = torch.Generator(self._device)
        seed = options.seed if options.seed is not None else random.randint(0, 2**32 - 1)
        generator.manual_seed(seed)

        start_time = time.perf_counter()
        result = self._pipeline(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=options.steps,
            generator=generator,
        )
        generation_time = time.perf_counter() - start_time

        return GenerationResult(
            image=result.images[0],
            seed=seed,
            generation_time=generation_time,
            model_name=self.MODEL_ID,
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

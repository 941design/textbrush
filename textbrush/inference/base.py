"""Base interface for inference engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from PIL import Image


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
        width: Image width in pixels (overridden by aspect_ratio).
        height: Image height in pixels (overridden by aspect_ratio).
        steps: Number of inference steps.
        aspect_ratio: Aspect ratio string (1:1, 16:9, 9:16).
    """

    seed: int | None = None
    width: int = 512
    height: int = 512
    steps: int = 4
    aspect_ratio: str = "1:1"


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

          Algorithm:
            1. Auto-detect available device (CUDA, MPS, or CPU)
            2. Select appropriate dtype based on device (bfloat16 for CUDA, float32 otherwise)
            3. Load model pipeline from HuggingFace
            4. Apply device-specific optimizations (CPU offload for CUDA, to(device) otherwise)
            5. Mark engine as loaded
        """
        pass

    @abstractmethod
    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        """Generate a single image from prompt.

        CONTRACT:
          Inputs:
            - prompt: text description, non-empty string
            - options: GenerationOptions with seed, dimensions, steps, aspect_ratio

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

          Properties:
            - Deterministic: same prompt + seed → same image (within numerical precision)
            - Seed monotonic: if options.seed is provided, use it; else generate random seed
            - Aspect ratio respected: output dimensions match aspect_ratio, ignore width/height

          Algorithm:
            1. Resolve dimensions from aspect_ratio (override width/height)
            2. Create torch.Generator with device and seed (auto-generate if None)
            3. Call pipeline with prompt, dimensions, steps, generator
            4. Measure generation time
            5. Return GenerationResult with image, seed, time, model_name
        """
        pass

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

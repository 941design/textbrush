"""Factory for creating inference engines."""

from __future__ import annotations

from textbrush.inference.base import InferenceEngine


def create_engine(backend: str, model_id: str = "flux1-schnell") -> InferenceEngine:
    """Create inference engine by backend name.

    CONTRACT:
      Inputs:
        - backend: string identifying backend type (e.g., "flux")

      Outputs:
        - InferenceEngine: concrete implementation instance

      Invariants:
        - Returned engine is not loaded (call engine.load() before use)
        - Engine type matches backend string

      Properties:
        - Factory pattern: abstracts engine construction
        - Extensible: new backends can be added by extending this function
        - Error handling: raises ValueError for unknown backends

      Algorithm:
        1. Match backend string to engine class
        2. If "flux": import FluxInferenceEngine and return instance
        3. If unknown: raise ValueError with helpful message
    """
    if backend == "flux":
        from textbrush.inference.flux import (
            Flux2KleinInferenceEngine,
            FluxInferenceEngine,
            FluxKontextInferenceEngine,
        )
        from textbrush.model.registry import FLUX1_KONTEXT_DEV, FLUX2_KLEIN_4B

        if model_id == FLUX1_KONTEXT_DEV:
            return FluxKontextInferenceEngine()
        if model_id == FLUX2_KLEIN_4B:
            return Flux2KleinInferenceEngine()
        return FluxInferenceEngine(model_id=model_id)
    else:
        msg = f"Unknown inference backend: {backend}"
        raise ValueError(msg)

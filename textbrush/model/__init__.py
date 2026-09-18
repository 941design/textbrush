"""Model weight management for text-to-image models.

Public surface:
    - `textbrush.model.registry`: per-model identity (short slug <-> HuggingFace
      repo id, the single-owner mapping required by S2-BC-1), cardinality
      metadata, discovery-cause enumeration, and launch-time-only default-
      model resolution (`resolve_model_selection`).
    - `textbrush.model.weights`: local-only discovery (`check_model_availability`),
      download, and local-only pipeline loading (`load_local_only`).

`model` is a leaf module: it must not import `backend`, `worker`, `ipc`, or
`inference`.
"""

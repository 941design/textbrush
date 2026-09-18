"""Reference image decode and normalization (leaf module).

Public surface for the `references` module: `normalize()` and the
NormalizedReference seam contract it produces, plus the constants and
exception taxonomy callers need to handle per-file failures.

See textbrush/references/normalization.py for the full contract and
specs/epic-multi-reference-flux-image-editing/architecture.md for this
module's boundary rules (must not import backend/worker/ipc).
"""

from __future__ import annotations

from textbrush.references.normalization import (
    NEUTRAL_FILL_VALUE,
    SUPPORTED_EXTENSIONS,
    CorruptReferenceError,
    NormalizationError,
    NormalizedReference,
    ReferenceImageError,
    ReferenceNotFoundError,
    ReferenceResourceConstrainedError,
    UnreadableReferenceError,
    UnsupportedExtensionError,
    normalize,
)

__all__ = [
    "NEUTRAL_FILL_VALUE",
    "SUPPORTED_EXTENSIONS",
    "CorruptReferenceError",
    "NormalizationError",
    "NormalizedReference",
    "ReferenceImageError",
    "ReferenceNotFoundError",
    "ReferenceResourceConstrainedError",
    "UnreadableReferenceError",
    "UnsupportedExtensionError",
    "normalize",
]

"""Reference image decode and normalization.

Leaf module (architecture.md boundary rule 2): must not import `backend`,
`worker`, `ipc`, `model`, `config`, `cli`, or `inference`. Both composition
roots (`cli.py` and `ipc/handler.py`, by way of the not-yet-existing S7
backend lifecycle) reach normalized reference data only through
`normalize()` below.

Implements spec.md sec 6.2 ("First-release normalization") and sec 6.1
("Source preservation"): references are opened read-only, never written to,
renamed, or relocated. The five-member failure taxonomy below covers
spec.md sec 11's "missing, unreadable, corrupt, unsupported, or
resource-constrained image files" and AC-INPUT-3.

CONTRACT (module-wide):
  Determinism (AC-PROCESS-2): normalize() is a pure function of its two
  inputs (the source file's bytes, and target_size). It performs no
  randomness, no time-of-day-dependent branching in its pixel-producing
  path, and its scale factor is a plain arithmetic function of the source
  and target dimensions -- never of available memory, CPU count, or any
  other runtime resource. `NormalizedReference.decoded_at` is the sole
  exception: it is a wall-clock provenance marker for S7's
  acknowledgement-time bookkeeping and is explicitly outside the
  determinism invariant, which covers only pixel_data/width/height/
  content_aspect_ratio/fill_value.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

# Case-insensitive by construction: callers compare against
# `path.suffix.lower()`, never the raw suffix, so "IMG_1234.JPG" is accepted
# (spec.md sec 5.2/6.2, AC-INPUT-3).
SUPPORTED_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})

# The single documented neutral fill (spec.md sec 6.2: "a documented neutral
# fill value"), applied to all three RGB channels. Used for BOTH alpha
# compositing ("sources carrying an alpha channel are composited onto the
# same documented neutral fill before conversion, so that transparency never
# becomes an undefined colour") and centered padding of the remainder after
# uniform scaling. Spec.md sec 6.2 BINDS these two uses to one value --
# "the same documented neutral fill" -- it is not merely a simplification
# available to the implementer; a future change must not split this into
# two constants without a spec amendment.
NEUTRAL_FILL_VALUE = 128

_NEUTRAL_FILL_RGB = (NEUTRAL_FILL_VALUE, NEUTRAL_FILL_VALUE, NEUTRAL_FILL_VALUE)

# Fixed, deterministic resample filter. LANCZOS produces no randomness and,
# for a given (source size, target size) pair, always produces the same
# output -- required by AC-PROCESS-2's determinism guarantee.
_RESAMPLE_FILTER = Image.Resampling.LANCZOS


class ReferenceImageError(Exception):
    """Base class for every failure `normalize()` raises.

    Named `ReferenceImageError` rather than `ReferenceError` to avoid
    shadowing the Python builtin exception of that name.
    """


class UnsupportedExtensionError(ReferenceImageError):
    """The file's extension is not one of SUPPORTED_EXTENSIONS."""


class ReferenceNotFoundError(ReferenceImageError):
    """The file does not exist at the given path."""


class UnreadableReferenceError(ReferenceImageError):
    """The file exists but cannot be opened (e.g. permission denied)."""


class CorruptReferenceError(ReferenceImageError):
    """The file cannot be decoded as a valid image: truncated, corrupt, or
    not an image at all, despite a supported extension."""


class ReferenceResourceConstrainedError(ReferenceImageError):
    """Decoding was refused because it would exceed a resource guard (e.g.
    Pillow's decompression-bomb protection) or exhausted available memory."""


class NormalizationError(ReferenceImageError):
    """The file decoded successfully but could not be normalized (scaled and
    padded) to the requested target size: either the scale/pad stage
    exhausted available resources, or the requested target_size is
    geometrically unreachable for this source (an extreme aspect ratio that
    would round a scaled axis down to 0 pixels; see `_scale_and_pad`) -- not
    a resource condition, but reported through this same class since it is
    likewise a scale/pad-stage failure distinct from the decode-time
    taxonomy."""


@dataclass(frozen=True, eq=False)
class NormalizedReference:
    """Decoded, normalized reference-image data.

    This is the seam contract consumed by S5 (inference engines, as the
    per-reference image handed to the Kontext / FLUX.2 pipelines) and S7
    (backend decode-at-acknowledgement lifecycle, which holds instances of
    this type for the lifetime of one acknowledged configuration).

    Attributes:
        pixel_data: RGB image at exactly (width, height), ready to hand to a
          diffusers-style pipeline unchanged. A `PIL.Image.Image` rather
          than a numpy array or tensor: it is what `textbrush/buffer.py` and
          `textbrush/inference/base.py` already use for image data
          elsewhere in this codebase, and what the FLUX reference-editing
          pipelines this epic targets accept directly, with no new
          array-library dependency.
        width: Always equals `pixel_data.width`. When normalize() was called
          with a `target_size`, this is `target_size[0]` (the padded-canvas
          width); when called with `target_size=None`, this is the
          EXIF-corrected source width (no scaling or padding applied).
        height: Always equals `pixel_data.height`. When normalize() was
          called with a `target_size`, this is `target_size[1]` (the
          padded-canvas height); when called with `target_size=None`, this
          is the EXIF-corrected source height (no scaling or padding
          applied).
        content_aspect_ratio: `source_width / source_height` of the
          EXIF-corrected visible content region, measured BEFORE scaling or
          padding. Never derived from the padded canvas (AC-PROCESS-1: "the
          visible content region retains its original aspect ratio... not
          the padded canvas").
        fill_value: The neutral fill value used for both alpha compositing
          and centered padding on this instance. Always NEUTRAL_FILL_VALUE.
        decoded_at: ISO-8601 UTC timestamp of when this instance was
          produced. Provenance only -- explicitly excluded from the
          determinism invariant (see module docstring).

    CONTRACT:
      Invariants:
        - content_aspect_ratio matches the source visible-content region,
          not the padded canvas (AC-PROCESS-1).
        - Identical pixel_data/width/height/content_aspect_ratio/fill_value
          for the same source bytes and the same target_size, on any run,
          regardless of available system resources (AC-PROCESS-2).
        - Never re-derived from disk after initial decode: this dataclass
          holds decoded pixel data, not a path: (spec.md sec 6.3;
          decode-once lifetime enforcement is S7's responsibility).
        - pixel_data is never produced via per-axis independent resizing:
          the single `scale` factor in `_scale_and_pad` is applied to both
          axes identically; any remainder after that uniform scale is
          reached by centered padding, never by an independent per-axis
          resize (AC-PROCESS-2).
      Mutability:
        - `frozen=True` prevents rebinding the dataclass's own fields, but
          does NOT protect the mutable `PIL.Image.Image` that `pixel_data`
          points to: consumers MUST NOT mutate `pixel_data` in place (e.g.
          `.paste()`, `.putpixel()`) -- doing so silently corrupts every
          later read of this same instance, including by S7's
          decode-once-per-acknowledged-configuration lifetime (spec.md sec
          6.3) and any other holder of the same reference. Callers that need
          a mutable working copy must call `pixel_data.copy()` first. This
          class deliberately does not deep-copy `pixel_data` on construction
          or access to avoid a per-generation memory cost for a hazard that
          is fully addressed by this contract statement.
        - `eq=False`: two instances are compared by identity, not value.
          `PIL.Image.Image` DOES define value equality (`Image.__eq__`
          compares mode/size/pixel bytes, so two independent normalizations
          of the same file compare `==` True) -- but `frozen=True`'s
          auto-generated `__eq__` would run that comparison on every `==`,
          an O(pixels) cost paid even when callers only want an identity
          check, and `decoded_at` (a wall-clock provenance field, excluded
          from the determinism invariant) would make whole-dataclass value
          equality meaningless regardless: two instances decoded from
          identical bytes a second apart would compare unequal on
          `decoded_at` alone even though every field the invariant covers
          matches. Auto-generated `__hash__` would also raise `TypeError`
          (`unhashable type: 'Image'` -- PIL defines `__eq__` without
          `__hash__`, so any *for hashing* attempt on `pixel_data` fails).
          `eq=False` makes identity comparison the honest, declared
          semantics instead of leaving a misleading value-equality default
          in place. Use `pixel_data.tobytes()` comparisons (see
          tests/test_references.py TestDeterminism) to compare instances by
          content.
    """

    pixel_data: Image.Image
    width: int
    height: int
    content_aspect_ratio: float
    fill_value: int
    decoded_at: str


def _validate_extension(path: Path) -> None:
    """Raise UnsupportedExtensionError unless path's extension (matched
    case-insensitively) is one of SUPPORTED_EXTENSIONS."""
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedExtensionError(
            f"unsupported reference image extension {path.suffix!r} for {path}; "
            f"supported extensions: {sorted(SUPPORTED_EXTENSIONS)}"
        )


def _decode(path: Path) -> Image.Image:
    """Open and fully decode `path`, translating decode failures into the
    per-file failure taxonomy.

    `Image.open()` alone is lazy -- it validates only the file header, not
    the full pixel stream -- so a truncated or otherwise corrupt file can
    open successfully and only fail on `.load()`. Both stages are guarded
    here so truncated files are classified as corrupt, not treated as
    decoded.

    Pillow's decompression-bomb guard has two tiers gated on
    `Image.MAX_IMAGE_PIXELS`, both applied inside `Image.open()` itself
    (against the header-reported size, before any pixel data is read):
    above roughly 2x the threshold it raises `DecompressionBombError`
    (handled below like any other exception from `Image.open()`), but
    between 1x and 2x it only emits a `DecompressionBombWarning` and, by
    default, proceeds to decode anyway.

    Round 2 (finding N3) rejected promoting that warning to an exception via
    `warnings.catch_warnings()` + `simplefilter("error", ...)`, because that
    pattern mutates CPython's global warnings-filter list (documented as
    not thread-safe) and restores the ENTIRE filter list, not just the one
    entry it added, on exit -- a real hazard in this codebase, where
    `references` decodes on the IPC command thread while worker and
    delivery threads run concurrently. It replaced that mechanism with the
    header-size check below (`width * height > Image.MAX_IMAGE_PIXELS`,
    against `image.size` exactly as Pillow itself read it from the header),
    which correctly and deterministically raises for the default case where
    no warnings-as-errors filter is configured.

    But round 2 also dropped `DecompressionBombWarning` from the `except`
    clause entirely when it removed the filter mutation, which reopened the
    original gap in a narrower form (round 3 finding C2): if the HOST
    APPLICATION independently configures
    `warnings.simplefilter("error", Image.DecompressionBombWarning)` (this
    module never does so itself, before or after this fix), Python raises
    the warning as an exception from INSIDE `Image.open()` -- before the
    header-size check below ever gets a chance to run -- so it would escape
    the ReferenceImageError hierarchy entirely, uncatchable by S7's
    acknowledgement-time handler (AC-STATE-3, AC-RECOVERY-1).

    The fix composes BOTH mechanisms; dropping either one reopens a gap:
      (a) the header-size check below (deterministic; covers the default
          case where the host has not configured warnings-as-errors);
      (b) `DecompressionBombWarning` restored to the `except` clause,
          alongside `DecompressionBombError` (covers the case where the
          HOST's own filter configuration turns the warning into an
          exception before (a) can run).
    (b) does NOT reintroduce N3's concurrency hazard: it installs no
    filter and mutates no global interpreter state of its own -- it only
    catches an exception that the host's own, independently-configured
    filter chose to raise. Whether that exception is ever raised at all
    remains entirely a function of the host's configuration, never of
    anything this module does.
    """
    try:
        image = Image.open(path)
        width, height = image.size
        if Image.MAX_IMAGE_PIXELS is not None and width * height > Image.MAX_IMAGE_PIXELS:
            raise ReferenceResourceConstrainedError(
                f"reference image exceeds the decode resource limit: {path}"
            )
        image.load()
    except FileNotFoundError as exc:
        raise ReferenceNotFoundError(f"reference image not found: {path}") from exc
    except PermissionError as exc:
        raise UnreadableReferenceError(f"reference image is not readable: {path}") from exc
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise ReferenceResourceConstrainedError(
            f"reference image exceeds the decode resource limit: {path}"
        ) from exc
    except MemoryError as exc:
        raise ReferenceResourceConstrainedError(
            f"reference image decode exhausted available memory: {path}"
        ) from exc
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError) as exc:
        raise CorruptReferenceError(
            f"reference image is corrupt, truncated, or not a valid image: {path}"
        ) from exc
    return image


def _to_rgb_with_neutral_fill(image: Image.Image) -> Image.Image:
    """Convert to RGB, compositing any alpha channel onto NEUTRAL_FILL_VALUE.

    Applies to RGBA/LA images (an explicit per-pixel alpha channel), and to
    ANY mode carrying a `"transparency"` entry in `image.info` -- not just
    palette ("P") images. A PNG's tRNS chunk can designate a single
    color-key as "transparent" without the image being in RGBA/LA/P mode at
    all: an RGB or grayscale ("L") source can carry a color-keyed tRNS
    chunk and still decode in mode "RGB"/"L", with the key recorded only in
    `image.info["transparency"]` (round 3 finding C1). `Image.convert
    ("RGBA")` honors that color-key entry for RGB/L sources exactly as it
    does the palette-transparency entry for "P" sources -- turning the
    key-colored pixels' alpha to 0 -- so routing all of these through the
    same composite path below is correct with no separate color-key-
    matching logic here. Before this fix, an RGB/L source carrying only
    color-key transparency took the direct `.convert("RGB")` branch and
    exposed its underlying key color instead of the neutral fill (spec.md
    sec 6.2, ledger concept neutral-fill-binding).
    """
    has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
    if not has_alpha:
        return image.convert("RGB")

    rgba = image.convert("RGBA")
    background = Image.new("RGB", rgba.size, _NEUTRAL_FILL_RGB)
    background.paste(rgba, mask=rgba.split()[3])
    return background


def _scale_and_pad(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    """Uniformly scale `image` to fit within (target_width, target_height)
    and center it on a canvas of exactly that size, padded with
    NEUTRAL_FILL_VALUE.

    A single scalar `scale` is computed from both axes and applied to both
    axes identically (AC-PROCESS-1/AC-PROCESS-2: "a scale factor that is
    exactly equal on both axes", "never by resizing an axis
    independently"). Any remainder after that uniform scale -- i.e. the
    gap between the scaled content and the target canvas on whichever axis
    doesn't exactly fill it -- is centered padding.

    Tie-break for an odd pixel of padding: the left/top margin uses floor
    division, so a single extra pixel of remainder (when target minus
    scaled is odd) lands on the right/bottom. Documented here because it
    must be deterministic and reproducible (AC-PROCESS-2), not an
    unspecified accident of rounding.

    Raises:
        NormalizationError: an extreme source aspect ratio (e.g. a
          many-thousand-pixel-wide, few-pixel-tall source scaled into a
          near-square target) rounds one scaled axis down to 0 pixels. A
          content-bearing axis cannot be represented at 0 pixels without
          either silently stretching it back up to 1px (which lies about
          the actual scale factor -- content_aspect_ratio would no longer
          match the pixels produced) or cropping it away entirely; spec.md
          sec 6.2 forbids both ("rather than silently crop, stretch, omit,
          or substitute"), so this is reported as an actionable rejection
          instead.
    """
    source_width, source_height = image.size
    scale = min(target_width / source_width, target_height / source_height)
    scaled_width = round(source_width * scale)
    scaled_height = round(source_height * scale)
    if scaled_width < 1 or scaled_height < 1:
        raise NormalizationError(
            f"reference image {source_width}x{source_height} cannot be scaled "
            f"to fit within the requested {target_width}x{target_height} canvas: "
            f"the extreme aspect ratio would round one axis down to 0 pixels "
            f"(scale factor {scale!r}, computed content size "
            f"{scaled_width}x{scaled_height})"
        )
    resized = image.resize((scaled_width, scaled_height), resample=_RESAMPLE_FILTER)

    canvas = Image.new("RGB", (target_width, target_height), _NEUTRAL_FILL_RGB)
    left = (target_width - scaled_width) // 2
    top = (target_height - scaled_height) // 2
    canvas.paste(resized, (left, top))
    return canvas


def normalize(path: str | Path, target_size: tuple[int, int] | None = None) -> NormalizedReference:
    """Decode and normalize a single reference image.

    `target_size` is optional because spec.md sec 6.2 items 3 and 4 (uniform
    resizing, and reaching a fixed rectangular canvas by centered padding)
    are each conditional -- "when required by the selected model" / "when a
    fixed rectangular tensor is required" -- not unconditional steps. Making
    the parameter required would silently promote both to unconditional,
    which this leaf module has no standing to decide on the spec's behalf.
    `target_size=None` means: apply EXIF orientation, RGB conversion, and
    alpha compositing only -- no scaling, no padding -- returning the image
    at its EXIF-corrected source dimensions. It is also the safer default: a
    forgotten `target_size` argument then yields an unpadded image that S5's
    model-boundary assertion (spec.md sec 6.2, "the guarantee must hold at
    the model boundary") catches loudly, rather than one silently padded to
    a guessed canvas.

    The fact "model X's pipeline accepts reference inputs at dimensions D"
    is owned by `inference` (S5), exposed as a `reference_input_size(...)`
    accessor on the `InferenceEngine` instance per stories.json blocking
    condition S5-BC-1 -- NOT by a slug-keyed table, and NOT by this module
    or S2's `ModelSpec`. `references` does not import `model` or
    `inference` and holds no per-model dimension table of its own; the
    caller (S7's backend lifecycle) is the pass-through conduit that reads
    that accessor and supplies the resulting value here as a plain tuple.

    CONTRACT:
      Inputs:
        - path: local filesystem path to the reference image. Opened
          read-only; never written to, renamed, or relocated (spec.md sec
          6.1).
        - target_size: (width, height) in pixels of the required output
          canvas, or None to skip scaling and padding entirely. When given,
          both elements must be positive integers.
      Outputs:
        - target_size given: NormalizedReference with pixel_data at exactly
          target_size, content_aspect_ratio measured on the pre-scale,
          EXIF-corrected source content, and fill_value ==
          NEUTRAL_FILL_VALUE.
        - target_size is None: NormalizedReference with pixel_data at the
          EXIF-corrected source dimensions (no scaling, no padding);
          width/height equal those dimensions; content_aspect_ratio and
          fill_value as above.
      Raises:
        - UnsupportedExtensionError: path's extension (case-insensitive) is
          not in SUPPORTED_EXTENSIONS.
        - ReferenceNotFoundError: no file exists at path.
        - UnreadableReferenceError: the file exists but cannot be opened.
        - CorruptReferenceError: the file cannot be decoded as a valid
          image (truncated, corrupt, or not an image).
        - ReferenceResourceConstrainedError: decoding was refused by
          Pillow's decompression-bomb guard (either its error tier or its
          warning tier, see `_decode`), or exhausted available memory.
        - NormalizationError: the file decoded successfully but scaling or
          padding to target_size failed -- either an extreme aspect ratio
          rounds a scaled axis down to 0 pixels (see `_scale_and_pad`), or
          the stage ran out of memory. Never raised when target_size is
          None, since no scale/pad stage runs.
        - ValueError: target_size is given and is not a pair of positive
          integers.
      Invariants:
        - Every source pixel's visible contribution is retained: when
          target_size is given, the uniform scale fits the complete source
          content within it on both axes (never crops); when target_size is
          None, the source content passes through unscaled and uncropped.
        - No geometric distortion: scale (when applied) is a single scalar
          applied to both axes (see _scale_and_pad).
        - Deterministic for the same source bytes and target_size,
          independent of available system resources (AC-PROCESS-2).
        - No facial recognition, no subject-dependent crop: this function
          performs only EXIF orientation, RGB conversion, alpha
          compositing, and (when target_size is given) uniform scaling and
          centered padding.
    """
    if target_size is not None:
        target_width, target_height = target_size
        if target_width <= 0 or target_height <= 0:
            raise ValueError(f"target_size must be positive, got {target_size!r}")

    path = Path(path)
    _validate_extension(path)
    image = _decode(path)

    try:
        # exif_transpose() returns None only when called with in_place=True
        # (not the case here), so the returned image is never None.
        image = ImageOps.exif_transpose(image)
        source_width, source_height = image.size
        content_aspect_ratio = source_width / source_height

        rgb_image = _to_rgb_with_neutral_fill(image)
        if target_size is None:
            canvas = rgb_image
            output_width, output_height = source_width, source_height
        else:
            canvas = _scale_and_pad(rgb_image, target_width, target_height)
            output_width, output_height = target_width, target_height
    except MemoryError as exc:
        raise NormalizationError(
            f"reference image could not be normalized within available resources: {path}"
        ) from exc

    return NormalizedReference(
        pixel_data=canvas,
        width=output_width,
        height=output_height,
        content_aspect_ratio=content_aspect_ratio,
        fill_value=NEUTRAL_FILL_VALUE,
        decoded_at=datetime.now(timezone.utc).isoformat(),
    )

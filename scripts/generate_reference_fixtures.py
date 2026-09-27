"""Generate the committed reference-image test fixtures under tests/fixtures/images/.

Run once, by hand, via `uv run python scripts/generate_reference_fixtures.py`, whenever
the fixture set needs to change. Not invoked by the test suite or by application code --
the fixture files it produces are committed to the repository and consumed directly by
tests/test_references.py.

Every "corrupt" fixture here is verified, at generation time, to actually fail to
decode via the real PIL.Image decoder (opened and .load()-ed exactly as
textbrush/references/normalization.py does) -- not merely a file with a misleading
name that a permissive decoder would open successfully (VQ-S3-001, VQ-S3-009).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "images"


def _assert_real_decode_failure(path: Path) -> None:
    """Fail the generation script itself if `path` is NOT a genuine decode failure."""
    try:
        with Image.open(path) as img:
            img.load()
    except Exception:
        return
    raise AssertionError(
        f"fixture {path} was expected to fail real PIL decoding, but it decoded "
        "successfully -- this fixture would not exercise the failure path it is "
        "named for (VQ-S3-001)"
    )


def _assert_real_decode_success(path: Path) -> None:
    with Image.open(path) as img:
        img.load()


def main() -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

    # --- Valid fixtures -----------------------------------------------------

    # Plain landscape RGB JPEG, no EXIF orientation tag.
    landscape = Image.new("RGB", (600, 400), (200, 60, 60))
    landscape.save(FIXTURES_DIR / "valid_landscape.jpg", format="JPEG")

    # Plain portrait RGB PNG, no alpha.
    portrait = Image.new("RGB", (300, 500), (60, 120, 200))
    portrait.save(FIXTURES_DIR / "valid_portrait.png", format="PNG")

    # Square RGB PNG.
    square = Image.new("RGB", (400, 400), (60, 200, 90))
    square.save(FIXTURES_DIR / "valid_square.png", format="PNG")

    # Landscape RGBA WebP (lossless, so the alpha region survives exactly):
    # decoded in memory and composited like a PNG, never converted on disk.
    webp = Image.new("RGBA", (600, 400), (200, 60, 60, 255))
    for x in range(300, 600):
        for y in range(400):
            webp.putpixel((x, y), (0, 0, 255, 0))
    webp.save(FIXTURES_DIR / "valid_landscape_alpha.webp", format="WEBP", lossless=True)

    # RGBA PNG with a genuinely semi-transparent region, for alpha-compositing tests.
    alpha = Image.new("RGBA", (200, 100), (255, 0, 0, 255))
    for x in range(100, 200):
        for y in range(100):
            alpha.putpixel((x, y), (0, 255, 0, 0))  # fully transparent right half
    alpha.save(FIXTURES_DIR / "valid_alpha.png", format="PNG")

    # RGB PNG with tRNS *color-key* transparency (round 3 finding C1): a
    # single designated "transparent" color, recorded only in
    # image.info["transparency"] -- NOT an RGBA/LA/P image with a real
    # per-pixel alpha channel. Left half opaque red; right half the
    # color-keyed "transparent" green, which must composite to the neutral
    # fill exactly like a real alpha channel would.
    colorkey = Image.new("RGB", (200, 100), (255, 0, 0))
    for x in range(100, 200):
        for y in range(100):
            colorkey.putpixel((x, y), (0, 255, 0))
    colorkey.save(
        FIXTURES_DIR / "valid_rgb_colorkey_transparency.png",
        format="PNG",
        transparency=(0, 255, 0),
    )

    # Same-content duplicate of valid_landscape.jpg but with an uppercase extension,
    # as an actual on-disk file (not a lowercased path string built only in a test),
    # for the case-insensitive extension-matching requirement (VQ-S3-006, AC-INPUT-3).
    landscape.save(FIXTURES_DIR / "IMG_1234.JPG", format="JPEG")

    # EXIF-rotated JPEG: stored content is landscape (300x200) but the Orientation
    # tag (6 = rotate 90 CW to display correctly) means the *visible* content is
    # portrait (200x300). Distinct colors per quadrant so orientation errors would
    # be visible under manual inspection.
    exif_source = Image.new("RGB", (300, 200), (0, 0, 0))
    for x in range(300):
        for y in range(200):
            exif_source.putpixel((x, y), (x % 256, y % 256, 128))
    exif_data = Image.Exif()
    exif_data[0x0112] = 6  # Orientation tag: rotate 90 CW
    exif_source.save(
        FIXTURES_DIR / "valid_exif_rotated.jpg", format="JPEG", exif=exif_data.tobytes()
    )

    # --- Unsupported extension (real, decodable image; wrong extension) -----

    unsupported = Image.new("RGB", (100, 100), (10, 10, 10))
    unsupported.save(FIXTURES_DIR / "unsupported_extension.bmp", format="BMP")

    # --- Corrupt / truncated fixtures ---------------------------------------

    # Truncated JPEG: valid header, data cut off mid-scan. Image.open() alone may
    # succeed (PIL is lazy), but .load() must raise -- exactly what normalize()'s
    # decode step guards against.
    full_jpeg_bytes = (FIXTURES_DIR / "valid_landscape.jpg").read_bytes()
    truncated_path = FIXTURES_DIR / "corrupt_truncated.jpg"
    truncated_path.write_bytes(full_jpeg_bytes[: len(full_jpeg_bytes) // 3])

    # Not an image at all, wrong-extension garbage bytes.
    garbage_path = FIXTURES_DIR / "corrupt_not_an_image.png"
    garbage_path.write_bytes(b"this is not image data, just plain text bytes\x00\x01\x02")

    # Zero-byte file with a supported extension.
    empty_path = FIXTURES_DIR / "corrupt_empty.jpg"
    empty_path.write_bytes(b"")

    for path in (truncated_path, garbage_path, empty_path):
        _assert_real_decode_failure(path)

    for path in (
        FIXTURES_DIR / "valid_landscape.jpg",
        FIXTURES_DIR / "valid_portrait.png",
        FIXTURES_DIR / "valid_square.png",
        FIXTURES_DIR / "valid_alpha.png",
        FIXTURES_DIR / "valid_rgb_colorkey_transparency.png",
        FIXTURES_DIR / "IMG_1234.JPG",
        FIXTURES_DIR / "valid_exif_rotated.jpg",
        FIXTURES_DIR / "unsupported_extension.bmp",
    ):
        _assert_real_decode_success(path)

    print(f"Generated fixtures under {FIXTURES_DIR}")
    for path in sorted(FIXTURES_DIR.iterdir()):
        print(f"  {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()

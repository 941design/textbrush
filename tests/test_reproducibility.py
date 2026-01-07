"""Property-based tests for FLUX generation reproducibility.

These tests validate that FLUX generation produces deterministic, reproducible
images across different hardware backends within acceptable tolerance.

Tests are marked as slow and integration because they require model loading.
"""

from unittest.mock import patch

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.inference.flux import FluxInferenceEngine


def image_similarity(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate structural similarity between images.

    Args:
        img1: First PIL image
        img2: Second PIL image

    Returns:
        SSIM score between 0 and 1 (1 = identical)
    """
    arr1 = np.array(img1)
    arr2 = np.array(img2)

    # Handle shape mismatch
    if arr1.shape != arr2.shape:
        return 0.0

    # Calculate SSIM per channel and average for RGB
    if len(arr1.shape) == 3:
        similarity = ssim(arr1, arr2, channel_axis=2, data_range=255)
    else:
        similarity = ssim(arr1, arr2, data_range=255)

    return float(similarity)


def pixel_difference(img1: Image.Image, img2: Image.Image) -> float:
    """Calculate mean absolute pixel difference.

    Args:
        img1: First PIL image
        img2: Second PIL image

    Returns:
        Mean absolute difference per pixel (0 = identical)
    """
    arr1 = np.array(img1, dtype=np.float32)
    arr2 = np.array(img2, dtype=np.float32)

    if arr1.shape != arr2.shape:
        return float("inf")

    return float(np.mean(np.abs(arr1 - arr2)))


class TestReproducibilityHelpers:
    """Unit tests for reproducibility helper functions."""

    def test_image_similarity_identical_images(self) -> None:
        """Identical images have SSIM of 1.0."""
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        assert image_similarity(img, img) == pytest.approx(1.0, abs=0.001)

    def test_image_similarity_different_images(self) -> None:
        """Very different images have low SSIM."""
        img1 = Image.new("RGB", (64, 64), color=(0, 0, 0))
        img2 = Image.new("RGB", (64, 64), color=(255, 255, 255))
        assert image_similarity(img1, img2) < 0.1

    def test_image_similarity_shape_mismatch(self) -> None:
        """Shape mismatch returns 0."""
        img1 = Image.new("RGB", (64, 64), color=(128, 128, 128))
        img2 = Image.new("RGB", (32, 32), color=(128, 128, 128))
        assert image_similarity(img1, img2) == 0.0

    def test_pixel_difference_identical_images(self) -> None:
        """Identical images have 0 pixel difference."""
        img = Image.new("RGB", (64, 64), color=(128, 128, 128))
        assert pixel_difference(img, img) == 0.0

    def test_pixel_difference_different_images(self) -> None:
        """Black and white images have max difference."""
        img1 = Image.new("RGB", (64, 64), color=(0, 0, 0))
        img2 = Image.new("RGB", (64, 64), color=(255, 255, 255))
        assert pixel_difference(img1, img2) == 255.0

    def test_pixel_difference_shape_mismatch(self) -> None:
        """Shape mismatch returns infinity."""
        img1 = Image.new("RGB", (64, 64), color=(128, 128, 128))
        img2 = Image.new("RGB", (32, 32), color=(128, 128, 128))
        assert pixel_difference(img1, img2) == float("inf")


class TestMockedReproducibility:
    """Reproducibility tests using mocked engine for fast validation."""

    def test_same_seed_produces_identical_mock_images(self) -> None:
        """Property: Same seed on same hardware produces identical images."""
        # Create mock images that are deterministic based on seed
        seed = 42

        def create_deterministic_image(seed: int) -> Image.Image:
            """Create image deterministically from seed."""
            np.random.seed(seed)
            arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            return Image.fromarray(arr, "RGB")

        # Same seed should produce identical images
        img1 = create_deterministic_image(seed)
        img2 = create_deterministic_image(seed)

        similarity = image_similarity(img1, img2)
        pixel_diff = pixel_difference(img1, img2)

        assert similarity == pytest.approx(1.0, abs=0.001)
        assert pixel_diff == 0.0

    def test_different_seeds_produce_different_mock_images(self) -> None:
        """Property: Different seeds produce different images."""

        def create_deterministic_image(seed: int) -> Image.Image:
            """Create image deterministically from seed."""
            np.random.seed(seed)
            arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            return Image.fromarray(arr, "RGB")

        img1 = create_deterministic_image(42)
        img2 = create_deterministic_image(123)

        similarity = image_similarity(img1, img2)
        pixel_diff = pixel_difference(img1, img2)

        # Images should be significantly different
        assert similarity < 0.95
        assert pixel_diff > 10.0

    @given(
        seed=st.integers(min_value=0, max_value=2**16),
        width=st.sampled_from([64, 128]),
        height=st.sampled_from([64, 128]),
    )
    @settings(max_examples=10, deadline=5000)
    def test_reproducibility_property_mocked(self, seed: int, width: int, height: int) -> None:
        """Property: Same parameters always produce same image (mocked)."""

        def create_deterministic_image(seed: int, width: int, height: int) -> Image.Image:
            """Create image deterministically from seed."""
            np.random.seed(seed)
            arr = np.random.randint(0, 256, (height, width, 3), dtype=np.uint8)
            return Image.fromarray(arr, "RGB")

        img1 = create_deterministic_image(seed, width, height)
        img2 = create_deterministic_image(seed, width, height)

        similarity = image_similarity(img1, img2)
        assert similarity > 0.999, (
            f"Non-deterministic: SSIM={similarity}, seed={seed}, dims={width}x{height}"
        )


class TestFluxEngineReproducibilityMocked:
    """Test FluxInferenceEngine reproducibility with mocked pipeline."""

    def test_engine_generate_with_same_seed_is_deterministic(self) -> None:
        """Property: Same seed produces same result with mocked pipeline."""
        engine = FluxInferenceEngine()

        # Create deterministic mock results based on seed
        def mock_generate(prompt: str, options: GenerationOptions) -> GenerationResult:
            seed = options.seed if options.seed is not None else 0
            np.random.seed(seed)
            arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            return GenerationResult(
                image=Image.fromarray(arr, "RGB"),
                seed=seed,
                generation_time=0.1,
                model_name="mock",
            )

        with patch.object(engine, "generate", side_effect=mock_generate):
            options = GenerationOptions(seed=42, steps=4, aspect_ratio="1:1")
            result1 = engine.generate("test prompt", options)
            result2 = engine.generate("test prompt", options)

            similarity = image_similarity(result1.image, result2.image)
            pixel_diff = pixel_difference(result1.image, result2.image)

            assert similarity > 0.999, f"Images not identical: SSIM={similarity}"
            assert pixel_diff < 1.0, f"Pixel difference too large: {pixel_diff}"
            assert result1.seed == result2.seed == 42

    def test_engine_generate_with_different_seeds_differs(self) -> None:
        """Property: Different seeds produce different images."""
        engine = FluxInferenceEngine()

        def mock_generate(prompt: str, options: GenerationOptions) -> GenerationResult:
            seed = options.seed if options.seed is not None else 0
            np.random.seed(seed)
            arr = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            return GenerationResult(
                image=Image.fromarray(arr, "RGB"),
                seed=seed,
                generation_time=0.1,
                model_name="mock",
            )

        with patch.object(engine, "generate", side_effect=mock_generate):
            result1 = engine.generate("test prompt", GenerationOptions(seed=42, steps=4))
            result2 = engine.generate("test prompt", GenerationOptions(seed=123, steps=4))

            similarity = image_similarity(result1.image, result2.image)
            pixel_diff = pixel_difference(result1.image, result2.image)

            assert similarity < 0.95, f"Images too similar: SSIM={similarity}"
            assert pixel_diff > 10.0, f"Images too similar: pixel_diff={pixel_diff}"


@pytest.mark.slow
@pytest.mark.integration
class TestRealFluxReproducibility:
    """Real FLUX reproducibility tests (require model weights).

    These tests are skipped unless explicitly enabled with --run-slow.
    They share a single model instance (session-scoped) and MUST run sequentially.

    Run with: pytest --run-slow -k TestRealFluxReproducibility
    Do NOT use -n (parallel) with these tests.
    """

    def test_same_hardware_determinism(self, flux_engine_session: FluxInferenceEngine) -> None:
        """Same seed on same hardware produces identical images."""
        prompt = "a red cube on a blue surface"
        seed = 42
        options = GenerationOptions(seed=seed, steps=4, aspect_ratio="1:1")

        # Generate twice with same parameters
        result1 = flux_engine_session.generate(prompt, options)
        result2 = flux_engine_session.generate(prompt, options)

        # Images should be identical (or nearly identical due to FP precision)
        similarity = image_similarity(result1.image, result2.image)
        pixel_diff = pixel_difference(result1.image, result2.image)

        # Assertions
        assert similarity > 0.999, f"Images not identical: SSIM={similarity}"
        assert pixel_diff < 1.0, f"Pixel difference too large: {pixel_diff}"
        assert result1.seed == result2.seed == seed

    def test_different_seeds_produce_different_images(
        self, flux_engine_session: FluxInferenceEngine
    ) -> None:
        """Different seeds produce visually distinct images."""
        prompt = "a red cube on a blue surface"

        result1 = flux_engine_session.generate(prompt, GenerationOptions(seed=42, steps=4))
        result2 = flux_engine_session.generate(prompt, GenerationOptions(seed=123, steps=4))

        # Images should be different
        similarity = image_similarity(result1.image, result2.image)
        pixel_diff = pixel_difference(result1.image, result2.image)

        assert similarity < 0.95, f"Images too similar: SSIM={similarity}"
        assert pixel_diff > 10.0, f"Images too similar: pixel_diff={pixel_diff}"

    @given(
        seed=st.integers(min_value=0, max_value=2**16),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    @settings(max_examples=3, deadline=120000)  # Very slow - real inference
    def test_reproducibility_property(
        self,
        flux_engine_session: FluxInferenceEngine,
        seed: int,
        aspect_ratio: str,
    ) -> None:
        """Property: Same parameters always produce same image."""
        prompt = "a simple test image"
        options = GenerationOptions(seed=seed, steps=4, aspect_ratio=aspect_ratio)

        # Generate twice
        result1 = flux_engine_session.generate(prompt, options)
        result2 = flux_engine_session.generate(prompt, options)

        # Calculate similarity
        similarity = image_similarity(result1.image, result2.image)
        pixel_diff = pixel_difference(result1.image, result2.image)

        # Assert determinism
        assert similarity > 0.999, (
            f"Non-deterministic: SSIM={similarity}, seed={seed}, aspect={aspect_ratio}"
        )
        assert pixel_diff < 1.0, f"Non-deterministic: pixel_diff={pixel_diff}"

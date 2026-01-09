"""Property-based tests for Backend._save_with_metadata() PNG metadata generation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock

import hypothesis.strategies as st
from hypothesis import given, settings
from PIL import Image, PngImagePlugin

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.config import Config, InferenceConfig, ModelConfig


def create_mock_config():
    """Create a properly structured mock config."""
    mock_config = Mock(spec=Config)
    mock_config.inference = Mock(spec=InferenceConfig)
    mock_config.inference.backend = "flux"
    mock_config.model = Mock(spec=ModelConfig)
    mock_config.model.buffer_size = 8
    return mock_config


@st.composite
def buffered_images_with_generated_dimensions(draw):
    """Generate BufferedImage instances with various dimension combinations."""
    width_base = draw(st.integers(min_value=8, max_value=128))
    height_base = draw(st.integers(min_value=8, max_value=128))
    width = width_base * 8
    height = height_base * 8

    image = Image.new("RGB", (width, height), color="blue")
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    prompt = draw(st.text(min_size=1, max_size=100))
    model_name = draw(st.text(min_size=1, max_size=50))
    aspect_ratio = draw(st.sampled_from(["1:1", "16:9", "9:16"]))

    gen_width_offset = draw(st.integers(min_value=0, max_value=16))
    gen_height_offset = draw(st.integers(min_value=0, max_value=16))
    gen_width = draw(st.none() | st.just((width_base + gen_width_offset) * 16))
    gen_height = draw(st.none() | st.just((height_base + gen_height_offset) * 16))

    return BufferedImage(
        image=image,
        seed=seed,
        prompt=prompt,
        model_name=model_name,
        aspect_ratio=aspect_ratio,
        generated_width=gen_width,
        generated_height=gen_height,
    )


@st.composite
def buffered_images_without_generated_dimensions(draw):
    """Generate BufferedImage instances with None for generated dimensions."""
    width_base = draw(st.integers(min_value=8, max_value=128))
    height_base = draw(st.integers(min_value=8, max_value=128))
    width = width_base * 8
    height = height_base * 8

    image = Image.new("RGB", (width, height), color="red")
    seed = draw(st.integers(min_value=0, max_value=2**32 - 1))
    prompt = draw(st.text(min_size=1, max_size=100))
    model_name = draw(st.text(min_size=1, max_size=50))
    aspect_ratio = draw(st.sampled_from(["1:1", "16:9", "9:16"]))

    return BufferedImage(
        image=image,
        seed=seed,
        prompt=prompt,
        model_name=model_name,
        aspect_ratio=aspect_ratio,
        generated_width=None,
        generated_height=None,
    )


class TestPNGMetadataGeneration:
    """Property-based tests for PNG metadata including generated dimensions."""

    @given(buffered_image=buffered_images_with_generated_dimensions())
    @settings(max_examples=20, deadline=None)
    def test_png_metadata_includes_generated_dimensions(self, buffered_image):
        """PNG metadata contains GeneratedWidth/GeneratedHeight when not None."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            backend._save_with_metadata(buffered_image, output_path)

            img = Image.open(output_path)
            assert isinstance(img, PngImagePlugin.PngImageFile)
            metadata = img.text

            width, height = buffered_image.image.size
            assert metadata["Width"] == str(width)
            assert metadata["Height"] == str(height)
            assert metadata["AspectRatio"] == buffered_image.aspect_ratio
            assert metadata["Prompt"] == buffered_image.prompt
            assert metadata["Model"] == buffered_image.model_name
            assert metadata["Seed"] == str(buffered_image.seed)

            if buffered_image.generated_width is not None:
                assert "GeneratedWidth" in metadata
                assert metadata["GeneratedWidth"] == str(buffered_image.generated_width)

            if buffered_image.generated_height is not None:
                assert "GeneratedHeight" in metadata
                assert metadata["GeneratedHeight"] == str(buffered_image.generated_height)
        finally:
            output_path.unlink(missing_ok=True)

    @given(buffered_image=buffered_images_without_generated_dimensions())
    @settings(max_examples=20, deadline=None)
    def test_png_metadata_omits_none_generated_dimensions(self, buffered_image):
        """PNG metadata omits GeneratedWidth/GeneratedHeight when None."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            backend._save_with_metadata(buffered_image, output_path)

            img = Image.open(output_path)
            assert isinstance(img, PngImagePlugin.PngImageFile)
            metadata = img.text

            assert "GeneratedWidth" not in metadata
            assert "GeneratedHeight" not in metadata

            assert "Width" in metadata
            assert "Height" in metadata
            assert "AspectRatio" in metadata
            assert "Prompt" in metadata
            assert "Model" in metadata
            assert "Seed" in metadata
        finally:
            output_path.unlink(missing_ok=True)

    @given(buffered_image=buffered_images_with_generated_dimensions())
    @settings(max_examples=20, deadline=None)
    def test_metadata_roundtrip_preserves_generated_dimensions(self, buffered_image):
        """Save and load preserves generated dimension metadata."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            backend._save_with_metadata(buffered_image, output_path)

            img = Image.open(output_path)
            assert isinstance(img, PngImagePlugin.PngImageFile)
            metadata = img.text

            if buffered_image.generated_width is not None:
                assert int(metadata["GeneratedWidth"]) == buffered_image.generated_width

            if buffered_image.generated_height is not None:
                assert int(metadata["GeneratedHeight"]) == buffered_image.generated_height

            width, height = buffered_image.image.size
            assert int(metadata["Width"]) == width
            assert int(metadata["Height"]) == height
        finally:
            output_path.unlink(missing_ok=True)


    @given(buffered_image=buffered_images_with_generated_dimensions())
    @settings(max_examples=20, deadline=None)
    def test_generated_dimensions_are_multiples_of_16(self, buffered_image):
        """Generated dimensions in metadata are multiples of 16 when present."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            backend._save_with_metadata(buffered_image, output_path)

            img = Image.open(output_path)
            assert isinstance(img, PngImagePlugin.PngImageFile)
            metadata = img.text

            if "GeneratedWidth" in metadata:
                gen_width = int(metadata["GeneratedWidth"])
                assert gen_width % 16 == 0

            if "GeneratedHeight" in metadata:
                gen_height = int(metadata["GeneratedHeight"])
                assert gen_height % 16 == 0
        finally:
            output_path.unlink(missing_ok=True)


class TestJPEGMetadataHandling:
    """Verify JPEG handling remains unchanged."""

    @given(buffered_image=buffered_images_with_generated_dimensions())
    @settings(max_examples=10, deadline=None)
    def test_jpeg_saves_without_custom_metadata(self, buffered_image):
        """JPEG format saves without custom metadata regardless of generated dimensions."""
        mock_config = create_mock_config()
        backend = TextbrushBackend(mock_config)

        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            output_path = Path(tmp.name)

        try:
            backend._save_with_metadata(buffered_image, output_path)

            assert output_path.exists()
            img = Image.open(output_path)
            assert img.format == "JPEG"
        finally:
            output_path.unlink(missing_ok=True)

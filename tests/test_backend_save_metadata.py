"""Property-based tests for Backend._save_with_metadata() PNG metadata generation."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import hypothesis.strategies as st
from hypothesis import given, settings
from PIL import Image, PngImagePlugin

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.config import (
    Config,
    HuggingFaceConfig,
    InferenceConfig,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)
from textbrush.model.registry import (
    FLUX1_SCHNELL,
    get_repo_id,
)


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


class TestAcceptedImageMetadata:
    """T06 (AC-META-1): the accepted-image PNG key set is closed.
    `Model` equals the active model's HuggingFace repo id, not the
    short slug. The `model_id` and `reference_ids` provenance fields on
    `BufferedImage` (T05) are never written into the output file."""

    @staticmethod
    def _factory_with_mock(model_id):
        from tests.mocks import MockInferenceEngine
        from textbrush.validation import is_editing_model

        canvas = (768, 576) if is_editing_model(model_id) else None
        eng = MockInferenceEngine(reference_canvas=canvas)
        eng.model_id = model_id
        return eng

    def _run_full_cycle(self, tmp_path: Path, model_id: str) -> dict:
        """Acknowledge + generate + accept one image; return the metadata dict."""
        side_effect_calls = []

        def factory(backend, slug):
            side_effect_calls.append(slug)
            return self._factory_with_mock(slug)

        config = Config(
            output=OutputConfig(directory=tmp_path / "out", format="png"),
            model=ModelConfig(directories=[], buffer_size=8, selected_id=None),
            huggingface=HuggingFaceConfig(token=None),
            inference=InferenceConfig(backend="flux"),
            logging=LoggingConfig(verbosity="info"),
        )
        backend = TextbrushBackend(config)
        backend.initialize()

        if model_id != FLUX1_SCHNELL:
            backend.apply_configuration(
                model_id=model_id,
                reference_paths=[
                    str(Path(__file__).parent / "fixtures" / "images" / "valid_square.png")
                ],
                preset="landscape-medium",
            )
        backend.start_generation(prompt="a prompt", seed=0)
        import time as _time

        _time.sleep(0.2)
        backend.get_next_image(timeout=2.0)
        output_path = tmp_path / "out" / "result.png"
        backend.accept_current(output_path=output_path)
        backend.shutdown()
        return {"output_path": output_path, "side_effect_calls": side_effect_calls}

    def test_png_keys_match_closed_set_for_schnell(self, tmp_path: Path) -> None:
        (tmp_path / "out").mkdir(parents=True, exist_ok=True)
        config = Config(
            output=OutputConfig(directory=tmp_path / "out", format="png"),
            model=ModelConfig(directories=[], buffer_size=8, selected_id=None),
            huggingface=HuggingFaceConfig(token=None),
            inference=InferenceConfig(backend="flux"),
            logging=LoggingConfig(verbosity="info"),
        )
        with patch(
            "textbrush.backend.create_engine", return_value=self._factory_with_mock(FLUX1_SCHNELL)
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.start_generation(prompt="a prompt", seed=0)
            import time as _time

            _time.sleep(0.2)
            backend.get_next_image(timeout=2.0)
            output_path = tmp_path / "out" / "result.png"
            backend.accept_current(output_path=output_path)
            backend.shutdown()

        img = Image.open(output_path)
        keys = set(img.text.keys())
        # The closed key set. GeneratedWidth/GeneratedHeight are
        # emitted whenever the engine records them on the buffered
        # image; the mock engine does, so they are present.
        expected = {
            "AspectRatio",
            "Width",
            "Height",
            "Prompt",
            "Model",
            "Seed",
            "GeneratedWidth",
            "GeneratedHeight",
        }
        assert keys == expected
        assert img.text["Model"] == get_repo_id(FLUX1_SCHNELL)

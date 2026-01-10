"""Property-based tests for TextbrushBackend._generate_output_path()."""

import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock

import hypothesis.strategies as st
from hypothesis import given, settings
from PIL import Image

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.config import Config, InferenceConfig, OutputConfig


def create_test_backend(output_dir: Path, output_format: str) -> TextbrushBackend:
    """Create a minimal TextbrushBackend for testing _generate_output_path."""
    config = Mock(spec=Config)
    config.output = OutputConfig(directory=output_dir, format=output_format)
    config.model = Mock()
    config.model.buffer_size = 8
    config.inference = InferenceConfig(backend="flux")

    backend = Mock(spec=TextbrushBackend)
    backend.config = config
    backend.buffer = Mock()
    backend._generate_output_path = TextbrushBackend._generate_output_path.__get__(
        backend, TextbrushBackend
    )

    return backend


class TestGenerateOutputPathProperties:
    """Property-based tests for _generate_output_path()."""

    @given(
        output_format=st.sampled_from(["png", "jpg", "jpeg", "webp", "bmp"]),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_path_in_output_directory(self, output_format: str, seed: int):
        """Generated path is in config.output.directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=seed)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert result_path.parent == output_dir
            assert result_path.is_relative_to(output_dir)

    @given(
        output_format=st.sampled_from(["png", "jpg", "jpeg", "webp", "bmp"]),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_extension_matches_format(self, output_format: str, seed: int):
        """File extension matches config.output.format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=seed)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert result_path.suffix == f".{output_format}"

    @given(
        output_format=st.sampled_from(["png", "jpg"]),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_filename_is_uuid(self, output_format: str, seed: int):
        """Filename is a valid UUID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=seed)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            # Filename without extension should be a valid UUID
            filename_without_ext = result_path.stem
            uuid.UUID(filename_without_ext)  # Raises ValueError if not valid UUID

    @given(
        output_format=st.sampled_from(["png", "jpg"]),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_creates_output_directory(self, output_format: str, seed: int):
        """Output directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "nested" / "output" / "dir"
            assert not output_dir.exists()

            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=seed)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert output_dir.exists()
            assert output_dir.is_dir()
            assert result_path.parent == output_dir

    @given(
        output_format=st.sampled_from(["png", "jpg"]),
    )
    @settings(max_examples=10)
    def test_uuid_when_buffer_empty(self, output_format: str):
        """Filename is UUID when buffer is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, output_format)
            backend.buffer.peek.return_value = None

            result_path = backend._generate_output_path()

            # Filename without extension should be a valid UUID
            filename_without_ext = result_path.stem
            uuid.UUID(filename_without_ext)  # Raises ValueError if not valid UUID
            assert result_path.suffix == f".{output_format}"

    @given(
        output_format=st.sampled_from(["png", "jpg"]),
        seed1=st.integers(min_value=0, max_value=2**31 - 1),
        seed2=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_multiple_calls_produce_different_filenames(
        self, output_format: str, seed1: int, seed2: int
    ):
        """Multiple calls produce different filenames (UUIDs are unique)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))

            buffered_image1 = BufferedImage(image=image, seed=seed1)
            backend.buffer.peek.return_value = buffered_image1
            path1 = backend._generate_output_path()

            buffered_image2 = BufferedImage(image=image, seed=seed2)
            backend.buffer.peek.return_value = buffered_image2
            path2 = backend._generate_output_path()

            assert path1.name != path2.name

    @given(
        output_format=st.sampled_from(["png", "jpg", "jpeg", "webp", "bmp"]),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=10)
    def test_path_is_absolute(self, output_format: str, seed: int):
        """Generated path is absolute."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir).resolve()
            backend = create_test_backend(output_dir, output_format)

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=seed)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert result_path.is_absolute()


class TestGenerateOutputPathExamples:
    """Example-based tests for edge cases and specific scenarios."""

    def test_zero_seed(self):
        """Handles seed value of zero correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, "png")

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=0)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            # Filename without extension should be a valid UUID
            filename_without_ext = result_path.stem
            uuid.UUID(filename_without_ext)  # Raises ValueError if not valid UUID
            assert result_path.suffix == ".png"

    def test_large_seed(self):
        """Handles large seed values correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, "jpg")

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=2147483647)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            # Filename without extension should be a valid UUID
            filename_without_ext = result_path.stem
            uuid.UUID(filename_without_ext)  # Raises ValueError if not valid UUID
            assert result_path.suffix == ".jpg"

    def test_special_characters_in_format(self):
        """Handles format string as-is without validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            backend = create_test_backend(output_dir, "png")

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=12345)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert result_path.suffix == ".png"
            assert result_path.parent == output_dir

    def test_directory_exists_already(self):
        """Handles case where output directory already exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "existing"
            output_dir.mkdir(parents=True)

            backend = create_test_backend(output_dir, "png")

            image = Image.new("RGB", (64, 64))
            buffered_image = BufferedImage(image=image, seed=42)
            backend.buffer.peek.return_value = buffered_image

            result_path = backend._generate_output_path()

            assert result_path.parent == output_dir
            # Filename without extension should be a valid UUID
            filename_without_ext = result_path.stem
            uuid.UUID(filename_without_ext)  # Raises ValueError if not valid UUID

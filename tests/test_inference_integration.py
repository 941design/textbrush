"""Integration tests for inference backend.

Tests complete workflows across multiple components: Engine → Worker → Buffer → Backend.
"""

import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

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
from textbrush.inference.flux import FluxInferenceEngine


def create_test_config(tmpdir: Path) -> Config:
    """Create minimal config for testing."""
    return Config(
        output=OutputConfig(directory=tmpdir, format="png"),
        model=ModelConfig(directories=[], buffer_size=8),
        huggingface=HuggingFaceConfig(token=None),
        inference=InferenceConfig(backend="flux"),
        logging=LoggingConfig(verbosity="info"),
    )


class MockFluxPipeline:
    """Mock FLUX pipeline for testing without model loading."""

    def __init__(self, *args, **kwargs):
        self.device = "cpu"
        self.last_requested_width = None
        self.last_requested_height = None

    def __call__(self, prompt, width, height, num_inference_steps, generator):
        """Generate small mock image, recording requested dimensions for contract verification."""
        self.last_requested_width = width
        self.last_requested_height = height
        # Use small 64x64 image regardless of requested size (resource efficient)
        image = Image.new("RGB", (64, 64), color="blue")
        return Mock(images=[image])

    def to(self, device):
        """Mock to() method."""
        self.device = device
        return self

    def enable_model_cpu_offload(self):
        """Mock CPU offload."""
        pass


@pytest.fixture
def mock_flux_pipeline():
    """Fixture to mock FluxPipeline.from_pretrained.

    The mock instance is accessible via mock_pipeline_class.from_pretrained.return_value
    to verify requested dimensions in contract tests.
    """
    with patch("textbrush.inference.flux.FluxPipeline") as mock_pipeline_class:
        mock_instance = MockFluxPipeline()
        mock_pipeline_class.from_pretrained.return_value = mock_instance
        yield mock_pipeline_class


@pytest.mark.integration
class TestEndToEndImageGeneration:
    """Test complete pipeline from initialization to image retrieval."""

    def test_backend_initializes_and_generates(self, mock_flux_pipeline, tmp_path):
        """Backend → Engine.load() → Worker → Buffer → get_next_image() produces image."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        assert backend.engine.is_loaded()

        backend.start_generation(prompt="a cat", seed=42, aspect_ratio="1:1")

        image = backend.get_next_image()
        assert image is not None
        assert isinstance(image, BufferedImage)
        # Verify contract: engine requested correct dimensions for 1:1 aspect ratio
        mock_instance = mock_flux_pipeline.from_pretrained.return_value
        requested = (mock_instance.last_requested_width, mock_instance.last_requested_height)
        assert requested == (1024, 1024)

        backend.shutdown()

    def test_backend_produces_multiple_images_fifo(self, mock_flux_pipeline, tmp_path):
        """Worker generates multiple images, buffer maintains FIFO order."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=100, aspect_ratio="1:1")

        images = [backend.get_next_image() for _ in range(3)]

        assert all(img is not None for img in images)
        assert images[0].seed == 100
        assert images[1].seed == 101
        assert images[2].seed == 102

        backend.shutdown()

    def test_buffer_blocks_when_empty(self, mock_flux_pipeline, tmp_path):
        """get_next_image() blocks until worker generates image."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()

        buffer_empty = backend.buffer.peek() is None
        assert buffer_empty

        backend.start_generation(prompt="test", seed=50, aspect_ratio="1:1")

        start_time = time.perf_counter()
        image = backend.get_next_image()
        elapsed = time.perf_counter() - start_time

        assert image is not None
        assert elapsed > 0

        backend.shutdown()

    def test_abort_stops_generation_and_clears_buffer(self, mock_flux_pipeline, tmp_path):
        """abort() stops worker and clears all buffered images."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=200, aspect_ratio="1:1")

        time.sleep(0.2)

        backend.abort()

        assert len(backend.buffer) == 0

    def test_shutdown_releases_resources(self, mock_flux_pipeline, tmp_path):
        """shutdown() stops worker, clears buffer, unloads model."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        assert backend.engine.is_loaded()

        backend.start_generation(prompt="test", seed=300, aspect_ratio="1:1")
        time.sleep(0.1)

        backend.shutdown()

        assert not backend.engine.is_loaded()
        assert len(backend.buffer) == 0


@pytest.mark.integration
class TestAspectRatioMapping:
    """Test aspect ratio dimensions across engine and worker."""

    @pytest.mark.parametrize(
        "aspect_ratio,expected_size",
        [
            ("1:1", (1024, 1024)),
            ("16:9", (1280, 720)),
            ("9:16", (720, 1280)),
        ],
    )
    def test_aspect_ratio_produces_correct_dimensions(
        self, mock_flux_pipeline, tmp_path, aspect_ratio, expected_size
    ):
        """Engine requests correct dimensions for each aspect ratio."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=400, aspect_ratio=aspect_ratio)

        image = backend.get_next_image()

        assert image is not None
        # Verify contract: engine requested correct dimensions
        mock_instance = mock_flux_pipeline.from_pretrained.return_value
        requested = (mock_instance.last_requested_width, mock_instance.last_requested_height)
        assert requested == expected_size

        backend.shutdown()


@pytest.mark.integration
class TestBufferWorkerInteraction:
    """Test worker and buffer interaction properties."""

    def test_worker_respects_buffer_capacity(self, mock_flux_pipeline, tmp_path):
        """Worker blocks when buffer is full."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=500, aspect_ratio="1:1")

        time.sleep(0.3)

        buffer_size = len(backend.buffer)
        assert buffer_size <= backend.config.model.buffer_size

        backend.shutdown()

    def test_buffer_fifo_under_concurrent_access(self, mock_flux_pipeline, tmp_path):
        """Buffer maintains FIFO even with concurrent put/get."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=600, aspect_ratio="1:1")

        retrieved_seeds = []

        def consumer():
            for _ in range(5):
                img = backend.get_next_image()
                if img:
                    retrieved_seeds.append(img.seed)

        consumer_thread = threading.Thread(target=consumer)
        consumer_thread.start()
        consumer_thread.join(timeout=3.0)

        assert len(retrieved_seeds) == 5
        assert retrieved_seeds == [600, 601, 602, 603, 604]

        backend.shutdown()


@pytest.mark.integration
class TestImageAcceptance:
    """Test accept_current() workflow."""

    def test_accept_saves_current_image(self, mock_flux_pipeline, tmp_path):
        """accept_current() saves current image without removing from buffer."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=700, aspect_ratio="1:1")

        time.sleep(0.1)

        current = backend.buffer.peek()
        assert current is not None

        output_path = tmp_path / "test_output.png"
        saved_path = backend.accept_current(output_path=output_path)

        assert saved_path == output_path
        assert output_path.exists()

        still_in_buffer = backend.buffer.peek()
        assert still_in_buffer is not None
        assert still_in_buffer.seed == current.seed

        backend.shutdown()

    def test_accept_auto_generates_path(self, mock_flux_pipeline, tmp_path):
        """accept_current() without path generates UUID-based filename."""
        import re

        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=800, aspect_ratio="1:1")

        time.sleep(0.1)

        saved_path = backend.accept_current()

        assert saved_path.parent == config.output.directory
        # UUID format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
        uuid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        stem = saved_path.stem
        assert re.match(uuid_pattern, stem), f"Expected UUID filename, got: {stem}"
        assert saved_path.suffix == ".png"
        assert saved_path.exists()

        backend.shutdown()

    def test_accept_raises_when_no_image(self, mock_flux_pipeline, tmp_path):
        """accept_current() raises RuntimeError when buffer empty."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()

        with pytest.raises(RuntimeError, match="No image to accept"):
            backend.accept_current()

        backend.shutdown()


@pytest.mark.integration
class TestEngineWorkerCoordination:
    """Test engine and worker coordination."""

    def test_worker_increments_seed(self, mock_flux_pipeline, tmp_path):
        """Worker increments seed for each generation."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=1000, aspect_ratio="1:1")

        seeds = []
        for _ in range(4):
            img = backend.get_next_image()
            if img:
                seeds.append(img.seed)

        assert seeds == [1000, 1001, 1002, 1003]

        backend.shutdown()

    def test_worker_stops_on_abort(self, mock_flux_pipeline, tmp_path):
        """Worker thread stops when abort() is called."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        backend.initialize()
        backend.start_generation(prompt="test", seed=1100, aspect_ratio="1:1")

        time.sleep(0.2)

        initial_thread_count = threading.active_count()

        backend.abort()

        time.sleep(0.3)

        final_thread_count = threading.active_count()
        assert final_thread_count <= initial_thread_count

        backend.shutdown()


@pytest.mark.integration
class TestFactoryIntegration:
    """Test factory creates correct engine."""

    def test_factory_creates_flux_engine(self, mock_flux_pipeline, tmp_path):
        """create_engine('flux') returns FluxInferenceEngine."""
        config = create_test_config(tmp_path)
        backend = TextbrushBackend(config)

        assert isinstance(backend.engine, FluxInferenceEngine)

    def test_backend_uses_factory(self, mock_flux_pipeline, tmp_path):
        """Backend uses factory to create engine based on config."""
        config = create_test_config(tmp_path)
        config.inference.backend = "flux"

        backend = TextbrushBackend(config)

        assert backend.engine is not None
        assert not backend.engine.is_loaded()

        backend.initialize()
        assert backend.engine.is_loaded()

        backend.shutdown()

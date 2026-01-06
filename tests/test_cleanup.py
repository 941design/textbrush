"""Property-based tests for BufferedImage cleanup and timeout functionality."""

import tempfile
import time
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st
from PIL import Image

from textbrush.buffer import BufferedImage, ImageBuffer


class TestBufferedImageCleanup:
    """Tests for BufferedImage.cleanup() method."""

    def test_cleanup_deletes_existing_temp_file(self):
        """Property: cleanup() deletes temp file if it exists."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)

        temp_path.write_text("test content")
        assert temp_path.exists()

        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=temp_path)

        buffered_img.cleanup()

        assert not temp_path.exists()

    def test_cleanup_with_none_temp_path_is_safe(self):
        """Property: cleanup() with temp_path=None does not raise error."""
        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=None)

        buffered_img.cleanup()

    def test_cleanup_with_nonexistent_file_is_safe(self):
        """Property: cleanup() with non-existent file does not raise error."""
        nonexistent_path = Path("/tmp/nonexistent_file_12345.png")
        assert not nonexistent_path.exists()

        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=nonexistent_path)

        buffered_img.cleanup()

    def test_cleanup_is_idempotent(self):
        """Property: cleanup() can be called multiple times safely."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)

        temp_path.write_text("test content")

        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=temp_path)

        buffered_img.cleanup()
        assert not temp_path.exists()

        buffered_img.cleanup()
        buffered_img.cleanup()


class TestBufferedImageContextManager:
    """Tests for BufferedImage context manager support."""

    def test_context_manager_cleans_up_temp_file(self):
        """Property: with statement calls cleanup() on exit."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)

        temp_path.write_text("test content")
        assert temp_path.exists()

        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=temp_path)

        with buffered_img:
            assert temp_path.exists()

        assert not temp_path.exists()

    def test_context_manager_cleans_up_on_exception(self):
        """Property: context manager calls cleanup() even if exception raised."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)

        temp_path.write_text("test content")

        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=temp_path)

        try:
            with buffered_img:
                assert temp_path.exists()
                raise ValueError("Test exception")
        except ValueError:
            pass

        assert not temp_path.exists()

    def test_context_manager_returns_self(self):
        """Property: __enter__ returns the BufferedImage instance."""
        img = Image.new("RGB", (10, 10))
        buffered_img = BufferedImage(image=img, seed=123, temp_path=None)

        with buffered_img as ctx_img:
            assert ctx_img is buffered_img


class TestImageBufferClearCleanup:
    """Tests for ImageBuffer.clear() cleanup behavior."""

    def test_clear_calls_cleanup_on_all_items(self):
        """Property: buffer.clear() deletes temp files of all items."""
        temp_paths = []
        for _ in range(3):
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_path = Path(tmp.name)
                temp_path.write_text("test")
                temp_paths.append(temp_path)

        buffer = ImageBuffer(max_size=5)

        for i, temp_path in enumerate(temp_paths):
            img = BufferedImage(image=Image.new("RGB", (10, 10)), seed=i, temp_path=temp_path)
            buffer.put(img)

        for temp_path in temp_paths:
            assert temp_path.exists()

        buffer.clear()

        for temp_path in temp_paths:
            assert not temp_path.exists()

    def test_clear_returns_items_before_cleanup(self):
        """Property: clear() returns items even though temp files are cleaned up."""
        temp_paths = []
        for _ in range(2):
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                temp_path = Path(tmp.name)
                temp_path.write_text("test")
                temp_paths.append(temp_path)

        buffer = ImageBuffer(max_size=5)

        for i, temp_path in enumerate(temp_paths):
            img = BufferedImage(image=Image.new("RGB", (10, 10)), seed=i, temp_path=temp_path)
            buffer.put(img)

        items = buffer.clear()

        assert len(items) == 2
        assert items[0].seed == 0
        assert items[1].seed == 1

        for temp_path in temp_paths:
            assert not temp_path.exists()

    def test_clear_handles_items_without_temp_path(self):
        """Property: clear() safely handles items with temp_path=None."""
        buffer = ImageBuffer(max_size=5)

        for i in range(3):
            img = BufferedImage(image=Image.new("RGB", (10, 10)), seed=i, temp_path=None)
            buffer.put(img)

        items = buffer.clear()

        assert len(items) == 3

    def test_clear_handles_mixed_items(self):
        """Property: clear() handles mix of items with and without temp files."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            temp_path = Path(tmp.name)
            temp_path.write_text("test")

        buffer = ImageBuffer(max_size=5)

        buffer.put(BufferedImage(image=Image.new("RGB", (10, 10)), seed=1, temp_path=None))
        buffer.put(BufferedImage(image=Image.new("RGB", (10, 10)), seed=2, temp_path=temp_path))
        buffer.put(BufferedImage(image=Image.new("RGB", (10, 10)), seed=3, temp_path=None))

        assert temp_path.exists()

        items = buffer.clear()

        assert len(items) == 3
        assert not temp_path.exists()


class TestImageBufferGetTimeout:
    """Tests for ImageBuffer.get() timeout behavior."""

    @given(st.floats(min_value=0.01, max_value=0.2))
    def test_get_respects_timeout(self, timeout):
        """Property: get() returns None when timeout expires."""
        buffer = ImageBuffer(max_size=1)

        start = time.time()
        result = buffer.get(timeout=timeout)
        elapsed = time.time() - start

        assert result is None
        assert timeout * 0.8 < elapsed < timeout * 2.5

    def test_get_with_default_timeout_returns_none_on_empty(self):
        """Example: get() with default timeout returns None on empty buffer."""
        buffer = ImageBuffer(max_size=1)

        start = time.time()
        result = buffer.get(timeout=0.1)
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 0.3

    def test_get_with_none_timeout_blocks_until_item(self):
        """Property: get(timeout=None) waits indefinitely until item available."""
        buffer = ImageBuffer(max_size=1)
        item = BufferedImage(image=Image.new("RGB", (10, 10)), seed=999, temp_path=None)

        retrieved_item = []

        def consumer():
            result = buffer.get(timeout=None)
            retrieved_item.append(result)

        import threading

        consumer_thread = threading.Thread(target=consumer, daemon=True)
        consumer_thread.start()

        time.sleep(0.05)
        assert len(retrieved_item) == 0

        with buffer._not_empty:
            buffer._buffer.append(item)
            buffer._not_empty.notify()

        consumer_thread.join(timeout=0.5)
        assert len(retrieved_item) == 1
        assert retrieved_item[0] is item


class TestBackendTimeouts:
    """Integration tests for backend timeout functionality."""

    @staticmethod
    def create_mock_config():
        """Create a properly structured mock config for testing."""
        from unittest.mock import Mock

        from textbrush.config import Config, InferenceConfig, ModelConfig

        mock_config = Mock(spec=Config)
        mock_config.inference = Mock(spec=InferenceConfig)
        mock_config.inference.backend = "flux"
        mock_config.model = Mock(spec=ModelConfig)
        mock_config.model.buffer_size = 8
        return mock_config

    def test_backend_get_next_image_has_default_timeout(self):
        """Property: get_next_image() has 30 second default timeout."""
        from textbrush.backend import TextbrushBackend

        config = self.create_mock_config()
        backend = TextbrushBackend(config)

        start = time.time()
        result = backend.get_next_image(timeout=0.05)
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 0.2

    def test_backend_skip_current_has_default_timeout(self):
        """Property: skip_current() has 30 second default timeout."""
        from textbrush.backend import TextbrushBackend

        config = self.create_mock_config()
        backend = TextbrushBackend(config)

        start = time.time()
        result = backend.skip_current(timeout=0.05)
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 0.2

    def test_backend_methods_accept_none_timeout(self):
        """Property: backend methods accept timeout=None for indefinite wait."""
        import threading

        from textbrush.backend import TextbrushBackend

        config = self.create_mock_config()
        backend = TextbrushBackend(config)

        retrieved = []

        def consumer():
            result = backend.get_next_image(timeout=None)
            retrieved.append(result)

        consumer_thread = threading.Thread(target=consumer, daemon=True)
        consumer_thread.start()

        time.sleep(0.05)

        backend.buffer.shutdown(grace_period=0.0)

        consumer_thread.join(timeout=0.5)
        assert len(retrieved) == 1
        assert retrieved[0] is None

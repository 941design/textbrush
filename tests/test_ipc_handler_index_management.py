"""Property-based tests for IPC handler index management methods."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from textbrush.buffer import BufferedImage
from textbrush.config import Config, get_default_config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType


@pytest.fixture
def config() -> Config:
    """Create test configuration."""
    return get_default_config()


@pytest.fixture
def mock_server():
    """Create mock IPC server."""
    server = Mock()
    server.send = Mock()
    server.shutdown = Mock()
    return server


@pytest.fixture
def handler(config):
    """Create message handler with test config."""
    return MessageHandler(config)


def create_test_buffered_image(seed: int = 12345, temp_path: Path | None = None) -> BufferedImage:
    """Create a test BufferedImage instance."""
    image = Image.new("RGB", (128, 128), color=(100, 150, 200))
    return BufferedImage(
        image=image,
        seed=seed,
        temp_path=temp_path,
        prompt="test prompt",
        model_name="test_model",
        aspect_ratio="1:1",
    )


class TestAssignImageIndex:
    """Property-based tests for _assign_image_index method."""

    def test_index_starts_at_zero(self, handler):
        """First assigned index is 0."""
        buffered = create_test_buffered_image()
        index = handler._assign_image_index(buffered)
        assert index == 0

    @given(st.integers(min_value=1, max_value=100))
    @settings(deadline=None)
    def test_index_uniqueness(self, num_images):
        """All assigned indices are unique."""
        handler = MessageHandler(get_default_config())
        indices = []

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            index = handler._assign_image_index(buffered)
            indices.append(index)

        assert len(indices) == len(set(indices))

    @given(st.integers(min_value=1, max_value=100))
    @settings(deadline=None)
    def test_index_monotonicity(self, num_images):
        """Indices are strictly monotonically increasing."""
        handler = MessageHandler(get_default_config())
        indices = []

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            index = handler._assign_image_index(buffered)
            indices.append(index)

        for i in range(len(indices) - 1):
            assert indices[i] < indices[i + 1]
            assert indices[i + 1] == indices[i] + 1

    @given(st.integers(min_value=1, max_value=100))
    @settings(deadline=None)
    def test_index_sequential(self, num_images):
        """Indices form a sequential series 0, 1, 2, ..., n-1."""
        handler = MessageHandler(get_default_config())
        indices = []

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            index = handler._assign_image_index(buffered)
            indices.append(index)

        assert indices == list(range(num_images))

    def test_index_stored_in_map(self, handler):
        """Assigned index creates entry in _image_index_map."""
        buffered = create_test_buffered_image()
        index = handler._assign_image_index(buffered)

        assert index in handler._image_index_map
        assert handler._image_index_map[index] is buffered

    @given(st.integers(min_value=1, max_value=50))
    @settings(deadline=None)
    def test_all_images_stored_in_map(self, num_images):
        """All assigned images are stored in index map."""
        handler = MessageHandler(get_default_config())
        buffered_images = []

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            buffered_images.append(buffered)
            index = handler._assign_image_index(buffered)
            assert handler._image_index_map[index] is buffered

        assert len(handler._image_index_map) == num_images

    def test_next_index_increments(self, handler):
        """_next_index increments after each assignment."""
        assert handler._next_index == 0

        buffered1 = create_test_buffered_image(seed=1)
        handler._assign_image_index(buffered1)
        assert handler._next_index == 1

        buffered2 = create_test_buffered_image(seed=2)
        handler._assign_image_index(buffered2)
        assert handler._next_index == 2

        buffered3 = create_test_buffered_image(seed=3)
        handler._assign_image_index(buffered3)
        assert handler._next_index == 3


class TestAssignImageIndexThreadSafety:
    """Property-based tests for thread safety of _assign_image_index."""

    @given(
        num_threads=st.integers(min_value=2, max_value=10),
        images_per_thread=st.integers(min_value=1, max_value=20),
    )
    @settings(deadline=None, max_examples=20)
    def test_concurrent_assignments_no_collision(self, num_threads, images_per_thread):
        """Concurrent index assignments produce unique indices."""
        handler = MessageHandler(get_default_config())
        all_indices = []
        lock = threading.Lock()
        barrier = threading.Barrier(num_threads)

        def assign_indices(thread_id: int):
            barrier.wait()
            for i in range(images_per_thread):
                buffered = create_test_buffered_image(seed=thread_id * 1000 + i)
                index = handler._assign_image_index(buffered)
                with lock:
                    all_indices.append(index)

        threads = []
        for t in range(num_threads):
            thread = threading.Thread(target=assign_indices, args=(t,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(all_indices) == num_threads * images_per_thread
        assert len(all_indices) == len(set(all_indices))

    @given(
        num_threads=st.integers(min_value=2, max_value=10),
        images_per_thread=st.integers(min_value=1, max_value=20),
    )
    @settings(deadline=None, max_examples=20)
    def test_concurrent_assignments_sequential_range(self, num_threads, images_per_thread):
        """Concurrent assignments produce complete sequential range."""
        handler = MessageHandler(get_default_config())
        all_indices = []
        lock = threading.Lock()
        barrier = threading.Barrier(num_threads)

        def assign_indices(thread_id: int):
            barrier.wait()
            for i in range(images_per_thread):
                buffered = create_test_buffered_image(seed=thread_id * 1000 + i)
                index = handler._assign_image_index(buffered)
                with lock:
                    all_indices.append(index)

        threads = []
        for t in range(num_threads):
            thread = threading.Thread(target=assign_indices, args=(t,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        total_expected = num_threads * images_per_thread
        assert sorted(all_indices) == list(range(total_expected))

    def test_concurrent_next_index_correctness(self):
        """_next_index is correct after concurrent assignments."""
        handler = MessageHandler(get_default_config())
        num_threads = 5
        images_per_thread = 10
        barrier = threading.Barrier(num_threads)

        def assign_indices():
            barrier.wait()
            for i in range(images_per_thread):
                buffered = create_test_buffered_image(seed=i)
                handler._assign_image_index(buffered)

        threads = []
        for _ in range(num_threads):
            thread = threading.Thread(target=assign_indices)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert handler._next_index == num_threads * images_per_thread


class TestHandleGetImageList:
    """Property-based tests for handle_get_image_list method."""

    def test_empty_list(self, handler, mock_server):
        """Empty index map produces empty image list."""
        handler.handle_get_image_list(mock_server)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.IMAGE_LIST
        assert call_args.payload["images"] == []

    @given(st.integers(min_value=1, max_value=50))
    @settings(deadline=None)
    def test_list_contains_all_images(self, num_images):
        """Image list contains all assigned images."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            handler._assign_image_index(buffered)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        assert len(images) == num_images

    @given(st.integers(min_value=1, max_value=50))
    @settings(deadline=None)
    def test_list_ordered_by_index(self, num_images):
        """Image list is ordered by index ascending."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            handler._assign_image_index(buffered)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        indices = [img["index"] for img in images]
        assert indices == sorted(indices)
        assert indices == list(range(num_images))

    def test_image_entry_structure(self, handler, mock_server, tmp_path):
        """Each image entry has required fields."""
        temp_file = tmp_path / "test.png"
        buffered = create_test_buffered_image(temp_path=temp_file)
        handler._assign_image_index(buffered)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        assert len(images) == 1

        entry = images[0]
        assert "index" in entry
        assert "path" in entry
        assert "display_path" in entry
        assert "deleted" in entry
        assert entry["index"] == 0
        assert entry["deleted"] is False

    def test_deleted_image_empty_paths(self, handler, mock_server, tmp_path):
        """Deleted images have empty path and display_path."""
        temp_file = tmp_path / "test.png"
        buffered = create_test_buffered_image(temp_path=temp_file)
        index = handler._assign_image_index(buffered)
        handler._deleted_indices.add(index)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        assert len(images) == 1

        entry = images[0]
        assert entry["index"] == 0
        assert entry["deleted"] is True
        assert entry["path"] == ""
        assert entry["display_path"] == ""

    @given(
        num_images=st.integers(min_value=2, max_value=30),
        delete_indices=st.data(),
    )
    @settings(deadline=None)
    def test_soft_delete_handling(self, num_images, delete_indices):
        """Soft-deleted images appear with deleted=True."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            handler._assign_image_index(buffered)

        indices_to_delete = delete_indices.draw(
            st.lists(
                st.integers(min_value=0, max_value=num_images - 1),
                min_size=0,
                max_size=num_images,
                unique=True,
            )
        )

        for idx in indices_to_delete:
            handler._deleted_indices.add(idx)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        assert len(images) == num_images

        for img in images:
            if img["index"] in indices_to_delete:
                assert img["deleted"] is True
                assert img["path"] == ""
                assert img["display_path"] == ""
            else:
                assert img["deleted"] is False

    def test_non_deleted_image_has_paths(self, handler, mock_server, tmp_path):
        """Non-deleted images have non-empty paths."""
        temp_file = tmp_path / "test.png"
        buffered = create_test_buffered_image(temp_path=temp_file)
        handler._assign_image_index(buffered)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        entry = images[0]

        assert entry["deleted"] is False
        assert entry["path"] == str(temp_file)
        assert entry["display_path"] != ""

    @given(st.integers(min_value=1, max_value=30))
    @settings(deadline=None)
    def test_list_consistency(self, num_images):
        """Multiple calls to get_image_list return consistent results."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            handler._assign_image_index(buffered)

        handler.handle_get_image_list(mock_server)
        first_call = mock_server.send.call_args[0][0].payload["images"]

        mock_server.reset_mock()
        handler.handle_get_image_list(mock_server)
        second_call = mock_server.send.call_args[0][0].payload["images"]

        assert first_call == second_call


class TestGetImageListThreadSafety:
    """Property-based tests for thread safety of handle_get_image_list."""

    def test_concurrent_read_write_no_error(self):
        """Concurrent reads and writes don't cause errors."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()
        num_readers = 3
        num_writers = 2
        images_per_writer = 10
        barrier = threading.Barrier(num_readers + num_writers)
        errors = []

        def reader():
            barrier.wait()
            try:
                for _ in range(5):
                    handler.handle_get_image_list(mock_server)
            except Exception as e:
                errors.append(e)

        def writer(thread_id: int):
            barrier.wait()
            try:
                for i in range(images_per_writer):
                    buffered = create_test_buffered_image(seed=thread_id * 1000 + i)
                    handler._assign_image_index(buffered)
            except Exception as e:
                errors.append(e)

        threads = []
        for _ in range(num_readers):
            thread = threading.Thread(target=reader)
            threads.append(thread)
            thread.start()

        for t in range(num_writers):
            thread = threading.Thread(target=writer, args=(t,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(errors) == 0

    @given(
        num_readers=st.integers(min_value=1, max_value=5),
        num_writers=st.integers(min_value=1, max_value=5),
        images_per_writer=st.integers(min_value=1, max_value=10),
    )
    @settings(deadline=None, max_examples=10)
    def test_final_list_complete(self, num_readers, num_writers, images_per_writer):
        """After concurrent operations, final list is complete and correct."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()
        barrier = threading.Barrier(num_readers + num_writers)

        def reader():
            barrier.wait()
            for _ in range(3):
                handler.handle_get_image_list(mock_server)

        def writer(thread_id: int):
            barrier.wait()
            for i in range(images_per_writer):
                buffered = create_test_buffered_image(seed=thread_id * 1000 + i)
                handler._assign_image_index(buffered)

        threads = []
        for _ in range(num_readers):
            thread = threading.Thread(target=reader)
            threads.append(thread)
            thread.start()

        for t in range(num_writers):
            thread = threading.Thread(target=writer, args=(t,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        mock_server.reset_mock()
        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]
        expected_count = num_writers * images_per_writer
        assert len(images) == expected_count

        indices = [img["index"] for img in images]
        assert sorted(indices) == list(range(expected_count))


class TestIndexGapsAfterDeletion:
    """Property-based tests for index gaps after soft deletion."""

    @given(
        num_images=st.integers(min_value=3, max_value=30),
        delete_positions=st.data(),
    )
    @settings(deadline=None)
    def test_deleted_images_create_gaps_in_active_list(self, num_images, delete_positions):
        """Deleted images create gaps when filtering for active images."""
        handler = MessageHandler(get_default_config())
        mock_server = Mock()

        for i in range(num_images):
            buffered = create_test_buffered_image(seed=i)
            handler._assign_image_index(buffered)

        indices_to_delete = delete_positions.draw(
            st.lists(
                st.integers(min_value=0, max_value=num_images - 1),
                min_size=1,
                max_size=max(1, num_images // 2),
                unique=True,
            )
        )

        for idx in indices_to_delete:
            handler._deleted_indices.add(idx)

        handler.handle_get_image_list(mock_server)

        call_args = mock_server.send.call_args[0][0]
        images = call_args.payload["images"]

        active_images = [img for img in images if not img["deleted"]]
        active_indices = [img["index"] for img in active_images]

        expected_count = num_images - len(indices_to_delete)
        assert len(active_images) == expected_count

        if len(active_indices) > 1:
            for i in range(len(active_indices) - 1):
                if active_indices[i + 1] - active_indices[i] > 1:
                    for gap_idx in range(active_indices[i] + 1, active_indices[i + 1]):
                        assert gap_idx in indices_to_delete

    def test_no_index_reuse_after_deletion(self, handler):
        """Deleting an image doesn't allow its index to be reused."""
        buffered1 = create_test_buffered_image(seed=1)
        index1 = handler._assign_image_index(buffered1)

        buffered2 = create_test_buffered_image(seed=2)
        index2 = handler._assign_image_index(buffered2)

        handler._deleted_indices.add(index1)

        buffered3 = create_test_buffered_image(seed=3)
        index3 = handler._assign_image_index(buffered3)

        assert index3 != index1
        assert index3 > index2

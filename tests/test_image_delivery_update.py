"""Property-based tests for _start_image_delivery updates.

Tests validate:
1. Index assignment: unique, stable, monotonic
2. IMAGE_READY event format: includes index, path, display_path (no buffer fields)
3. State transitions: GENERATING → IDLE or PAUSED after each image
4. Thread safety: concurrent deliveries don't corrupt indices
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from textbrush.buffer import BufferedImage
from textbrush.config import get_default_config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType


@pytest.fixture
def handler():
    """Create message handler with test config."""
    config = get_default_config()
    return MessageHandler(config)


@pytest.fixture
def mock_server():
    """Create mock IPC server."""
    server = Mock()
    server.send = Mock()
    return server


class TestIndexAssignment:
    """Property-based tests for _assign_image_index."""

    @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
    def test_assigns_unique_index(self, seed):
        """Each image gets unique index starting from 0."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=seed)

        index = handler._assign_image_index(buffered)

        assert index == 0
        assert index in handler._image_index_map
        assert handler._image_index_map[index] is buffered

    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**31 - 1), min_size=1, max_size=10))
    def test_indices_are_monotonic(self, seeds):
        """Indices increase monotonically: 0, 1, 2, 3, ..."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))
        indices = []

        for seed in seeds:
            buffered = BufferedImage(image=image, seed=seed)
            index = handler._assign_image_index(buffered)
            indices.append(index)

        assert indices == list(range(len(seeds)))

    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**31 - 1), min_size=2, max_size=20))
    def test_indices_never_reused(self, seeds):
        """Once assigned, index is permanent and never reused."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))
        assigned_indices = set()

        for seed in seeds:
            buffered = BufferedImage(image=image, seed=seed)
            index = handler._assign_image_index(buffered)
            assert index not in assigned_indices
            assigned_indices.add(index)

    def test_thread_safety_concurrent_assignments(self, handler):
        """Concurrent index assignments don't corrupt counter."""
        num_threads = 10
        images_per_thread = 5
        image = Image.new("RGB", (64, 64))
        all_indices = []
        lock = threading.Lock()

        def assign_indices():
            local_indices = []
            for i in range(images_per_thread):
                buffered = BufferedImage(image=image, seed=i)
                index = handler._assign_image_index(buffered)
                local_indices.append(index)
            with lock:
                all_indices.extend(local_indices)

        threads = [threading.Thread(target=assign_indices) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(all_indices) == num_threads * images_per_thread
        assert len(set(all_indices)) == len(all_indices)
        assert set(all_indices) == set(range(num_threads * images_per_thread))

    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**31 - 1), min_size=1, max_size=10))
    def test_stores_in_image_index_map(self, seeds):
        """Assigned index maps to correct BufferedImage in _image_index_map."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))
        buffered_images = [BufferedImage(image=image, seed=s) for s in seeds]

        for i, buffered in enumerate(buffered_images):
            index = handler._assign_image_index(buffered)
            assert handler._image_index_map[index] is buffered
            assert index == i


class TestImageReadyEvent:
    """Property-based tests for IMAGE_READY event format."""

    def test_image_ready_includes_index(self, handler, mock_server, tmp_path):
        """IMAGE_READY event includes index field."""
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=12345)
        preview_path = tmp_path / "preview.png"

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(return_value=preview_path)
        handler.backend = mock_backend

        delivery_done = threading.Event()

        def signal_after_delivery():
            time.sleep(0.1)
            handler._signal_action()
            delivery_done.set()

        threading.Thread(target=signal_after_delivery, daemon=True).start()
        handler._start_image_delivery(mock_server, None)
        assert delivery_done.wait(timeout=2.0)

        image_ready_call = None
        for call_obj in mock_server.send.call_args_list:
            msg = call_obj[0][0]
            if msg.type == MessageType.IMAGE_READY:
                image_ready_call = msg
                break

        assert image_ready_call is not None
        assert "index" in image_ready_call.payload
        assert image_ready_call.payload["index"] == 0

    def test_image_ready_no_buffer_fields(self, handler, mock_server, tmp_path):
        """IMAGE_READY event does not include buffer_count or buffer_max."""
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=12345)
        preview_path = tmp_path / "preview.png"

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(return_value=preview_path)
        handler.backend = mock_backend

        delivery_done = threading.Event()

        def signal_after_delivery():
            time.sleep(0.1)
            handler._signal_action()
            delivery_done.set()

        threading.Thread(target=signal_after_delivery, daemon=True).start()
        handler._start_image_delivery(mock_server, None)
        assert delivery_done.wait(timeout=2.0)

        image_ready_call = None
        for call_obj in mock_server.send.call_args_list:
            msg = call_obj[0][0]
            if msg.type == MessageType.IMAGE_READY:
                image_ready_call = msg
                break

        assert image_ready_call is not None
        assert "buffer_count" not in image_ready_call.payload
        assert "buffer_max" not in image_ready_call.payload

    def test_image_ready_includes_paths(self, handler, mock_server, tmp_path):
        """IMAGE_READY event includes path and display_path."""
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=12345)
        preview_path = tmp_path / "preview.png"

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(return_value=preview_path)
        handler.backend = mock_backend

        delivery_done = threading.Event()

        def signal_after_delivery():
            time.sleep(0.1)
            handler._signal_action()
            delivery_done.set()

        threading.Thread(target=signal_after_delivery, daemon=True).start()
        handler._start_image_delivery(mock_server, None)
        assert delivery_done.wait(timeout=2.0)

        image_ready_call = None
        for call_obj in mock_server.send.call_args_list:
            msg = call_obj[0][0]
            if msg.type == MessageType.IMAGE_READY:
                image_ready_call = msg
                break

        assert image_ready_call is not None
        assert "path" in image_ready_call.payload
        assert "display_path" in image_ready_call.payload
        assert image_ready_call.payload["path"] == str(preview_path.absolute())

    def test_delivery_continues_without_waiting_for_user_action(
        self, handler, mock_server, tmp_path
    ):
        """Delivery persists multiple previews without requiring skip/accept signals."""
        image = Image.new("RGB", (64, 64))
        buffered_1 = BufferedImage(image=image, seed=100)
        buffered_2 = BufferedImage(image=image, seed=101)
        preview_paths = [tmp_path / "preview_1.png", tmp_path / "preview_2.png"]

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered_1, buffered_2, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(side_effect=preview_paths)
        handler.backend = mock_backend

        handler._start_image_delivery(mock_server, None)
        time.sleep(0.2)

        image_ready_calls = [
            call_obj[0][0]
            for call_obj in mock_server.send.call_args_list
            if call_obj[0][0].type == MessageType.IMAGE_READY
        ]
        assert len(image_ready_calls) == 2
        assert image_ready_calls[0].payload["path"] == str(preview_paths[0].absolute())
        assert image_ready_calls[1].payload["path"] == str(preview_paths[1].absolute())

    @given(num_images=st.integers(min_value=1, max_value=5))
    @settings(deadline=None)
    def test_multiple_images_get_sequential_indices(self, num_images):
        """Multiple images get sequential indices 0, 1, 2, ..."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = get_default_config()
            handler = MessageHandler(config)
            mock_server = Mock()

            image = Image.new("RGB", (64, 64))
            buffered_images = [BufferedImage(image=image, seed=i) for i in range(num_images)]

            preview_paths = [tmp_path / f"preview_{i}.png" for i in range(num_images)]

            mock_backend = Mock()
            mock_backend.get_next_image = Mock(side_effect=buffered_images + [None])
            mock_backend.check_worker_error = Mock(return_value=None)
            mock_backend.save_to_preview = Mock(side_effect=preview_paths)
            handler.backend = mock_backend

            delivery_done = threading.Event()
            signal_count = [0]

            def signal_after_each():
                while signal_count[0] < num_images:
                    time.sleep(0.05)
                    handler._signal_action()
                    signal_count[0] += 1
                delivery_done.set()

            threading.Thread(target=signal_after_each, daemon=True).start()
            handler._start_image_delivery(mock_server, None)
            assert delivery_done.wait(timeout=5.0)

            image_ready_indices = []
            for call_obj in mock_server.send.call_args_list:
                msg = call_obj[0][0]
                if msg.type == MessageType.IMAGE_READY:
                    image_ready_indices.append(msg.payload["index"])

            assert image_ready_indices == list(range(num_images))


class TestStateTransitions:
    """Property-based tests for state transitions after image ready."""

    @pytest.mark.parametrize("is_paused", [False, True])
    def test_emits_state_changed_after_image(self, handler, mock_server, tmp_path, is_paused):
        """STATE_CHANGED emits idle/paused after IMAGE_READY based on backend pause state."""
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=12345)
        preview_path = tmp_path / "preview.png"

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(return_value=preview_path)
        mock_backend.is_paused = Mock(return_value=is_paused)
        handler.backend = mock_backend

        delivery_done = threading.Event()

        def signal_after_delivery():
            time.sleep(0.1)
            handler._signal_action()
            delivery_done.set()

        threading.Thread(target=signal_after_delivery, daemon=True).start()
        handler._start_image_delivery(mock_server, None)
        assert delivery_done.wait(timeout=2.0)

        state_changed_found = False
        expected_state = "paused" if is_paused else "idle"
        for call_obj in mock_server.send.call_args_list:
            msg = call_obj[0][0]
            if msg.type == MessageType.STATE_CHANGED:
                assert msg.payload["state"] == expected_state
                state_changed_found = True
                break

        assert state_changed_found

    def test_state_changed_comes_after_image_ready(self, handler, mock_server, tmp_path):
        """STATE_CHANGED event comes after IMAGE_READY in event sequence."""
        image = Image.new("RGB", (64, 64))
        buffered = BufferedImage(image=image, seed=12345)
        preview_path = tmp_path / "preview.png"

        mock_backend = Mock()
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
        mock_backend.save_to_preview = Mock(return_value=preview_path)
        mock_backend.is_paused = Mock(return_value=False)
        handler.backend = mock_backend

        delivery_done = threading.Event()

        def signal_after_delivery():
            time.sleep(0.1)
            handler._signal_action()
            delivery_done.set()

        threading.Thread(target=signal_after_delivery, daemon=True).start()
        handler._start_image_delivery(mock_server, None)
        assert delivery_done.wait(timeout=2.0)

        event_types = [call_obj[0][0].type for call_obj in mock_server.send.call_args_list]

        image_ready_idx = None
        state_changed_idx = None

        for i, evt_type in enumerate(event_types):
            if evt_type == MessageType.IMAGE_READY:
                image_ready_idx = i
            elif evt_type == MessageType.STATE_CHANGED and image_ready_idx is not None:
                state_changed_idx = i
                break

        assert image_ready_idx is not None
        assert state_changed_idx is not None
        assert state_changed_idx > image_ready_idx

    @given(num_images=st.integers(min_value=2, max_value=4), is_paused=st.booleans())
    @settings(deadline=None)
    def test_state_emitted_after_each_image_matches_pause_status(self, num_images, is_paused):
        """STATE_CHANGED emits expected state after each image delivery."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = get_default_config()
            handler = MessageHandler(config)
            mock_server = Mock()

            image = Image.new("RGB", (64, 64))
            buffered_images = [BufferedImage(image=image, seed=i) for i in range(num_images)]
            preview_paths = [tmp_path / f"preview_{i}.png" for i in range(num_images)]

            mock_backend = Mock()
            mock_backend.get_next_image = Mock(side_effect=buffered_images + [None])
            mock_backend.check_worker_error = Mock(return_value=None)
            mock_backend.save_to_preview = Mock(side_effect=preview_paths)
            mock_backend.is_paused = Mock(return_value=is_paused)
            handler.backend = mock_backend

            delivery_done = threading.Event()
            signal_count = [0]

            def signal_after_each():
                while signal_count[0] < num_images:
                    time.sleep(0.05)
                    handler._signal_action()
                    signal_count[0] += 1
                delivery_done.set()

            threading.Thread(target=signal_after_each, daemon=True).start()
            handler._start_image_delivery(mock_server, None)
            assert delivery_done.wait(timeout=5.0)

            expected_state = "paused" if is_paused else "idle"
            state_changed_count = 0
            for call_obj in mock_server.send.call_args_list:
                msg = call_obj[0][0]
                if (
                    msg.type == MessageType.STATE_CHANGED
                    and msg.payload.get("state") == expected_state
                ):
                    state_changed_count += 1

            assert state_changed_count == num_images


class TestEmitStateChanged:
    """Property-based tests for _emit_state_changed method."""

    @given(state=st.sampled_from(["loading", "idle", "paused", "error"]))
    def test_emits_valid_states(self, state):
        """_emit_state_changed emits valid BackendState values."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        if state == "error":
            handler._emit_state_changed(mock_server, state, message="Test error")
        else:
            handler._emit_state_changed(mock_server, state)

        mock_server.send.assert_called_once()
        msg = mock_server.send.call_args[0][0]
        assert msg.type == MessageType.STATE_CHANGED
        assert msg.payload["state"] == state

    @given(prompt=st.text(min_size=1, max_size=100))
    def test_generating_state_includes_prompt(self, prompt):
        """STATE_CHANGED(generating) includes prompt field."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, "generating", prompt=prompt)

        msg = mock_server.send.call_args[0][0]
        assert msg.payload["state"] == "generating"
        assert msg.payload["prompt"] == prompt

    def test_generating_without_prompt_raises(self, handler, mock_server):
        """STATE_CHANGED(generating) without prompt raises ValueError."""
        with pytest.raises(ValueError, match="prompt must be provided"):
            handler._emit_state_changed(mock_server, "generating")

    @given(error_msg=st.text(min_size=1, max_size=200))
    def test_error_state_includes_message(self, error_msg):
        """STATE_CHANGED(error) includes message field."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, "error", message=error_msg, fatal=False)

        msg = mock_server.send.call_args[0][0]
        assert msg.payload["state"] == "error"
        assert msg.payload["message"] == error_msg
        assert msg.payload["fatal"] is False

    def test_error_without_message_raises(self, handler, mock_server):
        """STATE_CHANGED(error) without message raises ValueError."""
        with pytest.raises(ValueError, match="message must be provided"):
            handler._emit_state_changed(mock_server, "error")

    @given(state=st.sampled_from(["loading", "idle", "paused"]))
    def test_non_generating_states_no_prompt(self, state):
        """Non-generating states don't include prompt in payload."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, state)

        msg = mock_server.send.call_args[0][0]
        assert msg.payload.get("prompt") is None


class TestImageIndexMap:
    """Property-based tests for _image_index_map consistency."""

    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**31 - 1), min_size=1, max_size=10))
    def test_map_contains_all_assigned_images(self, seeds):
        """_image_index_map contains entry for every assigned index."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))

        for i, seed in enumerate(seeds):
            buffered = BufferedImage(image=image, seed=seed)
            index = handler._assign_image_index(buffered)
            assert index == i
            assert index in handler._image_index_map

        assert len(handler._image_index_map) == len(seeds)

    @given(seeds=st.lists(st.integers(min_value=0, max_value=2**31 - 1), min_size=1, max_size=10))
    def test_map_retrieves_correct_image(self, seeds):
        """Can retrieve correct BufferedImage from _image_index_map by index."""
        config = get_default_config()
        handler = MessageHandler(config)
        image = Image.new("RGB", (64, 64))
        buffered_images = []

        for seed in seeds:
            buffered = BufferedImage(image=image, seed=seed)
            buffered_images.append(buffered)
            handler._assign_image_index(buffered)

        for i, buffered in enumerate(buffered_images):
            assert handler._image_index_map[i] is buffered
            assert handler._image_index_map[i].seed == buffered.seed

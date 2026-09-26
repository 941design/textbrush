"""Property-based tests for IPC message handler."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from queue import Queue
from unittest.mock import ANY, Mock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.config import Config, get_default_config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import (
    ErrorEvent,
    MessageType,
    dataclass_to_dict,
)
from textbrush.model.registry import (
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    AvailabilityReport,
    DiscoveryCause,
    get_model_spec,
)
from textbrush.validation import TEXT_ASPECT_RATIOS


def _available() -> AvailabilityReport:
    """Availability report for a model that is fully installed locally."""
    return AvailabilityReport(True, None, "all declared files present")


def _absent() -> AvailabilityReport:
    """Availability report for a model with no local weights."""
    return AvailabilityReport(False, DiscoveryCause.ABSENT, "no local marker found")


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


@pytest.fixture
def installed_models():
    """Report every registered model as installed locally.

    Deferred loading resolves the SELECTED model through
    `check_model_availability` before constructing a backend, so a test
    that wants INIT to reach the load must say the weights are there.
    """
    with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
        yield


class TestInitialization:
    """Property-based tests for handler initialization."""

    def test_lazy_backend_creation(self, handler):
        """Backend is not created until handle_init."""
        assert handler.backend is None
        assert handler._current_image is None

    @given(st.text(min_size=1, max_size=100))
    def test_config_stored(self, prompt):
        """Configuration is stored for later use."""
        config = get_default_config()
        handler = MessageHandler(config)
        assert handler.config is config


class TestInitCommand:
    """Property-based tests for INIT command handling."""

    @given(
        prompt=st.text(min_size=1, max_size=200),
        seed=st.one_of(st.none(), st.integers(min_value=0, max_value=2**31 - 1)),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    @settings(deadline=None, max_examples=10)
    def test_init_payload_parsing(self, prompt, seed, aspect_ratio):
        """Init command parses various payload combinations correctly."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        payload = {
            "prompt": prompt,
            "seed": seed,
            "aspect_ratio": aspect_ratio,
            "output_path": None,
            "format": "png",
            # Deferred loading: a backend exists only once a model has
            # been selected. INIT carries the selection here.
            "model_id": FLUX1_SCHNELL,
        }

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
            with patch.object(TextbrushBackend, "__init__", return_value=None):
                with patch.object(handler, "_init_backend"):
                    handler.handle_init(payload, mock_server)

        assert handler.backend is not None
        assert isinstance(handler.backend, TextbrushBackend)

    @pytest.mark.parametrize("seed", [0, 42, None])
    def test_init_forwards_seed_to_generation(self, handler, mock_server, installed_models, seed):
        ready_callbacks = Queue()
        backend = Mock(spec=TextbrushBackend)
        backend.model_id = FLUX1_SCHNELL
        backend.references = ()
        backend.reference_paths = ()
        backend.preset = None
        backend.canvas = (256, 256)
        backend.is_paused.return_value = True
        backend.is_settled.return_value = True
        with (
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=backend),
            patch.object(handler, "_emit_model_list"),
            patch.object(
                handler,
                "_init_backend",
                side_effect=lambda ready, server: ready_callbacks.put(ready),
            ),
            patch.object(handler, "_start_image_delivery"),
        ):
            handler.handle_init(
                {"prompt": "cat", "model_id": FLUX1_SCHNELL, "seed": seed}, mock_server
            )
            ready_callbacks.get(timeout=2)()
        assert backend.start_generation.call_count == 1
        assert backend.start_generation.call_args.kwargs["seed"] == seed

    def test_init_creates_backend(self, handler, mock_server, installed_models):
        """Init command creates TextbrushBackend instance."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
        }

        with patch.object(TextbrushBackend, "__init__", return_value=None):
            with patch.object(handler, "_init_backend"):
                handler.handle_init(payload, mock_server)

        assert handler.backend is not None

    def test_init_starts_background_thread(self, handler, mock_server, installed_models):
        """Init command starts background initialization thread."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
        }

        init_called = threading.Event()

        def mock_init_backend(on_ready, server):
            init_called.set()

        with patch.object(TextbrushBackend, "__init__", return_value=None):
            with patch.object(handler, "_init_backend", side_effect=mock_init_backend):
                handler.handle_init(payload, mock_server)
                assert init_called.wait(timeout=1.0)

    def test_init_emits_loading_state_first(self, handler, mock_server, installed_models):
        """handle_init emits state_changed(loading) as first STATE_CHANGED event."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
        }

        with patch.object(TextbrushBackend, "__init__", return_value=None):
            with patch.object(handler, "_init_backend"):
                handler.handle_init(payload, mock_server)

        state_changed_calls = [
            call
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert len(state_changed_calls) >= 1, "At least one STATE_CHANGED message must be sent"
        first_state = state_changed_calls[0][0][0].payload["state"]
        assert first_state == "loading", (
            f"First STATE_CHANGED must be 'loading', got '{first_state}'"
        )

    def test_init_emits_loading_unconditionally(self, handler, mock_server, installed_models):
        """handle_init emits state_changed(loading) unconditionally for all payload variations."""
        # Test with a non-default aspect ratio to confirm no conditional branching skips loading
        payload = {
            "prompt": "another test prompt",
            "seed": 42,
            "aspect_ratio": "16:9",
            "output_path": "/tmp/out.png",
            "format": "png",
            "model_id": FLUX1_SCHNELL,
        }

        with patch.object(TextbrushBackend, "__init__", return_value=None):
            with patch.object(handler, "_init_backend"):
                handler.handle_init(payload, mock_server)

        state_changed_calls = [
            call
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert len(state_changed_calls) >= 1, "At least one STATE_CHANGED message must be sent"
        first_state = state_changed_calls[0][0][0].payload["state"]
        assert first_state == "loading", (
            f"First STATE_CHANGED must be 'loading' for all payload variations, got '{first_state}'"
        )

    def test_pause_during_loading_toggles_to_running(self, handler, mock_server, installed_models):
        """PAUSE during loading toggles pending startup state from paused to running."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
            "width": 256,
            "height": 256,
        }

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.start_generation = Mock()
        mock_backend.initialize = Mock()
        mock_backend.is_paused.return_value = False
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (256, 256)

        class ImmediateThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target = target
                self._args = args

            def start(self):
                if self._target:
                    self._target(*self._args)

        def mock_init_backend(on_ready, server):
            # Startup defaults to paused; PAUSE toggles to running.
            handler.handle_pause(server)
            on_ready()

        with patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend):
            with patch("textbrush.ipc.handler.threading.Thread", side_effect=ImmediateThread):
                with patch.object(handler, "_init_backend", side_effect=mock_init_backend):
                    with patch.object(handler, "_start_image_delivery"):
                        handler.handle_init(payload, mock_server)

        mock_backend.start_generation.assert_called_once()
        start_kwargs = mock_backend.start_generation.call_args.kwargs
        assert start_kwargs["start_paused"] is False

        state_changed_calls = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert state_changed_calls[-1].payload["state"] == "idle"

    def test_init_starts_worker_paused_by_default(self, handler, mock_server, installed_models):
        """INIT starts generation paused by default."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
            "width": 256,
            "height": 256,
        }

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.start_generation = Mock()
        mock_backend.initialize = Mock()
        mock_backend.is_paused.return_value = True
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (256, 256)

        class ImmediateThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target = target
                self._args = args

            def start(self):
                if self._target:
                    self._target(*self._args)

        def mock_init_backend(on_ready, server):
            on_ready()

        with patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend):
            with patch("textbrush.ipc.handler.threading.Thread", side_effect=ImmediateThread):
                with patch.object(handler, "_init_backend", side_effect=mock_init_backend):
                    with patch.object(handler, "_start_image_delivery"):
                        handler.handle_init(payload, mock_server)

        mock_backend.start_generation.assert_called_once()
        start_kwargs = mock_backend.start_generation.call_args.kwargs
        assert start_kwargs["start_paused"] is True

        state_changed_calls = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert state_changed_calls[-1].payload["state"] == "paused"
        startup_acks = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.CONFIG_ACK
        ]
        assert len(startup_acks) == 1
        assert startup_acks[0].payload["model_id"] == "flux1-schnell"
        assert startup_acks[0].payload["reference_paths"] == []

    def test_handle_pause_resume_uses_handler_check_compatibility(self):
        """Regression for a T12 finding: `handle_pause` used to call
        `self.backend._check_compatibility()`, which does not exist on
        `TextbrushBackend` (the helper is a `MessageHandler` method).
        The real-backend `full_stack` harness in T12 trips this on
        the first resume; this test pins the call against a real
        `MessageHandler._check_compatibility` to catch a regression."""
        from textbrush.config import get_default_config
        from textbrush.ipc.handler import MessageHandler

        config = get_default_config()
        handler = MessageHandler(config)
        backend = Mock()
        backend.model_id = "flux1-schnell"
        backend.references = ()
        backend.preset = None
        handler.backend = backend

        verdict = handler._check_compatibility()

        # The verdict reflects the (mocked) backend's acknowledged
        # state: schnell, 0 references, None preset is a valid combo.
        assert verdict.valid is True


class TestSkipCommand:
    """Property-based tests for SKIP command handling."""

    def test_skip_clears_current_image(self, handler, mock_server):
        """Skip command clears current image reference."""
        handler._current_image = Mock()
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.__len__ = Mock(return_value=3)
        handler.backend.buffer.max_size = 8

        handler.handle_skip(mock_server)

        assert handler._current_image is None

    def test_skip_signals_delivery_thread(self, handler, mock_server):
        """Skip command signals waiting delivery thread."""
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.__len__ = Mock(return_value=3)
        handler.backend.buffer.max_size = 8

        handler._action_event.clear()
        handler.handle_skip(mock_server)

        assert handler._action_event.is_set()

    def test_skip_no_buffer_status_sent(self):
        """Skip no longer sends BUFFER_STATUS (deprecated per FR7)."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.__len__ = Mock(return_value=2)
        handler.backend.buffer.max_size = 8

        handler.handle_skip(mock_server)

        # BUFFER_STATUS is deprecated - no message should be sent
        mock_server.send.assert_not_called()


class TestAcceptCommand:
    """Property-based tests for ACCEPT command handling."""

    def test_accept_no_image_sends_error(self, handler, mock_server):
        """Accept with no delivered images sends non-fatal error."""
        handler._delivered_images = []
        handler.backend = None

        handler.handle_accept(mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is False
        assert "No images to accept" in call_args.payload["message"]

    def test_accept_saves_image(self, handler, mock_server, tmp_path):
        """Accept command batch saves all non-deleted images via backend."""
        image1 = Mock()
        image2 = Mock()
        # Use index-based tracking (new architecture)
        handler._image_index_map = {0: image1, 1: image2}
        handler._delivery_order = [0, 1]
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        output_paths = [tmp_path / "img1.png", tmp_path / "img2.png"]
        mock_backend.accept_all = Mock(return_value=output_paths)
        handler.backend = mock_backend

        handler.handle_accept(mock_server)

        mock_backend.accept_all.assert_called_once()
        # Verify it was called with the delivered images in delivery order
        call_args = mock_backend.accept_all.call_args[0][0]
        assert call_args == [image1, image2]

        # Verify ACCEPTED event was sent with paths
        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ACCEPTED
        assert len(call_args.payload["paths"]) == 2

    def test_accept_uses_delivery_order_not_index_order(self, handler, mock_server, tmp_path):
        """Accept emits paths in delivery (viewing) order, not sorted index order."""
        image0 = Mock()
        image1 = Mock()
        # Simulate delivery order: index 1 was delivered before index 0
        handler._image_index_map = {0: image0, 1: image1}
        handler._delivery_order = [1, 0]  # index 1 delivered first
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        output_paths = [tmp_path / "img_first.png", tmp_path / "img_second.png"]
        mock_backend.accept_all = Mock(return_value=output_paths)
        handler.backend = mock_backend

        handler.handle_accept(mock_server)

        mock_backend.accept_all.assert_called_once()
        # Delivery order is [1, 0], so image1 must come before image0
        call_args = mock_backend.accept_all.call_args[0][0]
        assert call_args == [image1, image0], (
            "images_to_accept must follow delivery order (viewing order), not index order"
        )

    def test_accept_clears_delivery_order_after_accept(self, handler, mock_server, tmp_path):
        """_delivery_order is cleared after a successful accept."""
        image1 = Mock()
        handler._image_index_map = {0: image1}
        handler._delivery_order = [0]
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_all = Mock(return_value=[tmp_path / "out.png"])
        handler.backend = mock_backend

        handler.handle_accept(mock_server)

        assert handler._delivery_order == [], "_delivery_order must be cleared after accept"

    def test_accept_signals_delivery_thread(self, handler, mock_server, tmp_path):
        """Accept command does NOT signal delivery thread (process exits)."""
        image1 = Mock()
        # Use index-based tracking (new architecture)
        handler._image_index_map = {0: image1}
        handler._delivery_order = [0]
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_all = Mock(return_value=[tmp_path / "test.png"])
        handler.backend = mock_backend

        handler._action_event.clear()
        handler.handle_accept(mock_server)

        # ACCEPT does NOT signal action event - process will exit
        assert not handler._action_event.is_set()

    def test_accept_exception_sends_error(self, handler, mock_server):
        """Accept handles backend exceptions gracefully."""
        image1 = Mock()
        # Use index-based tracking (new architecture)
        handler._image_index_map = {0: image1}
        handler._delivery_order = [0]
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_all = Mock(side_effect=RuntimeError("Disk full"))
        handler.backend = mock_backend

        handler.handle_accept(mock_server)

        error_sent = False
        for call in mock_server.send.call_args_list:
            msg = call[0][0]
            if msg.type == MessageType.ERROR:
                error_sent = True
                assert msg.payload["fatal"] is False
                assert "Disk full" in msg.payload["message"]

        assert error_sent


class TestAbortCommand:
    """Property-based tests for ABORT command handling."""

    def test_abort_calls_backend_abort(self, handler, mock_server):
        """Abort command calls backend.abort if backend exists."""
        mock_backend = Mock(spec=TextbrushBackend)
        handler.backend = mock_backend

        handler.handle_abort(mock_server)

        mock_backend.abort.assert_called_once()

    def test_abort_sends_aborted_event(self, handler, mock_server):
        """Abort command sends ABORTED event."""
        handler.backend = Mock(spec=TextbrushBackend)

        handler.handle_abort(mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ABORTED

    def test_abort_triggers_server_shutdown(self, handler, mock_server):
        """Abort command triggers server shutdown."""
        handler.backend = Mock(spec=TextbrushBackend)

        handler.handle_abort(mock_server)

        mock_server.shutdown.assert_called_once()

    def test_abort_idempotent_no_backend(self, handler, mock_server):
        """Abort is safe to call with no backend."""
        handler.backend = None

        handler.handle_abort(mock_server)

        mock_server.send.assert_called()
        mock_server.shutdown.assert_called_once()


class TestDeleteCommand:
    """Behavioral tests for DELETE command handling."""

    def test_delete_removes_image_from_tracking(self, handler, mock_server, tmp_path):
        """DELETE adds the index to _deleted_indices."""
        image = Mock(spec=BufferedImage)
        image.temp_path = tmp_path / "img0.png"
        image.temp_path.write_bytes(b"fake")

        handler._image_index_map = {0: image}
        handler._deleted_indices = set()

        handler.handle_delete({"index": 0}, mock_server)

        assert 0 in handler._deleted_indices

    def test_delete_sends_delete_ack_event(self, handler, mock_server, tmp_path):
        """DELETE sends DELETE_ACK with the correct index."""
        image = Mock(spec=BufferedImage)
        image.temp_path = tmp_path / "img1.png"
        image.temp_path.write_bytes(b"fake")

        handler._image_index_map = {0: image}
        handler._deleted_indices = set()

        handler.handle_delete({"index": 0}, mock_server)

        mock_server.send.assert_called_once()
        sent = mock_server.send.call_args[0][0]
        assert sent.type == MessageType.DELETE_ACK
        assert sent.payload["index"] == 0

    def test_delete_deletes_temp_file(self, handler, mock_server, tmp_path):
        """DELETE deletes the real temp file from disk."""
        real_file = tmp_path / "img0.png"
        real_file.write_bytes(b"fake image data")

        image = BufferedImage(image=Mock(), seed=42, temp_path=real_file)
        handler._image_index_map = {0: image}
        handler._deleted_indices = set()

        handler.handle_delete({"index": 0}, mock_server)

        assert not real_file.exists()

    def test_delete_already_deleted_is_idempotent(self, handler, mock_server, tmp_path):
        """DELETE of an already-deleted index is a no-op but still sends DELETE_ACK."""
        image = Mock(spec=BufferedImage)
        image.temp_path = tmp_path / "img0.png"

        handler._image_index_map = {0: image}
        handler._deleted_indices = {0}  # already deleted

        handler.handle_delete({"index": 0}, mock_server)

        # cleanup() must NOT be called again on already-deleted image
        image.cleanup.assert_not_called()
        # DELETE_ACK still sent
        mock_server.send.assert_called_once()
        sent = mock_server.send.call_args[0][0]
        assert sent.type == MessageType.DELETE_ACK
        assert sent.payload["index"] == 0

    def test_delete_nonexistent_index_is_idempotent(self, handler, mock_server):
        """DELETE of a non-existent index is a no-op but still sends DELETE_ACK."""
        handler._image_index_map = {}
        handler._deleted_indices = set()

        handler.handle_delete({"index": 99}, mock_server)

        assert handler._deleted_indices == set()
        mock_server.send.assert_called_once()
        sent = mock_server.send.call_args[0][0]
        assert sent.type == MessageType.DELETE_ACK
        assert sent.payload["index"] == 99

    def test_delete_then_accept_excludes_deleted_image(self, handler, mock_server, tmp_path):
        """DELETE then ACCEPT excludes the deleted image from accept_all."""
        image1 = Mock(spec=BufferedImage)
        image1.temp_path = tmp_path / "img0.png"
        image1.temp_path.write_bytes(b"fake")

        image2 = Mock(spec=BufferedImage)
        image2.temp_path = tmp_path / "img1.png"

        handler._image_index_map = {0: image1, 1: image2}
        handler._delivery_order = [0, 1]
        handler._deleted_indices = set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_all = Mock(return_value=[tmp_path / "out.png"])
        handler.backend = mock_backend

        handler.handle_delete({"index": 0}, mock_server)
        mock_server.reset_mock()
        handler.handle_accept(mock_server)

        mock_backend.accept_all.assert_called_once()
        call_images = mock_backend.accept_all.call_args[0][0]
        assert call_images == [image2]


class TestStatusCommand:
    """Property-based tests for STATUS command handling (deprecated per FR7)."""

    def test_status_is_noop(self, handler, mock_server):
        """Status command is deprecated and does nothing."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.__len__ = Mock(return_value=5)
        mock_backend.buffer.max_size = 8
        handler.backend = mock_backend

        handler.handle_status(mock_server)

        # STATUS is deprecated - no message should be sent
        mock_server.send.assert_not_called()

    def test_status_no_backend_no_send(self, handler, mock_server):
        """Status command does nothing if no backend (deprecated per FR7)."""
        handler.backend = None

        handler.handle_status(mock_server)

        mock_server.send.assert_not_called()


class TestThreadSynchronization:
    """Property-based tests for thread synchronization primitives."""

    def test_wait_blocks_until_signaled(self, handler):
        """Wait blocks current thread until signal."""
        waited = threading.Event()

        def waiter():
            handler._wait_for_action()
            waited.set()

        thread = threading.Thread(target=waiter)
        thread.start()

        time.sleep(0.1)
        assert not waited.is_set()

        handler._signal_action()

        assert waited.wait(timeout=1.0)
        thread.join(timeout=1.0)

    def test_signal_unblocks_waiter(self, handler):
        """Signal unblocks waiting thread."""
        handler._action_event.clear()

        signaled = threading.Event()

        def waiter():
            handler._wait_for_action()
            signaled.set()

        thread = threading.Thread(target=waiter)
        thread.start()

        handler._signal_action()

        assert signaled.wait(timeout=1.0)
        thread.join(timeout=1.0)

    def test_event_resets_after_wait(self, handler):
        """Action event resets after each wait."""
        handler._signal_action()
        handler._wait_for_action()

        assert not handler._action_event.is_set()


class TestImageDelivery:
    """Tests for image delivery (path-based)."""

    def test_image_delivery_sends_path(self):
        """Image delivery thread saves to preview and sends path."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = get_default_config()
            handler = MessageHandler(config)
            mock_server = Mock()
            test_image = Image.new("RGB", (128, 128), color=(100, 150, 200))
            buffered = BufferedImage(image=test_image, seed=12345)

            # Create a mock preview path
            preview_path = tmp_path / "preview.png"

            mock_backend = Mock(spec=TextbrushBackend)
            mock_backend.get_next_image = Mock(side_effect=[buffered, None])
            mock_backend.check_worker_error = Mock(return_value=None)
            mock_backend.save_to_preview = Mock(return_value=preview_path)
            mock_backend.buffer = Mock()
            mock_backend.buffer.__len__ = Mock(return_value=1)
            mock_backend.buffer.max_size = 8
            handler.backend = mock_backend

            delivery_done = threading.Event()

            def signal_after_delivery():
                time.sleep(0.1)
                handler._signal_action()
                delivery_done.set()

            threading.Thread(target=signal_after_delivery, daemon=True).start()

            handler._start_image_delivery(mock_server, None)

            assert delivery_done.wait(timeout=2.0)

            image_ready_sent = False
            for call in mock_server.send.call_args_list:
                msg = call[0][0]
                if msg.type == MessageType.IMAGE_READY:
                    image_ready_sent = True
                    assert "path" in msg.payload
                    assert msg.payload["path"] == str(preview_path.absolute())
                    # Seed is now in PNG metadata, not in payload
                    assert "seed" not in msg.payload
                    assert "image_data" not in msg.payload

            assert image_ready_sent
            mock_backend.save_to_preview.assert_called_once_with(buffered)

    def test_image_delivery_preserves_paused_state(self):
        """Delivery emits paused (not idle) when worker is paused."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config = get_default_config()
            handler = MessageHandler(config)
            mock_server = Mock()
            test_image = Image.new("RGB", (64, 64), color=(1, 2, 3))
            buffered = BufferedImage(image=test_image, seed=111)

            preview_path = tmp_path / "preview.png"

            mock_backend = Mock(spec=TextbrushBackend)
            mock_backend.get_next_image = Mock(side_effect=[buffered, None])
            mock_backend.check_worker_error = Mock(return_value=None)
            mock_backend.save_to_preview = Mock(return_value=preview_path)
            mock_backend.is_paused = Mock(return_value=True)
            handler.backend = mock_backend

            handler._start_image_delivery(mock_server, None)
            time.sleep(0.1)

            states = [
                call[0][0].payload["state"]
                for call in mock_server.send.call_args_list
                if call[0][0].type == MessageType.STATE_CHANGED
            ]
            assert "paused" in states
            assert "idle" not in states


class TestBackendInitialization:
    """Property-based tests for backend initialization."""

    def test_init_backend_success_calls_ready(self, handler, mock_server):
        """Successful backend init calls on_ready callback."""
        ready_called = threading.Event()

        def on_ready():
            ready_called.set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
            handler._init_backend(on_ready, mock_server)

        assert ready_called.is_set()
        mock_backend.initialize.assert_called_once()

    def test_init_backend_failure_emits_error_state(self, handler, mock_server):
        """Backend init failure emits state_changed(error) via state machine."""

        def on_ready():
            pass

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock(side_effect=RuntimeError("Model load failed"))
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
            handler._init_backend(on_ready, mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.STATE_CHANGED
        assert call_args.payload["state"] == "error"
        assert call_args.payload["fatal"] is True
        assert "Model load failed" in call_args.payload["message"]


class TestModelDiscoveryInInitBackend:
    """Tests for model discovery and download logic in _init_backend."""

    def test_model_available_proceeds_to_initialize(self, handler, mock_server):
        """When model is available, backend.initialize() is called without download."""
        ready_called = threading.Event()

        def on_ready():
            ready_called.set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
            with patch("textbrush.ipc.handler.download_model_weights") as mock_download:
                handler._init_backend(on_ready, mock_server)

        assert ready_called.is_set()
        mock_backend.initialize.assert_called_once()
        mock_download.assert_not_called()

    def test_model_missing_no_credentials_emits_fatal_error(self, handler, mock_server):
        """When model missing and no credentials, fatal error emitted with instructions."""

        def on_ready():
            pass

        mock_backend = Mock(spec=TextbrushBackend)
        handler.backend = mock_backend
        handler.config.huggingface.token = None

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            with patch("textbrush.ipc.handler.download_model_weights") as mock_download:
                with patch.object(handler, "_detect_hf_credentials", return_value=None):
                    handler._init_backend(on_ready, mock_server)

        # Should emit fatal error
        state_changed_calls = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        error_states = [c for c in state_changed_calls if c.payload["state"] == "error"]
        assert len(error_states) == 1
        assert error_states[0].payload["fatal"] is True
        assert "FLUX.1 schnell" in error_states[0].payload["message"]
        assert "huggingface.co/settings/tokens" in error_states[0].payload["message"]
        assert "textbrush --download-model" in error_states[0].payload["message"]

        # backend.initialize() must NOT be called
        mock_backend.initialize.assert_not_called()
        mock_download.assert_not_called()

    def test_model_missing_with_credentials_triggers_download(self, handler, mock_server):
        """When model missing but credentials available, download is triggered."""
        ready_called = threading.Event()

        def on_ready():
            ready_called.set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            with patch("textbrush.ipc.handler.download_model_weights") as mock_download:
                with patch.object(handler, "_detect_hf_credentials", return_value="hf_test_token"):
                    handler._init_backend(on_ready, mock_server)

        # Loading state must have been emitted before download
        state_changed_calls = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        loading_states = [c for c in state_changed_calls if c.payload["state"] == "loading"]
        assert len(loading_states) >= 1

        # Download must have been called
        mock_download.assert_called_once()

        # backend.initialize() must have been called after download
        mock_backend.initialize.assert_called_once()
        assert ready_called.is_set()

    def test_download_failure_emits_fatal_error(self, handler, mock_server):
        """When download fails, fatal error emitted and backend.initialize() not called."""

        def on_ready():
            pass

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            with patch(
                "textbrush.ipc.handler.download_model_weights",
                side_effect=RuntimeError("network error"),
            ):
                with patch.object(handler, "_detect_hf_credentials", return_value="hf_test_token"):
                    handler._init_backend(on_ready, mock_server)

        # Fatal error emitted
        state_changed_calls = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        error_states = [c for c in state_changed_calls if c.payload["state"] == "error"]
        assert len(error_states) == 1
        assert error_states[0].payload["fatal"] is True
        assert "Model download failed" in error_states[0].payload["message"]
        assert "network error" in error_states[0].payload["message"]

        # backend.initialize() must NOT be called after download failure
        mock_backend.initialize.assert_not_called()

    def test_discovery_unexpected_error_falls_back_to_initialize(self, handler, mock_server):
        """Unexpected error in model discovery falls back to backend.initialize()."""
        ready_called = threading.Event()

        def on_ready():
            ready_called.set()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch(
            "textbrush.ipc.handler.check_model_availability",
            side_effect=Exception("Unexpected discovery error"),
        ):
            handler._init_backend(on_ready, mock_server)

        # Should still call backend.initialize() (graceful degradation)
        mock_backend.initialize.assert_called_once()
        assert ready_called.is_set()


class TestDetectHfCredentials:
    """Tests for HuggingFace credential detection in MessageHandler."""

    def test_huggingface_hub_token_env_var_found(self, handler):
        """HUGGINGFACE_HUB_TOKEN env var is returned first."""
        import os

        with patch.dict(os.environ, {"HUGGINGFACE_HUB_TOKEN": "hf_env_token"}, clear=False):
            handler.config.huggingface.token = None
            result = handler._detect_hf_credentials()

        assert result == "hf_env_token"

    def test_config_token_found_when_no_env_var(self, handler):
        """config.huggingface.token returned when HUGGINGFACE_HUB_TOKEN not set."""
        import os

        env = {k: v for k, v in os.environ.items() if k != "HUGGINGFACE_HUB_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            handler.config.huggingface.token = "hf_config_token"
            result = handler._detect_hf_credentials()

        assert result == "hf_config_token"

    def test_hf_cli_cache_file_used_as_fallback(self, handler, tmp_path):
        """HuggingFace CLI login cache file used when env var and config token absent."""
        import os
        from pathlib import Path as RealPath

        # Create fake HF home with token file
        hf_cache_dir = tmp_path / ".cache" / "huggingface"
        hf_cache_dir.mkdir(parents=True)
        token_file = hf_cache_dir / "token"
        token_file.write_text("hf_cached_token\n")

        env = {k: v for k, v in os.environ.items() if k != "HUGGINGFACE_HUB_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            handler.config.huggingface.token = None
            with patch.object(RealPath, "home", staticmethod(lambda: tmp_path)):
                result = handler._detect_hf_credentials()

        assert result == "hf_cached_token"

    def test_no_credentials_returns_none(self, handler):
        """Returns None when no credentials found from any source."""
        import os

        env = {k: v for k, v in os.environ.items() if k != "HUGGINGFACE_HUB_TOKEN"}
        with patch.dict(os.environ, env, clear=True):
            handler.config.huggingface.token = None
            with patch("pathlib.Path.exists", return_value=False):
                result = handler._detect_hf_credentials()

        assert result is None

    def test_env_var_takes_priority_over_config(self, handler):
        """HUGGINGFACE_HUB_TOKEN env var takes priority over config token."""
        import os

        with patch.dict(os.environ, {"HUGGINGFACE_HUB_TOKEN": "hf_env_token"}, clear=False):
            handler.config.huggingface.token = "hf_config_token"
            result = handler._detect_hf_credentials()

        assert result == "hf_env_token"


class TestErrorHandling:
    """Property-based tests for error handling throughout handler."""

    @given(error_msg=st.text(min_size=1, max_size=100))
    def test_fatal_error_format(self, error_msg):
        """Fatal errors have correct format."""
        event = ErrorEvent(message=error_msg, fatal=True)
        payload = dataclass_to_dict(event)

        assert payload["message"] == error_msg
        assert payload["fatal"] is True

    @given(error_msg=st.text(min_size=1, max_size=100))
    def test_non_fatal_error_format(self, error_msg):
        """Non-fatal errors have correct format."""
        event = ErrorEvent(message=error_msg, fatal=False)
        payload = dataclass_to_dict(event)

        assert payload["message"] == error_msg
        assert payload["fatal"] is False


class TestImageReadyEventSerialization:
    """Tests for ImageReadyEvent serialization (path-based protocol)."""

    def test_image_ready_event_serialization(self):
        """ImageReadyEvent serializes index, path, display_path to valid JSON."""
        from textbrush.ipc.protocol import ImageReadyEvent, dataclass_to_dict

        event = ImageReadyEvent(
            index=0,
            path="/Users/test/Pictures/preview.png",
            display_path="~/Pictures/preview.png",
        )
        payload = dataclass_to_dict(event)

        assert payload["index"] == 0
        assert payload["path"] == "/Users/test/Pictures/preview.png"
        assert payload["display_path"] == "~/Pictures/preview.png"
        # Buffer fields removed from protocol
        assert "buffer_count" not in payload
        assert "buffer_max" not in payload
        # Seed and dimensions are in PNG metadata, not in payload
        assert "seed" not in payload
        assert "image_data" not in payload
        assert "generated_width" not in payload
        assert "final_width" not in payload


class TestEmitStateChanged:
    """Property-based tests for _emit_state_changed method."""

    @given(prompt=st.text(min_size=1, max_size=200))
    def test_generating_state_requires_prompt(self, prompt):
        """GENERATING state requires prompt field."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, BackendState.GENERATING.value, prompt=prompt)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.STATE_CHANGED
        assert call_args.payload["state"] == BackendState.GENERATING.value
        assert call_args.payload["prompt"] == prompt
        assert handler._current_state == BackendState.GENERATING.value

    def test_generating_state_without_prompt_raises_error(self):
        """GENERATING state without prompt raises ValueError."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        with pytest.raises(ValueError, match="prompt must be provided"):
            handler._emit_state_changed(mock_server, BackendState.GENERATING.value)

    @given(
        message=st.text(min_size=1, max_size=200),
        fatal=st.booleans(),
    )
    def test_error_state_requires_message(self, message, fatal):
        """ERROR state requires message field."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(
            mock_server, BackendState.ERROR.value, message=message, fatal=fatal
        )

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.STATE_CHANGED
        assert call_args.payload["state"] == BackendState.ERROR.value
        assert call_args.payload["message"] == message
        assert call_args.payload["fatal"] == fatal
        assert handler._current_state == BackendState.ERROR.value

    def test_error_state_without_message_raises_error(self):
        """ERROR state without message raises ValueError."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        with pytest.raises(ValueError, match="message must be provided"):
            handler._emit_state_changed(mock_server, BackendState.ERROR.value, fatal=True)

    @given(state=st.sampled_from(["loading", "idle", "paused"]))
    def test_simple_states_no_extra_fields(self, state):
        """LOADING, IDLE, PAUSED states don't require extra fields."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, state)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.STATE_CHANGED
        assert call_args.payload["state"] == state
        assert call_args.payload.get("prompt") is None
        assert call_args.payload.get("message") is None
        assert call_args.payload.get("fatal") is None
        assert handler._current_state == state

    @given(
        prompt1=st.text(min_size=1, max_size=100),
        prompt2=st.text(min_size=1, max_size=100),
    )
    def test_state_transitions_update_current_state(self, prompt1, prompt2):
        """State transitions correctly update _current_state."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(mock_server, BackendState.LOADING.value)
        assert handler._current_state == BackendState.LOADING.value

        handler._emit_state_changed(mock_server, BackendState.IDLE.value)
        assert handler._current_state == BackendState.IDLE.value

        handler._emit_state_changed(mock_server, BackendState.GENERATING.value, prompt=prompt1)
        assert handler._current_state == BackendState.GENERATING.value

        handler._emit_state_changed(mock_server, BackendState.GENERATING.value, prompt=prompt2)
        assert handler._current_state == BackendState.GENERATING.value

        handler._emit_state_changed(mock_server, BackendState.PAUSED.value)
        assert handler._current_state == BackendState.PAUSED.value

    def test_payload_constraints_generating_no_message(self):
        """GENERATING state should not have message/fatal fields in payload."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(
            mock_server, BackendState.GENERATING.value, prompt="test prompt"
        )

        call_args = mock_server.send.call_args[0][0]
        assert call_args.payload.get("message") is None
        assert call_args.payload.get("fatal") is None

    def test_payload_constraints_error_no_prompt(self):
        """ERROR state should not have prompt field in payload."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        handler._emit_state_changed(
            mock_server, BackendState.ERROR.value, message="error occurred", fatal=True
        )

        call_args = mock_server.send.call_args[0][0]
        assert call_args.payload.get("prompt") is None

    def test_thread_safety_concurrent_state_changes(self):
        """Concurrent state changes are thread-safe."""
        import concurrent.futures

        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        states = [
            BackendState.LOADING.value,
            BackendState.IDLE.value,
            BackendState.PAUSED.value,
        ]

        def change_state(state):
            handler._emit_state_changed(mock_server, state)

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(change_state, state) for state in states * 10]
            concurrent.futures.wait(futures)

        assert handler._current_state in states

    @given(
        prompt=st.text(min_size=1, max_size=200),
        message=st.text(min_size=1, max_size=200),
    )
    def test_all_valid_state_transitions(self, prompt, message):
        """All valid state transitions work correctly."""
        from textbrush.ipc.protocol import BackendState

        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()

        transitions = [
            (BackendState.LOADING.value, {}),
            (BackendState.IDLE.value, {}),
            (BackendState.GENERATING.value, {"prompt": prompt}),
            (BackendState.IDLE.value, {}),
            (BackendState.PAUSED.value, {}),
            (BackendState.GENERATING.value, {"prompt": prompt}),
            (BackendState.ERROR.value, {"message": message, "fatal": False}),
        ]

        for state, kwargs in transitions:
            handler._emit_state_changed(mock_server, state, **kwargs)
            assert handler._current_state == state


class TestUpdateConfigCommand:
    """Property-based tests for UPDATE_CONFIG command handling."""

    @given(
        prompt=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    def test_update_config_valid_inputs(self, prompt, aspect_ratio):
        """Valid config updates call update_config and send BUFFER_STATUS."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        payload = {"prompt": prompt, "aspect_ratio": aspect_ratio}
        handler.handle_update_config(payload, mock_server)

        mock_backend.update_config.assert_called_once_with(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            width=None,
            height=None,
            on_generation_start=ANY,
        )
        # BUFFER_STATUS sent to indicate buffer was cleared
        mock_server.send.assert_called_once()
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0
        assert message.payload["max"] == 8
        assert message.payload["generating"] is True

    def test_update_config_no_backend_sends_error(self, handler, mock_server):
        """Update config with no backend sends non-fatal error."""
        handler.backend = None
        payload = {"prompt": "test prompt", "aspect_ratio": "1:1"}

        handler.handle_update_config(payload, mock_server)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is False
        assert "Backend not initialized" in call_args.payload["message"]

    def test_update_config_while_loading_is_queued_not_applied(self, handler, mock_server):
        """UPDATE_CONFIG during model loading is queued instead of raising worker error."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.update_config.side_effect = RuntimeError(
            "No worker to update. Call start_generation() first."
        )
        handler.backend = mock_backend
        handler._generation_started = False

        payload = {
            "prompt": "futuristic neon lobster",
            "aspect_ratio": "1:1",
            "width": 512,
            "height": 512,
        }
        handler.handle_update_config(payload, mock_server)

        mock_backend.update_config.assert_called_once()
        assert handler._pending_startup_config is not None
        assert handler._pending_startup_config["prompt"] == "futuristic neon lobster"
        mock_server.send.assert_not_called()

    def test_init_applies_latest_queued_update_config_before_start_generation(
        self, handler, mock_server
    ):
        """Queued UPDATE_CONFIG during init load overrides INIT config for first generation."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (512, 512)
        mock_backend.update_config.side_effect = RuntimeError(
            "No worker to update. Call start_generation() first."
        )

        first_update = {
            "prompt": "futuristic neon lobster",
            "aspect_ratio": "1:1",
            "width": 256,
            "height": 256,
        }
        second_update = {
            "prompt": "futuristic neon lobster",
            "aspect_ratio": "1:1",
            "width": 512,
            "height": 512,
        }

        def initialize_side_effect():
            # Simulate user edits while model is still loading.
            handler.handle_update_config(first_update, mock_server)
            handler.handle_update_config(second_update, mock_server)

        mock_backend.initialize.side_effect = initialize_side_effect

        class ImmediateThread:
            def __init__(self, target=None, args=(), daemon=None):
                self._target = target
                self._args = args

            def start(self):
                if self._target:
                    self._target(*self._args)

        with patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend):
            with patch("textbrush.ipc.handler.threading.Thread", side_effect=ImmediateThread):
                with patch.object(handler, "_start_image_delivery") as mock_start_delivery:
                    with patch(
                        "textbrush.ipc.handler.check_model_availability", return_value=_available()
                    ):
                        init_payload = {
                            "prompt": "A watercolor painting of a cat",
                            "aspect_ratio": "1:1",
                            "width": 256,
                            "height": 256,
                            # Deferred loading: naming the model is what
                            # starts the load this test queues against.
                            "model_id": FLUX1_SCHNELL,
                        }
                        handler.handle_init(init_payload, mock_server)

                        mock_backend.start_generation.assert_called_once()
                        start_call = mock_backend.start_generation.call_args.kwargs
                        assert start_call["prompt"] == "futuristic neon lobster"
                        assert start_call["width"] == 512
                        assert start_call["height"] == 512
                        mock_start_delivery.assert_called_once()

        error_events = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.ERROR
        ]
        assert len(error_events) == 0

    @given(invalid_aspect=st.text().filter(lambda x: x not in set(TEXT_ASPECT_RATIOS) | {"custom"}))
    def test_update_config_invalid_aspect_ratio_sends_error(self, invalid_aspect):
        """A ratio outside the shared vocabulary sends a non-fatal error.

        The excluded set is read from `validation.TEXT_ASPECT_RATIOS`, not
        restated: it was a literal three-entry set here, so every ratio
        added since (3:1, 4:1, 4:5, and later 4:3 and 3:4) was being
        generated as "invalid" input for a handler that should accept it.
        """
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        handler.backend = mock_backend

        payload = {"prompt": "test prompt", "aspect_ratio": invalid_aspect}
        handler.handle_update_config(payload, mock_server)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is False
        assert "Invalid aspect_ratio" in call_args.payload["message"]
        mock_backend.abort.assert_not_called()
        mock_backend.start_generation.assert_not_called()

    @given(
        empty_prompt=st.one_of(
            st.just(""),
            st.text(max_size=20).filter(lambda x: not x.strip()),
        )
    )
    def test_update_config_empty_prompt_sends_error(self, empty_prompt):
        """Empty or whitespace-only prompt sends non-fatal error."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        handler.backend = mock_backend

        payload = {"prompt": empty_prompt, "aspect_ratio": "1:1"}
        handler.handle_update_config(payload, mock_server)

        mock_server.send.assert_called_once()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is False
        assert "Prompt cannot be empty" in call_args.payload["message"]
        mock_backend.abort.assert_not_called()
        mock_backend.start_generation.assert_not_called()

    def test_update_config_calls_update_config_on_backend(self, handler, mock_server):
        """Update config calls backend.update_config with correct params."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        payload = {"prompt": "new prompt", "aspect_ratio": "16:9"}
        handler.handle_update_config(payload, mock_server)

        mock_backend.update_config.assert_called_once()
        call_kwargs = mock_backend.update_config.call_args[1]
        assert call_kwargs["prompt"] == "new prompt"
        assert call_kwargs["aspect_ratio"] == "16:9"

    def test_update_config_sends_buffer_status(self, handler, mock_server):
        """Update config sends BUFFER_STATUS showing cleared buffer."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        payload = {"prompt": "new prompt", "aspect_ratio": "1:1"}
        handler.handle_update_config(payload, mock_server)

        # BUFFER_STATUS sent to indicate buffer was cleared after config update
        mock_server.send.assert_called_once()
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0
        assert message.payload["generating"] is True

    def test_update_config_preserves_pause_state(self, handler, mock_server):
        """Update config preserves paused state in BUFFER_STATUS."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True  # Was paused before
        handler.backend = mock_backend

        payload = {"prompt": "new prompt", "aspect_ratio": "1:1"}
        handler.handle_update_config(payload, mock_server)

        # BUFFER_STATUS sent with generating=False since paused
        mock_server.send.assert_called_once()
        message = mock_server.send.call_args[0][0]
        assert message.type == MessageType.BUFFER_STATUS
        assert message.payload["count"] == 0
        assert message.payload["generating"] is False  # Paused state preserved

    @given(
        prompt=st.text(min_size=1, max_size=200).filter(lambda x: x.strip()),
        aspect_ratio=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    def test_update_config_uses_update_config_method(self, prompt, aspect_ratio):
        """Update config calls update_config (seeds auto-generated by worker)."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        payload = {"prompt": prompt, "aspect_ratio": aspect_ratio}
        handler.handle_update_config(payload, mock_server)

        mock_backend.update_config.assert_called_once()
        call_kwargs = mock_backend.update_config.call_args[1]
        assert call_kwargs["prompt"] == prompt
        assert call_kwargs["aspect_ratio"] == aspect_ratio
        # update_config doesn't take seed - seeds are auto-generated by worker
        assert "seed" not in call_kwargs

    @given(
        prompt1=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        prompt2=st.text(min_size=1, max_size=100).filter(lambda x: x.strip()),
        aspect1=st.sampled_from(["1:1", "16:9", "9:16"]),
        aspect2=st.sampled_from(["1:1", "16:9", "9:16"]),
    )
    def test_update_config_multiple_updates(self, prompt1, prompt2, aspect1, aspect2):
        """Multiple config updates work correctly."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        payload1 = {"prompt": prompt1, "aspect_ratio": aspect1}
        handler.handle_update_config(payload1, mock_server)

        payload2 = {"prompt": prompt2, "aspect_ratio": aspect2}
        handler.handle_update_config(payload2, mock_server)

        assert mock_backend.update_config.call_count == 2

        last_call_kwargs = mock_backend.update_config.call_args[1]
        assert last_call_kwargs["prompt"] == prompt2
        assert last_call_kwargs["aspect_ratio"] == aspect2

    def test_update_config_does_not_restart_image_delivery_thread(self, handler, mock_server):
        """Update config does not create new image delivery thread."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        handler.backend = mock_backend

        with patch.object(handler, "_start_image_delivery") as mock_delivery:
            payload = {"prompt": "new prompt", "aspect_ratio": "1:1"}
            handler.handle_update_config(payload, mock_server)

            mock_delivery.assert_not_called()


class TestGenerationStartCallbackPromptBinding:
    """Tests for on_generation_start callback prompt binding.

    BUG SCENARIO (pre-fix):
    1. INIT command with prompt "cat" - sets _current_prompt = "cat"
    2. Worker starts generating with prompt "cat"
    3. UPDATE_CONFIG with prompt "dog" - sets _current_prompt = "dog"
    4. Worker fires on_generation_start callback (still generating "cat")
    5. BUG: state_changed emitted with prompt="dog" (from _current_prompt)
       CORRECT: state_changed should emit prompt="cat" (the actual generation prompt)

    The fix is to capture the prompt at callback registration time, not read
    _current_prompt dynamically in the callback.
    """

    def test_init_on_generation_start_uses_correct_prompt_after_config_update(
        self, handler, mock_server
    ):
        """on_generation_start callback from handle_init uses INIT prompt, not updated prompt.

        This tests the race condition where UPDATE_CONFIG changes _current_prompt
        but the worker's on_generation_start callback should still use the original
        prompt from when the generation was started.
        """
        # Capture the on_generation_start callback passed to start_generation
        captured_callback = None

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        mock_backend.initialize.return_value = None

        def capture_start_generation(**kwargs):
            nonlocal captured_callback
            captured_callback = kwargs.get("on_generation_start")

        mock_backend.start_generation.side_effect = capture_start_generation
        mock_backend.update_config.return_value = None
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (256, 256)

        # Step 1: INIT with prompt "cat". Deferred loading: naming the
        # model is what starts the load.
        init_payload = {
            "prompt": "cat painting",
            "aspect_ratio": "1:1",
            "model_id": FLUX1_SCHNELL,
        }

        # Mock _init_backend to call on_ready synchronously for testing
        def mock_init_backend(on_ready, server):
            handler.backend.initialize()
            on_ready()

        # Patch TextbrushBackend constructor to return our mock
        with (
            patch("textbrush.ipc.handler.check_model_availability", return_value=_available()),
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch.object(handler, "_init_backend", side_effect=mock_init_backend),
        ):
            handler.handle_init(init_payload, mock_server)

        # Verify callback was captured
        assert captured_callback is not None, "on_generation_start callback should be captured"

        # Step 2: UPDATE_CONFIG with prompt "dog" (changes _current_prompt)
        update_payload = {"prompt": "dog portrait", "aspect_ratio": "1:1"}
        handler.handle_update_config(update_payload, mock_server)

        # Verify _current_prompt changed
        assert handler._current_prompt == "dog portrait"

        # Step 3: Simulate worker calling on_generation_start for the ORIGINAL "cat" generation
        mock_server.reset_mock()
        captured_callback(seed=12345, queue_position=0)

        # Step 4: Verify state_changed was emitted with ORIGINAL prompt "cat painting"
        # NOT the current _current_prompt "dog portrait"
        state_changed_calls = [
            call
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert len(state_changed_calls) == 1

        state_payload = state_changed_calls[0][0][0].payload
        assert state_payload["state"] == "generating"
        # This is the key assertion - prompt should be "cat painting", not "dog portrait"
        assert state_payload["prompt"] == "cat painting", (
            f"Expected prompt 'cat painting' from original generation, "
            f"got '{state_payload['prompt']}' (likely using stale _current_prompt)"
        )

    def test_update_config_on_generation_start_uses_correct_prompt_after_another_update(
        self, handler, mock_server
    ):
        """on_generation_start callback from handle_update_config uses that UPDATE's prompt.

        Similar race condition test but for update_config's callback.
        """
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = False
        handler.backend = mock_backend

        # Capture the on_generation_start callbacks
        captured_callbacks = []

        def capture_update_config(**kwargs):
            callback = kwargs.get("on_generation_start")
            if callback:
                captured_callbacks.append(callback)

        mock_backend.update_config.side_effect = capture_update_config

        # Step 1: First UPDATE_CONFIG with prompt "cat"
        payload1 = {"prompt": "cat painting", "aspect_ratio": "1:1"}
        handler.handle_update_config(payload1, mock_server)

        # Step 2: Second UPDATE_CONFIG with prompt "dog" (before first generation completes)
        payload2 = {"prompt": "dog portrait", "aspect_ratio": "1:1"}
        handler.handle_update_config(payload2, mock_server)

        assert len(captured_callbacks) == 2

        # Step 3: Simulate worker calling on_generation_start for FIRST update ("cat")
        mock_server.reset_mock()
        captured_callbacks[0](seed=12345, queue_position=0)

        # Step 4: Verify state_changed uses "cat painting", not "dog portrait"
        state_changed_calls = [
            call
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.STATE_CHANGED
        ]
        assert len(state_changed_calls) == 1

        state_payload = state_changed_calls[0][0][0].payload
        assert state_payload["prompt"] == "cat painting", (
            f"Expected prompt 'cat painting' from first update, got '{state_payload['prompt']}'"
        )


def _state_changed(mock_server, state: str) -> list:
    """All STATE_CHANGED payloads recorded for `state`, in emission order."""
    return [
        call[0][0].payload
        for call in mock_server.send.call_args_list
        if call[0][0].type == MessageType.STATE_CHANGED and call[0][0].payload["state"] == state
    ]


def _config_acks(mock_server) -> list:
    """All CONFIG_ACK payloads recorded, in emission order."""
    return [
        call[0][0].payload
        for call in mock_server.send.call_args_list
        if call[0][0].type == MessageType.CONFIG_ACK
    ]


class _ImmediateThread:
    """threading.Thread stand-in that runs the target on the calling thread."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        if self._target:
            self._target(*self._args)


class TestInitBackendChecksResolvedModel:
    """_init_backend must check (and download) the model handle_init
    actually resolved, not a hard-coded FLUX.1 schnell.

    Regression: the availability probe was `is_flux_available(...)`, i.e.
    schnell only. A launch that correctly resolved to klein-4B (the only
    installed model) then aborted fatally, or -- with HF credentials
    present -- downloaded schnell's weights instead of the model the user
    was about to run.
    """

    def test_checks_the_resolved_model(self, handler, mock_server):
        """Availability is probed for config.model.selected_id."""
        handler.config.model.selected_id = FLUX2_KLEIN_4B
        checked: list[str] = []

        def availability(model_id, *, custom_dirs=None):
            checked.append(model_id)
            return _available() if model_id == FLUX2_KLEIN_4B else _absent()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", side_effect=availability):
            with patch("textbrush.ipc.handler.download_model_weights") as mock_download:
                handler._init_backend(lambda: None, mock_server)

        assert checked == [FLUX2_KLEIN_4B], (
            f"availability must be checked for the resolved model, got {checked}"
        )
        mock_backend.initialize.assert_called_once()
        mock_download.assert_not_called()
        assert _state_changed(mock_server, "error") == []

    def test_falls_back_to_schnell_without_a_committed_selection(self, handler, mock_server):
        """No committed selection keeps the pre-resolution schnell default."""
        handler.config.model.selected_id = None
        checked: list[str] = []

        def availability(model_id, *, custom_dirs=None):
            checked.append(model_id)
            return _available()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", side_effect=availability):
            handler._init_backend(lambda: None, mock_server)

        assert checked == [FLUX1_SCHNELL]

    def test_downloads_the_resolved_model(self, handler, mock_server):
        """A missing resolved model downloads THAT model, not schnell."""
        handler.config.model.selected_id = FLUX2_KLEIN_4B

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock()
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            with patch("textbrush.ipc.handler.download_model_weights") as mock_download:
                with patch.object(handler, "_detect_hf_credentials", return_value="hf_test_token"):
                    handler._init_backend(lambda: None, mock_server)

        mock_download.assert_called_once_with(FLUX2_KLEIN_4B)
        mock_backend.initialize.assert_called_once()

    def test_missing_model_message_names_the_resolved_model(self, handler, mock_server):
        """The fatal setup instructions name the model that is missing."""
        handler.config.model.selected_id = FLUX2_KLEIN_4B
        handler.config.huggingface.token = None
        spec = get_model_spec(FLUX2_KLEIN_4B)

        mock_backend = Mock(spec=TextbrushBackend)
        handler.backend = mock_backend

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            with patch.object(handler, "_detect_hf_credentials", return_value=None):
                handler._init_backend(lambda: None, mock_server)

        errors = _state_changed(mock_server, "error")
        assert len(errors) == 1
        assert errors[0]["fatal"] is True
        assert spec.display_name in errors[0]["message"]
        assert spec.license_url in errors[0]["message"]
        assert "FLUX.1 schnell" not in errors[0]["message"]
        mock_backend.initialize.assert_not_called()


class TestDeferredModelSelection:
    """Deferred loading: INIT loads nothing, and the first UPDATE_CONFIG
    carrying a model_id is what starts the session.

    The point is that the UI stays responsive rather than spending tens
    of seconds (or a multi-gigabyte download) on a model the user may not
    want, so "no backend is constructed" is the load-bearing assertion
    here, not an implementation detail.
    """

    def test_init_without_a_selection_constructs_no_backend(self, handler, mock_server):
        handler.handle_init({"prompt": "cat", "aspect_ratio": "1:1"}, mock_server)

        assert handler.backend is None
        states = _state_changed(mock_server, "awaiting_model")
        assert states, "INIT with no model selected must park in awaiting_model"

    def test_update_config_with_a_model_id_starts_the_session(self, handler, mock_server):
        """The selection arrives as UPDATE_CONFIG and creates the backend
        that INIT deliberately did not."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True
        mock_backend.is_settled.return_value = True
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (512, 512)

        handler.handle_init({"prompt": "cat", "aspect_ratio": "1:1"}, mock_server)
        assert handler.backend is None

        with (
            patch("textbrush.ipc.handler.check_model_availability", return_value=_available()),
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch("textbrush.ipc.handler.threading.Thread", side_effect=_ImmediateThread),
            patch.object(handler, "_init_backend", side_effect=lambda on_ready, server: on_ready()),
            patch.object(handler, "_start_image_delivery"),
        ):
            handler.handle_update_config(
                {
                    "prompt": "cat",
                    "aspect_ratio": "1:1",
                    "width": 512,
                    "height": 512,
                    "model_id": FLUX1_SCHNELL,
                },
                mock_server,
            )

        assert handler.backend is mock_backend
        mock_backend.start_generation.assert_called_once()
        start_kwargs = mock_backend.start_generation.call_args.kwargs
        assert start_kwargs["width"] == 512 and start_kwargs["height"] == 512

    def test_update_config_without_a_model_id_still_reports_no_backend(self, handler, mock_server):
        """Only a model_id counts as the selection; a prompt-only update
        while awaiting has nothing to act on."""
        handler.handle_init({"prompt": "cat", "aspect_ratio": "1:1"}, mock_server)
        mock_server.send.reset_mock()

        handler.handle_update_config({"prompt": "dog", "aspect_ratio": "1:1"}, mock_server)

        assert handler.backend is None
        errors = [
            call[0][0].payload
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.ERROR
        ]
        assert errors and errors[0]["fatal"] is False

    def test_an_unavailable_selection_is_non_fatal_and_reopens_the_selection(
        self, handler, mock_server
    ):
        """A model whose weights are absent must not end the session:
        with deferred loading there is always another model to pick."""
        handler.handle_init({"prompt": "cat", "aspect_ratio": "1:1"}, mock_server)
        mock_server.send.reset_mock()

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_absent()):
            handler.handle_update_config(
                {"prompt": "cat", "aspect_ratio": "1:1", "model_id": FLUX2_KLEIN_4B},
                mock_server,
            )

        assert handler.backend is None
        errors = [
            call[0][0].payload
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.ERROR
        ]
        assert errors, "a blocked selection must be reported"
        assert errors[0]["fatal"] is False, (
            "an unavailable model is a rejected pick, not a dead app"
        )
        assert get_model_spec(FLUX2_KLEIN_4B).display_name in errors[0]["message"]
        assert _state_changed(mock_server, "awaiting_model"), (
            "the session must return to awaiting_model so another model can be chosen"
        )

    def test_model_list_names_every_registered_model_with_its_cardinality(
        self, handler, mock_server
    ):
        """The UI renders its selector from this event, including which
        models take reference images and which are installed."""
        from textbrush.model.registry import iter_model_slugs

        with patch("textbrush.ipc.handler.check_model_availability", return_value=_available()):
            handler._emit_model_list(mock_server)

        payloads = [
            call[0][0].payload
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.MODEL_LIST
        ]
        assert len(payloads) == 1
        listed = {entry["model_id"]: entry for entry in payloads[0]["models"]}
        assert list(listed) == list(iter_model_slugs()), "registry order, every model"
        for slug, entry in listed.items():
            spec = get_model_spec(slug)
            assert entry["display_name"] == spec.display_name
            assert entry["min_references"] == spec.min_references
            assert entry["max_references"] == spec.max_references
            assert entry["available"] is True


class TestLaunchSettledSignal:
    """The launch-time `state_changed(paused, ...)` must report the
    worker's real quiescence.

    Regression: launch hard-coded settled=False and nothing ever emitted
    settled=True afterwards (start_generation takes no on_settled
    callback), so every consumer gating on that flag stayed disabled until
    a full resume/pause cycle -- while the handler's own editing gate
    (`is_paused() and is_settled()`) already accepted editing commands.
    """

    def _launch(self, handler, mock_server, mock_backend):
        def init_backend(on_ready, server):
            on_ready()

        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = ()
        mock_backend.reference_paths = ()
        mock_backend.preset = None
        mock_backend.canvas = (256, 256)
        with (
            patch("textbrush.ipc.handler.check_model_availability", return_value=_available()),
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch("textbrush.ipc.handler.threading.Thread", side_effect=_ImmediateThread),
            patch.object(handler, "_init_backend", side_effect=init_backend),
            patch.object(handler, "_start_image_delivery"),
        ):
            # Deferred loading: INIT loads only the model it is told to.
            handler.handle_init(
                {"prompt": "a cat", "aspect_ratio": "1:1", "model_id": FLUX1_SCHNELL},
                mock_server,
            )

    def test_settled_true_when_worker_parks_at_launch(self, handler, mock_server):
        """A worker started paused is settled immediately; say so."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True
        mock_backend.is_settled.return_value = True

        self._launch(handler, mock_server, mock_backend)

        paused = _state_changed(mock_server, "paused")
        assert paused, "launch must emit state_changed(paused)"
        assert paused[-1]["settled"] is True, (
            "launch reported the worker as unsettled although it is parked; "
            "editing controls gated on this flag stay disabled"
        )

    def test_launch_config_ack_reports_the_same_settled_value(self, handler, mock_server):
        """The launch config_ack carries backend truth, not a fixed False."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True
        mock_backend.is_settled.return_value = True

        self._launch(handler, mock_server, mock_backend)

        acks = _config_acks(mock_server)
        assert len(acks) == 1
        assert acks[0]["settled"] is True

    def test_settled_false_when_worker_has_not_parked(self, handler, mock_server):
        """The value is read from the backend, not hard-coded the other way."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True
        mock_backend.is_settled.return_value = False

        self._launch(handler, mock_server, mock_backend)

        paused = _state_changed(mock_server, "paused")
        assert paused
        assert paused[-1]["settled"] is False


class TestEditingUpdateHonoursPrompt:
    """The editing branch of handle_update_config must apply the prompt
    that travelled with the editing fields.

    Regression: the branch returned right after emitting config_ack, so a
    prompt the user had typed but not blurred was silently discarded on
    every reference add/remove or model switch, and _current_prompt went
    stale for every later state_changed(generating).
    """

    @staticmethod
    def _editing_backend():
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.max_size = 8
        mock_backend.is_paused.return_value = True
        mock_backend.is_settled.return_value = True
        mock_backend.model_id = FLUX2_KLEIN_4B
        mock_backend.references = ["ref-a", "ref-b"]
        mock_backend.reference_paths = ["/tmp/a.png", "/tmp/b.png"]
        mock_backend.preset = None
        # The acknowledged output canvas travels on every config_ack, so
        # the UI can reconcile its output-size group to backend truth.
        mock_backend.canvas = (768, 576)
        return mock_backend

    def test_editing_update_applies_the_prompt(self, handler, mock_server):
        """An editing update propagates its prompt to the backend."""
        mock_backend = self._editing_backend()
        handler.backend = mock_backend
        handler._current_prompt = "stale prompt"

        handler.handle_update_config(
            {
                "prompt": "unblurred new prompt",
                "aspect_ratio": "custom",
                "references": ["/tmp/a.png", "/tmp/b.png"],
            },
            mock_server,
        )

        mock_backend.apply_configuration.assert_called_once()
        assert handler._current_prompt == "unblurred new prompt", (
            "editing update dropped the prompt; _current_prompt is stale"
        )
        mock_backend.update_config.assert_called_once()
        assert mock_backend.update_config.call_args.kwargs["prompt"] == "unblurred new prompt"
        assert _config_acks(mock_server), "editing update must still emit config_ack"

    def test_editing_update_rebinds_generation_start_prompt(self, handler, mock_server):
        """state_changed(generating) after the edit uses the new prompt."""
        mock_backend = self._editing_backend()
        handler.backend = mock_backend
        handler._current_prompt = "stale prompt"

        handler.handle_update_config(
            {"prompt": "new prompt", "aspect_ratio": "custom", "preset": "edit_1024"},
            mock_server,
        )

        on_generation_start = mock_backend.update_config.call_args.kwargs["on_generation_start"]
        assert on_generation_start is not None
        mock_server.reset_mock()
        on_generation_start(seed=7, queue_position=0)

        generating = _state_changed(mock_server, "generating")
        assert len(generating) == 1
        assert generating[0]["prompt"] == "new prompt"

    def test_editing_update_reports_the_cleared_buffer(self, handler, mock_server):
        """update_config clears the buffer, so BUFFER_STATUS follows."""
        mock_backend = self._editing_backend()
        handler.backend = mock_backend

        handler.handle_update_config(
            {"prompt": "new prompt", "aspect_ratio": "custom", "references": []},
            mock_server,
        )

        buffer_events = [
            call[0][0].payload
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.BUFFER_STATUS
        ]
        assert len(buffer_events) == 1
        assert buffer_events[0]["count"] == 0

    def test_empty_prompt_is_skipped_not_rejected(self, handler, mock_server):
        """A blank prompt is not a change and must not fail the edit."""
        mock_backend = self._editing_backend()
        handler.backend = mock_backend
        handler._current_prompt = "kept prompt"

        handler.handle_update_config(
            {"prompt": "   ", "aspect_ratio": "custom", "references": ["/tmp/a.png"]},
            mock_server,
        )

        mock_backend.apply_configuration.assert_called_once()
        mock_backend.update_config.assert_not_called()
        assert handler._current_prompt == "kept prompt"
        error_events = [
            call[0][0]
            for call in mock_server.send.call_args_list
            if call[0][0].type == MessageType.ERROR
        ]
        assert error_events == []

    def test_rejected_editing_update_still_rolls_back_without_touching_prompt(
        self, handler, mock_server
    ):
        """A refused editing update leaves the prompt and worker alone."""
        from textbrush.backend import ModelUnavailableError

        mock_backend = self._editing_backend()
        mock_backend.apply_configuration.side_effect = ModelUnavailableError(
            DiscoveryCause.ABSENT, "no local marker found", FLUX2_KLEIN_4B
        )
        handler.backend = mock_backend
        handler._current_prompt = "kept prompt"

        handler.handle_update_config(
            {"prompt": "new prompt", "aspect_ratio": "custom", "model_id": FLUX2_KLEIN_4B},
            mock_server,
        )

        mock_backend.update_config.assert_not_called()
        assert handler._current_prompt == "kept prompt"
        assert _config_acks(mock_server), "a rejected update must still emit the rollback ack"


class TestPauseSettleEventOrdering:
    """handle_pause must emit settled=False before the settle callback
    can fire.

    Regression: the callback was registered first and settled=False was
    emitted afterwards. The callback runs on the worker thread the moment
    it parks, so a worker between iterations emitted settled=True first
    and the handler's settled=False then clobbered it.
    """

    def test_settled_false_precedes_settled_true(self, handler, mock_server):
        """An immediately-parking worker still yields False then True."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.is_paused.return_value = False

        def pause_generation(on_settled=None):
            # Worst case: the worker parks and settles before
            # pause_generation() has even returned.
            if on_settled is not None:
                on_settled()

        mock_backend.pause_generation.side_effect = pause_generation
        handler.backend = mock_backend
        handler._generation_started = True

        handler.handle_pause(mock_server)

        assert [p["settled"] for p in _state_changed(mock_server, "paused")] == [False, True], (
            "settled=False must be emitted before the worker's settled=True"
        )

    def test_resume_branch_is_unchanged(self, handler, mock_server):
        """Resuming still emits state_changed(generating) with the prompt."""
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.is_paused.return_value = True
        mock_backend.model_id = FLUX1_SCHNELL
        mock_backend.references = []
        mock_backend.preset = None
        handler.backend = mock_backend
        handler._generation_started = True
        handler._current_prompt = "a cat"

        handler.handle_pause(mock_server)

        mock_backend.resume_generation.assert_called_once()
        generating = _state_changed(mock_server, "generating")
        assert len(generating) == 1
        assert generating[0]["prompt"] == "a cat"
        assert _state_changed(mock_server, "paused") == []

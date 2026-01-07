"""Property-based tests for IPC message handler."""

from __future__ import annotations

import base64
import io
import threading
import time
from unittest.mock import Mock, patch

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
        }

        with patch.object(handler, "_init_backend"):
            handler.handle_init(payload, mock_server)

        assert handler.backend is not None
        assert isinstance(handler.backend, TextbrushBackend)

    def test_init_creates_backend(self, handler, mock_server):
        """Init command creates TextbrushBackend instance."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
        }

        with patch.object(handler, "_init_backend"):
            handler.handle_init(payload, mock_server)

        assert handler.backend is not None

    def test_init_starts_background_thread(self, handler, mock_server):
        """Init command starts background initialization thread."""
        payload = {
            "prompt": "test prompt",
            "seed": None,
            "aspect_ratio": "1:1",
        }

        init_called = threading.Event()

        def mock_init_backend(on_ready, server):
            init_called.set()

        with patch.object(handler, "_init_backend", side_effect=mock_init_backend):
            handler.handle_init(payload, mock_server)
            assert init_called.wait(timeout=1.0)


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

    @given(
        buffer_count=st.integers(min_value=0, max_value=8),
        buffer_max=st.integers(min_value=1, max_value=16),
    )
    def test_skip_sends_buffer_status(self, buffer_count, buffer_max):
        """Skip sends BUFFER_STATUS with correct values."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        handler.backend = Mock(spec=TextbrushBackend)
        handler.backend.buffer = Mock()
        handler.backend.buffer.__len__ = Mock(return_value=buffer_count)
        handler.backend.buffer.max_size = buffer_max

        handler.handle_skip(mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.BUFFER_STATUS
        assert call_args.payload["count"] == buffer_count
        assert call_args.payload["max"] == buffer_max
        assert call_args.payload["generating"] is True


class TestAcceptCommand:
    """Property-based tests for ACCEPT command handling."""

    def test_accept_no_image_sends_error(self, handler, mock_server):
        """Accept with no current image sends non-fatal error."""
        handler._current_image = None
        handler.backend = None

        handler.handle_accept(mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is False
        assert "No image to accept" in call_args.payload["message"]

    def test_accept_saves_image(self, handler, mock_server, tmp_path):
        """Accept command saves current image to disk."""
        handler._current_image = Mock()
        handler._output_path = tmp_path / "test.png"

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_current = Mock(return_value=tmp_path / "test.png")
        handler.backend = mock_backend

        handler.handle_accept(mock_server)

        mock_backend.accept_current.assert_called_once_with(handler._output_path)
        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ACCEPTED

    def test_accept_signals_delivery_thread(self, handler, mock_server, tmp_path):
        """Accept command signals waiting delivery thread."""
        handler._current_image = Mock()
        handler._output_path = tmp_path / "test.png"

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_current = Mock(return_value=tmp_path / "test.png")
        handler.backend = mock_backend

        handler._action_event.clear()
        handler.handle_accept(mock_server)

        assert handler._action_event.is_set()

    def test_accept_exception_sends_error(self, handler, mock_server):
        """Accept handles backend exceptions gracefully."""
        handler._current_image = Mock()

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.accept_current = Mock(side_effect=RuntimeError("Disk full"))
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


class TestStatusCommand:
    """Property-based tests for STATUS command handling."""

    @given(
        buffer_count=st.integers(min_value=0, max_value=8),
        buffer_max=st.integers(min_value=1, max_value=16),
        has_worker=st.booleans(),
    )
    def test_status_reports_buffer_state(self, buffer_count, buffer_max, has_worker):
        """Status command reports accurate buffer state."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.buffer = Mock()
        mock_backend.buffer.__len__ = Mock(return_value=buffer_count)
        mock_backend.buffer.max_size = buffer_max
        mock_backend._worker = Mock() if has_worker else None
        handler.backend = mock_backend

        handler.handle_status(mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.BUFFER_STATUS
        assert call_args.payload["count"] == buffer_count
        assert call_args.payload["max"] == buffer_max
        assert call_args.payload["generating"] is has_worker

    def test_status_no_backend_no_send(self, handler, mock_server):
        """Status command does nothing if no backend."""
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


class TestBase64Encoding:
    """Property-based tests for image base64 encoding."""

    @given(
        width=st.integers(min_value=64, max_value=512),
        height=st.integers(min_value=64, max_value=512),
        r=st.integers(min_value=0, max_value=255),
        g=st.integers(min_value=0, max_value=255),
        b=st.integers(min_value=0, max_value=255),
    )
    def test_base64_encoding_roundtrip(self, width, height, r, g, b):
        """Base64 encoded images can be decoded correctly."""
        original_image = Image.new("RGB", (width, height), color=(r, g, b))

        buffer = io.BytesIO()
        original_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode()

        decoded_data = base64.b64decode(encoded)
        decoded_image = Image.open(io.BytesIO(decoded_data))

        assert decoded_image.size == (width, height)
        assert decoded_image.mode == "RGB"

    @given(seed=st.integers(min_value=0, max_value=2**31 - 1))
    def test_image_delivery_encodes_correctly(self, seed):
        """Image delivery thread encodes images as base64 PNG."""
        config = get_default_config()
        handler = MessageHandler(config)
        mock_server = Mock()
        test_image = Image.new("RGB", (128, 128), color=(100, 150, 200))
        buffered = BufferedImage(image=test_image, seed=seed)

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.get_next_image = Mock(side_effect=[buffered, None])
        mock_backend.check_worker_error = Mock(return_value=None)
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
                assert "image_data" in msg.payload
                assert msg.payload["seed"] == seed

                encoded = msg.payload["image_data"]
                decoded_data = base64.b64decode(encoded)
                decoded_image = Image.open(io.BytesIO(decoded_data))
                assert decoded_image.size == (128, 128)

        assert image_ready_sent


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

        handler._init_backend(on_ready, mock_server)

        assert ready_called.is_set()
        mock_backend.initialize.assert_called_once()

    def test_init_backend_failure_sends_fatal_error(self, handler, mock_server):
        """Backend init failure sends fatal ERROR event."""

        def on_ready():
            pass

        mock_backend = Mock(spec=TextbrushBackend)
        mock_backend.initialize = Mock(side_effect=RuntimeError("Model load failed"))
        handler.backend = mock_backend

        handler._init_backend(on_ready, mock_server)

        mock_server.send.assert_called()
        call_args = mock_server.send.call_args[0][0]
        assert call_args.type == MessageType.ERROR
        assert call_args.payload["fatal"] is True
        assert "Model load failed" in call_args.payload["message"]


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

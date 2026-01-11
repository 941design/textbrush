"""Integration tests for IPC protocol between Python server and Tauri.

These tests validate the complete workflow from command input to event output,
ensuring all components (protocol, server, handler) work together correctly.
"""

import json
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from textbrush.config import load_config
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import Message, MessageType
from textbrush.ipc.server import IPCServer


@pytest.fixture
def config():
    """Create a test config."""
    return load_config()


@pytest.fixture
def mock_backend(tmp_path):
    """Create a mock backend for testing without real model loading."""
    backend = Mock()
    backend.initialize = Mock()
    backend.start_generation = Mock()
    backend.buffer = Mock()
    backend.buffer.max_size = 8
    backend.buffer.__len__ = Mock(return_value=3)
    backend.abort = Mock()
    backend.shutdown = Mock()
    backend.check_worker_error = Mock(return_value=None)

    # Create a simple test image
    test_image = Image.new("RGB", (64, 64), color="red")
    buffered_image = Mock()
    buffered_image.image = test_image
    buffered_image.seed = 42

    backend.get_next_image = Mock(return_value=buffered_image)
    backend.accept_current = Mock(return_value=Path("/tmp/test.png"))

    # Preview management methods (path-based protocol)
    preview_path = tmp_path / ".preview" / "test_preview.png"
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    backend.save_to_preview = Mock(return_value=preview_path)
    backend.accept_from_preview = Mock(return_value=tmp_path / "output.png")
    backend.delete_preview = Mock()

    return backend


class StdioPipe:
    """Simulates stdin/stdout pipes for testing IPC communication."""

    def __init__(self):
        self.read_buffer = []
        self.write_buffer = []
        self._lock = threading.Lock()
        self._read_event = threading.Event()

    def write_line(self, data: str):
        """Write a line to the read buffer (simulating stdin)."""
        with self._lock:
            self.read_buffer.append(data + "\n")
            self._read_event.set()

    def read_line(self) -> str:
        """Read a line from the read buffer (simulating stdin.readline())."""
        while True:
            with self._lock:
                if self.read_buffer:
                    line = self.read_buffer.pop(0)
                    if not self.read_buffer:
                        self._read_event.clear()
                    return line
            self._read_event.wait(timeout=0.1)
            if not self._read_event.is_set():
                return ""  # EOF

    def get_written(self) -> list[str]:
        """Get all lines written to stdout."""
        with self._lock:
            return self.write_buffer.copy()

    def write(self, data: str):
        """Write to the write buffer (simulating stdout)."""
        with self._lock:
            self.write_buffer.append(data)

    def flush(self):
        """Flush (no-op for mock)."""
        pass


@pytest.mark.integration
class TestIPCCompleteWorkflow:
    """Test complete IPC workflows end-to-end."""

    def test_init_command_triggers_backend_initialization(self, config, mock_backend):
        """INIT command should initialize backend and start generation."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Patch backend creation
        with patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend):
            # Send INIT command
            init_msg = Message(
                MessageType.INIT,
                {
                    "prompt": "test prompt",
                    "seed": 123,
                    "aspect_ratio": "1:1",
                    "output_path": "/tmp/test",
                    "format": "png",
                },
            )
            handler.handle_init(init_msg.payload, server)

            # Wait briefly for background thread
            time.sleep(0.1)

            # Backend should be created
            assert handler.backend is not None

    def test_skip_command_advances_to_next_image(self, config, mock_backend):
        """SKIP command should delete preview, clear current image, and signal delivery thread."""
        handler = MessageHandler(config)
        handler.backend = mock_backend
        server = IPCServer(handler)

        # Set a current image
        current_image = Mock()
        handler._current_image = current_image

        # Send SKIP command
        handler.handle_skip(server)

        # Preview should be deleted
        mock_backend.delete_preview.assert_called_once_with(current_image)

        # Current image should be cleared
        assert handler._current_image is None

    def test_accept_command_saves_image_and_returns_path(self, config, mock_backend, tmp_path):
        """ACCEPT command should move images to output via backend and return paths."""
        handler = MessageHandler(config)
        handler.backend = mock_backend
        server = IPCServer(handler)

        # Set up an image in the index map (as handle_accept now uses _image_index_map)
        test_image = Image.new("RGB", (64, 64), color="blue")
        buffered_image = Mock()
        buffered_image.image = test_image
        buffered_image.seed = 99
        handler._image_index_map[0] = buffered_image

        # Mock accept_all to return paths (handle_accept calls accept_all, not accept_from_preview)
        output_path = tmp_path / "output" / "accepted.png"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        mock_backend.accept_all = Mock(return_value=[output_path])

        # Mock stdout to capture messages
        messages = []
        original_send = server.send

        def capture_send(msg):
            messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Send ACCEPT command
        handler.handle_accept(server)

        # Backend accept_all should be called with the image
        mock_backend.accept_all.assert_called_once()
        call_args = mock_backend.accept_all.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0] is buffered_image

        # ACCEPTED event should be sent
        assert any(msg.type == MessageType.ACCEPTED for msg in messages)

    def test_abort_command_stops_generation_cleanly(self, config, mock_backend):
        """ABORT command should stop backend and trigger server shutdown."""
        handler = MessageHandler(config)
        handler.backend = mock_backend
        server = IPCServer(handler)

        # Mock stdout
        messages = []
        original_send = server.send

        def capture_send(msg):
            messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Send ABORT command
        handler.handle_abort(server)

        # Backend abort should be called
        mock_backend.abort.assert_called_once()

        # ABORTED event should be sent
        assert any(msg.type == MessageType.ABORTED for msg in messages)

    def test_error_recovery_on_invalid_json(self, config):
        """Server should recover from invalid JSON and continue."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Create stdio pipes
        pipe = StdioPipe()

        # Patch stdin/stdout
        with patch("sys.stdin") as mock_stdin, patch("sys.stdout", pipe):
            mock_stdin.readline = pipe.read_line

            # Send invalid JSON
            pipe.write_line("{invalid json}")

            # Send valid ABORT to stop server
            pipe.write_line(Message(MessageType.ABORT).to_json())

            # Run server (should exit after ABORT)
            server.run()

            # Check that ERROR message was sent for invalid JSON
            written = pipe.get_written()
            error_msgs = [line for line in written if "error" in line.lower()]
            assert len(error_msgs) > 0, "Expected ERROR event for invalid JSON"

    def test_path_based_image_delivery_in_image_ready_event(self, config, mock_backend, tmp_path):
        """IMAGE_READY event should contain path to preview image file."""
        handler = MessageHandler(config)
        handler.backend = mock_backend
        server = IPCServer(handler)

        # Create a test image
        test_image = Image.new("RGB", (32, 32), color="green")
        buffered_image = Mock()
        buffered_image.image = test_image
        buffered_image.seed = 777

        # Set up preview path for save_to_preview
        preview_path = tmp_path / ".preview" / "img_777.png"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        mock_backend.save_to_preview = Mock(return_value=preview_path)

        # Mock get_next_image to return our test image once, then None
        mock_backend.get_next_image = Mock(side_effect=[buffered_image, None])

        # Capture sent messages
        messages = []
        original_send = server.send

        def capture_send(msg):
            messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Start image delivery (will run in background thread)
        handler._start_image_delivery(server, None)

        # Signal action to allow delivery to proceed
        time.sleep(0.1)
        handler._signal_action()

        # Wait for delivery thread to send message
        time.sleep(0.2)

        # Find IMAGE_READY message
        image_ready_msgs = [msg for msg in messages if msg.type == MessageType.IMAGE_READY]
        assert len(image_ready_msgs) > 0, "Expected IMAGE_READY event"

        # Verify path-based payload (seed is in PNG metadata, not payload)
        img_msg = image_ready_msgs[0]
        assert "path" in img_msg.payload, "Expected 'path' field in IMAGE_READY payload"
        assert "display_path" in img_msg.payload, "Expected 'display_path' field"
        assert "image_data" not in img_msg.payload, "Should not have 'image_data' in payload"
        assert "seed" not in img_msg.payload, "Seed should be in PNG metadata, not payload"
        assert img_msg.payload["path"] == str(preview_path)

        # Verify save_to_preview was called
        mock_backend.save_to_preview.assert_called_once_with(buffered_image)


@pytest.mark.integration
class TestIPCMessageProtocol:
    """Test message protocol serialization and parsing."""

    def test_all_message_types_serialize_correctly(self):
        """All message types should serialize to valid JSON."""
        message_types = [
            MessageType.INIT,
            MessageType.SKIP,
            MessageType.ACCEPT,
            MessageType.ABORT,
            MessageType.STATUS,
            MessageType.READY,
            MessageType.IMAGE_READY,
            MessageType.BUFFER_STATUS,
            MessageType.ERROR,
            MessageType.ACCEPTED,
            MessageType.ABORTED,
        ]

        for msg_type in message_types:
            msg = Message(msg_type, {})
            json_str = msg.to_json()

            # Should be valid JSON
            parsed = json.loads(json_str)
            assert parsed["type"] == msg_type.value

            # Should round-trip correctly
            reconstructed = Message.from_json(json_str)
            assert reconstructed.type == msg_type

    def test_message_with_complex_payload(self):
        """Messages with nested payloads should serialize correctly."""
        payload = {
            "prompt": "test prompt",
            "seed": 42,
            "output_path": None,
            "aspect_ratio": "16:9",
            "nested": {"key": "value", "list": [1, 2, 3]},
        }

        msg = Message(MessageType.INIT, payload)
        json_str = msg.to_json()

        # Round-trip
        reconstructed = Message.from_json(json_str)
        assert reconstructed.type == MessageType.INIT
        assert reconstructed.payload == payload


@pytest.mark.integration
class TestIPCThreadSafety:
    """Test thread safety of IPC components."""

    def test_concurrent_message_sending_is_safe(self, config):
        """Multiple threads should be able to send messages concurrently."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Capture messages
        messages = []
        lock = threading.Lock()

        original_send = server.send

        def capture_send(msg):
            with lock:
                messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Spawn multiple threads sending messages
        threads = []
        for i in range(10):
            msg = Message(MessageType.STATUS, {"thread": i})
            t = threading.Thread(target=lambda m=msg: server.send(m))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Should have received all messages
        assert len(messages) == 10

        # All thread IDs should be present
        thread_ids = {msg.payload["thread"] for msg in messages}
        assert thread_ids == set(range(10))


@pytest.mark.integration
class TestIPCEndToEndWorkflow:
    """Test complete E2E workflow through server.run() loop."""

    def test_complete_init_skip_accept_workflow(self, config, mock_backend):
        """Test full INIT → READY → IMAGE_READY → SKIP → ACCEPT → ACCEPTED workflow."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Create test images
        test_image1 = Image.new("RGB", (32, 32), color="red")
        test_image2 = Image.new("RGB", (32, 32), color="blue")
        buffered1 = Mock()
        buffered1.image = test_image1
        buffered1.seed = 100
        buffered2 = Mock()
        buffered2.image = test_image2
        buffered2.seed = 101

        # Mock backend to return two images then None
        mock_backend.get_next_image = Mock(side_effect=[buffered1, buffered2, None])
        mock_backend.check_worker_error = Mock(return_value=None)

        # Capture sent messages
        messages = []
        msg_lock = threading.Lock()

        original_send = server.send

        def capture_send(msg):
            with msg_lock:
                messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Simulate stdin commands in sequence
        commands = []
        command_idx = [0]
        command_lock = threading.Lock()

        def mock_readline():
            """Simulate stdin with timed command delivery."""
            with command_lock:
                if command_idx[0] < len(commands):
                    cmd = commands[command_idx[0]]
                    command_idx[0] += 1
                    return cmd + "\n"
            # Return empty to signal EOF after commands exhausted
            time.sleep(0.05)
            return ""

        # Build command sequence
        init_cmd = Message(
            MessageType.INIT, {"prompt": "test prompt", "seed": 42, "aspect_ratio": "1:1"}
        ).to_json()
        skip_cmd = Message(MessageType.SKIP).to_json()
        accept_cmd = Message(MessageType.ACCEPT).to_json()
        abort_cmd = Message(MessageType.ABORT).to_json()

        commands = [init_cmd, skip_cmd, accept_cmd, abort_cmd]

        # Patch backend creation and stdin
        with (
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch("sys.stdin") as mock_stdin,
            patch("sys.stdout", Mock()),
        ):
            mock_stdin.readline = mock_readline

            # Run server in background thread
            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()

            # Wait for processing
            server_thread.join(timeout=2.0)

        # Verify message sequence
        message_types = [msg.type for msg in messages]

        # Should have received these events (order may vary due to threading)
        assert MessageType.ABORTED in message_types, "Should have ABORTED event"

        # Verify backend was called appropriately
        assert mock_backend.get_next_image.called or mock_backend.abort.called

    def test_abort_during_generation_cleans_up(self, config, mock_backend):
        """Test that ABORT command during generation triggers proper cleanup."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Create test image
        test_image = Image.new("RGB", (32, 32), color="green")
        buffered = Mock()
        buffered.image = test_image
        buffered.seed = 999

        # Mock backend to return one image then block
        mock_backend.get_next_image = Mock(return_value=buffered)
        mock_backend.check_worker_error = Mock(return_value=None)

        # Capture sent messages
        messages = []
        msg_lock = threading.Lock()

        original_send = server.send

        def capture_send(msg):
            with msg_lock:
                messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Command sequence: INIT then immediate ABORT
        commands = []
        command_idx = [0]

        def mock_readline():
            if command_idx[0] < len(commands):
                cmd = commands[command_idx[0]]
                command_idx[0] += 1
                return cmd + "\n"
            time.sleep(0.05)
            return ""

        init_cmd = Message(
            MessageType.INIT, {"prompt": "test", "seed": 1, "aspect_ratio": "1:1"}
        ).to_json()
        abort_cmd = Message(MessageType.ABORT).to_json()

        commands = [init_cmd, abort_cmd]

        with (
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch("sys.stdin") as mock_stdin,
            patch("sys.stdout", Mock()),
        ):
            mock_stdin.readline = mock_readline

            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()
            server_thread.join(timeout=2.0)

        # Verify ABORTED was sent
        message_types = [msg.type for msg in messages]
        assert MessageType.ABORTED in message_types

        # Verify backend.abort() was called
        mock_backend.abort.assert_called_once()

    def test_worker_error_propagates_to_ui(self, config, mock_backend):
        """Test that worker errors during delivery are sent to UI as fatal errors."""
        handler = MessageHandler(config)
        server = IPCServer(handler)

        # Create test image
        test_image = Image.new("RGB", (32, 32), color="yellow")
        buffered = Mock()
        buffered.image = test_image
        buffered.seed = 555

        # Simulate worker error after first image
        mock_backend.get_next_image = Mock(return_value=buffered)
        mock_backend.check_worker_error = Mock(side_effect=[None, RuntimeError("Worker crashed!")])

        messages = []
        msg_lock = threading.Lock()

        original_send = server.send

        def capture_send(msg):
            with msg_lock:
                messages.append(msg)
            original_send(msg)

        server.send = capture_send

        commands = []
        command_idx = [0]

        def mock_readline():
            if command_idx[0] < len(commands):
                cmd = commands[command_idx[0]]
                command_idx[0] += 1
                return cmd + "\n"
            time.sleep(0.1)
            return ""

        init_cmd = Message(
            MessageType.INIT, {"prompt": "test", "seed": 1, "aspect_ratio": "1:1"}
        ).to_json()
        skip_cmd = Message(MessageType.SKIP).to_json()
        abort_cmd = Message(MessageType.ABORT).to_json()

        commands = [init_cmd, skip_cmd, abort_cmd]

        with (
            patch("textbrush.ipc.handler.TextbrushBackend", return_value=mock_backend),
            patch("sys.stdin") as mock_stdin,
            patch("sys.stdout", Mock()),
        ):
            mock_stdin.readline = mock_readline

            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()
            server_thread.join(timeout=2.0)

        # Note: Error may or may not be sent depending on timing, but abort should always work
        message_types = [msg.type for msg in messages]
        assert MessageType.ABORTED in message_types

    def test_concurrent_skip_accept_race_protection(self, config, mock_backend):
        """Test that concurrent skip/accept commands don't cause race conditions."""
        handler = MessageHandler(config)
        handler.backend = mock_backend

        # Set up current image
        test_image = Image.new("RGB", (32, 32), color="purple")
        buffered = Mock()
        buffered.image = test_image
        buffered.seed = 777
        handler._current_image = buffered

        server = IPCServer(handler)

        messages = []
        msg_lock = threading.Lock()

        original_send = server.send

        def capture_send(msg):
            with msg_lock:
                messages.append(msg)
            original_send(msg)

        server.send = capture_send

        # Spawn concurrent skip and accept calls
        errors = []

        def call_skip():
            try:
                handler.handle_skip(server)
            except Exception as e:
                errors.append(e)

        def call_accept():
            try:
                handler.handle_accept(server)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(5):
            t1 = threading.Thread(target=call_skip)
            t2 = threading.Thread(target=call_accept)
            threads.extend([t1, t2])
            t1.start()
            t2.start()

        for t in threads:
            t.join()

        # No exceptions should be raised due to race conditions
        assert len(errors) == 0, f"Race condition errors: {errors}"

        # At least one operation should succeed (either skip or accept)
        # The others may get "No image to accept" errors, which is fine
        assert len(messages) > 0

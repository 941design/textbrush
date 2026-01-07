"""Property-based tests for IPC server."""

import io
import json
import sys
import threading

from hypothesis import given, settings
from hypothesis import strategies as st

from textbrush.ipc.protocol import Message, MessageType
from textbrush.ipc.server import IPCServer


class MockHandler:
    """Mock message handler for testing."""

    def __init__(self):
        self.init_calls = []
        self.skip_calls = []
        self.accept_calls = []
        self.abort_calls = []
        self.status_calls = []

    def handle_init(self, payload, server):
        self.init_calls.append((payload, server))

    def handle_skip(self, server):
        self.skip_calls.append(server)

    def handle_accept(self, server):
        self.accept_calls.append(server)

    def handle_abort(self, server):
        self.abort_calls.append(server)

    def handle_status(self, server):
        self.status_calls.append(server)


@st.composite
def message_strategy(draw):
    """Generate random valid messages."""
    msg_type = draw(
        st.sampled_from(
            [
                MessageType.INIT,
                MessageType.SKIP,
                MessageType.ACCEPT,
                MessageType.ABORT,
                MessageType.STATUS,
                MessageType.READY,
                MessageType.IMAGE_READY,
                MessageType.BUFFER_STATUS,
                MessageType.ERROR,
            ]
        )
    )

    payload = draw(
        st.one_of(
            st.none(),
            st.dictionaries(
                st.text(min_size=1, max_size=20),
                st.one_of(
                    st.text(max_size=100),
                    st.integers(),
                    st.booleans(),
                ),
                max_size=5,
            ),
        )
    )

    return Message(msg_type, payload)


@given(message=message_strategy())
@settings(max_examples=100)
def test_send_serializes_and_writes_newline(message):
    """Messages are serialized to JSON with newline and flushed."""
    handler = MockHandler()
    server = IPCServer(handler)

    output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = output

    try:
        server.send(message)
        result = output.getvalue()

        assert result.endswith("\n"), "Message must end with newline"

        parsed = json.loads(result.strip())
        assert parsed["type"] == message.type.value
        assert parsed["payload"] == message.payload
    finally:
        sys.stdout = original_stdout


@given(messages=st.lists(message_strategy(), min_size=2, max_size=20))
@settings(max_examples=50, deadline=1000)
def test_concurrent_sends_are_thread_safe(messages):
    """Multiple threads can send concurrently without corruption."""
    handler = MockHandler()
    server = IPCServer(handler)

    output = io.StringIO()
    original_stdout = sys.stdout
    sys.stdout = output

    threads = []

    try:
        for message in messages:
            thread = threading.Thread(target=server.send, args=(message,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join(timeout=2.0)

        lines = output.getvalue().strip().split("\n")

        assert len(lines) == len(messages), "All messages must be written"

        for line in lines:
            parsed = json.loads(line)
            assert "type" in parsed
            assert "payload" in parsed
    finally:
        sys.stdout = original_stdout


@given(st.sampled_from([" ", "  ", "\t", "\t\t", "   \n", "\n", "  \t  "]))
@settings(max_examples=20)
def test_run_ignores_empty_lines(whitespace_lines):
    """Empty or whitespace-only lines are ignored."""
    handler = MockHandler()
    server = IPCServer(handler)

    stdin_data = whitespace_lines
    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    sys.stdout = io.StringIO()

    try:
        server.run()

        assert len(handler.init_calls) == 0
        assert len(handler.skip_calls) == 0
        assert len(handler.accept_calls) == 0
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


@given(
    st.sampled_from(
        [
            "not json at all",
            "{missing quotes}",
            '{"type": "init"',
            "invalid",
            '{type: "init"}',
        ]
    )
)
@settings(max_examples=20)
def test_run_recovers_from_json_decode_errors(invalid_json):
    """Invalid JSON sends error message and continues processing."""
    handler = MockHandler()
    server = IPCServer(handler)

    valid_message = Message(MessageType.STATUS).to_json()
    stdin_data = f"{invalid_json}\n{valid_message}\n"

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    output = io.StringIO()
    sys.stdout = output

    try:
        server.run()

        lines = output.getvalue().strip().split("\n")

        assert len(lines) >= 1

        error_found = False
        for line in lines:
            parsed = json.loads(line)
            if parsed["type"] == "error" and "Invalid JSON" in parsed["payload"]["message"]:
                error_found = True
                assert parsed["payload"]["fatal"] is False

        assert error_found, "Error message should be sent for invalid JSON"
        assert len(handler.status_calls) == 1, "Valid message should still be processed"
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_run_recovers_from_malformed_messages():
    """Valid JSON but invalid message format sends error and continues."""
    handler = MockHandler()
    server = IPCServer(handler)

    malformed = "null"
    valid_message = Message(MessageType.STATUS).to_json()
    stdin_data = f"{malformed}\n{valid_message}\n"

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    output = io.StringIO()
    sys.stdout = output

    try:
        server.run()

        lines = output.getvalue().strip().split("\n")

        assert len(lines) >= 1

        error_found = False
        for line in lines:
            parsed = json.loads(line)
            if parsed["type"] == "error":
                error_found = True
                assert parsed["payload"]["fatal"] is False

        assert error_found, "Error message should be sent for malformed message"
        assert len(handler.status_calls) == 1, "Valid message should still be processed"
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_run_handles_eof():
    """Server exits cleanly when stdin closes."""
    handler = MockHandler()
    server = IPCServer(handler)

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO("")
    sys.stdout = io.StringIO()

    try:
        server.run()
        assert server._running is False
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


@given(
    st.sampled_from(
        [
            MessageType.INIT,
            MessageType.SKIP,
            MessageType.ACCEPT,
            MessageType.STATUS,
        ]
    )
)
@settings(max_examples=20)
def test_message_dispatching(msg_type):
    """Messages are dispatched to correct handler methods."""
    handler = MockHandler()
    server = IPCServer(handler)

    payload = {"test": "data"} if msg_type == MessageType.INIT else {}
    message = Message(msg_type, payload)

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(message.to_json() + "\n")
    sys.stdout = io.StringIO()

    try:
        server.run()

        if msg_type == MessageType.INIT:
            assert len(handler.init_calls) == 1
            assert handler.init_calls[0][0] == payload
        elif msg_type == MessageType.SKIP:
            assert len(handler.skip_calls) == 1
        elif msg_type == MessageType.ACCEPT:
            assert len(handler.accept_calls) == 1
        elif msg_type == MessageType.STATUS:
            assert len(handler.status_calls) == 1
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_abort_stops_server():
    """ABORT message stops the server loop."""
    handler = MockHandler()
    server = IPCServer(handler)

    abort_msg = Message(MessageType.ABORT).to_json()
    status_msg = Message(MessageType.STATUS).to_json()

    stdin_data = f"{abort_msg}\n{status_msg}\n"

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    sys.stdout = io.StringIO()

    try:
        server.run()

        assert len(handler.abort_calls) == 1
        assert len(handler.status_calls) == 0, "Messages after abort should not be processed"
        assert server._running is False
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_shutdown_stops_loop():
    """shutdown() sets flag causing run() to exit."""
    handler = MockHandler()
    server = IPCServer(handler)

    assert server._running is False

    def run_and_shutdown():
        threading.Timer(0.1, server.shutdown).start()
        server.run()

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO()
    sys.stdout = io.StringIO()

    try:
        run_and_shutdown()
        assert server._running is False
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_shutdown_is_idempotent():
    """shutdown() can be called multiple times safely."""
    handler = MockHandler()
    server = IPCServer(handler)

    server.shutdown()
    assert server._running is False

    server.shutdown()
    assert server._running is False

    server.shutdown()
    assert server._running is False


def test_handler_exception_sends_error_and_continues():
    """Exceptions in handler send error message and continue processing."""
    handler = MockHandler()

    def failing_init(payload, server):
        raise ValueError("Handler error")

    handler.handle_init = failing_init

    server = IPCServer(handler)

    init_msg = Message(MessageType.INIT, {"test": "data"}).to_json()
    status_msg = Message(MessageType.STATUS).to_json()

    stdin_data = f"{init_msg}\n{status_msg}\n"

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    output = io.StringIO()
    sys.stdout = output

    try:
        server.run()

        lines = output.getvalue().strip().split("\n")

        error_found = False
        for line in lines:
            parsed = json.loads(line)
            if parsed["type"] == "error" and "Handler error" in parsed["payload"]["message"]:
                error_found = True
                assert parsed["payload"]["fatal"] is False

        assert error_found, "Error message should be sent for handler exception"
        assert len(handler.status_calls) == 1, "Processing should continue after handler error"
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout


def test_unknown_message_type_logged_no_error():
    """Unknown message types are logged but don't send error events."""
    handler = MockHandler()
    server = IPCServer(handler)

    unknown_msg = json.dumps({"type": "unknown_type", "payload": {}})
    status_msg = Message(MessageType.STATUS).to_json()

    stdin_data = f"{unknown_msg}\n{status_msg}\n"

    original_stdin = sys.stdin
    original_stdout = sys.stdout

    sys.stdin = io.StringIO(stdin_data)
    output = io.StringIO()
    sys.stdout = output

    try:
        server.run()

        assert len(handler.status_calls) == 1
    finally:
        sys.stdin = original_stdin
        sys.stdout = original_stdout

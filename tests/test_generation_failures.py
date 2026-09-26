"""Failure signalling and engine ownership without model dependencies."""

import threading
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from textbrush.backend import TextbrushBackend
from textbrush.buffer import ImageBuffer
from textbrush.cli import main
from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType
from textbrush.model.registry import AvailabilityReport
from textbrush.worker import GenerationWorker


def result():
    return GenerationResult(Image.new("RGB", (16, 16)), 7, 0.01, "fake")


def test_failure_wakes_consumer_without_retry_and_fresh_run_clears_error():
    buffer = ImageBuffer(1)
    failed = OSError("device disconnected before first image")
    engine = Mock()
    engine.generate.side_effect = failed
    worker = GenerationWorker(engine, buffer, "prompt", GenerationOptions(seed=0))
    received = []
    consumer = threading.Thread(target=lambda: received.append(buffer.get(timeout=None)))
    consumer.start()
    worker.start()
    try:
        worker.join(1)
        consumer.join(1)
        assert not worker._thread.is_alive()
        assert not consumer.is_alive()
        assert received == [None]
        assert worker.get_error() is failed
        assert engine.generate.call_count == 1

        engine.generate.side_effect = None
        engine.generate.return_value = result()
        worker.update_config("prompt", worker.options, lambda *_: worker.pause())
        worker.start()
        assert buffer.get(timeout=1) is not None
        assert worker.get_error() is None
    finally:
        worker.stop()
        worker.join(1)
        consumer.join(1)


def test_delivery_reports_failure_that_occurs_during_empty_buffer_read(sample_config):
    entered = threading.Event()
    release = threading.Event()
    delivered_error = threading.Event()
    engine = Mock()
    failure = RuntimeError("inference failed before any preview")

    def generate(*_):
        entered.set()
        assert release.wait(2)
        raise failure

    engine.generate.side_effect = generate
    with patch("textbrush.backend.create_engine", return_value=engine):
        backend = TextbrushBackend(sample_config)
    backend._worker = GenerationWorker(engine, backend.buffer, "prompt", GenerationOptions())
    handler = MessageHandler(sample_config)
    handler.backend = backend
    server = Mock()
    messages = []

    def send(message):
        messages.append(message)
        if message.type == MessageType.STATE_CHANGED and message.payload.get("state") == "error":
            delivered_error.set()

    server.send.side_effect = send
    backend._worker.start()
    assert entered.wait(1)
    handler._start_image_delivery(server, None)
    release.set()
    try:
        assert delivered_error.wait(1)
        error = next(m for m in messages if m.payload.get("state") == "error")
        assert error.payload["message"] == str(failure)
        assert error.payload["fatal"] is True
        assert not any(m.type == MessageType.IMAGE_READY for m in messages)
    finally:
        release.set()
        backend.shutdown()


def test_cli_reports_original_worker_failure_before_timeout(sample_config, capsys):
    engine = Mock()
    engine.default_sampling_settings.return_value = {}
    engine.generate.side_effect = OSError("test inference device lost")
    with (
        patch("textbrush.cli.load_config", return_value=sample_config),
        patch(
            "textbrush.cli.check_model_availability", return_value=AvailabilityReport(True, None)
        ),
        patch("textbrush.backend.create_engine", return_value=engine),
        patch.object(
            TextbrushBackend, "_check_availability", return_value=AvailabilityReport(True, None)
        ),
        pytest.raises(SystemExit) as exit_info,
    ):
        main(["--headless", "--prompt", "test", "--model", "flux1-schnell"])
    assert exit_info.value.code == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "test inference device lost" in output.err
    assert "timeout" not in output.err
    assert engine.generate.call_count == 1


def test_shutdown_never_unloads_engine_during_inference(sample_config):
    entered = threading.Event()
    release = threading.Event()
    stopped = threading.Event()
    engine = Mock()
    produced = result()

    def generate(*_):
        entered.set()
        assert release.wait(10)
        return produced

    engine.generate.side_effect = generate
    with patch("textbrush.backend.create_engine", return_value=engine):
        backend = TextbrushBackend(sample_config)
    worker = GenerationWorker(engine, backend.buffer, "prompt", GenerationOptions())
    backend._worker = worker
    worker.start()
    assert entered.wait(1)

    def shutdown():
        backend.shutdown()
        stopped.set()

    shutdown_thread = threading.Thread(target=shutdown)
    shutdown_thread.start()
    try:
        # Exceed the old five-second join: the engine must remain owned by
        # inference, and shutdown must not falsely report completion.
        assert not stopped.wait(5.1)
        engine.unload.assert_not_called()
        assert len(backend.buffer) == 0
    finally:
        release.set()
        shutdown_thread.join(2)
    assert stopped.is_set()
    assert not worker._thread.is_alive()
    engine.unload.assert_called_once()
    assert len(backend.buffer) == 0
    with pytest.raises(ValueError, match="closed image"):
        produced.image.getpixel((0, 0))


def test_slow_success_has_no_arbitrary_generation_deadline(monkeypatch):
    from textbrush.cli import _wait_for_image

    elapsed = [0.0]
    backend = Mock()
    backend.check_worker_error.return_value = None
    backend.buffer.peek.side_effect = lambda: object() if elapsed[0] >= 180 else None
    monkeypatch.setattr("time.time", lambda: elapsed[0])
    monkeypatch.setattr("time.monotonic", lambda: elapsed[0])

    def sleep(seconds):
        elapsed[0] += seconds

    monkeypatch.setattr("time.sleep", sleep)
    _wait_for_image(backend)
    assert elapsed[0] >= 180

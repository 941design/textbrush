"""Session teardown on EOF, abort and concurrent initialization/publication."""

import io
import threading
from unittest.mock import Mock

from PIL import Image

from textbrush.backend import TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.ipc import __main__ as entry
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType


def test_eof_cleans_delivered_previews_and_unloads(sample_config, monkeypatch):
    engine = Mock()
    monkeypatch.setattr("textbrush.backend.create_engine", lambda *_: engine)
    handler = MessageHandler(sample_config)
    backend = handler.backend = TextbrushBackend(sample_config)
    image = BufferedImage(Image.new("RGB", (8, 8)), 1)
    path = backend.save_to_preview(image)
    handler._assign_image_index(image)
    handler._current_image = image
    monkeypatch.setattr(entry, "load_config", lambda _path=None: sample_config)
    monkeypatch.setattr(entry, "MessageHandler", lambda _: handler)
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    entry.main()  # real IPCServer observes EOF
    assert not path.exists()
    assert handler._session_closed
    assert not handler._image_index_map
    assert not handler._delivery_order
    assert handler._current_image is None
    engine.unload.assert_called_once()
    handler.shutdown()
    engine.unload.assert_called_once()


def test_shutdown_waits_for_loading_without_starting_generation(sample_config, monkeypatch):
    handler = MessageHandler(sample_config)
    backend = handler.backend = Mock()
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    backend.initialize.side_effect = lambda: (entered.set(), release.wait(3))
    monkeypatch.setattr(
        "textbrush.ipc.handler.check_model_availability", lambda *a, **k: Mock(available=True)
    )
    ready = Mock()
    load = threading.Thread(target=handler._init_backend, args=(ready, Mock()))
    load.start()
    assert entered.wait(2)
    close = threading.Thread(target=lambda: (handler.shutdown(), closed.set()))
    close.start()
    # Wait at the lifecycle lock only after the publication boundary is closed.
    for _ in range(200):
        if handler._session_closed:
            break
        closed.wait(0.005)
    assert handler._session_closed
    backend.shutdown.assert_not_called()
    assert not closed.is_set()
    release.set()
    load.join(2)
    close.join(2)
    assert not load.is_alive() and not close.is_alive()
    ready.assert_not_called()
    backend.shutdown.assert_called_once()


def test_abort_cleans_late_delivery_without_publication(sample_config):
    handler = MessageHandler(sample_config)
    backend = handler.backend = Mock()
    image = BufferedImage(Image.new("RGB", (8, 8)), 2)
    entered, release, cleaned = threading.Event(), threading.Event(), threading.Event()
    original_cleanup = image.cleanup
    image.cleanup = lambda: (original_cleanup(), cleaned.set())
    backend.get_next_image.side_effect = lambda **kwargs: (entered.set(), release.wait(3), image)[2]
    backend.check_worker_error.return_value = None
    server = Mock()
    handler._start_image_delivery(server, None)
    assert entered.wait(2)
    handler.handle_abort(server)
    release.set()
    assert cleaned.wait(2)
    backend.save_to_preview.assert_not_called()
    assert not handler._image_index_map
    assert [call.args[0].type for call in server.send.call_args_list] == [MessageType.ABORTED]
    backend.shutdown.assert_called_once()


def test_desktop_preview_directory_keeps_outputs_outside_session(
    sample_config, monkeypatch, tmp_path
):
    session = tmp_path / "session with spaces"
    monkeypatch.setenv("TEXTBRUSH_PREVIEW_DIR", str(session))
    monkeypatch.setattr("textbrush.backend.create_engine", lambda *_: Mock())
    backend = TextbrushBackend(sample_config)
    image = BufferedImage(Image.new("RGB", (8, 8)), 0)
    preview = backend.save_to_preview(image)
    assert preview.parent == session
    output = backend.accept_from_preview(image)
    assert output.parent == sample_config.output.directory
    assert output.exists() and not preview.exists()


def test_accept_then_shutdown_preserves_committed_output(sample_config, monkeypatch, tmp_path):
    monkeypatch.setenv("TEXTBRUSH_PREVIEW_DIR", str(tmp_path / "session previews"))
    engine = Mock()
    monkeypatch.setattr("textbrush.backend.create_engine", lambda *_: engine)
    handler = MessageHandler(sample_config)
    backend = handler.backend = TextbrushBackend(sample_config)
    image = BufferedImage(Image.new("RGB", (8, 8)), 7)
    preview = backend.save_to_preview(image)
    handler._assign_image_index(image)
    server = Mock()
    handler.handle_accept(server)
    accepted = server.send.call_args.args[0]
    assert accepted.type == MessageType.ACCEPTED
    handler.shutdown()
    from pathlib import Path

    output = Path(accepted.payload["paths"][0])
    assert output.exists() and not preview.exists()
    with Image.open(output) as saved:
        assert saved.size == (8, 8)
    engine.unload.assert_called_once()

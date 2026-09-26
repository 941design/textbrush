"""Actual filesystem acceptance, encoding and publication recovery."""

import errno
import threading
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from textbrush.backend import AcceptanceError, TextbrushBackend
from textbrush.buffer import BufferedImage
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import MessageType


@pytest.fixture
def backend(sample_config, monkeypatch):
    monkeypatch.setattr("textbrush.backend.create_engine", lambda *_: Mock())
    return TextbrushBackend(sample_config)


def preview(backend, seed=0, mode="RGB"):
    image = BufferedImage(
        Image.new(mode, (24, 16)),
        seed,
        prompt=f"prompt {seed}",
        model_name="fake",
        reference_ids=("/private/reference.png",),
    )
    backend.save_to_preview(image)
    return image


@pytest.mark.parametrize("mode", ["RGB", "RGBA", "L", "P"])
def test_jpeg_is_encoded_and_has_no_reference_metadata(backend, mode):
    backend.config.output.format = "jpg"
    image = preview(backend, mode=mode)
    original = image.temp_path
    saved = backend.accept_from_preview(image)
    with Image.open(saved) as encoded:
        assert encoded.format == "JPEG"
        assert encoded.size == (24, 16)
        assert encoded.mode in ("RGB", "L")
        assert not encoded.getexif()
    assert not original.exists()
    assert image.temp_path is None
    assert backend.accept_from_preview(image) == saved


def test_png_keeps_bytes_and_metadata_without_reencoding(backend, monkeypatch):
    image = preview(backend, 12)
    data = image.temp_path.read_bytes()
    monkeypatch.setattr(
        backend, "_save_with_metadata", Mock(side_effect=AssertionError("reencoded"))
    )
    saved = backend.accept_from_preview(image)
    assert saved.read_bytes() == data
    with Image.open(saved) as encoded:
        assert encoded.info["Seed"] == "12"
        assert encoded.info["Prompt"] == "prompt 12"
        assert "/private/reference.png" not in str(encoded.info)


def test_encoding_failure_leaves_preview_and_no_output(backend, tmp_path, monkeypatch):
    image = preview(backend, mode="RGBA")
    source = image.temp_path
    destination = tmp_path / "with spaces" / "result.jpg"
    monkeypatch.setattr(backend, "_save_with_metadata", Mock(side_effect=OSError("encoder failed")))
    with pytest.raises(OSError, match="encoder failed"):
        backend.accept_from_preview(image, destination)
    assert source.is_file()
    assert image.accepted_path is None
    assert list(destination.parent.iterdir()) == []


def test_output_directory_and_default_directory(backend, tmp_path):
    custom = tmp_path / "explicit output directory"
    image = preview(backend, 1)
    saved = backend.accept_all([image], output_dir=custom)
    assert saved[0].parent == custom
    assert saved[0].is_file()
    default = backend.accept_all([preview(backend, 2)])[0]
    assert default.parent == backend.config.output.directory.absolute()


def test_explicit_filename_suffixes_and_collisions(backend, tmp_path):
    destination = tmp_path / "with spaces" / "result.jpg"
    images = [preview(backend, seed) for seed in range(3)]
    paths = backend.accept_all(images, output_path=destination)
    assert [p.name for p in paths] == ["result.jpg", "result-002.jpg", "result-003.jpg"]
    for path in paths:
        with Image.open(path) as encoded:
            assert encoded.format == "JPEG"
    original = destination.read_bytes()
    colliding = preview(backend, 9)
    with pytest.raises(AcceptanceError) as error:
        backend.accept_all([colliding], output_path=destination)
    assert isinstance(error.value.__cause__, FileExistsError)
    assert destination.read_bytes() == original
    assert colliding.temp_path.exists()


@pytest.mark.parametrize("fail_at", [1, 2])
def test_handler_save_failure_preserves_selection_and_retry_commits_once(
    backend, tmp_path, monkeypatch, fail_at
):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    images = [preview(backend, seed) for seed in [2, 0, 1]]
    sources = [image.temp_path for image in images]
    for image in images:
        handler._assign_image_index(image)
    server = Mock()
    publish = backend._publish_output
    attempts = []

    def failing_publish(source, destination):
        attempts.append(destination)
        if len(attempts) == fail_at:
            raise OSError("disk full")
        publish(source, destination)

    monkeypatch.setattr(backend, "_publish_output", failing_publish)
    handler.handle_accept(server)
    error = server.send.call_args.args[0]
    assert error.type == MessageType.ERROR
    assert "disk full" in error.payload["message"]
    assert len(error.payload["saved_paths"]) == fail_at - 1
    assert list(handler._image_index_map.values()) == images
    assert handler._delivery_order == [0, 1, 2]
    assert all(source.exists() for source in sources)
    committed = [image.accepted_path for image in images if image.accepted_path]

    handler.handle_accept(server)
    accepted = server.send.call_args.args[0]
    assert accepted.type == MessageType.ACCEPTED
    paths = [Path(path) for path in accepted.payload["paths"]]
    assert paths[: len(committed)] == committed
    seeds = []
    for path in paths:
        with Image.open(path) as image:
            seeds.append(image.info["Seed"])
    assert seeds == ["2", "0", "1"]
    assert len(list(backend.config.output.directory.glob("*.png"))) == 3
    assert not any(source.exists() for source in sources)
    assert len(attempts) == 4  # Three commits plus one failed attempt, never a duplicate.
    assert handler._image_index_map == {}


def test_cross_filesystem_copy_failure_keeps_source_and_removes_partial_destination(
    backend, tmp_path, monkeypatch
):
    image = preview(backend)
    destination = tmp_path / "target.png"
    monkeypatch.setattr("os.link", Mock(side_effect=OSError(errno.EXDEV, "cross device")))

    def fail_copy(source, target):
        target.write(b"partial")
        raise OSError("disk full")

    monkeypatch.setattr("shutil.copyfileobj", fail_copy)
    with pytest.raises(OSError, match="disk full"):
        backend.accept_from_preview(image, destination)
    assert image.temp_path.is_file()
    assert not destination.exists()
    assert image.accepted_path is None


def test_accept_waits_for_complete_preview_before_snapshot(backend, monkeypatch, tmp_path):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    image = BufferedImage(Image.new("RGB", (16, 16)), 3)
    monkeypatch.setattr(backend, "get_next_image", Mock(side_effect=[image, None]))
    started = threading.Event()
    release = threading.Event()
    accepted = threading.Event()
    server = Mock()
    save = backend.save_to_preview

    def slow_preview(buffered):
        started.set()
        assert release.wait(2)
        return save(buffered)

    def accept():
        handler.handle_accept(server)
        accepted.set()

    monkeypatch.setattr(backend, "save_to_preview", slow_preview)
    destination = tmp_path / "custom output" / "chosen.png"
    handler._start_image_delivery(server, str(destination))
    assert started.wait(1)
    assert handler._image_index_map == {}
    accepting = threading.Thread(target=accept)
    accepting.start()
    try:
        assert not accepted.wait(0.05)
        release.set()
        assert accepted.wait(1)
        events = [call.args[0] for call in server.send.call_args_list]
        successful = next(event for event in events if event.type == MessageType.ACCEPTED)
        assert successful.payload["paths"] == [str(destination)]
        assert destination.exists()
        assert handler._session_closed
    finally:
        release.set()
        accepting.join(2)


def test_delivery_during_accept_is_discarded_after_success(backend, monkeypatch):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    first = preview(backend)
    handler._assign_image_index(first)
    late = BufferedImage(Image.new("RGB", (16, 16)), 1)
    saving = threading.Event()
    release = threading.Event()
    pending_delivery = threading.Event()
    discarded = threading.Event()
    server = Mock()
    publish = backend._publish_output

    def blocked_publish(source, destination):
        saving.set()
        assert release.wait(2)
        publish(source, destination)

    def read_image(timeout=None):
        pending_delivery.set()
        return late

    def cleanup():
        discarded.set()

    monkeypatch.setattr(backend, "_publish_output", blocked_publish)
    monkeypatch.setattr(backend, "get_next_image", read_image)
    monkeypatch.setattr(late, "cleanup", cleanup)
    accepting = threading.Thread(target=handler.handle_accept, args=(server,))
    accepting.start()
    try:
        assert saving.wait(1)
        handler._start_image_delivery(server, None)
        assert pending_delivery.wait(1)
        # Repeated commands while a save owns the batch cannot start another save.
        handler.handle_accept(server)
        release.set()
        accepting.join(1)
        assert not accepting.is_alive()
        assert discarded.wait(1)
        messages = [call.args[0] for call in server.send.call_args_list]
        accepted = [message for message in messages if message.type == MessageType.ACCEPTED]
        assert len(accepted) == 1
        assert len(accepted[0].payload["paths"]) == 1
        assert not any(message.type == MessageType.IMAGE_READY for message in messages)
        assert handler._image_index_map == {}
        assert late.temp_path is None
    finally:
        release.set()
        accepting.join(2)


def test_failed_accept_resumes_delivery_and_retry_includes_new_image(backend, monkeypatch):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    first = preview(backend, 1)
    handler._assign_image_index(first)
    server = Mock()
    publish = backend._publish_output
    monkeypatch.setattr(backend, "_publish_output", Mock(side_effect=OSError("disk full")))
    handler.handle_accept(server)
    assert not handler._session_closed
    monkeypatch.setattr(backend, "_publish_output", publish)
    late = BufferedImage(Image.new("RGB", (16, 16)), 2)
    ready = threading.Event()
    monkeypatch.setattr(backend, "get_next_image", Mock(side_effect=[late, None]))

    def send(message):
        if message.type == MessageType.IMAGE_READY:
            ready.set()

    server.send.side_effect = send
    handler._start_image_delivery(server, None)
    assert ready.wait(1)
    handler.handle_accept(server)
    accepted = server.send.call_args.args[0]
    assert accepted.type == MessageType.ACCEPTED
    assert len(accepted.payload["paths"]) == 2
    assert first.accepted_path.exists() and late.accepted_path.exists()


def test_deleted_tombstone_releases_pixels_and_acceptance_excludes_it(backend):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    server = Mock()
    deleted = preview(backend, 1)
    kept = preview(backend, 2)
    path = deleted.temp_path
    deleted_index = handler._assign_image_index(deleted)
    handler._assign_image_index(kept)
    handler.handle_delete({"index": deleted_index}, server)
    handler.handle_delete({"index": deleted_index}, server)
    assert handler._image_index_map[deleted_index] is deleted
    assert not path.exists()
    with pytest.raises(ValueError, match="closed image"):
        deleted.image.getpixel((0, 0))
    handler.handle_accept(server)
    accepted = server.send.call_args.args[0]
    assert accepted.type == MessageType.ACCEPTED
    assert len(accepted.payload["paths"]) == 1
    with Image.open(accepted.payload["paths"][0]) as image:
        assert image.info["Seed"] == "2"


def test_repeated_deletions_leave_only_metadata_tombstones(backend):
    handler = MessageHandler(backend.config)
    handler.backend = backend
    server = Mock()
    for seed in range(20):
        image = preview(backend, seed)
        index = handler._assign_image_index(image)
        handler.handle_delete({"index": index}, server)
        handler.handle_delete({"index": index}, server)
        with pytest.raises(ValueError, match="closed image"):
            image.image.getpixel((0, 0))
    handler.handle_get_image_list(server)
    tombstones = server.send.call_args.args[0].payload["images"]
    assert [entry["index"] for entry in tombstones] == list(range(20))
    assert all(entry["deleted"] and entry["path"] == "" for entry in tombstones)

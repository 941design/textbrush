"""Adversarial configuration/publication ordering without model inference."""

import threading
from unittest.mock import Mock

import pytest
from PIL import Image

from textbrush.buffer import ImageBuffer
from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.worker import GenerationWorker


def generated(seed):
    return GenerationResult(Image.new("RGB", (16, 16)), seed, 0.01, "fake-model")


def finish(worker):
    worker.stop()
    worker.join(2)
    assert not worker._thread.is_alive()


def test_update_after_epoch_validation_serializes_with_publication(monkeypatch):
    entered_put = threading.Event()
    release_put = threading.Event()
    update_started = threading.Event()
    update_done = threading.Event()
    buffer = ImageBuffer(1)
    engine = Mock()
    worker = GenerationWorker(engine, buffer, "old", GenerationOptions(seed=0))

    def generate(*_):
        worker.pause()
        return generated(0)

    engine.generate.side_effect = generate
    actual_put = buffer.put

    def blocked_put(image, timeout=None):
        entered_put.set()
        assert release_put.wait(2)
        return actual_put(image, timeout)

    monkeypatch.setattr(buffer, "put", blocked_put)

    def update():
        update_started.set()
        worker.update_config("new", GenerationOptions(seed=100))
        update_done.set()

    worker.start()
    updater = threading.Thread(target=update)
    try:
        assert entered_put.wait(1)
        updater.start()
        assert update_started.wait(1)
        # Publication owns the lock through insertion AND seed advancement.
        assert not update_done.wait(0.05)
        release_put.set()
        assert update_done.wait(1)
        assert buffer.get(timeout=0) is None
        assert worker.prompt == "new"
        assert worker.options.seed == 100
    finally:
        release_put.set()
        updater.join(2)
        finish(worker)


@pytest.mark.parametrize("old_fails", [False, True])
def test_update_during_inference_discards_old_result_or_error(old_fails):
    entered = threading.Event()
    release = threading.Event()
    engine = Mock()
    buffer = ImageBuffer(1)
    worker = GenerationWorker(engine, buffer, "old", GenerationOptions(seed=0))
    captured = []

    def generate(prompt, options):
        captured.append((prompt, options))
        if prompt == "old":
            entered.set()
            assert release.wait(2)
            if old_fails:
                raise RuntimeError("obsolete configuration failed")
        else:
            worker.pause()
        return generated(options.seed)

    engine.generate.side_effect = generate
    worker.start()
    try:
        assert entered.wait(1)
        worker.update_config(
            "new",
            GenerationOptions(seed=55, aspect_ratio="16:9"),
            model_id="flux2-klein-4b",
            reference_ids=("ref:0", "ref:0"),
        )
        release.set()
        image = buffer.get(timeout=1)
        assert image is not None
        assert (image.prompt, image.seed, image.aspect_ratio) == ("new", 55, "16:9")
        assert image.model_id == "flux2-klein-4b"
        assert image.reference_ids == ("ref:0", "ref:0")
        assert worker.options.seed == 56
        assert worker.get_error() is None
        assert [prompt for prompt, _ in captured] == ["old", "new"]
    finally:
        release.set()
        finish(worker)


def test_configuration_owns_inputs_even_if_caller_or_engine_mutates_options():
    settings = {"guidance_scale": 1.0}
    options = GenerationOptions(seed=0, sampling_settings=settings)
    engine = Mock()
    buffer = ImageBuffer(1)
    worker = GenerationWorker(engine, buffer, "prompt", options)
    options.seed = 91
    settings["guidance_scale"] = 99.0
    detached = worker.options
    detached.seed = 92
    detached.sampling_settings["guidance_scale"] = 98.0

    def generate(prompt, received):
        assert received.seed == 0
        assert received.sampling_settings == {"guidance_scale": 1.0}
        # An engine may modify its own options; attribution and next seed
        # must still use the captured inputs.
        received.seed = 93
        received.aspect_ratio = "3:1"
        worker.pause()
        return generated(0)

    engine.generate.side_effect = generate
    worker.start()
    try:
        image = buffer.get(timeout=1)
        assert image is not None
        assert image.aspect_ratio == "1:1"
        assert worker.options.seed == 1
    finally:
        finish(worker)


def test_full_buffer_retains_result_and_seed_across_pause_and_resume(monkeypatch):
    buffer = ImageBuffer(1)
    engine = Mock()
    full = threading.Event()
    third_inference = threading.Event()
    results = []
    worker = GenerationWorker(engine, buffer, "prompt", GenerationOptions(seed=0))

    def generate(prompt, options):
        result = generated(options.seed)
        results.append(result)
        if len(results) >= 3:
            third_inference.set()
            worker.pause()
        return result

    engine.generate.side_effect = generate
    actual_put = buffer.put

    def observe_put(image, timeout=None):
        success = actual_put(image, timeout)
        if not success:
            full.set()
        return success

    monkeypatch.setattr(buffer, "put", observe_put)
    worker.start()
    try:
        assert full.wait(2)
        assert not third_inference.wait(1.2)  # Beyond the old put timeout.
        worker.pause()
        assert worker.wait_settled(1)
        assert worker.options.seed == 1  # Pending seed has not advanced.
        first = buffer.get(timeout=0)
        assert first.seed == 0
        assert buffer.get(timeout=0) is None
        worker.resume()
        second = buffer.get(timeout=1)
        assert second.seed == 1
        assert second.image is results[1].image  # Retained, never regenerated.
        assert third_inference.wait(1)
        assert worker.wait_settled(1)
        worker.resume()  # The third result may also be pending at capacity.
        third = buffer.get(timeout=1)
        assert third.seed == 2
    finally:
        finish(worker)


@pytest.mark.parametrize("action", ["update", "stop"])
def test_pending_full_buffer_allows_update_or_stop_without_consumer(monkeypatch, action):
    buffer = ImageBuffer(1)
    engine = Mock()
    full = threading.Event()
    pending_released = threading.Event()
    results = []
    worker = GenerationWorker(engine, buffer, "old", GenerationOptions(seed=0))

    def generate(prompt, options):
        result = generated(options.seed)
        results.append(result)
        if len(results) == 2:
            close = result.image.close

            def observe_close():
                close()
                pending_released.set()

            result.image.close = observe_close
        if prompt == "new":
            worker.pause()
        return result

    engine.generate.side_effect = generate
    actual_put = buffer.put

    def observe_put(image, timeout=None):
        success = actual_put(image, timeout)
        if not success:
            full.set()
        return success

    monkeypatch.setattr(buffer, "put", observe_put)
    worker.start()
    try:
        assert full.wait(2)
        worker.pause()
        assert worker.wait_settled(1)
        if action == "update":
            worker.update_config("new", GenerationOptions(seed=70))
            assert pending_released.wait(1)
            assert buffer.get(timeout=0) is None
            assert worker.options.seed == 70
            worker.resume()
            image = buffer.get(timeout=1)
            assert (image.prompt, image.seed) == ("new", 70)
        else:
            worker.stop()
            assert pending_released.wait(1)
    finally:
        finish(worker)


def test_active_full_buffer_update_publishes_only_new_configuration(monkeypatch):
    buffer = ImageBuffer(1)
    full = threading.Event()
    engine = Mock()
    worker = GenerationWorker(engine, buffer, "old", GenerationOptions(seed=0))
    actual_put = buffer.put

    def observe_put(image, timeout=None):
        success = actual_put(image, timeout)
        if not success:
            full.set()
        return success

    def generate(prompt, options):
        if prompt == "new":
            worker.pause()
        return generated(options.seed)

    engine.generate.side_effect = generate
    monkeypatch.setattr(buffer, "put", observe_put)
    worker.start()
    try:
        assert full.wait(1)
        worker.update_config("new", GenerationOptions(seed=70))
        image = buffer.get(timeout=1)
        assert (image.prompt, image.seed) == ("new", 70)
        assert worker.wait_settled(1)
        assert worker.options.seed == 71
    finally:
        finish(worker)


def test_backend_does_not_clear_new_output_after_worker_update(sample_config, monkeypatch):
    from textbrush.backend import TextbrushBackend

    engine = Mock()
    engine.default_sampling_settings.return_value = {}
    monkeypatch.setattr("textbrush.backend.create_engine", lambda *_: engine)
    backend = TextbrushBackend(sample_config)
    worker = GenerationWorker(
        engine, backend.buffer, "old", GenerationOptions(seed=0), start_paused=True
    )
    backend._worker = worker

    def generate(*_):
        worker.pause()
        return generated(73)

    engine.generate.side_effect = generate
    update = worker.update_config

    def publish_before_return(*args, **kwargs):
        update(*args, **kwargs)
        worker.resume()
        assert worker.wait_settled(1)
        assert len(backend.buffer) == 1

    monkeypatch.setattr(worker, "update_config", publish_before_return)
    worker.start()
    try:
        backend.update_config("new", width=16, height=16)
        image = backend.get_next_image(timeout=0)
        assert image is not None
        assert image.prompt == "new"
    finally:
        backend.shutdown()

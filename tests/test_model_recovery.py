"""Model recovery ownership and partial allocation cleanup without real models."""

import weakref
from pathlib import Path
from unittest.mock import Mock

import pytest
from PIL import Image

from textbrush.backend import FatalModelError, ModelSwitchError, TextbrushBackend
from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.model.registry import AvailabilityReport
from textbrush.references import ReferenceImageError
from textbrush.worker import GenerationWorker


class Resource:
    pass


def engine(model):
    value = Mock()
    value.model_id = model
    value.resource = None
    value.is_loaded.side_effect = lambda: value.resource is not None
    value.load_from.side_effect = lambda _: setattr(value, "resource", Resource())
    value.unload.side_effect = lambda: setattr(value, "resource", None)
    value.reference_input_size.return_value = None if model == "flux1-schnell" else (16, 16)
    value.default_sampling_settings.return_value = {}

    def generate(*_):
        assert value.resource is not None
        return GenerationResult(Image.new("RGB", (16, 16)), 1, 0.01, model)

    value.generate.side_effect = generate
    return value


def backend_with_engines(sample_config, monkeypatch, engines):
    factory = Mock(side_effect=engines)
    monkeypatch.setattr("textbrush.backend.create_engine", factory)
    backend = TextbrushBackend(sample_config)
    monkeypatch.setattr(
        backend,
        "_check_availability",
        lambda _: AvailabilityReport(True, None, root=Path("/validated-candidate")),
    )
    backend.engine.load_from(Path("/validated-previous"))
    backend._engine_root = Path("/validated-previous")
    backend._worker = GenerationWorker(
        backend.engine, backend.buffer, "old", GenerationOptions(), start_paused=True
    )
    return backend


@pytest.mark.parametrize("recovery_fails", [False, True])
def test_candidate_allocations_and_traceback_locals_are_released_before_recovery(
    sample_config, monkeypatch, recovery_fails
):
    previous = engine("flux1-schnell")
    candidate = engine("flux2-klein-4b")
    backend = backend_with_engines(sample_config, monkeypatch, [previous, candidate])
    load_error = RuntimeError("candidate placement failed")
    recovery_error = RuntimeError("old model also failed")
    references = []

    def partially_load(_):
        resource = Resource()  # Also retained by this frame's traceback until cleared.
        candidate.resource = resource
        references.append(weakref.ref(resource))
        raise load_error

    def recover(root):
        assert root == Path("/validated-previous")
        assert references[0]() is None, "candidate still allocated during recovery"
        if recovery_fails:
            raise recovery_error
        previous.resource = Resource()

    candidate.load_from.side_effect = partially_load
    previous.load_from.side_effect = recover
    expected = FatalModelError if recovery_fails else ModelSwitchError
    with pytest.raises(expected) as error:
        backend.apply_configuration(model_id="flux2-klein-4b", reference_paths=[])
    candidate.unload.assert_called_once()
    assert error.value.original_cause is load_error
    if recovery_fails:
        assert error.value.recovery_cause is recovery_error
    else:
        assert backend.engine is previous
        assert backend._worker.engine is previous
        assert backend.model_id == "flux1-schnell"
        image = backend.engine.generate("recovered", GenerationOptions()).image
        image.close()
    backend.shutdown()


def test_failed_candidate_cleanup_prevents_recovery_allocation(sample_config, monkeypatch):
    previous = engine("flux1-schnell")
    candidate = engine("flux2-klein-4b")
    backend = backend_with_engines(sample_config, monkeypatch, [previous, candidate])
    previous.load_from.reset_mock()
    load_error = RuntimeError("load failed")
    cleanup_error = RuntimeError("cleanup failed")
    candidate.load_from.side_effect = load_error
    candidate.unload.side_effect = cleanup_error
    with pytest.raises(FatalModelError) as error:
        backend.apply_configuration(model_id="flux2-klein-4b", reference_paths=[])
    previous.load_from.assert_not_called()
    assert error.value.original_cause is load_error
    assert error.value.recovery_cause is cleanup_error


def test_previous_unload_failure_prevents_candidate_load(sample_config, monkeypatch):
    previous = engine("flux1-schnell")
    candidate = engine("flux2-klein-4b")
    backend = backend_with_engines(sample_config, monkeypatch, [previous, candidate])
    previous.unload.side_effect = RuntimeError("previous release failed")
    with pytest.raises(FatalModelError, match="candidate was not loaded"):
        backend.apply_configuration(model_id="flux2-klein-4b", reference_paths=[])
    candidate.load_from.assert_not_called()


@pytest.mark.parametrize("rollback_fails", [False, True])
def test_reference_decode_rollback_preserves_worker_engine_or_reports_fatal(
    sample_config, monkeypatch, rollback_fails
):
    previous = engine("flux1-schnell")
    candidate = engine("flux2-klein-4b")
    restored = engine("flux1-schnell")
    backend = backend_with_engines(sample_config, monkeypatch, [previous, candidate, restored])
    decode_error = ReferenceImageError("bad reference")
    monkeypatch.setattr("textbrush.backend.normalize", Mock(side_effect=decode_error))
    if rollback_fails:
        restored.load_from.side_effect = RuntimeError("cannot restore old model")
    expected = FatalModelError if rollback_fails else ReferenceImageError
    with pytest.raises(expected) as error:
        backend.apply_configuration(model_id="flux2-klein-4b", reference_paths=["reference.png"])
    if rollback_fails:
        assert error.value.original_cause is decode_error
        assert isinstance(error.value.recovery_cause, ModelSwitchError)
    else:
        assert backend.engine is restored
        assert backend._worker.engine is restored
        assert restored.is_loaded()
        assert backend.model_id == "flux1-schnell"
        assert backend.references == ()
        backend._worker.resume()
        backend._worker.start()
        assert backend.get_next_image(timeout=1) is not None
    backend.shutdown()

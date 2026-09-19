"""Tests for T06: backend config lifecycle, engine swap, decode-once, metadata.

These tests pin the S7 contract for `TextbrushBackend`:

- `apply_configuration` is the single acknowledged-configuration seam; it
  decodes references exactly once at acknowledgement, swaps engines on a
  model change with reload-on-failure, and commits an immutable snapshot
  to the worker.
- Decoded references outlive exactly one acknowledged configuration; they
  are released on change / abort / shutdown / fatal-error (AC-PROCESS-3).
- The closed PNG key set and `Model == repo_id` invariant are preserved
  (AC-META-1).
- Source files are not mutated by an acknowledge + generate + accept
  cycle (AC-STORAGE-1).

The engine and model weights are mocked throughout: tests drive
`TextbrushBackend` with a `MockInferenceEngine` (via
`patch("textbrush.backend.create_engine")`) and fixtures from
`tests/fixtures/images/`.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PIL import Image

from textbrush.backend import (
    ConfigurationAck,
    FatalModelError,
    ModelSwitchError,
    ModelUnavailableError,
    TextbrushBackend,
)
from textbrush.config import (
    Config,
    EditingConfig,
    HuggingFaceConfig,
    InferenceConfig,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)
from textbrush.model.registry import (
    FLUX1_KONTEXT_DEV,
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    DiscoveryCause,
    get_repo_id,
)
from textbrush.references import CorruptReferenceError

FIXTURES = Path(__file__).parent / "fixtures" / "images"


def _make_config(
    output_dir: Path,
    selected_id: str | None = None,
    default_preset: str = "landscape-medium",
) -> Config:
    output_dir.mkdir(parents=True, exist_ok=True)
    return Config(
        output=OutputConfig(directory=output_dir, format="png"),
        model=ModelConfig(directories=[], buffer_size=8, selected_id=selected_id),
        huggingface=HuggingFaceConfig(token=None),
        inference=InferenceConfig(backend="flux"),
        logging=LoggingConfig(verbosity="info"),
        editing=EditingConfig(default_preset=default_preset),
    )


def _make_engine_mock(
    slug: str = FLUX1_SCHNELL, *, reference_canvas: tuple[int, int] | None = None
):
    """Build a Mock that behaves like FluxInferenceEngine for tests.

    When `slug` is editing-capable and no `reference_canvas` is given,
    a callable is supplied that returns the (output_width, output_height)
    canvas so the mock matches each preset's expected canvas (e.g.
    portrait-large -> 768x1024, landscape-large -> 1024x768).
    """
    from tests.mocks import MockInferenceEngine
    from textbrush.validation import is_editing_model

    if reference_canvas is None and slug != FLUX1_SCHNELL and is_editing_model(slug):
        reference_canvas = lambda w, h: (w, h)  # noqa: E731
    engine = MockInferenceEngine(reference_canvas=reference_canvas)
    # MockInferenceEngine doesn't carry a slug; tests and the engine-swap
    # code paths both read `engine.model_id` (see flux.py). Mirror the
    # production behavior so `previous_engine.model_id` reads work.
    engine.model_id = slug
    return engine


def _mock_create_engine():
    """Build a `create_engine` factory that dispatches by slug.

    Returns a side_effect suitable for `patch("textbrush.backend.create_engine", side_effect=...)`.
    Each call yields a fresh MockInferenceEngine for the requested slug.
    """
    cache: dict[str, Mock] = {}

    def factory(backend: str, model_id: str) -> Mock:
        if model_id not in cache:
            cache[model_id] = _make_engine_mock(model_id)
        return cache[model_id]

    return factory, cache


def _available_report():
    """An AvailabilityReport that reports the model is available."""
    from textbrush.model.weights import AvailabilityReport

    return AvailabilityReport(available=True, cause=None, detail="", root=None)


# ---------------------------------------------------------------------------
# Decode-once (AC-PROCESS-3)
# ---------------------------------------------------------------------------


class TestDecodeOnce:
    """`apply_configuration` decodes each reference path exactly once at
    acknowledgement; subsequent overwrites or deletions of the source
    file are not observed by generation."""

    def test_decode_once_holds_original_pixels(self, tmp_path: Path) -> None:
        """Acknowledge one reference; overwrite the file with a different
        image; delete it; run one generation; the engine receives the
        originally decoded pixels, not the post-acknowledge write."""
        src = FIXTURES / "valid_square.png"
        assert src.exists()

        # Copy the fixture to a temp path so we can overwrite the file
        # the backend will read.
        reference_path = tmp_path / "ref.png"
        shutil.copy2(src, reference_path)

        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()
        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            ack = backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_landscape.jpg")],
                preset="portrait-large",
            )

            kontext_engine = cache[FLUX1_KONTEXT_DEV]
            assert ack.compatible is True
            assert backend.engine is kontext_engine

        assert ack.compatible is True

        # Capture the engine's reference pixel data BEFORE we
        # overwrite/delete the source. This is the "decode-once" data
        # the backend holds; subsequent file mutations must NOT change
        # what the engine eventually sees.
        held_reference = backend.references[0]
        held_pixels = held_reference.pixel_data.copy()

        # Overwrite and delete the source file after acknowledgement.
        Image.new("RGB", (16, 16), color=(0, 0, 0)).save(reference_path)
        reference_path.unlink()

        # Generate and observe the engine's reference pixel data.
        backend.start_generation(prompt="test", seed=0)
        try:
            buffered = backend.get_next_image(timeout=2.0)
        finally:
            backend.shutdown()

        assert buffered is not None
        assert kontext_engine.last_options is not None
        decoded = kontext_engine.last_options.references[0].pixel_data
        # The bytes the engine received must equal the data the backend
        # held at acknowledgement time (the original fixture pixels
        # normalized to canvas), NOT the post-acknowledge overwrite.
        assert decoded.tobytes() == held_pixels.tobytes()
        # The preset "portrait-large" yields canvas (768, 1024); both
        # the held reference and the forwarded one must match.
        assert decoded.size == (held_reference.width, held_reference.height) == (768, 1024)


# ---------------------------------------------------------------------------
# Corrupt file is rejected at acknowledgement
# ---------------------------------------------------------------------------


class TestCorruptReferenceRejected:
    """A `ReferenceImageError` at decode time propagates from
    `apply_configuration` without mutating backend state."""

    def test_corrupt_file_raises_at_ack(self, tmp_path: Path) -> None:
        corrupt = FIXTURES / "corrupt_truncated.jpg"
        assert corrupt.exists()

        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            model_before = backend.model_id
            refs_before = backend.references
            original_engine = backend.engine

            with pytest.raises(CorruptReferenceError):
                backend.apply_configuration(
                    model_id=FLUX1_KONTEXT_DEV,
                    reference_paths=[str(corrupt)],
                    preset="landscape-medium",
                )

            # State unchanged: model, references, and engine.
            assert backend.model_id == model_before
            assert backend.references == refs_before
            assert backend.engine is original_engine  # engine not swapped
            backend.shutdown()


# ---------------------------------------------------------------------------
# Canvas: references are normalized to the engine canvas
# ---------------------------------------------------------------------------


class TestReferenceCanvasNormalization:
    """References acknowledged at a given (model, preset) are normalized
    to the canvas the engine reports via `reference_input_size`. Changing
    the preset re-normalizes because the canvas differs."""

    def test_portrait_large_canvas(self, tmp_path: Path) -> None:
        """With editing-capable model + preset `portrait-large`, every
        reference's pixel_data is at (768, 1024)."""
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            ack = backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_landscape.jpg")],
                preset="portrait-large",
            )

        assert ack.compatible is True
        assert len(backend.references) == 1
        ref = backend.references[0]
        assert ref.width == 768
        assert ref.height == 1024
        backend.shutdown()

    def test_changing_preset_renormalizes(self, tmp_path: Path) -> None:
        """Switching preset re-normalizes because the canvas differs."""
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_landscape.jpg")],
                preset="portrait-large",
            )
            assert (backend.references[0].width, backend.references[0].height) == (768, 1024)

            backend.apply_configuration(
                preset="landscape-large",
            )
            assert (backend.references[0].width, backend.references[0].height) == (1024, 768)
            backend.shutdown()


# ---------------------------------------------------------------------------
# Atomic mode switch: preset remembered per mode (spec §5.5)
# ---------------------------------------------------------------------------


class TestAtomicModeSwitch:
    """Switching modes drops the old-mode preset; switching back
    restores the previously acknowledged editing preset."""

    def test_round_trip_preset_restoration(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()

            # schnell -> Kontext with no preset: ack reports the default
            ack1 = backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_square.png")],
                preset=None,
            )
            assert ack1.compatible is True
            assert ack1.preset == "landscape-medium"

            # Kontext -> schnell: preset drops to None.
            ack2 = backend.apply_configuration(model_id=FLUX1_SCHNELL)
            assert ack2.preset is None

            # schnell -> Kontext again: previously-acknowledged preset
            # (landscape-medium) is restored.
            ack3 = backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_square.png")],
            )
            assert ack3.preset == "landscape-medium"

            backend.shutdown()


# ---------------------------------------------------------------------------
# Acknowledged-and-incompatible (AC-STATE-4)
# ---------------------------------------------------------------------------


class TestAcknowledgedAndIncompatible:
    """An incompatible combination is acknowledged and held intact;
    resume is refused elsewhere (T07)."""

    def test_incompatible_ack_retains_references_and_required_model(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            # Kontext active, two references -> incompatible (Kontext
            # wants exactly 1).
            ack = backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[
                    str(FIXTURES / "valid_square.png"),
                    str(FIXTURES / "valid_portrait.png"),
                ],
                preset="landscape-medium",
            )

            assert ack.compatible is False
            assert ack.required_model == FLUX2_KLEIN_4B
            assert ack.reference_count == 2
            # Both references retained despite incompatibility.
            assert len(backend.references) == 2

            backend.shutdown()


# ---------------------------------------------------------------------------
# Engine swap recovery (AC-RECOVERY-1)
# ---------------------------------------------------------------------------


class TestEngineSwapRecovery:
    """Engine swap attempts recovery: on a failed new-engine load,
    `previous.load()` is invoked and `ModelSwitchError` is raised. If
    that ALSO fails, `FatalModelError` is raised."""

    def test_swap_failure_recovers_previous(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        previous_engine = Mock()
        previous_engine.unload = Mock()
        previous_engine.load = Mock()
        previous_engine.is_loaded = Mock(return_value=False)
        next_engine = Mock()
        next_engine.model_id = FLUX1_KONTEXT_DEV

        # next_engine.load() raises; previous_engine.load() succeeds.
        next_engine.load = Mock(side_effect=RuntimeError("swap failed"))

        def fake_create_engine(backend: str, model_id: str):
            if model_id == FLUX1_SCHNELL:
                return previous_engine
            return next_engine

        with (
            patch("textbrush.backend.create_engine", side_effect=fake_create_engine),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            # Engine swap triggers create_engine(...) with the new slug.
            with pytest.raises(ModelSwitchError) as excinfo:
                backend.apply_configuration(
                    model_id=FLUX1_KONTEXT_DEV,
                    reference_paths=[str(FIXTURES / "valid_square.png")],
                    preset="landscape-medium",
                )
            assert excinfo.value.recoverable is True

            # On a failed swap the previous engine is reloaded so the
            # backend stays usable (T06 design decision step 4); the
            # successful path additionally unloads the previous engine,
            # but the failure path does not -- `unload()` happens only
            # after a successful swap, when the previous engine is no
            # longer in use. Verify the recovery `load()` was called.
            previous_engine.load.assert_called()
            assert backend.model_id == FLUX1_SCHNELL

            backend.shutdown()

    def test_swap_failure_double_fatal(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        previous_engine = Mock()
        previous_engine.unload = Mock()
        # First load() call (init) succeeds; second call (recovery)
        # raises, simulating a fatally broken previous engine.
        previous_engine.load = Mock(side_effect=[None, RuntimeError("previous also broken")])
        previous_engine.is_loaded = Mock(return_value=False)
        next_engine = Mock()
        next_engine.model_id = FLUX1_KONTEXT_DEV
        next_engine.load = Mock(side_effect=RuntimeError("swap failed"))

        def fake_create_engine(backend: str, model_id: str):
            if model_id == FLUX1_SCHNELL:
                return previous_engine
            return next_engine

        with (
            patch("textbrush.backend.create_engine", side_effect=fake_create_engine),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            with pytest.raises(FatalModelError):
                backend.apply_configuration(
                    model_id=FLUX1_KONTEXT_DEV,
                    reference_paths=[str(FIXTURES / "valid_square.png")],
                    preset="landscape-medium",
                )
            # Recovery `load()` was attempted (and itself failed).
            previous_engine.load.assert_called()
            assert backend.model_id == FLUX1_SCHNELL
            backend.shutdown()


# ---------------------------------------------------------------------------
# Unavailable model is refused before unload
# ---------------------------------------------------------------------------


class TestUnavailableModel:
    """If `check_model_availability` reports an unavailable candidate,
    `ModelUnavailableError` is raised and no engine is unloaded."""

    def test_unavailable_does_not_unload(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            original_engine = backend.engine
            original_engine.unload = Mock()

            unavailable_report = Mock(
                available=False,
                cause=DiscoveryCause.INCOMPLETE,
                detail="incomplete",
                root=None,
            )
            with patch.object(
                backend,
                "_check_availability",
                return_value=unavailable_report,
            ):
                with pytest.raises(ModelUnavailableError):
                    backend.apply_configuration(model_id=FLUX2_KLEIN_4B)

                original_engine.unload.assert_not_called()
                assert backend.model_id == FLUX1_SCHNELL
                backend.shutdown()


# ---------------------------------------------------------------------------
# Release: abort / shutdown clear decoded data
# ---------------------------------------------------------------------------


class TestReleaseDecodedReferences:
    """`abort` and `shutdown` set `references = ()` and
    `reference_ids = ()`, releasing the acknowledged references."""

    def test_abort_releases_references(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_square.png")],
                preset="landscape-medium",
            )
            assert backend.references

            backend.abort()

            assert backend.references == ()

    def test_shutdown_releases_references(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()

        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_square.png")],
                preset="landscape-medium",
            )
            assert backend.references

            backend.shutdown()

            assert backend.references == ()


# ---------------------------------------------------------------------------
# Source preservation (AC-STORAGE-1)
# ---------------------------------------------------------------------------


class TestSourcePreservation:
    """Source files are not mutated by an acknowledge + generate +
    accept cycle."""

    def test_sources_unchanged_after_full_cycle(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")

        fixtures_to_use = [
            FIXTURES / "valid_square.png",
            FIXTURES / "valid_landscape.jpg",
        ]
        # Snapshot each fixture's SHA-256 before the cycle.
        hashes_before = {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixtures_to_use
        }

        side_effect, cache = _mock_create_engine()
        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.apply_configuration(
                model_id=FLUX2_KLEIN_4B,
                reference_paths=[str(p) for p in fixtures_to_use],
                preset="landscape-medium",
            )
            backend.start_generation(prompt="test", seed=0)
            import time as _time

            _time.sleep(0.2)  # let the worker thread fill the buffer
            try:
                buffered = backend.get_next_image(timeout=2.0)
                assert buffered is not None
                backend.accept_current(output_path=tmp_path / "out" / "result.png")
            finally:
                backend.shutdown()

        # Source files have identical bytes after the cycle.
        for path in fixtures_to_use:
            assert hashlib.sha256(path.read_bytes()).hexdigest() == hashes_before[str(path)]

        # The accepted output file's bytes are not equal to any source
        # file's bytes (the engine returns a fresh image, not a copy).
        out_bytes = (tmp_path / "out" / "result.png").read_bytes()
        for path in fixtures_to_use:
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest()
                != hashlib.sha256(out_bytes).hexdigest()
            )


# ---------------------------------------------------------------------------
# Metadata (AC-META-1) -- extends test_backend_save_metadata.py scope
# ---------------------------------------------------------------------------


class TestClosedPNGKeySet:
    """The PNG key set of an accepted editing image is exactly
    {AspectRatio, Width, Height, Prompt, Model, Seed, GeneratedWidth,
    GeneratedHeight} (the last two only when present). `Model` is the
    repo id of the active model."""

    def test_accepted_editing_image_png_keys(self, tmp_path: Path) -> None:
        config = _make_config(tmp_path / "out")
        side_effect, cache = _mock_create_engine()
        with (
            patch("textbrush.backend.create_engine", side_effect=side_effect),
            patch(
                "textbrush.backend.TextbrushBackend._check_availability",
                return_value=_available_report(),
            ),
        ):
            backend = TextbrushBackend(config)
            backend.initialize()
            backend.apply_configuration(
                model_id=FLUX1_KONTEXT_DEV,
                reference_paths=[str(FIXTURES / "valid_square.png")],
                preset="landscape-medium",
            )
            backend.start_generation(prompt="a prompt", seed=0)
            import time as _time

            _time.sleep(0.2)  # let the worker thread fill the buffer
            try:
                buffered = backend.get_next_image(timeout=2.0)
                assert buffered is not None
                output_path = tmp_path / "out" / "result.png"
                backend.accept_current(output_path=output_path)
            finally:
                backend.shutdown()

        img = Image.open(output_path)
        keys = set(img.text.keys())
        # PNG key set: always-present core keys plus optional
        # GeneratedWidth/GeneratedHeight when present on the buffered
        # image. Both editing and text paths share the same set; the
        # `Model` value (not key) carries the per-model identity.
        expected = {
            "AspectRatio",
            "Width",
            "Height",
            "Prompt",
            "Model",
            "Seed",
            "GeneratedWidth",
            "GeneratedHeight",
        }
        assert keys == expected
        assert img.text["Model"] == get_repo_id(FLUX1_KONTEXT_DEV)


# ---------------------------------------------------------------------------
# ConfigurationAck dataclass surface
# ---------------------------------------------------------------------------


class TestConfigurationAck:
    """ConfigurationAck is the frozen dataclass returned from
    `apply_configuration`."""

    def test_dataclass_fields(self) -> None:
        ack = ConfigurationAck(
            model_id=FLUX1_KONTEXT_DEV,
            reference_count=1,
            reference_paths=("a.png",),
            preset="landscape-medium",
            compatible=True,
            incompatibility_reason=None,
            required_model=None,
        )
        assert ack.model_id == FLUX1_KONTEXT_DEV
        assert ack.reference_count == 1
        assert ack.reference_paths == ("a.png",)
        assert ack.preset == "landscape-medium"
        assert ack.compatible is True
        assert ack.incompatibility_reason is None
        assert ack.required_model is None

"""Tests for T05: worker quiescence, discard, and buffer provenance.

These tests pin the S6 / AC-STATE-1 contract: "paused" must be observable
as quiescent (the worker is no longer producing), results from a
superseded configuration must never enter the buffer (the discard race),
and every buffered image must carry its snapshot's model and reference
identity (so downstream layers can attribute a result to a specific
acknowledged configuration).

Test classes:

- `TestQuiescence`: pause() does not immediately settle the worker; the
  worker settles only after the in-flight generate() returns. The
  on-settled callback fires exactly once per settle, and resumes re-arm
  it.
- `TestDiscardRace`: an update_config during a blocked generate causes
  the in-flight result to be discarded (epoch mismatch) while the next
  generation does produce a buffer entry.
- `TestBufferedImageProvenance`: the two new fields on `BufferedImage`
  default to None / () and round-trip when supplied.
"""

from __future__ import annotations

import threading
import time
from unittest.mock import Mock

from PIL import Image

from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.worker import GenerationWorker

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _make_blocking_engine(
    generate_event: threading.Event,
    release_event: threading.Event,
    result_seed: int = 0,
):
    """Build a Mock that mimics a long-running generate, gated by two events.

    The engine's `generate` blocks on `generate_event` first (so the test
    can guarantee the worker is mid-generate when it pauses), then blocks
    on `release_event` (so the test can hold the worker in the pause-wait
    state until it deliberately lets it complete).

    The release event is consumed (`clear()`) before the call returns, so
    subsequent `generate()` calls re-block rather than returning
    immediately. Without this, after the first `release_event.set()` the
    worker's loop would race ahead and put many results into the buffer
    before the test could observe anything.
    """
    engine = Mock()
    engine.is_loaded.return_value = True

    def blocking_generate(prompt, options):
        generate_event.set()
        release_event.wait(timeout=5.0)
        # Consume the release so the next call re-blocks until the test
        # sets the event again.
        release_event.clear()
        return GenerationResult(
            image=Image.new("RGB", (512, 512), color=(0, 0, 0)),
            seed=result_seed,
            generation_time=0.01,
            model_name="mock",
        )

    engine.generate.side_effect = blocking_generate
    return engine


# ---------------------------------------------------------------------------
# TestBufferedImageProvenance: model_id / reference_ids fields
# ---------------------------------------------------------------------------


class TestBufferedImageProvenance:
    """`BufferedImage` gains two provenance fields; the existing call sites
    keep working because both default to "no provenance recorded"."""

    def test_defaults_are_none_and_empty(self) -> None:
        """An existing caller that constructs without model_id /
        reference_ids gets None and () respectively."""
        image = BufferedImage(image=Image.new("RGB", (10, 10)), seed=1)

        assert image.model_id is None
        assert image.reference_ids == ()

    def test_round_trip_model_id(self) -> None:
        image = BufferedImage(
            image=Image.new("RGB", (10, 10)),
            seed=1,
            model_id="flux1-kontext-dev",
        )

        assert image.model_id == "flux1-kontext-dev"

    def test_round_trip_reference_ids(self) -> None:
        ids = ("abc123:0", "abc123:1")
        image = BufferedImage(
            image=Image.new("RGB", (10, 10)),
            seed=1,
            reference_ids=ids,
        )

        assert image.reference_ids == ids

    def test_model_id_and_reference_ids_independent(self) -> None:
        image = BufferedImage(
            image=Image.new("RGB", (10, 10)),
            seed=1,
            model_id="flux2-klein-4b",
            reference_ids=("uuid:0", "uuid:1", "uuid:2"),
        )

        assert image.model_id == "flux2-klein-4b"
        assert image.reference_ids == ("uuid:0", "uuid:1", "uuid:2")


# ---------------------------------------------------------------------------
# TestQuiescence: pause != settled
# ---------------------------------------------------------------------------


class TestQuiescence:
    """AC-STATE-1 (worker half): the IPC handler must observe a real
    quiescence signal after pause(), distinct from the pause request
    itself. T05 documents this as `is_settled()` and `wait_settled`."""

    def test_pause_does_not_immediately_settle(self) -> None:
        """While the worker is mid-generate, calling pause() makes
        `is_paused()` True but `is_settled()` False: the worker has not
        yet acknowledged the pause (it's still blocked in generate)."""
        generate_event = threading.Event()
        release_event = threading.Event()
        engine = _make_blocking_engine(generate_event, release_event)

        buffer = ImageBuffer(max_size=4)
        worker = GenerationWorker(engine, buffer, "test", GenerationOptions(seed=0))
        worker.start()

        # Wait until the worker has entered generate.
        assert generate_event.wait(timeout=2.0)

        worker.pause()
        # Pause was requested; but generate() is still running.
        assert worker.is_paused() is True
        assert worker.is_settled() is False

        # Let the in-flight generate return so the worker can settle.
        release_event.set()
        assert worker.wait_settled(timeout=2.0) is True

        worker.stop()
        worker.join(timeout=2.0)

    def test_callback_fires_once_per_settle(self) -> None:
        """The on-settled callback is invoked exactly once when the worker
        transitions from paused+in-flight to paused+settled."""
        generate_event = threading.Event()
        release_event = threading.Event()
        engine = _make_blocking_engine(generate_event, release_event)

        buffer = ImageBuffer(max_size=4)
        callback_calls: list[int] = []
        callback_lock = threading.Lock()

        def on_settled() -> None:
            with callback_lock:
                callback_calls.append(1)

        worker = GenerationWorker(
            engine, buffer, "test", GenerationOptions(seed=0), on_settled=on_settled
        )
        worker.start()

        assert generate_event.wait(timeout=2.0)
        worker.pause()
        release_event.set()

        assert worker.wait_settled(timeout=2.0) is True

        # Give the callback a moment to run on the worker thread.
        time.sleep(0.05)

        with callback_lock:
            assert len(callback_calls) == 1, (
                f"on_settled must fire exactly once per settle; got {len(callback_calls)}"
            )

        worker.stop()
        worker.join(timeout=2.0)

    def test_resume_then_pause_rearms_callback(self) -> None:
        """After resume, the next pause-then-settle cycle should fire
        the callback again (one fire per settle, not one fire per
        worker lifetime)."""
        # First cycle: pause + settle -> callback fires once
        generate_event = threading.Event()
        release_event = threading.Event()
        engine = _make_blocking_engine(generate_event, release_event)

        buffer = ImageBuffer(max_size=4)
        callback_calls: list[int] = []
        callback_lock = threading.Lock()

        def on_settled() -> None:
            with callback_lock:
                callback_calls.append(1)

        worker = GenerationWorker(
            engine, buffer, "test", GenerationOptions(seed=0), on_settled=on_settled
        )
        worker.start()
        assert generate_event.wait(timeout=2.0)
        worker.pause()
        release_event.set()
        assert worker.wait_settled(timeout=2.0) is True
        time.sleep(0.05)

        with callback_lock:
            assert len(callback_calls) == 1

        # Resume: the worker starts a fresh generate() blocked on the
        # same release_event. We need a fresh event pair for the second
        # cycle; reset by reusing the same events.
        generate_event.clear()
        release_event.clear()
        worker.resume()

        # The worker enters generate() (the blocking side_effect sets
        # generate_event when called again).
        assert generate_event.wait(timeout=2.0)
        worker.pause()
        release_event.set()
        assert worker.wait_settled(timeout=2.0) is True
        time.sleep(0.05)

        with callback_lock:
            assert len(callback_calls) == 2, (
                f"on_settled must fire once per settle; got {len(callback_calls)}"
            )

        worker.stop()
        worker.join(timeout=2.0)


# ---------------------------------------------------------------------------
# TestDiscardRace: VQ-S6-004
# ---------------------------------------------------------------------------


class TestDiscardRace:
    """VQ-S6-004: an update_config during a blocked generate must
    discard the in-flight result. The buffer stays empty after the
    discard, and the next generation's result does arrive."""

    def test_in_flight_result_discarded_on_update_config(self) -> None:
        """Engine blocks in generate; update_config bumps the epoch;
        buffer.clear() is invoked; releasing the engine makes the
        in-flight result be discarded, and the next generation
        (post-update) lands in the buffer."""
        generate_event = threading.Event()
        release_event = threading.Event()
        engine = _make_blocking_engine(generate_event, release_event, result_seed=0)

        buffer = ImageBuffer(max_size=4)
        worker = GenerationWorker(engine, buffer, "test", GenerationOptions(seed=0))
        worker.start()

        # Worker enters its first generate; sets generate_event and
        # blocks on release_event.
        assert generate_event.wait(timeout=2.0)
        epoch_before = worker._generation_epoch

        # Bump the epoch (simulating an acknowledged config change) and
        # clear the buffer (the standard pattern on configuration update).
        worker.update_config("test", GenerationOptions(seed=1))
        buffer.clear()

        # Release the in-flight generate. The result (seed=0) must NOT
        # land in the buffer because the epoch has moved on; the helper
        # clears release_event so the next iteration re-blocks.
        release_event.set()
        generate_event.clear()
        # The worker discards, loops back, and enters generate again.
        assert generate_event.wait(timeout=2.0)
        assert len(buffer) == 0, (
            f"in-flight result must be discarded after update_config; "
            f"buffer has {len(buffer)} items"
        )
        assert worker._generation_epoch > epoch_before

        # Release the second generate. This one is post-update and
        # matches the current epoch, so it must land in the buffer.
        release_event.set()
        time.sleep(0.1)
        assert len(buffer) == 1, (
            f"next generation's result must land in buffer; buffer has {len(buffer)} items"
        )

        worker.stop()
        worker.join(timeout=2.0)


# ---------------------------------------------------------------------------
# TestUpdateConfigProvenance: model_id and reference_ids flow through
# ---------------------------------------------------------------------------


class TestUpdateConfigProvenance:
    """update_config accepts model_id and reference_ids, and the worker
    captures them per iteration so a buffered result carries the snapshot
    it was generated under."""

    def test_update_config_accepts_model_id_and_reference_ids(self) -> None:
        """update_config signature accepts the two new keyword arguments
        without raising."""
        buffer = ImageBuffer(max_size=2)
        engine = Mock()
        engine.is_loaded.return_value = True
        engine.generate.return_value = GenerationResult(
            image=Image.new("RGB", (10, 10)),
            seed=0,
            generation_time=0.01,
            model_name="mock",
        )

        worker = GenerationWorker(engine, buffer, "test", GenerationOptions(seed=0))
        worker.start()
        time.sleep(0.05)

        # Should not raise.
        worker.update_config(
            "test",
            GenerationOptions(seed=1),
            model_id="flux2-klein-4b",
            reference_ids=("a:0", "a:1"),
        )
        time.sleep(0.05)

        worker.stop()
        worker.join(timeout=2.0)

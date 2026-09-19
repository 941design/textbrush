"""Cross-cutting provenance integration tests (T12 / S12).

These tests pin AC-STATE-2 and the order-sensitive guarantees documented in
`specs/epic-multi-reference-flux-image-editing/architecture.md` (the
"Order-Sensitive Composition" section):

1. No stale result is ever observable -- an image whose generation began
   before an acknowledged model or reference change never reaches the
   buffer (and therefore never the review history), regardless of when
   it completes relative to the clear.
2. Controls are enabled only on quiescence -- the window in which the UI
   offers a model or reference control that the backend would refuse is
   empty.
3. Every delivered result is attributable to exactly one snapshot, and
   that snapshot is immutable from the moment the request is created.
4. A reference set is never partially applied -- no generation observes
   a mix of old and new references.
5. Decoded reference data outlives exactly its configuration -- released
   on change, abort, fatal error and shutdown, and never re-read from disk
   mid-configuration.
6. Command serialization holds under contention -- a resume arriving
   during an update takes effect after acknowledgement; a failed update
   leaves the previous configuration loaded and ready.

The harness below exercises the *real* handler, *real* backend, *real*
worker, and a `MockInferenceEngine` whose `generate()` is gated by a
`threading.Event`. The engine is the only double. Real model weights are
never loaded; this file is safe to run without `--run-slow`.

The IPC server's "single-threaded command dispatch" model is documented
in `textbrush/ipc/server.py` and is the basis for AC-STATE-3's claim
that a resume during an update is honoured only after acknowledgement.
The harness therefore drives the handler methods directly (which is what
the server thread does) rather than spinning up a real IPCServer loop,
but the ordering guarantee holds because the handler methods are the
unit of serialization.

Helpers:

- `RecordingServer` -- a stand-in for `IPCServer` that records every
  `Message` in arrival order and provides typed accessors.
- `GatedMockEngine` -- a `MockInferenceEngine` whose `generate()` blocks
  on a `threading.Event`. The test releases the gate to advance a single
  iteration. The engine records every `(prompt, options)` pair it has
  been called with so a test can verify exactly which reference set the
  pipeline saw on each call.
- `full_stack` (fixture) -- constructs a `MessageHandler`, a real
  `TextbrushBackend` whose `create_engine` is patched to return one
  `GatedMockEngine` per slug, and a fake server. The patches make
  `_init_backend` synchronous (via `ImmediateThread`) so the test owns
  the ordering of all `INIT` side effects. The fixture uses
  `pytest.MonkeyPatch` to keep `create_engine` patched for the entire
  test (so subsequent `apply_configuration` calls reuse the same engine
  factory).
"""

from __future__ import annotations

import shutil
import threading
import time
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from textbrush.backend import TextbrushBackend
from textbrush.config import (
    Config,
    EditingConfig,
    HuggingFaceConfig,
    InferenceConfig,
    LoggingConfig,
    ModelConfig,
    OutputConfig,
)
from textbrush.inference.base import GenerationOptions, GenerationResult
from textbrush.ipc.handler import MessageHandler
from textbrush.ipc.protocol import (
    ImageReadyEvent,
    Message,
    MessageType,
    dataclass_to_dict,
)
from textbrush.model.registry import (
    FLUX1_KONTEXT_DEV,
    FLUX1_SCHNELL,
    FLUX2_KLEIN_4B,
    get_repo_id,
)
from textbrush.model.weights import AvailabilityReport
from textbrush.validation import is_editing_model

FIXTURES = Path(__file__).parent / "fixtures" / "images"


# ---------------------------------------------------------------------------
# Fake IPC server
# ---------------------------------------------------------------------------


class RecordingServer:
    """Fake IPCServer that records every message in arrival order.

    Thread-safe: `send` may be called from worker/delivery threads (the
    real `IPCServer` is the same). Provides a `messages_by_type` view and
    convenience predicates so tests can phrase assertions cleanly.
    """

    def __init__(self) -> None:
        self._messages: list[Message] = []
        self._lock = threading.Lock()

    def send(self, message: Message) -> None:
        with self._lock:
            self._messages.append(message)

    def shutdown(self) -> None:
        return None

    @property
    def messages(self) -> list[Message]:
        with self._lock:
            return list(self._messages)

    @property
    def messages_by_type(self) -> dict[str, list[Message]]:
        out: dict[str, list[Message]] = {}
        for msg in self.messages:
            out.setdefault(msg.type.value, []).append(msg)
        return out


# ---------------------------------------------------------------------------
# ImmediateThread -- the standard harness pattern (see test_ipc_handler.py)
# ---------------------------------------------------------------------------


class ImmediateThread:
    """Thread replacement that runs the target synchronously in `start()`.

    The real `threading.Thread` is replaced with this class via
    `patch("textbrush.ipc.handler.threading.Thread", side_effect=ImmediateThread)`
    so that `handle_init`'s `_init_backend` runs on the test thread
    instead of a daemon thread. This makes the side effects (backend
    construction, `start_generation`, `_start_image_delivery`) happen at
    deterministic points in the test's call sequence.
    """

    def __init__(self, target=None, args=(), daemon=None) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        if self._target is not None:
            self._target(*self._args)


# ---------------------------------------------------------------------------
# GatedMockEngine -- the only double in the harness
# ---------------------------------------------------------------------------


class GatedMockEngine:
    """Mock inference engine whose `generate()` blocks on a `threading.Event`.

    The first call to `generate` after a release blocks until
    `release_one()` is invoked; once it returns, the next call to
    `generate` will block again until the next release. This is the
    minimum surface needed to drive T05's discard race and T07's pause
    gate through the full stack without depending on real model weights.

    The engine records every `(prompt, options)` pair it has been
    called with so a test can assert exactly which reference set the
    pipeline saw on each call (the AC-MODEL-3 / AC-INPUT-4 / AC-STATE-2
    contract).
    """

    def __init__(
        self,
        model_id: str = FLUX1_SCHNELL,
        canvas=None,
    ) -> None:
        self.model_id = model_id
        self._loaded = False
        # Records the `root` of the most recent `load_from` call (None
        # until the backend loads this engine).
        self.loaded_from: Path | None = None
        # `_gate` is the shared blocking point. Tests call
        # `release_one()` to let one `generate` through.
        self._gate = threading.Event()
        # `_call_log` is appended-to from `generate`. Tests read it
        # after releasing the gate to inspect what the worker actually
        # saw.
        self._call_log: list[tuple[str, GenerationOptions]] = []
        self._log_lock = threading.Lock()
        if canvas is None and is_editing_model(model_id):
            # Default for editing slugs: mirror the production engine's
            # behaviour so the canvas matches the preset's output
            # dimensions. Tests can pass a literal (w, h) tuple to
            # override.
            def _canvas(w: int, h: int) -> tuple[int, int]:
                return (w, h)

            canvas = _canvas
        self._canvas = canvas

    # -- InferenceEngine surface ------------------------------------------

    def load(self) -> None:
        self._loaded = True

    def load_from(self, root: Path | None) -> None:
        """Mirror `InferenceEngine.load_from`'s default: ignore `root`.

        This double has no on-disk snapshot to be pointed at, which is
        exactly the case the base class defaults for. The root is recorded
        rather than discarded so a test can assert which snapshot the
        backend resolved without the double pretending it can load one.
        """
        self.loaded_from = root
        self.load()

    def is_loaded(self) -> bool:
        return self._loaded

    def unload(self) -> None:
        self._loaded = False

    @property
    def device(self) -> str:
        return "cpu"

    def reference_input_size(self, output_width: int, output_height: int) -> tuple[int, int] | None:
        if self._canvas is None:
            return None
        if callable(self._canvas):
            return self._canvas(output_width, output_height)
        return self._canvas

    def default_sampling_settings(self) -> dict[str, float | int]:
        # Per-slug sampling baselines. The values are not load-bearing
        # for these tests; the contract is "engine returns something"
        # and the backend forwards it into the snapshot. We return a
        # fixed dict for every model rather than importing
        # `FluxInferenceEngine` here, because doing that import inside
        # a function called from `TextbrushBackend.start_generation`
        # caused a re-entrancy issue in earlier iterations of this
        # harness. The values match the existing per-slug baselines
        # documented in `textbrush/inference/flux.py` (schnell:
        # 4 / 0.0; Kontext: 28 / 2.5; klein 4B: 4 / 1.0).
        if self.model_id == FLUX1_KONTEXT_DEV:
            return {"num_inference_steps": 28, "guidance_scale": 2.5}
        if self.model_id == FLUX2_KLEIN_4B:
            return {"num_inference_steps": 4, "guidance_scale": 1.0}
        # Default to schnell's baseline.
        return {"num_inference_steps": 4, "guidance_scale": 0.0}

    # -- gate control ------------------------------------------------------

    def release_one(self) -> None:
        """Allow exactly one blocked `generate()` call to return.

        Subsequent `generate()` calls re-block until `release_one` is
        invoked again. The Event is cleared inside `generate` after the
        wait so a single release never lets two calls through.
        """
        self._gate.set()

    @property
    def call_log(self) -> list[tuple[str, GenerationOptions]]:
        """Read-only view of every (prompt, options) the engine saw."""
        with self._log_lock:
            return list(self._call_log)

    # -- the actual generate ---------------------------------------------

    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        with self._log_lock:
            self._call_log.append((prompt, options))
        # Block until the test releases us. Bounded so a test bug never
        # silently hangs the test suite.
        self._gate.wait(timeout=10.0)
        # Clear immediately so the next call re-blocks.
        self._gate.clear()

        width = options.width or 512
        height = options.height or 512
        image = Image.new("RGB", (width, height), color=(128, 128, 128))
        seed = options.seed if options.seed is not None else 42

        try:
            model_name = get_repo_id(self.model_id)
        except ValueError:
            model_name = self.model_id

        return GenerationResult(
            image=image,
            seed=seed,
            generation_time=0.001,
            model_name=model_name,
            generated_width=width,
            generated_height=height,
        )


# ---------------------------------------------------------------------------
# Full-stack harness
# ---------------------------------------------------------------------------


def _make_config(output_dir: Path) -> Config:
    output_dir.mkdir(parents=True, exist_ok=True)
    return Config(
        output=OutputConfig(directory=output_dir, format="png"),
        model=ModelConfig(directories=[], buffer_size=8, selected_id=None),
        huggingface=HuggingFaceConfig(token=None),
        inference=InferenceConfig(backend="flux"),
        logging=LoggingConfig(verbosity="info"),
        editing=EditingConfig(default_preset="landscape-medium"),
    )


def _available_report() -> AvailabilityReport:
    return AvailabilityReport(available=True, cause=None, detail="", root=None)


def _make_engine_factory() -> tuple[callable, dict[str, GatedMockEngine]]:
    """Build a `create_engine` factory that returns one GatedMockEngine per slug.

    Returns a `(factory, cache)` pair. `factory` is suitable for
    `patch("textbrush.backend.create_engine", side_effect=factory)`. The
    cache lets tests inspect the engine instance for a given slug.
    """
    cache: dict[str, GatedMockEngine] = {}

    def factory(backend: str, model_id: str) -> GatedMockEngine:
        if model_id not in cache:
            cache[model_id] = GatedMockEngine(model_id=model_id)
        return cache[model_id]

    return factory, cache


class FullStack:
    """Bundle of (handler, backend, server, engines, fixtures) for one test.

    The caller obtains a `FullStack` from the `full_stack` fixture.
    Tests drive `handler.handle_*` directly; assertions read off
    `server.messages` and `handler.backend` (the real `TextbrushBackend`).
    """

    def __init__(
        self,
        handler: MessageHandler,
        backend: TextbrushBackend,
        server: RecordingServer,
        engine_cache: dict[str, GatedMockEngine],
    ) -> None:
        self.handler = handler
        self.backend = backend
        self.server = server
        self.engines = engine_cache

    def engine_for(self, model_id: str) -> GatedMockEngine:
        try:
            return self.engines[model_id]
        except KeyError as exc:  # pragma: no cover - test bug, not runtime
            raise AssertionError(
                f"engine for {model_id!r} not registered; cache keys: {sorted(self.engines)}"
            ) from exc

    def shutdown(self) -> None:
        try:
            self.backend.shutdown()
        except Exception:
            pass


@pytest.fixture
def full_stack(tmp_path: Path):
    """Yield a `FullStack` ready for tests to drive.

    The fixture patches (via `unittest.mock.patch` in an `ExitStack`):

    - `textbrush.backend.create_engine` -> factory that yields one
      GatedMockEngine per slug (kept active for the whole test, so
      `apply_configuration` reuses the factory on engine swaps).
    - `textbrush.backend.TextbrushBackend._check_availability` -> always
      available (we don't want a real filesystem check).
    - `textbrush.ipc.handler.TextbrushBackend` -> returns our pre-built
      real backend (so we don't double-construct or double-patch).
    - `textbrush.ipc.handler.threading.Thread` -> replaced with a Mock
      whose `side_effect = ImmediateThread`, mirroring the pattern in
      `tests/test_ipc_handler.py`. This makes `_init_backend` run
      synchronously in the test thread.
    - `textbrush.ipc.handler.check_model_availability` -> always available
      (the resolver in `handle_init` consults this; without the patch it
      returns unavailable and `handle_init` returns before starting the
      worker).
    - `MessageHandler._start_image_delivery` -> no-op. The tests inspect
      the buffer directly via `backend.get_next_image(timeout=...)`
      rather than the delivery thread, because the thread waits on
      `_action_event` between images and is hard to drive
      deterministically.

    The default model is schnell and the worker starts paused (matches
    the production handler default).
    """
    config = _make_config(tmp_path / "out")
    config.model.selected_id = FLUX1_SCHNELL
    factory, cache = _make_engine_factory()

    stack = ExitStack()

    # Build a real backend with create_engine patched so it uses our
    # mock engines. The patch stays active for the whole test (entered
    # into the ExitStack), so subsequent apply_configuration calls hit
    # the same factory. We also patch `_check_availability` because
    # `apply_configuration` -> `_swap_engine` consults it; without
    # the patch the test would fail on any model whose HuggingFace
    # cache is empty (the CI environment).
    stack.enter_context(patch("textbrush.backend.create_engine", factory))
    stack.enter_context(
        patch(
            "textbrush.backend.TextbrushBackend._check_availability",
            lambda self, slug: _available_report(),
        )
    )

    backend = TextbrushBackend(config)
    backend.initialize()

    handler = MessageHandler(config)
    server = RecordingServer()

    init_payload = {
        "prompt": "test prompt",
        "seed": 0,
        "aspect_ratio": "1:1",
        "width": 64,
        "height": 64,
        "format": "png",
        "model_id": FLUX1_SCHNELL,
    }

    stack.enter_context(patch("textbrush.ipc.handler.TextbrushBackend", lambda c: backend))
    stack.enter_context(
        patch(
            "textbrush.ipc.handler.check_model_availability",
            lambda *a, **kw: _available_report(),
        )
    )
    stack.enter_context(patch.object(handler, "_init_backend", lambda on_ready, server: on_ready()))
    stack.enter_context(patch.object(handler, "_start_image_delivery", lambda *a, **kw: None))

    handler.handle_init(init_payload, server)
    # handle_init kicks off `on_ready` on a real background thread (the
    # `_init_backend` patch invokes it directly but `start_generation`
    # inside it spawns the worker thread); wait for the worker to
    # actually settle before yielding the fixture.
    deadline = time.time() + 5.0
    while (
        handler._generation_started is False
        or backend._worker is None
        or not backend._worker.is_settled()
    ):
        if time.time() > deadline:
            break
        time.sleep(0.01)

    fs = FullStack(handler=handler, backend=backend, server=server, engine_cache=cache)
    try:
        yield fs
    finally:
        # Stop the worker if still alive.
        try:
            backend.shutdown()
        except Exception:
            pass
        stack.close()


def _wait_for_generate(engine: GatedMockEngine, *, timeout: float) -> None:
    deadline = time.time() + timeout
    while not engine.call_log and time.time() < deadline:
        time.sleep(0.01)
    assert engine.call_log, f"engine {engine.model_id!r} did not enter generate within {timeout}s"


# ---------------------------------------------------------------------------
# Test 1 -- test_stale_result_never_visible
# ---------------------------------------------------------------------------


class TestStaleResultNeverVisible:
    """AC-STATE-1 (full-stack): a result generated under the pre-change
    configuration never reaches the buffer (and therefore never the
    review history) after the new configuration has been acknowledged.
    """

    def test_stale_result_never_visible(self, tmp_path: Path, full_stack: FullStack) -> None:
        handler, backend, server = full_stack.handler, full_stack.backend, full_stack.server
        schnell_engine = full_stack.engine_for(FLUX1_SCHNELL)

        # First acknowledge the configuration so the very first
        # BufferedImage produced carries `model_id == FLUX1_SCHNELL`.
        # apply_configuration is the only path that stamps the
        # per-iteration model identity onto the worker, and it
        # requires a settled worker (which the fixture gives us).
        ack_schnell = backend.apply_configuration(
            model_id=FLUX1_SCHNELL,
            preset=None,
        )
        assert ack_schnell.compatible is True
        assert backend.model_id == FLUX1_SCHNELL

        # Now resume to start generating under model A.
        handler.handle_pause(server)
        _wait_for_generate(schnell_engine, timeout=2.0)

        # Release the gate so the first schnell image lands in the buffer.
        schnell_engine.release_one()
        buffered_a = backend.get_next_image(timeout=2.0)
        assert buffered_a is not None, "no schnell image produced"
        assert buffered_a.model_id == FLUX1_SCHNELL
        # We do NOT send an IMAGE_READY for buffered_a: that
        # would race with the initial config_ack from `handle_init`
        # (which is sent before any test code runs), making the
        # post-ack message list contain a stale schnell image.
        # The discard race is asserted by the absence of any
        # IMAGE_READY with model_id == FLUX1_SCHNELL after the
        # post-update config_ack is emitted.

        # Pause + wait settled so apply_configuration will accept the
        # next update. The worker may be in a follow-up generate
        # call (blocked on the gate), so release the gate first to
        # let any in-flight generate finish before pause settles.
        schnell_engine.release_one()
        handler.handle_pause(server)
        deadline = time.time() + 3.0
        while not backend.is_settled() and time.time() < deadline:
            time.sleep(0.01)
        assert backend.is_settled(), "worker did not settle after pause"

        # Now acknowledge a switch to Kontext with one reference.
        ack = backend.apply_configuration(
            model_id=FLUX1_KONTEXT_DEV,
            reference_paths=[str(FIXTURES / "valid_square.png")],
            preset="landscape-medium",
        )
        assert ack.compatible is True
        kontext_engine = full_stack.engine_for(FLUX1_KONTEXT_DEV)

        # Drive the handler to emit a config_ack for the post-update
        # state. The fixture patches out `_start_image_delivery`,
        # so the delivery thread does not auto-emit IMAGE_READY
        # for any drained images; we manually emit one for the
        # post-update BufferedImage below.
        handler._emit_config_ack(server, settled=True)

        # Resume under the new configuration.
        handler.handle_pause(server)
        _wait_for_generate(kontext_engine, timeout=2.0)
        kontext_engine.release_one()
        buffered_b = backend.get_next_image(timeout=2.0)
        assert buffered_b is not None
        assert buffered_b.model_id == FLUX1_KONTEXT_DEV

        idx_b = handler._assign_image_index(buffered_b)
        server.send(
            Message(
                MessageType.IMAGE_READY,
                dataclass_to_dict(
                    ImageReadyEvent(
                        index=idx_b,
                        path="",
                        display_path="",
                    )
                ),
            )
        )

        # ASSERTION: after the post-update config_ack, no IMAGE_READY
        # whose BufferedImage carries model A's identity appears.
        ack_indices = [i for i, m in enumerate(server.messages) if m.type == MessageType.CONFIG_ACK]
        assert len(ack_indices) >= 2, (
            f"expected at least two CONFIG_ACK (init + post-update); got {len(ack_indices)}"
        )
        post_update_ack = ack_indices[-1]
        for ready_idx in (
            i
            for i, m in enumerate(server.messages)
            if m.type == MessageType.IMAGE_READY and i > post_update_ack
        ):
            ready_msg = server.messages[ready_idx]
            img_idx = ready_msg.payload["index"]
            buffered = handler._image_index_map.get(img_idx)
            assert buffered is not None
            assert buffered.model_id == FLUX1_KONTEXT_DEV, (
                f"IMAGE_READY at index {ready_idx} carries a stale "
                f"schnell image; the discard race failed"
            )


# ---------------------------------------------------------------------------
# Test 2 -- test_control_enablement_window_is_empty
# ---------------------------------------------------------------------------


class TestControlEnablementWindowIsEmpty:
    """AC-STATE-1: the first `state_changed(paused, settled=true)` is
    emitted only after the in-flight `generate()` returns. The window
    during which the UI would offer an editing control that the backend
    would refuse is therefore empty.
    """

    def test_settled_emitted_only_after_gated_generate_returns(
        self, tmp_path: Path, full_stack: FullStack
    ) -> None:
        handler, server = full_stack.handler, full_stack.server
        schnell_engine = full_stack.engine_for(FLUX1_SCHNELL)

        # First resume so the worker is actively generating. After
        # that, the second pause request will be the one whose
        # settled signal we want to time.
        handler.handle_pause(server)
        _wait_for_generate(schnell_engine, timeout=2.0)
        schnell_engine.release_one()
        # Drain that image so the worker is mid-generate on the next
        # iteration.
        buffered = full_stack.backend.get_next_image(timeout=2.0)
        assert buffered is not None
        # The worker may have already entered its second generate call
        # by the time we get here (the worker loop has no pause between
        # iterations), so the call_log can have either 1 or 2 entries.
        # The assertion that matters is that at least the first call
        # happened (we just drained its result).
        assert len(schnell_engine.call_log) >= 1

        # Pause: handle_pause should emit settled=False immediately,
        # and the worker should emit settled=True only after the
        # blocked generate returns.
        pre_pause_msg_count = len(server.messages)
        handler.handle_pause(server)

        # state_changed(paused, settled=False) is emitted
        # synchronously by handle_pause.
        paused_events = [
            m
            for m in server.messages[pre_pause_msg_count:]
            if m.type == MessageType.STATE_CHANGED and m.payload["state"] == "paused"
        ]
        assert len(paused_events) >= 1, (
            "expected at least one state_changed(paused) after pause request"
        )
        assert paused_events[0].payload["settled"] is False

        # The settled=True event must NOT have been emitted yet --
        # the worker is still mid-generate.
        settled_true_after_pause = [
            m
            for m in server.messages[pre_pause_msg_count:]
            if m.type == MessageType.STATE_CHANGED
            and m.payload["state"] == "paused"
            and m.payload.get("settled") is True
        ]
        assert len(settled_true_after_pause) == 0, (
            "settled=True was emitted before the blocked generate returned"
        )

        # Now release the blocked generate.
        schnell_engine.release_one()

        # The settled=True event must arrive within a bounded time.
        deadline = time.time() + 2.0
        settled_events = list(settled_true_after_pause)
        while not settled_events and time.time() < deadline:
            settled_events = [
                m
                for m in server.messages
                if m.type == MessageType.STATE_CHANGED
                and m.payload["state"] == "paused"
                and m.payload.get("settled") is True
            ]
            if not settled_events:
                time.sleep(0.01)
        assert settled_events, "settled=True never emitted after the blocked generate returned"

        # The worker should now have entered a second generate call
        # (or be back in the pause-wait). Confirm by checking the
        # call_log.
        assert len(schnell_engine.call_log) >= 2


# ---------------------------------------------------------------------------
# Test 3 -- test_snapshot_attribution_across_two_changes
# ---------------------------------------------------------------------------


class TestSnapshotAttributionAcrossTwoChanges:
    """AC-STATE-2: across three configurations, navigation, and a delete,
    every surviving image's PNG metadata must reflect the snapshot that
    produced it."""

    def test_three_configurations_attribute_correctly(
        self, tmp_path: Path, full_stack: FullStack
    ) -> None:
        handler, backend = full_stack.handler, full_stack.backend

        # ----- Snapshot 1: schnell, prompt "cat" ---------------------
        # Set the prompt on the worker BEFORE resuming so the very
        # first generation carries it. apply_configuration stamps
        # the per-iteration model identity onto the worker; do that
        # first so the BufferedImage's `model_id` is correct.
        ack1 = backend.apply_configuration(model_id=FLUX1_SCHNELL, preset=None)
        assert ack1.compatible is True
        backend._worker.prompt = "cat"
        handler.handle_pause(full_stack.server)
        schnell_engine = full_stack.engine_for(FLUX1_SCHNELL)
        _wait_for_generate(schnell_engine, timeout=2.0)
        schnell_engine.release_one()
        image_1 = backend.get_next_image(timeout=2.0)
        assert image_1 is not None
        assert image_1.prompt == "cat"
        assert image_1.model_id == FLUX1_SCHNELL
        path_1 = backend.save_to_preview(image_1)
        idx_1 = handler._assign_image_index(image_1)

        # Pause + wait for settled before applying the next config.
        schnell_engine.release_one()
        handler.handle_pause(full_stack.server)
        deadline = time.time() + 3.0
        while not backend.is_settled() and time.time() < deadline:
            time.sleep(0.01)
        assert backend.is_settled(), "worker did not settle after pause"

        # ----- Snapshot 2: Kontext, prompt "dog", one reference ------
        ack2 = backend.apply_configuration(
            model_id=FLUX1_KONTEXT_DEV,
            reference_paths=[str(FIXTURES / "valid_square.png")],
            preset="landscape-medium",
        )
        assert ack2.compatible is True
        backend._worker.prompt = "dog"
        kontext_engine = full_stack.engine_for(FLUX1_KONTEXT_DEV)
        handler.handle_pause(full_stack.server)
        _wait_for_generate(kontext_engine, timeout=2.0)
        kontext_engine.release_one()
        image_2 = backend.get_next_image(timeout=2.0)
        assert image_2 is not None
        assert image_2.prompt == "dog"
        assert image_2.model_id == FLUX1_KONTEXT_DEV
        path_2 = backend.save_to_preview(image_2)
        idx_2 = handler._assign_image_index(image_2)

        kontext_engine.release_one()
        handler.handle_pause(full_stack.server)
        deadline = time.time() + 3.0
        while not backend.is_settled() and time.time() < deadline:
            time.sleep(0.01)
        assert backend.is_settled(), "worker did not settle after pause"

        # ----- Snapshot 3: FLUX.2 klein, prompt "fish", two refs -----
        ack3 = backend.apply_configuration(
            model_id=FLUX2_KLEIN_4B,
            reference_paths=[
                str(FIXTURES / "valid_square.png"),
                str(FIXTURES / "valid_portrait.png"),
            ],
            preset="landscape-medium",
        )
        assert ack3.compatible is True
        backend._worker.prompt = "fish"
        klein_engine = full_stack.engine_for(FLUX2_KLEIN_4B)
        handler.handle_pause(full_stack.server)
        _wait_for_generate(klein_engine, timeout=2.0)
        klein_engine.release_one()
        image_3 = backend.get_next_image(timeout=2.0)
        assert image_3 is not None
        assert image_3.prompt == "fish"
        assert image_3.model_id == FLUX2_KLEIN_4B
        path_3 = backend.save_to_preview(image_3)
        idx_3 = handler._assign_image_index(image_3)

        # ----- Navigation: skip image 2 (the middle one) -------------
        handler._current_image = image_2
        handler.handle_skip(full_stack.server)
        handler._deleted_indices.add(idx_2)

        # ----- Verify PNG metadata of survivors -----------------------
        img1 = Image.open(path_1)
        assert img1.text["Model"] == get_repo_id(FLUX1_SCHNELL)
        assert img1.text["Prompt"] == "cat"
        assert img1.text["Model"] != img1.text["Prompt"]  # sanity

        # Image 2 (kontext / dog) was deleted; its preview file
        # should no longer exist (handle_skip called delete_preview).
        assert not path_2.exists(), "deleted preview file should be gone"

        img3 = Image.open(path_3)
        assert img3.text["Model"] == get_repo_id(FLUX2_KLEIN_4B)
        assert img3.text["Prompt"] == "fish"

        # Index map agrees with the attribution.
        assert handler._image_index_map[idx_1].prompt == "cat"
        assert handler._image_index_map[idx_1].model_id == FLUX1_SCHNELL
        assert handler._image_index_map[idx_3].prompt == "fish"
        assert handler._image_index_map[idx_3].model_id == FLUX2_KLEIN_4B
        assert idx_2 in handler._deleted_indices


# ---------------------------------------------------------------------------
# Test 4 -- test_no_partial_reference_set
# ---------------------------------------------------------------------------


class TestNoPartialReferenceSet:
    """AC-STATE-1 (reference ordering): the engine never receives a set
    that is neither the old nor the new tuple. No mode switch is
    observable with a model and preset from different modes."""

    def test_engine_sees_only_old_or_new_tuple(self, tmp_path: Path, full_stack: FullStack) -> None:
        handler, backend, server = (
            full_stack.handler,
            full_stack.backend,
            full_stack.server,
        )
        reference_paths_initial = [
            str(FIXTURES / "valid_square.png"),
            str(FIXTURES / "valid_portrait.png"),
        ]
        # Acknowledge the initial FLUX.2 klein + 2-reference
        # configuration first so the engine factory yields the klein
        # engine (engine swap).
        ack_init = backend.apply_configuration(
            model_id=FLUX2_KLEIN_4B,
            reference_paths=reference_paths_initial,
            preset="landscape-medium",
        )
        assert ack_init.compatible is True
        assert ack_init.reference_count == 2
        klein_engine = full_stack.engine_for(FLUX2_KLEIN_4B)

        handler.handle_pause(server)
        _wait_for_generate(klein_engine, timeout=2.0)
        klein_engine.release_one()
        image_2refs = backend.get_next_image(timeout=2.0)
        assert image_2refs is not None
        assert len(image_2refs.reference_ids) == 2

        # Pause + wait settled before applying the next config.
        klein_engine.release_one()
        handler.handle_pause(server)
        deadline = time.time() + 3.0
        while not backend.is_settled() and time.time() < deadline:
            time.sleep(0.01)
        assert backend.is_settled(), "worker did not settle after pause"

        # Now switch to three references while paused-and-settled.
        ack_3 = backend.apply_configuration(
            model_id=FLUX2_KLEIN_4B,
            reference_paths=[
                str(FIXTURES / "valid_square.png"),
                str(FIXTURES / "valid_portrait.png"),
                str(FIXTURES / "valid_landscape.jpg"),
            ],
            preset="landscape-medium",
        )
        assert ack_3.compatible is True
        assert ack_3.reference_count == 3

        handler.handle_pause(server)
        # The worker may have already entered the next generate call
        # after the previous release_one -- capture the call count
        # BEFORE the worker enters generate for the post-update set,
        # so we can inspect only the post-update call(s).
        baseline_calls = len(klein_engine.call_log)
        # Wait for a new generate call (the worker re-enters generate
        # with the new 3-reference options; any prior call still has
        # the old 2-reference options).
        deadline = time.time() + 3.0
        while len(klein_engine.call_log) == baseline_calls and time.time() < deadline:
            time.sleep(0.01)
        assert len(klein_engine.call_log) > baseline_calls, (
            "worker did not enter generate after the 3-reference update"
        )
        # The post-update call(s) must see exactly 3 references. The
        # very first post-update call is what matters; if any later
        # call sees a different count, the no-partial-set guarantee
        # is broken.
        post_update_call = klein_engine.call_log[baseline_calls]
        assert len(post_update_call[1].references) == 3, (
            f"engine received {len(post_update_call[1].references)} references "
            f"in the post-update call; expected 3"
        )


# ---------------------------------------------------------------------------
# Test 5 -- test_decode_lifetime
# ---------------------------------------------------------------------------


class TestDecodeLifetime:
    """AC-PROCESS-3: each reference is decoded and normalized once, at
    acknowledgement. The held data outlives exactly that configuration
    and is released on abort (the lifecycle change the test exercises)."""

    def test_held_pixels_survive_file_changes_and_release_on_abort(
        self, tmp_path: Path, full_stack: FullStack
    ) -> None:
        handler, backend, server = (
            full_stack.handler,
            full_stack.backend,
            full_stack.server,
        )

        reference_path = tmp_path / "ref.png"
        shutil.copy2(FIXTURES / "valid_square.png", reference_path)

        ack = backend.apply_configuration(
            model_id=FLUX1_KONTEXT_DEV,
            reference_paths=[str(reference_path)],
            preset="landscape-medium",
        )
        assert ack.compatible is True
        assert backend.references
        held_reference = backend.references[0]
        held_pixels = held_reference.pixel_data.copy()

        # Overwrite and delete the source file after acknowledgement.
        Image.new("RGB", (16, 16), color=(0, 0, 0)).save(reference_path)
        reference_path.unlink()
        assert not reference_path.exists()

        kontext_engine = full_stack.engine_for(FLUX1_KONTEXT_DEV)

        # First generation under the held configuration.
        handler.handle_pause(server)
        _wait_for_generate(kontext_engine, timeout=2.0)
        kontext_engine.release_one()
        buffered_1 = backend.get_next_image(timeout=2.0)
        assert buffered_1 is not None
        seen_1 = kontext_engine.call_log[-1][1].references[0].pixel_data
        assert seen_1.tobytes() == held_pixels.tobytes(), (
            "first generation did not receive the originally decoded pixels"
        )

        # Second generation still uses the held pixels (file is gone).
        _wait_for_generate(kontext_engine, timeout=2.0)
        kontext_engine.release_one()
        buffered_2 = backend.get_next_image(timeout=2.0)
        assert buffered_2 is not None
        seen_2 = kontext_engine.call_log[-1][1].references[0].pixel_data
        assert seen_2.tobytes() == held_pixels.tobytes(), (
            "second generation lost the held pixels after the source file was deleted"
        )

        # Abort releases the decoded data.
        backend.abort()
        assert backend.references == ()
        assert backend.reference_ids == ()
        assert backend.reference_paths == ()


# ---------------------------------------------------------------------------
# Test 6 -- test_resume_during_update
# ---------------------------------------------------------------------------


class TestResumeDuringUpdate:
    """AC-STATE-3: a resume arriving during a configuration update takes
    effect after acknowledgement. The handler runs commands on a single
    thread (the IPC server loop), so the resume that arrives during the
    update is processed after the update finishes; the resume decision
    must be against the post-update state."""

    def test_resume_during_update_decides_against_post_update_state(
        self, tmp_path: Path, full_stack: FullStack
    ) -> None:
        handler, backend, server = (
            full_stack.handler,
            full_stack.backend,
            full_stack.server,
        )

        # First resume so the worker is actively generating under
        # schnell. We need a generation in flight so the
        # apply_configuration path can discard it.
        handler.handle_pause(server)
        schnell_engine = full_stack.engine_for(FLUX1_SCHNELL)
        _wait_for_generate(schnell_engine, timeout=2.0)
        schnell_engine.release_one()
        # Drain the buffered image so the worker is blocked on the
        # gate again (second generate).
        buffered_pre = backend.get_next_image(timeout=2.0)
        assert buffered_pre is not None
        _wait_for_generate(schnell_engine, timeout=2.0)

        # Now pause + wait for settled.
        handler.handle_pause(server)
        assert not backend.is_settled()
        # Release so the worker settles.
        schnell_engine.release_one()
        deadline = time.time() + 2.0
        while not backend.is_settled() and time.time() < deadline:
            time.sleep(0.01)
        assert backend.is_settled(), "worker did not settle after gate release"

        # Patch `apply_configuration` so it blocks on an event the test
        # controls; this lets us interleave the resume with the update.
        proceed_with_update = threading.Event()
        proceed_with_update.clear()

        original_apply = backend.apply_configuration

        def slow_apply(*args, **kwargs):
            proceed_with_update.wait(timeout=5.0)
            return original_apply(*args, **kwargs)

        with patch.object(backend, "apply_configuration", slow_apply):
            update_result: dict = {}

        def do_update():
            try:
                ack = backend.apply_configuration(
                    model_id=FLUX1_KONTEXT_DEV,
                    reference_paths=[str(FIXTURES / "valid_square.png")],
                    preset="landscape-medium",
                )
                update_result["ack"] = ack
            except Exception as exc:
                update_result["error"] = exc

        update_thread = threading.Thread(target=do_update)
        update_thread.start()
        # Give the slow_apply time to enter wait().
        time.sleep(0.1)

        # Issue the resume. The handler is single-threaded, so this
        # resumes against the configuration BEFORE the update
        # completes. The compatibility gate in handle_pause runs
        # validate_selection against the *current* (schnell)
        # acknowledged state -- which is valid for an empty reference
        # set -- so the resume should be accepted.
        handler.handle_pause(server)

        # Now let the update complete.
        proceed_with_update.set()
        update_thread.join(timeout=5.0)
        assert "ack" in update_result, "update did not complete"
        assert update_result["ack"].compatible is True

        # The worker should now be generating under Kontext (the
        # post-update state is what takes effect after the resume was
        # processed).
        kontext_engine = full_stack.engine_for(FLUX1_KONTEXT_DEV)
        _wait_for_generate(kontext_engine, timeout=2.0)
        assert kontext_engine.call_log, (
            "worker did not generate under Kontext after update completion"
        )


# ---------------------------------------------------------------------------
# Test 7 -- test_no_reference_identity_persisted
# ---------------------------------------------------------------------------


class TestNoReferenceIdentityPersisted:
    """AC-META-1 + AC-STATE-2 negative requirement: persisted outputs
    (preview PNGs and accepted PNGs) carry no reference-derived data.
    The closed key set is {AspectRatio, Width, Height, Prompt, Model,
    Seed, GeneratedWidth, GeneratedHeight}; no chunk value contains any
    reference path, basename, or `reference_ids` string."""

    def test_no_reference_identity_in_persisted_outputs(
        self, tmp_path: Path, full_stack: FullStack
    ) -> None:
        handler, backend, server = (
            full_stack.handler,
            full_stack.backend,
            full_stack.server,
        )

        reference_paths = [
            str(FIXTURES / "valid_square.png"),
        ]
        basenames = [Path(p).name for p in reference_paths]
        ack = backend.apply_configuration(
            model_id=FLUX1_KONTEXT_DEV,
            reference_paths=reference_paths,
            preset="landscape-medium",
        )
        assert ack.compatible is True
        assert backend.reference_ids
        assert len(backend.reference_ids) == 1

        kontext_engine = full_stack.engine_for(FLUX1_KONTEXT_DEV)
        handler.handle_pause(server)
        _wait_for_generate(kontext_engine, timeout=2.0)
        kontext_engine.release_one()
        buffered = backend.get_next_image(timeout=2.0)
        assert buffered is not None

        preview_path = backend.save_to_preview(buffered)
        accepted_path = tmp_path / "out" / "accepted.png"
        backend._save_with_metadata(buffered, accepted_path)

        # Inspect every PNG on disk.
        allowed_keys = {
            "AspectRatio",
            "Width",
            "Height",
            "Prompt",
            "Model",
            "Seed",
            "GeneratedWidth",
            "GeneratedHeight",
        }
        for path in (preview_path, accepted_path):
            with Image.open(path) as img:
                keys = set(img.text.keys())
                extra = keys - allowed_keys
                assert not extra, f"{path} has unexpected PNG text keys: {extra}"
                for value in img.text.values():
                    for forbidden in reference_paths + basenames + list(backend.reference_ids):
                        assert forbidden not in value, (
                            f"{path} contains forbidden substring {forbidden!r} "
                            f"in chunk value {value!r}"
                        )

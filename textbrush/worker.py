"""Background inference with atomic configuration and bounded publication."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from textbrush.buffer import BufferedImage, ImageBuffer
from textbrush.inference.base import GenerationOptions, InferenceEngine

if TYPE_CHECKING:
    from textbrush.references import NormalizedReference

logger = logging.getLogger(__name__)
OnGenerationStartCallback = Callable[[int, int], None]


@dataclass(frozen=True)
class _Inputs:
    """Owned value snapshot; mutable sampling dictionaries never cross the boundary."""

    seed: int | None
    width: int | None
    height: int | None
    steps: int
    aspect_ratio: str
    references: tuple[NormalizedReference, ...]
    model_id: str
    sampling_settings: tuple[tuple[str, float | int], ...]

    @classmethod
    def capture(cls, options: GenerationOptions) -> _Inputs:
        return cls(
            seed=options.seed,
            width=options.width,
            height=options.height,
            steps=options.steps,
            aspect_ratio=options.aspect_ratio,
            references=tuple(options.references),
            model_id=options.model_id,
            sampling_settings=tuple(options.sampling_settings.items()),
        )

    def as_options(self) -> GenerationOptions:
        return GenerationOptions(
            **{**vars(self), "sampling_settings": dict(self.sampling_settings)}
        )


@dataclass(frozen=True)
class _Configuration:
    prompt: str
    inputs: _Inputs
    epoch: int
    model_id: str | None
    reference_ids: tuple[str, ...]
    on_start: OnGenerationStartCallback | None


class GenerationWorker:
    """Run one inference at a time, keeping at most one unpublished result.

    Configuration replacement, buffer clearing, publication, and seed advancement
    share `_changed`'s lock. Publication never waits for capacity with that lock
    held. No old result can enter the buffer after update_config returns.

    Pause allows active inference to finish. If its result cannot fit, it remains
    pending while the worker settles; resume publishes it before doing more work.
    Configuration replacement or stop discards a pending result. Engine replacement
    by the backend is permitted only while the worker is paused and settled.
    """

    def __init__(
        self,
        engine: InferenceEngine,
        buffer: ImageBuffer,
        prompt: str,
        options: GenerationOptions,
        on_generation_start: OnGenerationStartCallback | None = None,
        on_settled: Callable[[], None] | None = None,
        start_paused: bool = False,
    ):
        self.engine = engine
        self.buffer = buffer
        self._changed = threading.Condition()
        self._config = _Configuration(
            prompt, _Inputs.capture(options), 0, options.model_id, (), on_generation_start
        )
        self._on_settled = on_settled
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._pause_event = threading.Event()
        if not start_paused:
            self._pause_event.set()
        self._settled_event = threading.Event()
        if start_paused:
            self._settled_event.set()
        self._settle_notified = False
        self._error: Exception | None = None

    @property
    def prompt(self) -> str:
        with self._changed:
            return self._config.prompt

    @prompt.setter
    def prompt(self, prompt: str) -> None:
        with self._changed:
            self.update_config(prompt, self.options, reference_ids=self._config.reference_ids)

    @property
    def options(self) -> GenerationOptions:
        """Return a detached options value; updates go through update_config."""
        with self._changed:
            return self._config.inputs.as_options()

    @property
    def _generation_epoch(self) -> int:
        with self._changed:
            return self._config.epoch

    def start(self) -> None:
        with self._changed:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Generation worker is already running")
            self._error = None
            self.buffer.reset_shutdown()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        """Stop future publication immediately; active inference may finish later."""
        with self._changed:
            self._stop_event.set()
            self._pause_event.set()
            self.buffer.shutdown(grace_period=0.0)
            self._changed.notify_all()

    def pause(self) -> None:
        with self._changed:
            if self._pause_event.is_set():
                self._pause_event.clear()
                self._settled_event.clear()
            self._changed.notify_all()

    def resume(self) -> None:
        with self._changed:
            self._pause_event.set()
            self._settled_event.clear()
            self._settle_notified = False
            self._changed.notify_all()

    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def is_settled(self) -> bool:
        return self.is_paused() and self._settled_event.is_set()

    def wait_settled(self, timeout: float | None) -> bool:
        return self._settled_event.wait(timeout)

    def set_on_settled(self, callback: Callable[[], None] | None) -> None:
        with self._changed:
            self._on_settled = callback

    def update_config(
        self,
        prompt: str,
        options: GenerationOptions,
        on_generation_start: OnGenerationStartCallback | None = None,
        *,
        model_id: str | None = None,
        reference_ids: tuple[str, ...] = (),
    ) -> None:
        """Atomically replace inputs and clear superseded buffered output.

        None preserves the previous model ID/callback. Reference IDs are replaced
        (empty means no references). In-flight inference continues but cannot
        publish or advance the seed of this new configuration.
        """
        with self._changed:
            old = self._config
            self._config = _Configuration(
                prompt,
                _Inputs.capture(options),
                old.epoch + 1,
                old.model_id if model_id is None else model_id,
                tuple(reference_ids),
                old.on_start if on_generation_start is None else on_generation_start,
            )
            self.buffer.clear()
            self._changed.notify_all()

    def join(self, timeout: float | None = None) -> None:
        if self._thread:
            self._thread.join(timeout)

    def get_error(self) -> Exception | None:
        with self._changed:
            return self._error

    def clear_error(self) -> None:
        with self._changed:
            self._error = None

    def _wait_until_running(self, epoch: int | None = None) -> bool:
        while True:
            callback = None
            with self._changed:
                if self._stop_event.is_set() or (epoch is not None and epoch != self._config.epoch):
                    return False
                if self._pause_event.is_set():
                    self._settled_event.clear()
                    return True
                self._settled_event.set()
                if not self._settle_notified:
                    callback = self._on_settled
                    self._settle_notified = True
            # Callbacks may invoke backend methods; never call them with our lock held.
            if callback is not None:
                try:
                    callback()
                except Exception:
                    logger.exception("on_settled callback raised")
            with self._changed:
                if not self._pause_event.is_set() and not self._stop_event.is_set():
                    self._changed.wait()

    def _publish(self, snapshot: _Configuration, image: BufferedImage) -> bool:
        """Publish once or discard. A full buffer preserves the pending output."""
        while True:
            with self._changed:
                if self._stop_event.is_set() or snapshot.epoch != self._config.epoch:
                    return False
                if self.buffer.put(image, timeout=0):
                    seed = snapshot.inputs.seed
                    next_seed = (image.seed if seed is None else seed) + 1
                    self._config = replace(
                        self._config, inputs=replace(snapshot.inputs, seed=next_seed)
                    )
                    logger.debug("Generated image with seed %s", image.seed)
                    return True
                # Release the configuration lock during backpressure. Configuration
                # and lifecycle notifications wake this early; consumer capacity is
                # rechecked at most 50 ms later. No new inference starts here.
                self._changed.wait(timeout=0.05)
            if not self._wait_until_running(snapshot.epoch):
                return False

    def _run(self) -> None:
        logger.info("Worker started")
        try:
            while self._wait_until_running():
                with self._changed:
                    if self._stop_event.is_set() or not self._pause_event.is_set():
                        continue
                    snapshot = self._config
                    engine = self.engine
                image = None
                try:
                    if snapshot.on_start is not None:
                        snapshot.on_start(snapshot.inputs.seed or 0, len(self.buffer))
                    result = engine.generate(snapshot.prompt, snapshot.inputs.as_options())
                    image = BufferedImage(
                        image=result.image,
                        seed=result.seed,
                        prompt=snapshot.prompt,
                        model_name=result.model_name,
                        aspect_ratio=snapshot.inputs.aspect_ratio,
                        generated_width=result.generated_width,
                        generated_height=result.generated_height,
                        model_id=snapshot.model_id,
                        reference_ids=snapshot.reference_ids,
                    )
                    if self._publish(snapshot, image):
                        image = None  # The buffer now owns it.
                except Exception as exc:
                    with self._changed:
                        if snapshot.epoch != self._config.epoch or self._stop_event.is_set():
                            continue
                        logger.error("Error during generation: %s", exc, exc_info=True)
                        self._error = exc
                        self._stop_event.set()
                        self.buffer.shutdown(grace_period=0.0)
                        self._changed.notify_all()
                    break
                finally:
                    if image is not None:
                        image.cleanup()
                        image.image.close()
        finally:
            logger.info("Worker stopped")

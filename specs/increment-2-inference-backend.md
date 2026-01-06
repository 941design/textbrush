# Increment 2: Inference Backend - Model Loading & Image Generation

## Overview
Implement the core image generation capability using FLUX.1 schnell. This increment creates the Python backend that handles model loading, inference, and the image buffer pipeline.

## Goals
- Port FluxGenerator from avatar-generator with adaptations
- Implement pluggable inference engine abstraction
- Create image buffer with FIFO semantics
- Handle hardware detection (CUDA/MPS/CPU)
- Implement deterministic seed-based generation

## Prerequisites
- Increment 1 complete (CLI, config, model weights)

## Deliverables

### 2.1 Inference Engine Abstraction

Create pluggable backend system (per spec section 7):

```
textbrush/
├── inference/
│   ├── __init__.py
│   ├── base.py              # Abstract InferenceEngine
│   ├── flux.py              # FLUX.1 implementation
│   └── factory.py           # Engine factory
```

**Base Interface (`textbrush/inference/base.py`):**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from PIL import Image

@dataclass
class GenerationResult:
    image: Image.Image
    seed: int
    generation_time: float
    model_name: str

@dataclass
class GenerationOptions:
    seed: int | None = None
    width: int = 512
    height: int = 512
    steps: int = 4
    aspect_ratio: str = "1:1"

class InferenceEngine(ABC):
    @abstractmethod
    def load(self) -> None:
        """Load model into memory."""
        pass

    @abstractmethod
    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        """Generate a single image from prompt."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is ready for inference."""
        pass

    @abstractmethod
    def unload(self) -> None:
        """Release model from memory."""
        pass

    @property
    @abstractmethod
    def device(self) -> str:
        """Return device being used (cuda/mps/cpu)."""
        pass
```

### 2.2 FLUX Generator Implementation

**Port from:** `avatar_generator/model/flux.py`

**Key adaptations:**
- Use new `InferenceEngine` base class
- Support aspect ratios (1:1, 16:9, 9:16)
- Simplified interface (no post-processing)

```python
# textbrush/inference/flux.py
class FluxInferenceEngine(InferenceEngine):
    MODEL_ID = "black-forest-labs/FLUX.1-schnell"

    def __init__(self):
        self._pipeline = None
        self._device = None
        self._dtype = None

    def load(self) -> None:
        # Auto-detect device
        if torch.cuda.is_available():
            self._device = "cuda"
            self._dtype = torch.bfloat16
        elif torch.backends.mps.is_available():
            self._device = "mps"
            self._dtype = torch.float32
        else:
            self._device = "cpu"
            self._dtype = torch.float32
            logger.warning("Running on CPU - generation will be slow")

        # Load pipeline
        self._pipeline = FluxPipeline.from_pretrained(
            self.MODEL_ID,
            torch_dtype=self._dtype
        )

        # Device-specific optimization
        if self._device == "cuda":
            self._pipeline.enable_model_cpu_offload()
        else:
            self._pipeline.to(self._device)

    def generate(self, prompt: str, options: GenerationOptions) -> GenerationResult:
        width, height = self._resolve_dimensions(options.aspect_ratio)

        generator = torch.Generator(self._device)
        seed = options.seed or random.randint(0, 2**32 - 1)
        generator.manual_seed(seed)

        start = time.perf_counter()
        result = self._pipeline(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=options.steps,
            generator=generator
        )
        elapsed = time.perf_counter() - start

        return GenerationResult(
            image=result.images[0],
            seed=seed,
            generation_time=elapsed,
            model_name=self.MODEL_ID
        )
```

### 2.3 Image Buffer System

Implement the 8-image FIFO buffer (per spec section 3.1):

```python
# textbrush/buffer.py
import threading
from collections import deque
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BufferedImage:
    image: Image.Image
    seed: int
    temp_path: Path | None = None

class ImageBuffer:
    def __init__(self, max_size: int = 8):
        self.max_size = max_size
        self._buffer: deque[BufferedImage] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._shutdown = False

    def put(self, item: BufferedImage, timeout: float | None = None) -> bool:
        """Add image to buffer, blocking if full."""
        with self._not_full:
            while len(self._buffer) >= self.max_size and not self._shutdown:
                if not self._not_full.wait(timeout):
                    return False
            if self._shutdown:
                return False
            self._buffer.append(item)
            self._not_empty.notify()
            return True

    def get(self, timeout: float | None = None) -> BufferedImage | None:
        """Get next image from buffer, blocking if empty."""
        with self._not_empty:
            while len(self._buffer) == 0 and not self._shutdown:
                if not self._not_empty.wait(timeout):
                    return None
            if self._shutdown and len(self._buffer) == 0:
                return None
            item = self._buffer.popleft()
            self._not_full.notify()
            return item

    def peek(self) -> BufferedImage | None:
        """Look at next image without removing."""
        with self._lock:
            return self._buffer[0] if self._buffer else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    def shutdown(self) -> None:
        """Signal shutdown and wake waiting threads."""
        with self._lock:
            self._shutdown = True
            self._not_empty.notify_all()
            self._not_full.notify_all()

    def clear(self) -> list[BufferedImage]:
        """Clear buffer and return discarded items."""
        with self._lock:
            items = list(self._buffer)
            self._buffer.clear()
            self._not_full.notify_all()
            return items
```

### 2.4 Generation Worker

Background worker that continuously fills the buffer:

```python
# textbrush/worker.py
import threading
import logging
from .inference.base import InferenceEngine, GenerationOptions
from .buffer import ImageBuffer, BufferedImage

logger = logging.getLogger(__name__)

class GenerationWorker:
    def __init__(
        self,
        engine: InferenceEngine,
        buffer: ImageBuffer,
        prompt: str,
        options: GenerationOptions
    ):
        self.engine = engine
        self.buffer = buffer
        self.prompt = prompt
        self.options = options
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start background generation."""
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal worker to stop."""
        self._stop_event.set()
        self.buffer.shutdown()

    def join(self, timeout: float | None = None) -> None:
        """Wait for worker thread to finish."""
        if self._thread:
            self._thread.join(timeout)

    def _run(self) -> None:
        """Worker loop - generate images until stopped."""
        logger.info("Generation worker started")

        while not self._stop_event.is_set():
            try:
                # Generate next image
                result = self.engine.generate(self.prompt, self.options)

                buffered = BufferedImage(
                    image=result.image,
                    seed=result.seed
                )

                # Add to buffer (blocks if full)
                if not self.buffer.put(buffered, timeout=0.1):
                    if self._stop_event.is_set():
                        break
                    continue

                logger.debug(f"Generated image with seed {result.seed}")

                # Increment seed for next image
                self.options = GenerationOptions(
                    seed=(self.options.seed or result.seed) + 1,
                    width=self.options.width,
                    height=self.options.height,
                    steps=self.options.steps,
                    aspect_ratio=self.options.aspect_ratio
                )

            except Exception as e:
                logger.error(f"Generation error: {e}")
                if not self._stop_event.is_set():
                    continue
                break

        logger.info("Generation worker stopped")
```

### 2.5 Backend Coordinator

Orchestrates model loading and generation:

```python
# textbrush/backend.py
from pathlib import Path
from .config import Config
from .inference.factory import create_engine
from .buffer import ImageBuffer
from .worker import GenerationWorker

class TextbrushBackend:
    def __init__(self, config: Config):
        self.config = config
        self.engine = create_engine(config.inference.backend)
        self.buffer = ImageBuffer(max_size=config.model.buffer_size)
        self._worker: GenerationWorker | None = None

    def initialize(self) -> None:
        """Load model - call before starting generation."""
        self.engine.load()

    def start_generation(self, prompt: str, seed: int | None = None, aspect_ratio: str = "1:1") -> None:
        """Begin background image generation."""
        options = GenerationOptions(
            seed=seed,
            aspect_ratio=aspect_ratio
        )
        self._worker = GenerationWorker(
            engine=self.engine,
            buffer=self.buffer,
            prompt=prompt,
            options=options
        )
        self._worker.start()

    def get_next_image(self) -> BufferedImage | None:
        """Get next generated image (blocks if buffer empty)."""
        return self.buffer.get()

    def skip_current(self) -> BufferedImage | None:
        """Skip current image and get next."""
        return self.buffer.get()

    def accept_current(self, output_path: Path | None = None) -> Path:
        """Save current image and return path."""
        current = self.buffer.peek()
        if not current:
            raise RuntimeError("No image to accept")

        if output_path is None:
            output_path = self._generate_output_path()

        current.image.save(output_path)
        return output_path

    def abort(self) -> None:
        """Stop generation and discard all images."""
        if self._worker:
            self._worker.stop()
            self._worker.join(timeout=5.0)
        self.buffer.clear()

    def shutdown(self) -> None:
        """Clean shutdown of backend."""
        self.abort()
        self.engine.unload()
```

## Dependencies

Add to pyproject.toml:
```toml
dependencies = [
    "huggingface-hub>=0.20.0",
    "torch>=2.0.0",
    "diffusers>=0.25.0",
    "transformers>=4.36.0",
    "accelerate>=0.25.0",
    "safetensors>=0.4.0",
    "Pillow>=10.0.0",
    "sentencepiece>=0.1.99",
]
```

## Acceptance Criteria

1. [ ] `FluxInferenceEngine` loads model successfully
2. [ ] Device auto-detection works (CUDA > MPS > CPU)
3. [ ] Single image generation produces valid PNG
4. [ ] Buffer maintains FIFO order
5. [ ] Buffer blocks correctly when full/empty
6. [ ] Worker continuously fills buffer
7. [ ] Worker stops cleanly on abort
8. [ ] Seed produces deterministic results
9. [ ] Aspect ratio mapping works (1:1, 16:9, 9:16)

## Testing

```python
# tests/test_buffer.py
def test_buffer_fifo_order():
    """Images come out in order they went in."""

def test_buffer_blocks_when_full():
    """Put blocks when buffer is at capacity."""

def test_buffer_blocks_when_empty():
    """Get blocks when buffer is empty."""

def test_buffer_shutdown_unblocks():
    """Shutdown unblocks waiting threads."""

# tests/test_worker.py
def test_worker_fills_buffer():
    """Worker continuously generates until stopped."""

def test_worker_stops_cleanly():
    """Worker responds to stop signal."""

# tests/test_inference.py (mark as slow)
@pytest.mark.slow
def test_flux_generates_image():
    """FLUX produces valid image from prompt."""

@pytest.mark.slow
def test_flux_seed_determinism():
    """Same seed produces same image."""
```

## Files to Port from avatar-generator

| Source | Destination | Changes |
|--------|-------------|---------|
| `avatar_generator/model/flux.py` | `textbrush/inference/flux.py` | Adapt to InferenceEngine base |
| `avatar_generator/model/weights.py` | Already ported in Increment 1 | - |

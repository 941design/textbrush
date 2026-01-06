"""Thread-safe FIFO image buffer for textbrush.

Implements bounded buffer with blocking put/get semantics.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class BufferedImage:
    """Image stored in buffer with metadata.

    Attributes:
        image: PIL Image object.
        seed: Random seed used for generation.
        temp_path: Optional path to temporary file on disk.
    """

    image: Image.Image
    seed: int
    temp_path: Path | None = None

    def cleanup(self) -> None:
        """Delete temporary file if it exists.

        CONTRACT:
          Inputs: none

          Outputs: none (modifies filesystem)

          Invariants:
            - After cleanup(), temp_path file does not exist (if temp_path was set)
            - If temp_path is None, no operation performed
            - If temp_path file doesn't exist, no error raised

          Properties:
            - Idempotent: safe to call multiple times
            - Safe: uses missing_ok=True to handle non-existent files
            - Side effect: deletes file from filesystem

          Algorithm:
            1. If temp_path is None: return immediately
            2. Call temp_path.unlink(missing_ok=True)
        """
        if self.temp_path is not None:
            self.temp_path.unlink(missing_ok=True)

    def __enter__(self) -> "BufferedImage":
        """Enter context manager.

        CONTRACT:
          Inputs: none

          Outputs:
            - self: BufferedImage instance

          Properties:
            - Returns self for use in with statement
            - No cleanup performed on entry
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and cleanup resources.

        CONTRACT:
          Inputs:
            - exc_type: exception type if exception occurred
            - exc_val: exception value if exception occurred
            - exc_tb: exception traceback if exception occurred

          Outputs: none (modifies filesystem)

          Invariants:
            - Calls cleanup() to delete temp_path file
            - Always performs cleanup regardless of exception

          Properties:
            - Cleanup on exit: ensures temp file is deleted
            - Exception propagation: does not suppress exceptions
        """
        self.cleanup()


class ImageBuffer:
    """Thread-safe bounded FIFO buffer for images.

    Supports blocking put/get operations with timeout.
    """

    def __init__(self, max_size: int = 8):
        """Initialize buffer with maximum capacity.

        CONTRACT:
          Inputs:
            - max_size: positive integer, maximum buffer capacity

          Outputs: none (constructs instance)

          Invariants:
            - 0 ≤ len(buffer) ≤ max_size at all times
            - FIFO order: first image in is first image out
            - Thread-safe: concurrent put/get operations are safe

          Properties:
            - Capacity bounded: buffer never exceeds max_size
            - Order preserved: get() returns images in put() order
        """
        self.max_size = max_size
        self._buffer: deque[BufferedImage] = deque(maxlen=max_size)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        self._shutdown = False
        self._shutdown_start_time: float | None = None
        self._shutdown_grace_period: float = 0.0

    def put(self, item: BufferedImage, timeout: float | None = None) -> bool:
        """Add image to buffer, blocking if full.

        CONTRACT:
          Inputs:
            - item: BufferedImage to add
            - timeout: optional timeout in seconds (None = wait indefinitely)

          Outputs:
            - boolean: True if added successfully, False if timeout or post-grace shutdown

          Invariants:
            - If buffer is full, blocks until space available or timeout
            - During grace period, can add items even after shutdown
            - After grace period, returns False immediately
            - On success, len(buffer) increases by 1 (or stays at max_size if maxlen triggers)
            - FIFO order maintained

          Properties:
            - Blocking: waits for space if buffer full
            - Thread-safe: multiple producers can call put() concurrently
            - Timeout respected: returns False if timeout expires
            - Shutdown signal: returns False if post-grace period

          Algorithm:
            1. Acquire not_full condition
            2. While buffer full and not post-grace: wait with timeout
            3. If post-grace or timeout: return False
            4. Append item to buffer
            5. Notify not_empty waiters
            6. Return True
        """
        with self._not_full:
            while len(self._buffer) >= self.max_size and not self._is_post_grace():
                if not self._not_full.wait(timeout):
                    return False

            if self._is_post_grace():
                return False

            self._buffer.append(item)
            self._not_empty.notify()
            return True

    def get(self, timeout: float | None = None) -> BufferedImage | None:
        """Get next image from buffer, blocking if empty.

        CONTRACT:
          Inputs:
            - timeout: optional timeout in seconds (None = wait indefinitely)

          Outputs:
            - BufferedImage if available, None if timeout or post-grace with empty buffer

          Invariants:
            - If buffer is empty, blocks until item available or timeout
            - If post-grace and empty, returns None immediately
            - Can drain buffer after shutdown even post-grace
            - On success, len(buffer) decreases by 1
            - FIFO order: returns oldest item

          Properties:
            - Blocking: waits for item if buffer empty
            - Thread-safe: multiple consumers can call get() concurrently
            - Timeout respected: returns None if timeout expires
            - Shutdown signal: returns None if post-grace and buffer empty

          Algorithm:
            1. Acquire not_empty condition
            2. While buffer empty and not post-grace: wait with timeout
            3. If post-grace and empty, or timeout: return None
            4. Pop item from left (FIFO)
            5. Notify not_full waiters
            6. Return item
        """
        with self._not_empty:
            while not self._buffer and not self._is_post_grace():
                if not self._not_empty.wait(timeout):
                    return None

            if self._is_post_grace() and not self._buffer:
                return None

            item = self._buffer.popleft()
            self._not_full.notify()
            return item

    def peek(self) -> BufferedImage | None:
        """Look at next image without removing.

        CONTRACT:
          Inputs: none

          Outputs:
            - BufferedImage at front of queue, or None if empty

          Invariants:
            - Does not modify buffer
            - Returns None if buffer empty
            - Returns oldest item if buffer non-empty

          Properties:
            - Non-blocking: returns immediately
            - Thread-safe: can be called concurrently with put/get
            - Read-only: len(buffer) unchanged after call
        """
        with self._lock:
            return self._buffer[0] if self._buffer else None

    def __len__(self) -> int:
        """Return current buffer size.

        CONTRACT:
          Inputs: none

          Outputs:
            - non-negative integer: current number of items in buffer

          Invariants:
            - 0 ≤ result ≤ max_size
            - Thread-safe read

          Properties:
            - Non-blocking
            - Snapshot: result may be stale immediately after return
        """
        with self._lock:
            return len(self._buffer)

    def _is_post_grace(self) -> bool:
        """Check if grace period has expired after shutdown.

        CONTRACT:
          Inputs: none

          Outputs:
            - boolean: True if shutdown and grace period expired, False otherwise

          Invariants:
            - Returns False if shutdown not called
            - Returns False if within grace period after shutdown
            - Returns True if grace period has expired after shutdown

          Properties:
            - Non-blocking
            - Thread-safe: must be called with lock held
        """
        if not self._shutdown:
            return False
        if self._shutdown_start_time is None:
            return True
        elapsed = time.time() - self._shutdown_start_time
        return elapsed > self._shutdown_grace_period

    def shutdown(self, grace_period: float = 2.0) -> None:
        """Signal shutdown and wake waiting threads.

        CONTRACT:
          Inputs:
            - grace_period: seconds to allow in-flight operations to complete

          Outputs: none (modifies internal state)

          Invariants:
            - After shutdown(), put() can succeed during grace period
            - After grace period expires, put() returns False
            - After shutdown(), get() returns None (if empty and post-grace)
            - All waiting threads are woken

          Properties:
            - Idempotent: calling multiple times does not extend grace period
            - Graceful: allows in-flight operations to complete during grace period
            - Signal: sets shutdown flag and notifies all waiters

          Algorithm:
            1. Acquire lock
            2. Set shutdown flag to True (if not already set)
            3. Record start time and grace period (only on first call)
            4. Notify all not_empty waiters
            5. Notify all not_full waiters
        """
        with self._lock:
            if not self._shutdown:
                self._shutdown = True
                self._shutdown_start_time = time.time()
                self._shutdown_grace_period = grace_period
            self._not_empty.notify_all()
            self._not_full.notify_all()

    def clear(self) -> list[BufferedImage]:
        """Clear buffer and return discarded items.

        CONTRACT:
          Inputs: none

          Outputs:
            - list of BufferedImage: all items removed from buffer

          Invariants:
            - After clear(), len(buffer) = 0
            - Returned list contains all items that were in buffer (in FIFO order)
            - Notifies all not_full waiters
            - Calls cleanup() on all removed items to delete temp files

          Properties:
            - Atomic: all items removed in single operation
            - Thread-safe: blocks other operations during clear
            - Returns copy: returned list is independent of buffer
            - Cleanup: deletes all temporary files associated with cleared items

          Algorithm:
            1. Acquire lock
            2. Copy all items from buffer to list
            3. Clear buffer
            4. Notify all not_full waiters
            5. Call cleanup() on each item to delete temp files
            6. Return copied list
        """
        with self._lock:
            items = list(self._buffer)
            self._buffer.clear()
            self._not_full.notify_all()

        for item in items:
            item.cleanup()

        return items

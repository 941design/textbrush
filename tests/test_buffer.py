"""Property-based tests for ImageBuffer using Hypothesis."""

import threading
import time
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.strategies import composite
from PIL import Image

from textbrush.buffer import BufferedImage, ImageBuffer


@composite
def buffered_image_strategy(draw):
    """Generate BufferedImage instances."""
    width = draw(st.integers(min_value=1, max_value=100))
    height = draw(st.integers(min_value=1, max_value=100))
    mode = draw(st.sampled_from(["RGB", "RGBA", "L"]))
    seed = draw(st.integers(min_value=0, max_value=2**31 - 1))

    img = Image.new(mode, (width, height))
    temp_path = draw(st.one_of(st.none(), st.just(Path("/tmp/test.png"))))

    return BufferedImage(image=img, seed=seed, temp_path=temp_path)


class TestImageBufferGet:
    """Property-based tests for ImageBuffer.get() method."""

    @given(buffered_image_strategy())
    def test_get_returns_item_when_buffer_has_item(self, item):
        """Property: get() returns the item when buffer contains one item."""
        buffer = ImageBuffer(max_size=1)
        buffer._buffer.append(item)

        result = buffer.get(timeout=0.1)

        assert result is item
        assert len(buffer) == 0

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=10))
    def test_get_maintains_fifo_order(self, items):
        """Property: get() returns items in FIFO order (oldest first)."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer._buffer.append(item)

        results = [buffer.get(timeout=0.1) for _ in range(len(items))]

        assert results == items

    def test_get_returns_none_on_timeout_when_empty(self):
        """Property: get() returns None when buffer is empty and timeout expires."""
        buffer = ImageBuffer(max_size=1)

        start = time.time()
        result = buffer.get(timeout=0.05)
        elapsed = time.time() - start

        assert result is None
        assert 0.04 < elapsed < 0.2

    @given(buffered_image_strategy())
    def test_get_decreases_buffer_length_by_one(self, item):
        """Property: get() decreases len(buffer) by 1 when successful."""
        buffer = ImageBuffer(max_size=2)
        buffer._buffer.append(item)
        initial_len = len(buffer)

        buffer.get(timeout=0.1)

        assert len(buffer) == initial_len - 1

    def test_get_returns_none_after_shutdown_when_empty(self):
        """Property: get() returns None after grace period with empty buffer."""
        buffer = ImageBuffer(max_size=1)
        buffer.shutdown(grace_period=0.0)

        start = time.time()
        result = buffer.get(timeout=1.0)
        elapsed = time.time() - start

        assert result is None
        assert elapsed < 0.1

    @given(buffered_image_strategy())
    def test_get_returns_existing_item_even_after_shutdown(self, item):
        """Property: get() returns existing items even after shutdown."""
        buffer = ImageBuffer(max_size=1)
        buffer._buffer.append(item)
        buffer.shutdown()

        result = buffer.get(timeout=0.1)

        assert result is item

    @given(buffered_image_strategy())
    def test_get_notifies_waiting_put_threads(self, item):
        """Property: get() notifies waiting put() threads via _not_full."""
        buffer = ImageBuffer(max_size=1)
        with buffer._lock:
            buffer._buffer.append(item)

        put_succeeded = threading.Event()

        def producer():
            new_item = BufferedImage(image=Image.new("RGB", (10, 10)), seed=42, temp_path=None)
            success = buffer.put(new_item, timeout=1.0)
            if success:
                put_succeeded.set()

        producer_thread = threading.Thread(target=producer)
        producer_thread.start()
        time.sleep(0.05)

        buffer.get(timeout=0.1)

        producer_thread.join(timeout=1.0)
        assert put_succeeded.is_set()

    @given(st.lists(buffered_image_strategy(), min_size=2, max_size=10))
    def test_concurrent_get_operations_are_thread_safe(self, items):
        """Property: multiple consumers can call get() concurrently."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer._buffer.append(item)

        results = []
        results_lock = threading.Lock()

        def consumer():
            result = buffer.get(timeout=0.5)
            with results_lock:
                results.append(result)

        threads = [threading.Thread(target=consumer) for _ in range(len(items))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == len(items)
        assert all(r is not None for r in results)
        assert sorted(results, key=id) == sorted(items, key=id)

    def test_get_blocks_when_buffer_empty_until_item_available(self):
        """Property: get() blocks when buffer is empty until item becomes available."""
        buffer = ImageBuffer(max_size=1)
        item = BufferedImage(image=Image.new("RGB", (10, 10)), seed=123, temp_path=None)

        get_completed = threading.Event()
        retrieved_item = []

        def consumer():
            result = buffer.get(timeout=1.0)
            retrieved_item.append(result)
            get_completed.set()

        consumer_thread = threading.Thread(target=consumer)
        consumer_thread.start()

        time.sleep(0.05)
        assert not get_completed.is_set()

        with buffer._not_empty:
            buffer._buffer.append(item)
            buffer._not_empty.notify()

        consumer_thread.join(timeout=0.5)
        assert get_completed.is_set()
        assert retrieved_item[0] is item

    @given(st.floats(min_value=0.01, max_value=0.2))
    def test_get_timeout_is_respected(self, timeout):
        """Property: get() respects timeout parameter and returns within expected time."""
        buffer = ImageBuffer(max_size=1)

        start = time.time()
        result = buffer.get(timeout=timeout)
        elapsed = time.time() - start

        assert result is None
        assert timeout * 0.8 < elapsed < timeout * 2.0

    def test_get_with_none_timeout_waits_indefinitely(self):
        """Property: get() with timeout=None waits until item available or shutdown."""
        buffer = ImageBuffer(max_size=1)
        item = BufferedImage(image=Image.new("RGB", (10, 10)), seed=999, temp_path=None)

        retrieved_item = []

        def consumer():
            result = buffer.get(timeout=None)
            retrieved_item.append(result)

        consumer_thread = threading.Thread(target=consumer, daemon=True)
        consumer_thread.start()

        time.sleep(0.05)
        assert len(retrieved_item) == 0

        with buffer._not_empty:
            buffer._buffer.append(item)
            buffer._not_empty.notify()

        consumer_thread.join(timeout=0.5)
        assert len(retrieved_item) == 1
        assert retrieved_item[0] is item

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=5))
    def test_get_removes_from_left_of_deque(self, items):
        """Property: get() removes items from left (popleft) maintaining FIFO."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer._buffer.append(item)

        first_item = buffer.get(timeout=0.1)

        assert first_item is items[0]
        assert list(buffer._buffer) == items[1:]

    def test_get_returns_none_when_shutdown_with_no_timeout(self):
        """Property: get() with no timeout returns None after grace period on empty buffer."""
        buffer = ImageBuffer(max_size=1)

        retrieved = []

        def consumer():
            result = buffer.get(timeout=None)
            retrieved.append(result)

        consumer_thread = threading.Thread(target=consumer, daemon=True)
        consumer_thread.start()

        time.sleep(0.05)
        buffer.shutdown(grace_period=0.0)

        consumer_thread.join(timeout=0.5)
        assert len(retrieved) == 1
        assert retrieved[0] is None


class TestImageBufferGetIntegration:
    """Integration tests for get() with other buffer operations."""

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=8))
    def test_get_integrates_with_peek(self, items):
        """Property: peek() shows same item as next get() without removing it."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer._buffer.append(item)

        for expected in items:
            peeked = buffer.peek()
            gotten = buffer.get(timeout=0.1)

            assert peeked is expected
            assert gotten is expected

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=8))
    def test_get_after_clear_returns_none(self, items):
        """Property: get() returns None after clear() with timeout."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer._buffer.append(item)

        cleared = buffer.clear()

        result = buffer.get(timeout=0.05)

        assert len(cleared) == len(items)
        assert result is None

    @given(buffered_image_strategy())
    def test_len_is_consistent_after_get(self, item):
        """Property: len(buffer) accurately reflects state after get()."""
        buffer = ImageBuffer(max_size=2)
        buffer._buffer.append(item)

        assert len(buffer) == 1
        buffer.get(timeout=0.1)
        assert len(buffer) == 0


class TestImageBufferPut:
    """Property-based tests for ImageBuffer.put() method."""

    @given(buffered_image_strategy())
    def test_put_into_empty_buffer_returns_true(self, item):
        """Property: put() into non-full buffer returns True."""
        buffer = ImageBuffer(max_size=8)
        result = buffer.put(item)
        assert result is True

    @given(buffered_image_strategy())
    def test_put_increases_buffer_length(self, item):
        """Property: successful put() increases buffer length by 1."""
        buffer = ImageBuffer(max_size=8)
        initial_len = len(buffer)
        buffer.put(item)
        assert len(buffer) == initial_len + 1

    @given(st.integers(min_value=1, max_value=10))
    def test_buffer_never_exceeds_max_size(self, max_size):
        """Property: buffer never exceeds max_size after put operations."""
        buffer = ImageBuffer(max_size=max_size)
        for i in range(max_size + 5):
            img = BufferedImage(Image.new("RGB", (10, 10)), seed=i)
            buffer.put(img, timeout=0.001)
            assert len(buffer) <= max_size

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=20))
    def test_put_maintains_fifo_order(self, items):
        """Property: items are retrieved in put() order (FIFO)."""
        buffer = ImageBuffer(max_size=len(items))
        for item in items:
            buffer.put(item)

        retrieved = []
        for _ in range(len(items)):
            retrieved.append(buffer.get())

        assert [item.seed for item in items] == [item.seed for item in retrieved]

    @given(buffered_image_strategy())
    def test_put_after_shutdown_returns_false(self, item):
        """Property: put() returns False after grace period expires."""
        buffer = ImageBuffer(max_size=8)
        buffer.shutdown(grace_period=0.05)
        time.sleep(0.1)
        result = buffer.put(item)
        assert result is False

    @given(buffered_image_strategy())
    def test_put_after_shutdown_does_not_modify_buffer(self, item):
        """Property: put() after grace period does not add item to buffer."""
        buffer = ImageBuffer(max_size=8)
        initial_len = len(buffer)
        buffer.shutdown(grace_period=0.05)
        time.sleep(0.1)
        buffer.put(item)
        assert len(buffer) == initial_len

    def test_put_blocked_on_full_buffer_wakes_on_shutdown(self):
        """Property: blocked put() returns False when shutdown grace period expires."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        result = [None]

        def put_blocking():
            item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
            result[0] = buffer.put(item, timeout=5.0)

        thread = threading.Thread(target=put_blocking)
        thread.start()

        time.sleep(0.05)
        buffer.shutdown(grace_period=0.0)
        thread.join(timeout=1.0)

        assert result[0] is False

    @given(st.floats(min_value=0.01, max_value=0.15))
    def test_put_on_full_buffer_respects_timeout(self, timeout_seconds):
        """Property: put() on full buffer returns False when timeout expires."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
        start = time.time()
        result = buffer.put(item, timeout=timeout_seconds)
        elapsed = time.time() - start

        assert result is False
        assert timeout_seconds * 0.8 < elapsed < timeout_seconds * 3.0

    def test_put_without_timeout_blocks_until_space_available(self):
        """Property: put() without timeout blocks until space available."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        result = [None]

        def put_blocking():
            item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
            result[0] = buffer.put(item, timeout=None)

        thread = threading.Thread(target=put_blocking)
        thread.start()

        time.sleep(0.05)
        assert thread.is_alive()

        buffer.get()
        thread.join(timeout=1.0)

        assert result[0] is True

    @given(st.floats(min_value=0.1, max_value=0.5))
    def test_put_succeeds_when_space_becomes_available_before_timeout(self, timeout_seconds):
        """Property: put() succeeds if space becomes available before timeout."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        result = [None]

        def put_with_timeout():
            item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
            result[0] = buffer.put(item, timeout=timeout_seconds)

        thread = threading.Thread(target=put_with_timeout)
        thread.start()

        time.sleep(0.02)
        buffer.get()
        thread.join(timeout=timeout_seconds + 1.0)

        assert result[0] is True

    @given(st.integers(min_value=1, max_value=5), st.integers(min_value=2, max_value=8))
    @settings(max_examples=3, deadline=None)
    def test_concurrent_put_operations_are_thread_safe(self, buffer_size, num_producers):
        """Property: multiple producers can call put() concurrently safely."""
        buffer = ImageBuffer(max_size=buffer_size)
        items_per_producer = 5

        def producer(producer_id):
            for i in range(items_per_producer):
                item = BufferedImage(Image.new("RGB", (10, 10)), seed=producer_id * 1000 + i)
                buffer.put(item, timeout=2.0)

        threads = [threading.Thread(target=producer, args=(i,)) for i in range(num_producers)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(timeout=5.0)

        assert len(buffer) <= buffer_size

    @given(st.integers(min_value=2, max_value=8))
    @settings(max_examples=3, deadline=None)
    def test_concurrent_put_and_get_maintain_invariants(self, buffer_size):
        """Property: concurrent put/get operations maintain buffer invariants."""
        buffer = ImageBuffer(max_size=buffer_size)
        num_items = 20

        def producer():
            for i in range(num_items):
                item = BufferedImage(Image.new("RGB", (10, 10)), seed=i)
                buffer.put(item, timeout=2.0)

        def consumer():
            for _ in range(num_items):
                buffer.get(timeout=2.0)

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        time.sleep(0.01)
        consumer_thread.start()

        producer_thread.join(timeout=5.0)
        consumer_thread.join(timeout=5.0)

        assert 0 <= len(buffer) <= buffer_size

    @given(buffered_image_strategy())
    @settings(max_examples=10, deadline=None)
    def test_put_notifies_waiting_get(self, item):
        """Property: put() notifies waiting get() operations."""
        buffer = ImageBuffer(max_size=8)

        result = [None]

        def consumer():
            result[0] = buffer.get(timeout=1.0)

        thread = threading.Thread(target=consumer)
        thread.start()

        time.sleep(0.02)
        buffer.put(item)
        thread.join(timeout=1.0)

        assert result[0] is not None
        assert result[0].seed == item.seed

    def test_put_with_zero_timeout_on_full_buffer_returns_false_immediately(self):
        """Example: put() with zero timeout returns False immediately on full buffer."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
        start = time.time()
        result = buffer.put(item, timeout=0.0)
        elapsed = time.time() - start

        assert result is False
        assert elapsed < 0.1

    def test_put_with_negative_timeout_returns_false_immediately(self):
        """Example: put() with negative timeout returns False immediately on full buffer."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))

        item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
        result = buffer.put(item, timeout=-1.0)

        assert result is False

    def test_put_into_buffer_size_one(self):
        """Example: put() operations work correctly with buffer size 1."""
        buffer = ImageBuffer(max_size=1)

        item1 = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
        assert buffer.put(item1) is True
        assert len(buffer) == 1

        item2 = BufferedImage(Image.new("RGB", (10, 10)), seed=2)
        assert buffer.put(item2, timeout=0.01) is False
        assert len(buffer) == 1

    def test_put_on_shutdown_buffer_returns_immediately(self):
        """Example: put() on shutdown buffer post-grace returns immediately without blocking."""
        buffer = ImageBuffer(max_size=1)
        buffer.put(BufferedImage(Image.new("RGB", (10, 10)), seed=0))
        buffer.shutdown(grace_period=0.0)

        item = BufferedImage(Image.new("RGB", (10, 10)), seed=1)
        start = time.time()
        result = buffer.put(item, timeout=5.0)
        elapsed = time.time() - start

        assert result is False
        assert elapsed < 0.1


class TestImageBufferShutdownGracePeriod:
    """Property-based tests for shutdown grace period mechanism."""

    @given(buffered_image_strategy())
    def test_grace_period_allows_inflight_puts(self, item):
        """Property: put() succeeds during grace period after shutdown."""
        buffer = ImageBuffer(max_size=8)
        buffer.shutdown(grace_period=0.5)

        result = buffer.put(item, timeout=0.1)

        assert result is True
        assert len(buffer) == 1

    @given(buffered_image_strategy())
    def test_post_grace_put_returns_false(self, item):
        """Property: put() returns False after grace period expires."""
        buffer = ImageBuffer(max_size=8)
        buffer.shutdown(grace_period=0.05)

        time.sleep(0.1)
        result = buffer.put(item, timeout=0.1)

        assert result is False
        assert len(buffer) == 0

    def test_shutdown_idempotent(self):
        """Property: multiple shutdown() calls do not extend grace period."""
        buffer = ImageBuffer(max_size=8)

        buffer.shutdown(grace_period=0.1)
        start_time = buffer._shutdown_start_time
        initial_grace = buffer._shutdown_grace_period

        time.sleep(0.05)
        buffer.shutdown(grace_period=5.0)

        assert buffer._shutdown_start_time == start_time
        assert buffer._shutdown_grace_period == initial_grace

    @given(st.lists(buffered_image_strategy(), min_size=1, max_size=5))
    def test_get_drains_after_shutdown(self, items):
        """Property: get() returns all remaining items even after shutdown."""
        buffer = ImageBuffer(max_size=len(items))

        for item in items:
            buffer.put(item)

        buffer.shutdown(grace_period=0.0)

        retrieved = []
        for _ in range(len(items)):
            result = buffer.get(timeout=0.1)
            if result is not None:
                retrieved.append(result)

        assert len(retrieved) == len(items)
        assert [r.seed for r in retrieved] == [i.seed for i in items]


class TestImageBufferResetShutdown:
    """Tests for ImageBuffer.reset_shutdown() functionality."""

    def test_reset_shutdown_allows_put_after_shutdown(self):
        """After shutdown and reset_shutdown, put() should work again."""
        buffer = ImageBuffer(max_size=5)
        img = Image.new("RGB", (10, 10))
        item = BufferedImage(image=img, seed=42)

        # First put should work
        assert buffer.put(item) is True

        # Shutdown the buffer
        buffer.shutdown(grace_period=0.0)
        time.sleep(0.1)  # Wait for grace period to expire

        # Put should fail after shutdown grace period
        item2 = BufferedImage(image=img, seed=43)
        assert buffer.put(item2, timeout=0.1) is False

        # Reset shutdown state
        buffer.reset_shutdown()

        # Put should work again after reset
        item3 = BufferedImage(image=img, seed=44)
        assert buffer.put(item3) is True

        # Get should also work
        result = buffer.get(timeout=0.1)
        assert result is not None

    def test_reset_shutdown_allows_blocking_get(self):
        """After shutdown and reset_shutdown, get() should block waiting for items."""
        buffer = ImageBuffer(max_size=5)
        img = Image.new("RGB", (10, 10))

        # Shutdown the buffer
        buffer.shutdown(grace_period=0.0)
        time.sleep(0.1)  # Wait for grace period to expire

        # Get should return None immediately after shutdown
        result = buffer.get(timeout=0.1)
        assert result is None

        # Reset shutdown state
        buffer.reset_shutdown()

        # Now put an item and verify get() works
        item = BufferedImage(image=img, seed=42)
        buffer.put(item)
        result = buffer.get(timeout=0.1)
        assert result is not None
        assert result.seed == 42

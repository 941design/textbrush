"""Stress tests for buffer behavior under concurrent load."""

import threading
import time
from collections import Counter

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from PIL import Image

from textbrush.buffer import BufferedImage, ImageBuffer


def create_test_image(seed: int) -> BufferedImage:
    """Create BufferedImage for testing."""
    img = Image.new("RGB", (64, 64), color=(seed % 256, 0, 0))
    return BufferedImage(image=img, seed=seed)


@pytest.mark.slow
class TestBufferStress:
    """Stress tests for buffer under concurrent load."""

    @given(st.integers(min_value=5, max_value=50), st.integers(min_value=1, max_value=8))
    @settings(max_examples=10, deadline=5000)
    def test_fast_producer_slow_consumer(self, num_items, buffer_size):
        """Property: fast producer with slow consumer preserves all data without loss."""
        buffer = ImageBuffer(max_size=buffer_size)
        produced_seeds = list(range(num_items))
        consumed_seeds = []
        consumed_lock = threading.Lock()

        def fast_producer():
            for seed in produced_seeds:
                item = create_test_image(seed)
                buffer.put(item, timeout=5.0)

        def slow_consumer():
            while True:
                item = buffer.get(timeout=0.5)
                if item is None:
                    break
                time.sleep(0.001)
                with consumed_lock:
                    consumed_seeds.append(item.seed)

        producer_thread = threading.Thread(target=fast_producer)
        consumer_thread = threading.Thread(target=slow_consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join(timeout=10.0)
        assert not producer_thread.is_alive(), "Producer did not complete"

        buffer.shutdown()
        consumer_thread.join(timeout=5.0)
        assert not consumer_thread.is_alive(), "Consumer did not complete"

        assert consumed_seeds == produced_seeds, "Data loss or order violation"

    @given(st.integers(min_value=5, max_value=50), st.integers(min_value=1, max_value=8))
    @settings(max_examples=10, deadline=5000)
    def test_slow_producer_fast_consumer(self, num_items, buffer_size):
        """Property: slow producer with fast consumer completes without deadlock."""
        buffer = ImageBuffer(max_size=buffer_size)
        produced_seeds = list(range(num_items))
        consumed_seeds = []
        consumed_lock = threading.Lock()

        def slow_producer():
            for seed in produced_seeds:
                time.sleep(0.001)
                item = create_test_image(seed)
                buffer.put(item, timeout=5.0)

        def fast_consumer():
            while True:
                item = buffer.get(timeout=0.5)
                if item is None:
                    break
                with consumed_lock:
                    consumed_seeds.append(item.seed)

        producer_thread = threading.Thread(target=slow_producer)
        consumer_thread = threading.Thread(target=fast_consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join(timeout=10.0)
        assert not producer_thread.is_alive(), "Producer did not complete"

        buffer.shutdown()
        consumer_thread.join(timeout=5.0)
        assert not consumer_thread.is_alive(), "Consumer did not complete"

        assert consumed_seeds == produced_seeds, "Data loss or order violation"

    @given(
        st.integers(min_value=2, max_value=5),
        st.integers(min_value=3, max_value=15),
        st.integers(min_value=1, max_value=8),
    )
    @settings(max_examples=10, deadline=5000)
    def test_multiple_producers_single_consumer(
        self, num_producers, items_per_producer, buffer_size
    ):
        """Property: N producers and 1 consumer retrieve all items without loss."""
        buffer = ImageBuffer(max_size=buffer_size)
        produced_seeds = {}
        consumed_seeds = []
        consumed_lock = threading.Lock()

        def producer(producer_id):
            seeds = [producer_id * 1000 + i for i in range(items_per_producer)]
            produced_seeds[producer_id] = seeds
            for seed in seeds:
                item = create_test_image(seed)
                success = buffer.put(item, timeout=5.0)
                assert success, f"Producer {producer_id} failed to put item {seed}"

        def consumer():
            expected_count = num_producers * items_per_producer
            while len(consumed_seeds) < expected_count:
                item = buffer.get(timeout=1.0)
                if item is None:
                    break
                with consumed_lock:
                    consumed_seeds.append(item.seed)

        producer_threads = [
            threading.Thread(target=producer, args=(i,)) for i in range(num_producers)
        ]
        consumer_thread = threading.Thread(target=consumer)

        for t in producer_threads:
            t.start()
        consumer_thread.start()

        for t in producer_threads:
            t.join(timeout=10.0)
            assert not t.is_alive(), "Producer thread did not complete"

        buffer.shutdown()
        consumer_thread.join(timeout=5.0)
        assert not consumer_thread.is_alive(), "Consumer thread did not complete"

        all_produced = []
        for seeds in produced_seeds.values():
            all_produced.extend(seeds)

        assert Counter(consumed_seeds) == Counter(all_produced), (
            "Not all items retrieved or duplicates exist"
        )

        for producer_id in range(num_producers):
            producer_items = [s for s in consumed_seeds if s // 1000 == producer_id]
            expected_items = produced_seeds[producer_id]
            assert producer_items == expected_items, (
                f"FIFO order violated for producer {producer_id}"
            )

    @given(st.integers(min_value=20, max_value=100), st.integers(min_value=1, max_value=8))
    @settings(max_examples=10, deadline=5000)
    def test_rapid_put_get_cycles(self, num_cycles, buffer_size):
        """Property: rapid alternating put/get operations are thread-safe."""
        buffer = ImageBuffer(max_size=buffer_size)
        put_count = [0]
        get_count = [0]
        put_lock = threading.Lock()
        get_lock = threading.Lock()

        def rapid_producer():
            for i in range(num_cycles):
                item = create_test_image(i)
                success = buffer.put(item, timeout=2.0)
                if success:
                    with put_lock:
                        put_count[0] += 1

        def rapid_consumer():
            for _ in range(num_cycles):
                item = buffer.get(timeout=2.0)
                if item is not None:
                    with get_lock:
                        get_count[0] += 1

        producer_thread = threading.Thread(target=rapid_producer)
        consumer_thread = threading.Thread(target=rapid_consumer)

        producer_thread.start()
        consumer_thread.start()

        producer_thread.join(timeout=10.0)
        consumer_thread.join(timeout=10.0)

        assert not producer_thread.is_alive(), "Producer thread did not complete"
        assert not consumer_thread.is_alive(), "Consumer thread did not complete"

        assert put_count[0] == num_cycles, f"Expected {num_cycles} puts, got {put_count[0]}"
        assert get_count[0] == num_cycles, f"Expected {num_cycles} gets, got {get_count[0]}"

    @given(
        st.integers(min_value=2, max_value=4),
        st.integers(min_value=2, max_value=4),
        st.integers(min_value=10, max_value=30),
        st.integers(min_value=1, max_value=8),
    )
    @settings(max_examples=10, deadline=5000)
    def test_shutdown_under_load(
        self, num_producers, num_consumers, items_per_producer, buffer_size
    ):
        """Property: shutdown during active operations causes all threads to exit cleanly."""
        buffer = ImageBuffer(max_size=buffer_size)
        producer_exits = []
        consumer_exits = []
        exit_lock = threading.Lock()

        def producer(producer_id):
            for i in range(items_per_producer):
                item = create_test_image(producer_id * 1000 + i)
                success = buffer.put(item, timeout=5.0)
                if not success:
                    break
            with exit_lock:
                producer_exits.append(producer_id)

        def consumer(consumer_id):
            while True:
                item = buffer.get(timeout=1.0)
                if item is None:
                    break
            with exit_lock:
                consumer_exits.append(consumer_id)

        producer_threads = [
            threading.Thread(target=producer, args=(i,)) for i in range(num_producers)
        ]
        consumer_threads = [
            threading.Thread(target=consumer, args=(i,)) for i in range(num_consumers)
        ]

        for t in producer_threads + consumer_threads:
            t.start()

        time.sleep(0.1)
        buffer.shutdown()

        for t in producer_threads + consumer_threads:
            t.join(timeout=5.0)
            assert not t.is_alive(), "Thread did not exit after shutdown"

        assert len(producer_exits) == num_producers, "Not all producers exited"
        assert len(consumer_exits) == num_consumers, "Not all consumers exited"

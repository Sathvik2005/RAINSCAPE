import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep

from rainscape.cache import BoundedTTLCache


class TestBoundedTTLCache(unittest.TestCase):
    def test_simultaneous_identical_misses_are_single_flight(self):
        cache = BoundedTTLCache[int](max_entries=2, ttl_seconds=2)
        counter = [0]
        guard = Lock()

        def load():
            with guard:
                counter[0] += 1
            sleep(0.04)
            return 42

        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: cache.get_or_load(("ifs", 6), load), range(8)))
        self.assertEqual(results, [42] * 8)
        self.assertEqual(counter[0], 1)
        self.assertEqual(cache.info().hits, 7)

    def test_expiry_invalidation_eviction_and_key_separation(self):
        cache = BoundedTTLCache[str](max_entries=1, ttl_seconds=0.02)
        self.assertEqual(cache.get_or_load("a", lambda: "first"), "first")
        self.assertEqual(cache.get_or_load("b", lambda: "second"), "second")
        self.assertEqual(cache.info().evictions, 1)
        sleep(0.03)
        self.assertEqual(cache.get_or_load("b", lambda: "fresh"), "fresh")
        cache.clear()
        self.assertEqual(cache.info().entries, 0)
        self.assertEqual(cache.get_or_load("b", lambda: "after-clear"), "after-clear")

    def test_failed_loader_is_not_cached(self):
        cache = BoundedTTLCache[str]()
        with self.assertRaises(RuntimeError):
            cache.get_or_load("broken", lambda: (_ for _ in ()).throw(RuntimeError("decode failed")))
        self.assertEqual(cache.info().entries, 0)
        self.assertEqual(cache.get_or_load("broken", lambda: "recovered"), "recovered")


if __name__ == "__main__":
    unittest.main()

import sys
import weakref

import pytest
import numpy as np

from volumina.utility.cache import KVCache


class TestKVCache:
    BYTES_OVERHEAD = 33

    @pytest.fixture
    def cache(self):
        return KVCache(8192, getsizeof=sys.getsizeof)

    def get_size(self, bytes_str):
        return self.BYTES_OVERHEAD + len(bytes_str)

    def test_setting_value(self, cache):
        cache["key"] = b"test"
        assert "key" in cache
        assert b"test" == cache.get("key")

    def test_memory(self, cache):
        cache["key"] = b"test"
        assert self.get_size(b"test") == cache.currsize

    def test_memory_on_setting_same_key(self, cache):
        cache["key"] = b"test"
        cache["key"] = b"testtest"

        assert self.get_size(b"testtest") == cache.currsize

    def test_eviction(self, cache):
        for idx in range(10):
            cache[f"key{idx}"] = (b"%d" % idx) * 1000

        assert 7 * self.get_size(b"0" * 1000) == cache.currsize

        assert "key0" not in cache
        assert "key1" not in cache
        assert "key2" not in cache
        assert "key3" in cache

    def test_eviction_weakref(self, cache):
        t = weakref.WeakValueDictionary()

        for idx in range(10):
            val = np.arange(200, dtype=np.int64)
            t[f"key{idx}"] = val
            cache[f"key{idx}"] = val

        ev_msg = f"Expected eviction. Size of entry {sys.getsizeof(np.arange(200))}"

        assert "key1" not in cache, ev_msg
        assert "key2" not in cache, ev_msg
        assert "key9" in cache

        assert "key1" not in t
        assert "key9" in t

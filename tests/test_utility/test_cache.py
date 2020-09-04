import sys
import weakref

import pytest
import numpy as np

from volumina.utility.cache import KVCache


class TestKVCache:
    BYTES_OVERHEAD = 33

    @pytest.fixture
    def cache(self):
        cache = KVCache(mem_limit=8192)
        cache.register_type(bytes, lambda obj: sys.getsizeof(obj))
        cache.register_type(np.ndarray, lambda obj: sys.getsizeof(obj))
        return cache

    def get_size(self, bytes_str):
        return self.BYTES_OVERHEAD + len(bytes_str)

    def test_setting_value(self, cache):
        cache.set("key", b"test")
        assert "key" in cache
        assert b"test" == cache.get("key")

    def test_memory(self, cache):
        cache.set("key", b"test")
        assert self.get_size(b"test") == cache.used_memory

    def test_memory_on_setting_same_key(self, cache):
        cache.set("key", b"test")
        cache.set("key", b"testtest")

        assert self.get_size(b"testtest") == cache.used_memory

    def test_eviction(self, cache):
        for idx in range(10):
            cache.set(f"key{idx}", (b"%d" % idx) * 1000)

        assert 10 * self.get_size(b"0" * 1000) == cache.used_memory

        cache.clean()

        assert "key0" not in cache
        assert "key1" not in cache
        assert "key2" not in cache
        assert "key3" in cache

    def test_eviction_weakref(self, cache):
        t = weakref.WeakValueDictionary()

        for idx in range(10):
            val = np.arange(200)
            t[f"key{idx}"] = val
            cache.set(f"key{idx}", val)

        cache.clean()

        assert "key1" not in cache
        assert "key2" not in cache
        assert "key9" in cache

        assert "key1" not in t
        assert "key9" in t

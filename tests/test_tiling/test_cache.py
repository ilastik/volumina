from unittest import mock

import pytest

from volumina.tiling.cache import MultiCache, TilesCache, CachePolicy


class TestMultiCache:
    @pytest.fixture
    def policy(self):
        return CachePolicy(size=3)

    @pytest.fixture
    def cache(self, policy):
        return MultiCache("testid", policy=policy)

    def test_creation(self, policy):
        cache = MultiCache("testid", policy=policy)

    def test_uid_collision_raises(self, cache):
        cache.add("mytestid")
        with pytest.raises(Exception):
            cache.add("mytestid")

    def test_add_creates_entry_in_caches(self, cache):
        cache.add("mytestid1")
        assert "mytestid1" in cache

    def test_resize_eviction(self, cache, policy):
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")
        policy.set_size(2)

        assert "mytestid1" not in cache
        assert "mytestid2" in cache
        assert "mytestid3" in cache

    def test_displace_eviction(self, cache, policy):
        policy.set_size(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")

        assert "mytestid1" not in cache
        assert "mytestid2" in cache
        assert "mytestid3" in cache

    def test_displace_eviction(self, cache, policy):
        policy.set_size(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")

        assert "mytestid1" not in cache
        assert "mytestid2" in cache
        assert "mytestid3" in cache

    def test_displace_eviction_touch(self, cache, policy):
        policy.set_size(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.touch("mytestid1")
        cache.add("mytestid3")

        assert "mytestid2" not in cache
        assert "mytestid1" in cache
        assert "mytestid3" in cache

    def test_iteration(self, cache):
        cache.add("mytestid1")
        cache.add("mytestid2")

        keys = []
        for key in cache:
            keys.append(key)

        assert ["testid", "mytestid1", "mytestid2"] == keys


class TestCachePolicy:
    @pytest.fixture
    def cache_policy(self):
        return CachePolicy(size=3)

    def test_size(self, cache_policy):
        assert cache_policy.size == 3

    def test_chaging_size(self, cache_policy):
        cache_policy.set_size(40)
        assert cache_policy.size == 40

    def test_chaging_size_notifies(self, cache_policy):
        callback = mock.Mock()
        cache_policy.subscribe(callback)
        cache_policy.set_size(40)
        callback.assert_called_once()

    def test_setting_to_the_same_size_doesnt_trigger_callbacks(self, cache_policy):
        cache_policy.set_size(40)
        callback = mock.Mock()
        cache_policy.subscribe(callback)
        cache_policy.set_size(40)
        callback.assert_not_called()

    def test_setting_size_to_negative_value_is_not_allowed(self, cache_policy):
        with pytest.raises(ValueError):
            cache_policy.set_size(-1)

        with pytest.raises(ValueError):
            CachePolicy(size=-1)

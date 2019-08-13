import pytest

from volumina.tiling.cache import MultiCache, TilesCache


class TestMultiCache:
    @pytest.fixture
    def cache(self):
        return MultiCache("testid", maxcaches=3)

    def test_creation(self):
        cache = MultiCache("testid", maxcaches=5)

    def test_uid_collision_raises(self, cache):
        cache.add("mytestid")
        with pytest.raises(Exception):
            cache.add("mytestid")

    def test_add_creates_entry_in_caches(self, cache):
        cache.add("mytestid1")
        assert "mytestid1" in cache.caches

    def test_resize_eviction(self, cache):
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")
        cache.set_maxcaches(2)

        assert "mytestid1" not in cache.caches
        assert "mytestid2" in cache.caches
        assert "mytestid3" in cache.caches

    def test_displace_eviction(self, cache):
        cache.set_maxcaches(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")

        assert "mytestid1" not in cache.caches
        assert "mytestid2" in cache.caches
        assert "mytestid3" in cache.caches

    def test_displace_eviction(self, cache):
        cache.set_maxcaches(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.add("mytestid3")

        assert "mytestid1" not in cache.caches
        assert "mytestid2" in cache.caches
        assert "mytestid3" in cache.caches

    def test_displace_eviction_touch(self, cache):
        cache.set_maxcaches(2)
        cache.add("mytestid1")
        cache.add("mytestid2")
        cache.touch("mytestid1")
        cache.add("mytestid3")

        assert "mytestid2" not in cache.caches
        assert "mytestid1" in cache.caches
        assert "mytestid3" in cache.caches

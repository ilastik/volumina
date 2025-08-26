import sys
import threading
import time
from unittest import mock

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from qtpy.QtCore import QObject, Signal

from volumina.pixelpipeline.datasources.cachesource import CacheSource
from volumina.utility.cache import KVCache


class DummySource(QObject):
    isDirty = Signal(object)
    numberOfChannelsChanged = Signal(int)

    class _Req:
        def __init__(self, arr):
            self._result = arr

        def wait(self):
            return self._result

    def __init__(self, data):
        self._data = data
        super().__init__()

    def set_data(self, value):
        self._data = value
        self.isDirty.emit(np.s_[:])

    def request(self, slicing):
        return self._Req(self._data[slicing])


class ErrorSource(DummySource):
    class ErrorReq:
        def wait(self):
            # Lazyflow requests are single-use. If they fail first try, they are permanently failed.
            # Lazyflow persists this state in Request.exception and Request.finished,
            # but in this test it's enough to just have a request that always fails.
            raise Exception("shouldn't retry a failed request")

    def __init__(self, data):
        self.n_requests = 0
        super().__init__(data)

    def request(self, slicing):
        # Return a functioning request only on second attempt.
        self.n_requests += 1
        if self.n_requests == 1:
            return self.ErrorReq()
        return super().request(slicing)


@pytest.fixture
def raw_source():
    arr = np.arange(60).reshape(3, 4, 5)
    source = DummySource(arr)
    return mock.Mock(wraps=source)


@pytest.fixture
def cached_source(raw_source):
    return CacheSource(raw_source)


@pytest.fixture
def raw_error_source():
    arr = np.arange(60).reshape(3, 4, 5)
    source = ErrorSource(arr)
    return mock.Mock(wraps=source)


@pytest.fixture
def cached_error_source(raw_error_source):
    return CacheSource(raw_error_source)


def test_consecutive_requests_are_cached(cached_source, raw_source):
    slicing = np.s_[1:2, 2:3, 3:4]
    res0 = cached_source.request(slicing).wait()
    res1 = cached_source.request(slicing).wait()

    assert_array_equal(np.array([[[33]]]), res0)
    assert_array_equal(np.array([[[33]]]), res1)

    raw_source.request.assert_called_once_with(slicing)


def test_cache_invalidation(cached_source, raw_source):
    slicing = np.s_[2:3, 0:1, 2:3]
    res0 = cached_source.request(slicing).wait()
    res1 = cached_source.request(slicing).wait()

    assert_array_equal(np.array([[[42]]]), res0)
    assert_array_equal(np.array([[[42]]]), res1)

    raw_source.set_data(np.arange(27, 87).reshape(3, 4, 5))
    res2 = cached_source.request(slicing).wait()
    assert_array_equal(np.array([[[69]]]), res2)
    assert raw_source.request.call_count == 2


def test_cache_results_are_readonly(cached_source):
    slicing = np.s_[2:3, 0:1, 2:3]
    res = cached_source.request(slicing).wait()

    with pytest.raises(ValueError):
        res[0] = 100


def test_cache_if_value_is_too_large(raw_source):
    cached_source = CacheSource(raw_source, cache=KVCache(1, getsizeof=sys.getsizeof))
    slicing = np.s_[2:3, 0:1, 2:3]
    res0 = cached_source.request(slicing).wait()
    res1 = cached_source.request(slicing).wait()

    assert_array_equal(np.array([[[42]]]), res0)
    assert_array_equal(np.array([[[42]]]), res1)

    assert raw_source.request.call_count == 2


def test_cache_drops_errored_request(cached_error_source):
    slicing = np.s_[2:3, 0:1, 2:3]

    # First try errors
    with pytest.raises(Exception):
        cached_error_source.request(slicing).wait()

    # Second try should work
    res = cached_error_source.request(slicing).wait()

    assert_array_equal(np.array([[[42]]]), res)


class RaceDetectingCache(KVCache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._set_calls = 0
        self._setting = False

    def __setitem__(self, key, value):
        if self._setting:
            raise RuntimeError("Caught attempt to concurrently modify cache.")

        self._setting = True
        try:
            time.sleep(0.05)  # Ensures threads don't avoid concurrency simply by being too fast
            super().__setitem__(key, value)
        finally:
            self._setting = False
            self._set_calls += 1


def test_cache_not_written_concurrently(monkeypatch, cached_source):
    def delay_wait():
        """Prevents thread 1 from finishing and setting req._result before
        thread 2 gets to checking `_result is None` in req.wait"""
        time.sleep(0.05)
        return np.array([[[42]]])

    slicing = np.s_[2:3, 0:1, 2:3]
    req = cached_source.request(slicing)
    monkeypatch.setattr(cached_source, "_cache", RaceDetectingCache(1000, getsizeof=sys.getsizeof))
    monkeypatch.setattr(req._rq, "wait", delay_wait)

    def await_req():
        try:
            req.wait()
        except Exception as e:
            exceptions.append(e)

    exceptions = []
    thread1 = threading.Thread(target=await_req)
    thread2 = threading.Thread(target=await_req)
    thread1.start()
    thread2.start()
    thread1.join()
    thread2.join()

    assert not exceptions
    assert cached_source._cache._set_calls == 2, "cache.__setitem__ must be called by both threads to test concurrency"

import sys
from unittest import mock

import numpy as np
import pytest
from numpy.testing import assert_array_equal
from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.datasources.cachesource import CacheSource
from volumina.utility.cache import KVCache


class DummySource(QObject):
    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)

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


@pytest.fixture
def raw_source():
    arr = np.arange(60).reshape(3, 4, 5)
    source = DummySource(arr)
    return mock.Mock(wraps=source)


@pytest.fixture
def cached_source(raw_source):
    return CacheSource(raw_source)


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

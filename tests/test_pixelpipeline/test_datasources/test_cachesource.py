import pytest
from unittest import mock

import numpy as np
from numpy.testing import assert_array_equal
from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.datasources.cachesource import CacheSource


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


class TestCacheSource:
    @pytest.fixture
    def orig_source(self):
        arr = np.arange(27).reshape(3, 3, 3)
        source = DummySource(arr)
        return mock.Mock(wraps=source)

    @pytest.fixture
    def cached_source(self, orig_source):
        return CacheSource(orig_source)

    def test_consecutive_requests_are_cached(self, cached_source, orig_source):
        slicing = np.s_[1:2, 1:2, 1:2]
        res0 = cached_source.request(slicing).wait()
        res1 = cached_source.request(slicing).wait()

        assert_array_equal(np.array([[[13]]]), res0)
        assert_array_equal(np.array([[[13]]]), res1)

        orig_source.request.assert_called_once_with(slicing)

    def test_cache_invalidation(self, cached_source, orig_source):
        slicing = np.s_[1:2, 1:2, 1:2]
        res0 = cached_source.request(slicing).wait()
        res1 = cached_source.request(slicing).wait()

        assert_array_equal(np.array([[[13]]]), res0)
        assert_array_equal(np.array([[[13]]]), res1)

        orig_source.set_data(np.arange(27, 54).reshape(3, 3, 3))
        res2 = cached_source.request(slicing).wait()
        assert_array_equal(np.array([[[40]]]), res2)
        assert orig_source.request.call_count == 2

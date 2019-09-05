import threading

from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.interface import DataSourceABC
from volumina.slicingtools import is_pure_slicing
from volumina.utility.cache import KVCache


class _Request:
    def __init__(self, cached_source, slicing, key):
        self._cached_source = cached_source
        self._slicing = slicing
        self._key = key
        self._result = None
        self._rq = self._cached_source._source.request(self._slicing)

    def wait(self):
        if self._result is None:
            self._result = res = self._rq.wait()
            self._cached_source._cache.set(self._key, res)
            self._cached_source._req.pop(self._key, None)

        return self._result

    def cancel(self):
        self._rq.cancel()


class _CachedRequest:
    def __init__(self, result):
        self._result = result

    def wait(self):
        return self._result

    def cancel(self):
        pass


class CacheSource(QObject, DataSourceABC):
    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)

    def __init__(self, source):
        super().__init__()
        self._lock = threading.Lock()

        self._source = source
        self._cache = KVCache()
        self._req = {}
        self._source.isDirty.connect(self.isDirty)
        self._source.numberOfChannelsChanged.connect(self.numberOfChannelsChanged)
        self._source.isDirty.connect(self.clear)
        self._source.numberOfChannelsChanged.connect(self.clear)

    def clear(self, *args):
        self._cache.clear()
        self._req.clear()

    def cache_key(self, slicing):
        parts = []

        for el in slicing:
            _, key_part = el.__reduce__()
            parts.append(key_part)

        return "::".join(str(p) for p in parts)

    def request(self, slicing):
        key = self.cache_key(slicing)

        with self._lock:
            if key in self._cache:
                return _CachedRequest(self._cache.get(key))

            else:
                if key not in self._req:
                    self._req[key] = _Request(self, slicing, key)

                return self._req[key]

    def __getattr__(self, attr):
        return getattr(self._source, attr)

    def setDirty(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        self.isDirty.emit(slicing)

    @property
    def numberOfChannels(self):
        return self._source.numberOfChannels

    def __repr__(self):
        return f"<CachedSource({self._source})>"

    def __eq__(self, other):
        if other is None:
            return False
        return self._source is other._source

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._source)

    def dtype(self):
        return self._source.dtype()

    def clean_up(self):
        self._cache.clear()
        self._source.clean_up()

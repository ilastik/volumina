import logging
import threading
import sys
import uuid
from typing import Union

from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.interface import DataSourceABC
from volumina.slicingtools import is_pure_slicing
from volumina.utility.cache import KVCache
from volumina.config import CONFIG

logger = logging.getLogger(__name__)


ARRAY_CACHE = KVCache(CONFIG.cache_size, getsizeof=sys.getsizeof)


class _Request:
    def __init__(self, cached_source: "CacheSource", slicing, key):
        self._cached_source = cached_source
        self._slicing = slicing
        self._key = key
        self._result = None
        self._rq = self._cached_source._source.request(self._slicing)

    def wait(self):
        if self._result is not None:
            return self._result

        try:
            res = self._rq.wait()

            self._result = cached_copy = res.copy()
            cached_copy.setflags(write=False)

            with self._cached_source._lock:
                try:
                    self._cached_source._cache[self._key] = cached_copy
                except ValueError:
                    logger.warning(
                        "Value too large, skipping cache; cache_size: %s, value size: %s",
                        self._cached_source._cache.maxsize,
                        self._cached_source._cache.getsizeof(cached_copy),
                    )
        finally:
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

    def __init__(self, source: "LazyflowSource", cache=ARRAY_CACHE):
        super().__init__()
        self._lock = threading.Lock()

        self._uniqueid = uuid.uuid4()  # id(self) wasn't unique enough
        self._source = source
        self._cache = cache
        self._req = {}
        self._source.isDirty.connect(self.isDirty)
        self._source.numberOfChannelsChanged.connect(self.numberOfChannelsChanged)
        self._source.isDirty.connect(self.clear)
        self._source.numberOfChannelsChanged.connect(self.clear)

    def clear(self, *args):
        self._cache.clear()
        self._req.clear()

    def __cache_key(self, slicing):
        parts = [self._uniqueid]

        for el in slicing:
            _, key_part = el.__reduce__()
            parts.append(key_part)

        return "::".join(str(p) for p in parts)

    def request(self, slicing) -> Union[_CachedRequest, _Request]:
        key = self.__cache_key(slicing)

        with self._lock:
            result = self._cache.get(key)
            if result is not None:
                return _CachedRequest(result)

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
        return f"<CachedSource(id:{id(self)}, source:{self._source!r})>"

    def __eq__(self, other):
        if other is None:
            return False
        return self._source is getattr(other, "_source", None)

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash(self._source)

    def dtype(self):
        return self._source.dtype()

    def clean_up(self):
        self._cache.clear()
        self._source.clean_up()

import abc
import sys
import threading
from collections import OrderedDict
from typing import NamedTuple, Dict, Any, Type, TypeVar, Callable

import numpy as np


T = TypeVar("T")
_256_MB = 256 * 1024 * 1024


class CacheABC(abc.ABC):
    @abc.abstractmethod
    def get(self, key: str, default=None) -> Any:
        ...

    @abc.abstractmethod
    def set(self, key: str, value: Any) -> Any:
        ...

    @abc.abstractmethod
    def delete(self, key: str) -> None:
        ...

    @abc.abstractmethod
    def touch(self, key: str) -> None:
        ...

    @abc.abstractmethod
    def __contains__(self, key: str) -> bool:
        ...


class KVCache(CacheABC):
    _MISSING = object()
    _cachable_types: Dict[T, Callable[[T], int]] = {}

    class _Entry(NamedTuple):
        obj: Any
        size: int  # bytes

    def __init__(self, mem_limit=_256_MB):
        self._cache = OrderedDict()
        self._mem_limit = mem_limit
        self._mem = 0
        self._lock = threading.RLock()

    def get(self, key: str, default=None) -> Any:
        with self._lock:
            entry = self._cache.get(key, self._MISSING)
            self._cache.move_to_end(key)

        if entry is not self._MISSING:
            return entry.obj
        else:
            return default

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def keys(self):
        return list(self._cache.keys())

    def set(self, key, value) -> None:
        with self._lock:
            old_entry = self._cache.get(key)

            if old_entry is not None:
                self._mem -= old_entry.size

            get_size_fn = self._cachable_types.get(type(value))
            if get_size_fn is None:
                raise ValueError(f"Unknown type {type(value)}")

            size = get_size_fn(value)
            self._mem += size
            self._cache[key] = self._Entry(value, size)
            self._cache.move_to_end(key)

    def __contains__(self, key) -> bool:
        return key in self._cache

    def __len__(self):
        return len(self._cache)

    def touch(self, key: str) -> None:
        with self._lock:
            self._cache.move_to_end(key)

    @classmethod
    def register_type(cls, _type: Type[T]):
        def _register(get_size_fn: Callable[[T], int]):
            cls._cachable_types[_type] = get_size_fn

        return _register

    @property
    def used_memory(self) -> int:
        return self._mem

    def clean(self) -> None:
        with self._lock:
            while self._mem > self._mem_limit:
                key, entry = next(iter(self._cache.items()))
                del self._cache[key]
                self._mem -= entry.size

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._mem = 0


@KVCache.register_type(np.ndarray)
def _get_size_of_ndarray(arr: np.ndarray) -> int:
    return sys.getsizeof(arr)

from cachetools import LRUCache


class KVCache(LRUCache):
    def __repr__(self):
        return "%s(%r, maxsize=%r, currsize=%r)" % (
            self.__class__.__name__,
            len(self.__data.items()),
            self.__maxsize,
            self.__currsize,
        )

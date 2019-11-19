from cachetools import LRUCache


class KVCache(LRUCache):
    def __repr__(self):
        return "%s(maxsize=%r, currsize=%r)" % (self.__class__.__name__, self.maxsize, self.currsize)

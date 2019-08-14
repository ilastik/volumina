import threading
import warnings
import logging
from collections import OrderedDict, defaultdict

import numpy
from PyQt5.QtWidgets import QGraphicsItem

logger = logging.getLogger()

__all__ = ["TilesCache"]


class CachePolicy:
    def __init__(self, size):
        self._validate_size(size)
        self._size = size
        self._subsribers = []

    @property
    def size(self):
        return self._size

    def _validate_size(self, value):
        if not isinstance(value, int) or value <= 0:
            raise ValueError("size should non negative integer")

    def set_size(self, value):
        if self._size == value:
            return

        self._validate_size(value)

        self._size = value

        for sub in self._subsribers:
            sub()

    def subscribe(self, fn):
        self._subsribers.append(fn)

    def unsubsribe(self, fn):
        try:
            self._subsribers.remove(fn)
        except ValueError:
            pass


class MultiCache:
    """
    A utility class for caching items in a of a dict-of-dicts
    """

    def __init__(self, first_uid, default_factory=lambda: None, policy=None):
        self._policy = policy
        self._policy.subscribe(self._clean)
        self._caches = OrderedDict()
        self._default_factory = default_factory
        self.add(first_uid)

    def add(self, uid) -> None:
        if uid not in self._caches:
            cache = defaultdict(self._default_factory)
            self._caches[uid] = cache
        else:
            raise Exception("MultiCache.add: uid %s is already in use" % str(uid))

        # remove oldest cache, if necessary
        self._clean()

    def __contains__(self, key):
        return key in self._caches

    def __getitem__(self, key):
        return self._caches[key]

    def __iter__(self):
        return iter(self._caches)

    def __len__(self):
        return len(self._caches)

    def touch(self, uid):
        self._caches.move_to_end(uid)

    @property
    def maxsize(self):
        return self._policy.size

    def _evict_one(self):
        self._caches.popitem(last=False)  # removes item in FIFO order

    def _clean(self):
        while len(self._caches) > self.maxsize:
            self._evict_one()


class TilesCache:
    """
    Contains the following caches, with convenience accessor functions for each.

        layerCache: A cache of 'layers', i.e. for every patch a QImage or QGraphicsItem
                    for every "image source" in the stack

        tileCache: A cache of 'tiles', i.e. the blended QImage objects
                   that were created by combining all QImage layers from layerCache for a given patch.
                   (The QGraphicsItem layers do not contribute to the composite tiles in the tileCache.
                   They are merely stored.)

        layerCacheDirty: A cache of dirty bits for all layers in layerCache
        layerCacheTimestamp: A cache of timestamps to track how recently each layer was needed.

        tileCacheDirty: A cache of dirty bits for the composite tiles
                        (i.e. for a given patch, if a single layer in the patch
                        is dirty, then the tile for that patch is dirty)
    """

    def __init__(self, first_stack_id, sims, maxstacks):
        self._lock = threading.Lock()
        self._sims = sims
        self._maxstacks = maxstacks
        self._policy = CachePolicy(maxstacks)

        kwargs = {"first_uid": first_stack_id, "policy": self._policy}

        # [stack_id][tile_id] -> QImage or QGraphicsItem
        self._tileCache = MultiCache(default_factory=lambda: (None, 0.0), **kwargs)

        # [stack_id][tile_id] -> bool
        self._tileCacheDirty = MultiCache(default_factory=lambda: True, **kwargs)

        # [stack_id][(ims, tile_id)] -> QImage or QGraphicsItem
        self._layerCache = MultiCache(**kwargs)

        # [stack_id][(ims, tile_id)] -> bool
        self._layerCacheDirty = MultiCache(default_factory=lambda: True, **kwargs)

        # [stack_id][(ims, tile_id)] -> float
        self._layerCacheTimestamp = MultiCache(default_factory=float, **kwargs)

    @property
    def maxstacks(self):
        return self._maxstacks

    def set_maxstacks(self, maxstacks):
        self._policy.set_size(maxstacks)

    def __enter__(self):
        self._lock.acquire()
        return self

    def __exit__(self, *args):
        assert self._lock.locked()
        self._lock.release()

    def __contains__(self, stack_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return stack_id in self._tileCache

    def __len__(self):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return len(self._tileCache)

    def tile(self, stack_id, tile_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._tileCache[stack_id][tile_id]

    def setTile(self, stack_id, tile_id, img, stack_visible, stack_occluded):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        progress = 1.0

        if len(stack_visible) > 0:
            visible = numpy.asarray(stack_visible)
            occluded = numpy.asarray(stack_occluded)
            visibleAndNotOccluded = numpy.logical_and(visible, numpy.logical_not(occluded))

            if visibleAndNotOccluded.any():
                dirty = numpy.asarray(
                    [self._layerCacheDirty[stack_id][(ims, tile_id)] for ims in self._sims.viewImageSources()]
                )
                num = numpy.count_nonzero(numpy.logical_and(dirty, visibleAndNotOccluded) == True)
                denom = float(numpy.count_nonzero(visibleAndNotOccluded))
                progress = 1.0 - num / denom

        self._tileCache[stack_id][tile_id] = (img, progress)

    def tileDirty(self, stack_id, tile_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._tileCacheDirty[stack_id][tile_id]

    def setTileDirty(self, stack_id, tile_id, b):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCacheDirty[stack_id][tile_id] = b

    def setTileDirtyAllStacks(self, tile_id, b):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._tileCacheDirty:
            self._tileCacheDirty[stack_id][tile_id] = b

    def graphicsitem_layers(self, stack_id, tile_id):
        """
        Return a list of the 'layers' in the cache that are of type QGraphicsItem.
        Unlike the QImage layers, the QGraphicsItem layers are not composited into the 'tile'.
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."

        warnings.warn(
            "FIXME: This is a slow way to look for the items we want.\n"
            "TilesCache._layerCache should be a dict-of-dict-of-dict for faster lookup!"
        )
        qgraphicsitems = []
        for (layer_id, t_id), img in self._layerCache[stack_id].items():
            if t_id == tile_id and isinstance(img, QGraphicsItem):
                qgraphicsitems.append(img)
        return qgraphicsitems

    def setAllTilesDirty(self):
        """
        Mark all tiles in all stacks as dirty.
        For speed, this is done by simply deleting all entries
        (by default missing entries are considered dirty).
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._tileCacheDirty:
            self._tileCacheDirty[stack_id].clear()

    def layerTile(self, stack_id, layer_id, tile_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCache[stack_id][(layer_id, tile_id)]

    def layerTileDirty(self, stack_id, layer_id, tile_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCacheDirty[stack_id][(layer_id, tile_id)]

    def setLayerTileDirtyAllStacks(self, layer_id, tile_id, b):
        """
        Mark the given tile as dirty in all stacks.
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._layerCacheDirty:
            self._layerCacheDirty[stack_id][(layer_id, tile_id)] = b

    def setLayerTilesDirty(self, layer_id):
        """
        For a given layer, marks all tiles in all stacks as dirty.
        This is achieved by simply deleting all tiles for the given
            layer (by default, missing entries are dirty)
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._layerCacheDirty:
            dirty_entries = [
                (l_id, t_id) for (l_id, t_id) in list(self._layerCacheDirty[stack_id].keys()) if l_id == layer_id
            ]
            # dirty_entries = filter( lambda (l_id, t_id): l_id == layer_id, self._layerCacheDirty[stack_id].keys() )
            for entry in dirty_entries:
                del self._layerCacheDirty[stack_id][entry]

    def layerTileTimestamp(self, stack_id, layer_id, tile_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCacheTimestamp[stack_id][(layer_id, tile_id)]

    def addStack(self, stack_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCache.add(stack_id)
        self._tileCacheDirty.add(stack_id)
        self._layerCache.add(stack_id)
        self._layerCacheDirty.add(stack_id)
        self._layerCacheTimestamp.add(stack_id)

    def touchStack(self, stack_id):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCache.touch(stack_id)
        self._tileCacheDirty.touch(stack_id)
        self._layerCache.touch(stack_id)
        self._layerCacheDirty.touch(stack_id)
        self._layerCacheTimestamp.touch(stack_id)

    def updateTileIfNecessary(self, stack_id, layer_id, tile_id, req_timestamp, img):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        if req_timestamp > self._layerCacheTimestamp[stack_id][(layer_id, tile_id)]:
            self._layerCache[stack_id][(layer_id, tile_id)] = img
            self._layerCacheDirty[stack_id][(layer_id, tile_id)] = False
            self._layerCacheTimestamp[stack_id][(layer_id, tile_id)] = req_timestamp

            # FIXME: We are currently keeping track of only 1 dirty bit.
            #        It is set if any layer in the tile is dirty, regardless of
            #        whether or not that layer is a QImage or QGraphicsItem
            #        This means that when a QGraphicsItem becomes dirty, the
            #        layer stack is re-blended.  It's a waste of time, because
            #        none of the raster layers changed (they were all clean and
            #        haven't changed since the last time the tile was blended.)
            #        We could fix this inefficiency by tracking 2 dirty bits, for
            #        QImage layers and QGraphicsLayers, respectively, and checking
            #        those bits in _blendTile()
            self._tileCacheDirty[stack_id][tile_id] = True

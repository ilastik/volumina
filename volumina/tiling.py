###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#		   http://ilastik.org/license/
###############################################################################
#Python
import sys
import time
import collections
import threading
from collections import defaultdict, OrderedDict
from contextlib import contextmanager
from functools import partial
import warnings

#SciPy
import numpy

#PyQt
from PyQt4.QtCore import QRect, QRectF, QMutex, QObject, pyqtSignal
from PyQt4.QtGui import QImage, QPainter, QTransform, QGraphicsItem

#volumina
from patchAccessor import PatchAccessor
import volumina
from volumina.pixelpipeline.asyncabcs import IndeterminateRequestError
from volumina.utility import log_exception, PrioritizedThreadPoolExecutor

import logging
logger = logging.getLogger(__name__)

# If lazyflow is installed, use that threadpool.
try:
    from lazyflow.request import Request
    USE_LAZYFLOW_THREADPOOL = True
except ImportError:
    USE_LAZYFLOW_THREADPOOL = False

def submit_to_threadpool(fn, priority):
    if USE_LAZYFLOW_THREADPOOL:
        # Tiling requests are less prioritized than most requests.
        root_priority = [1] + list(priority)
        req = Request(fn, root_priority)
        req.submit()
    else:
        get_render_pool().submit(fn, priority)

renderer_pool = None
def get_render_pool():
    """
    Return the global thread pool for requesting layer data from ImageSource objects.
    (Create it first if necessary.)
    """
    global renderer_pool
    if renderer_pool is None:
        renderer_pool = PrioritizedThreadPoolExecutor(6)
    return renderer_pool


@contextmanager
def TileTimer():
    result = TileTime()
    start = time.time()
    try:
        yield result
    finally:
        result.seconds = time.time() - start

class TileTime(object):
    seconds = 0.0

class Tiling(object):
    """
    Describes the geometry of a tiling, for easy access
    to patch rects, overall shape, tile size, and data2scene transform.
    """

    def __init__(self, sliceShape, data2scene=QTransform(),
                 blockSize=512, overlap=0, overlap_draw=1e-3,
                 name="Unnamed Tiling"):
        """
        Args:
            sliceShape -- (width, height)
            data2scene -- QTransform from data to image coordinates (default:
                          identity transform)
            blockSize  -- base tile size: blockSize x blockSize (default 256)
            overlap    -- overlap between tiles positive number prevents rendering
                          artifacts between tiles for certain zoom levels (default 1)
        """
        self.blockSize = blockSize
        self.overlap = overlap
        self._patchAccessor = PatchAccessor(sliceShape[0],
                                            sliceShape[1],
                                            blockSize=self.blockSize)
        self._overlap_draw = overlap_draw
        self._overlap = overlap

        numPatches = self._patchAccessor.patchCount

        self.imageRectFs = [None]*numPatches
        self.dataRectFs  = [None]*numPatches
        self.tileRectFs  = [None]*numPatches
        self.imageRects  = [None]*numPatches
        self.dataRects   = [None]*numPatches
        self.tileRects   = [None]*numPatches
        self.sliceShape  = sliceShape
        self.name = name
        self.data2scene = data2scene

    @property
    def data2scene(self):
        return self._data2scene

    @data2scene.setter
    def data2scene(self, data2scene):
        self._data2scene = data2scene
        self.scene2data, isInvertible = data2scene.inverted()
        assert isInvertible

        for patchNr in range(self._patchAccessor.patchCount):
            # the patch accessor uses the data coordinate system.
            # because the patch is drawn on the screen, its holds coordinates
            # corresponding to Qt's QGraphicsScene's system, which need to be
            # converted to scene coordinates

            # the image rectangle includes an overlap margin
            imageRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, self.overlap))

            # the patch rectangle has per default no overlap
            patchRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, 0))

            # add a little overlap when the overlap_draw setting is
            # activated
            if self._overlap_draw != 0:
                patchRectF = QRectF(patchRectF.x() - self._overlap_draw,
                                    patchRectF.y() - self._overlap_draw,
                                    patchRectF.width() + 2 * self._overlap_draw,
                                    patchRectF.height() + 2 * self._overlap_draw)

            patchRect = QRect(round(patchRectF.x()),
                              round(patchRectF.y()),
                              round(patchRectF.width()),
                              round(patchRectF.height()))

            # the image rectangles of neighboring patches can overlap
            # slightly, to account for inaccuracies in sub-pixel
            # rendering of many ImagePatch objects
            imageRect = QRect(round(imageRectF.x()),
                              round(imageRectF.y()),
                              round(imageRectF.width()),
                              round(imageRectF.height()))

            self.imageRectFs[patchNr] = imageRectF
            self.dataRectFs[ patchNr] = imageRectF
            self.tileRectFs[ patchNr] = patchRectF
            self.imageRects[ patchNr] = imageRect
            self.tileRects[  patchNr] = patchRect


    def boundingRectF(self):
        if self.tileRectFs:
            p = self.tileRectFs[-1]
            br = QRectF(0,0, p.x()+p.width(), p.y()+p.height())
        else:
            br = QRectF(0,0,0,0)
        return br

    def containsF(self, point):
        for i, p in enumerate(self.tileRectFs):
            if p.contains(point):
                return i

    def intersected(self, sceneRect):
        if not sceneRect.isValid():
            return range(len(self.tileRects))

        # Patch accessor uses data coordinates
        rect = self.data2scene.inverted()[0].mapRect(sceneRect)
        patchNumbers = self._patchAccessor.getPatchesForRect(
                            rect.topLeft().x(), rect.topLeft().y(),
                            rect.bottomRight().x(), rect.bottomRight().y() )
        return patchNumbers

    def __len__(self):
        return len(self.imageRectFs)

class _MultiCache( object ):
    """
    A utility class for caching items in a of a dict-of-dicts
    """
    def __init__( self, first_uid, default_factory=lambda:None, maxcaches=None ):
        self._maxcaches = maxcaches
        self.caches = OrderedDict()
        self.add( first_uid, default_factory=default_factory)

    def add( self, uid, default_factory=lambda:None ):
        assert isinstance(uid[1], tuple)
        if uid not in self.caches:
            cache = defaultdict(default_factory)
            self.caches[uid] = cache
        else:
            raise Exception('MultiCache.add: uid %s is already in use' % str(uid))

        # remove oldest cache, if necessary
        old_uid = None
        if self._maxcaches and len(self.caches) > self._maxcaches:
            old_uid, v = self.caches.popitem(False) # removes item in FIFO order
        return old_uid

    def touch( self, uid ):
        c = self.caches[uid]
        del self.caches[uid]
        self.caches[uid] = c

    def set_maxcaches(self, newmax):
        self._maxcaches = newmax
        while len(self.caches) > self._maxcaches:
            old_uid, v = self.caches.popitem(False) # removes item in FIFO order

class _TilesCache( object ):
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
    def __init__(self, first_stack_id, sims, maxstacks=None):
        self._lock = threading.Lock()
        self._sims = sims
        self._maxstacks = maxstacks

        kwargs = {'first_uid' : first_stack_id,
                  'maxcaches' : maxstacks}
        
        # [stack_id][tile_id] -> QImage or QGraphicsItem
        self._tileCache = _MultiCache(default_factory=lambda: (None, 0.), **kwargs)

        # [stack_id][tile_id] -> bool
        self._tileCacheDirty = _MultiCache(default_factory=lambda: True, **kwargs)
        
        # [stack_id][(ims, tile_id)] -> QImage or QGraphicsItem
        self._layerCache = _MultiCache(**kwargs)
        
        # [stack_id][(ims, tile_id)] -> bool
        self._layerCacheDirty = _MultiCache(default_factory=lambda: True, **kwargs)
        
        # [stack_id][(ims, tile_id)] -> float
        self._layerCacheTimestamp = _MultiCache(default_factory=float, **kwargs)
        

    @property
    def maxstacks(self):
        return self._maxstacks
    
    def set_maxstacks(self, maxstacks):
        if self._maxstacks == maxstacks:
            return
        self._maxstacks = maxstacks
        self._tileCache.set_maxcaches(self._maxstacks)
        self._tileCacheDirty.set_maxcaches(self._maxstacks)
        self._layerCache.set_maxcaches(self._maxstacks)
        self._layerCacheDirty.set_maxcaches(self._maxstacks)
        self._layerCacheTimestamp.set_maxcaches(self._maxstacks)

    def __enter__(self):
        self._lock.acquire()
        return self
    
    def __exit__(self, *args):
        assert self._lock.locked()
        self._lock.release()

    def __contains__( self, stack_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return stack_id in self._tileCache.caches

    def __len__( self ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return len(self._tileCache.caches)

    def tile( self, stack_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._tileCache.caches[stack_id][tile_id]

    def setTile( self, stack_id, tile_id, img, stack_visible, stack_occluded ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        if len(stack_visible) > 0:
            visible = numpy.asarray(stack_visible)
            occluded = numpy.asarray(stack_occluded)
            visibleAndNotOccluded = numpy.logical_and(visible, numpy.logical_not(occluded))
            if visibleAndNotOccluded.any():
                dirty = numpy.asarray([self._layerCacheDirty.caches[stack_id][(ims, tile_id)]
                                       for ims in self._sims.viewImageSources()])
                num = numpy.count_nonzero(numpy.logical_and(dirty, visibleAndNotOccluded) == True)
                denom = float(numpy.count_nonzero(visibleAndNotOccluded))
                progress = 1.0 - num / denom
            else:
                progress = 1.0
        else:
            progress = 1.0
        self._tileCache.caches[stack_id][tile_id] = (img, progress)

    def tileDirty( self, stack_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._tileCacheDirty.caches[stack_id][tile_id]

    def setTileDirty( self, stack_id, tile_id, b):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCacheDirty.caches[stack_id][tile_id] = b

    def setTileDirtyAllStacks( self, tile_id, b):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._tileCacheDirty.caches:
            self._tileCacheDirty.caches[stack_id][tile_id] = b

    def graphicsitem_layers(self, stack_id, tile_id):
        """
        Return a list of the 'layers' in the cache that are of type QGraphicsItem.
        Unlike the QImage layers, the QGraphicsItem layers are not composited into the 'tile'. 
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."

        warnings.warn("FIXME: This is a slow way to look for the items we want.\n"
                      "_TilesCache._layerCache should be a dict-of-dict-of-dict for faster lookup!")
        qgraphicsitems = []
        for (layer_id, t_id), img in self._layerCache.caches[stack_id].iteritems():
            if t_id == tile_id and isinstance(img, QGraphicsItem):
                qgraphicsitems.append(img)
        return qgraphicsitems

    def setAllTilesDirty( self ):
        """
        Mark all tiles in all stacks as dirty.
        For speed, this is done by simply deleting all entries 
        (by default missing entries are considered dirty).
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._tileCacheDirty.caches:
            self._tileCacheDirty.caches[stack_id].clear()

    def layer(self, stack_id, layer_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCache.caches[stack_id][(layer_id,tile_id)]

    def layerDirty(self, stack_id, layer_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)]

    def setLayerDirtyAllStacks( self, layer_id, tile_id, b ):
        """
        Mark the given tile as dirty in all stacks.
        """
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._layerCacheDirty.caches:
            self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = b

    def setLayerDirtyAllTiles(self, layer_id):
        """
        For a given layer, marks all tiles in all stacks as dirty.
        This is achieved by simply deleting all tiles for the given 
            layer (by default, missing entries are dirty)
        """ 
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        for stack_id in self._layerCacheDirty.caches:
            dirty_entries = [(l_id, t_id) for (l_id, t_id) in self._layerCacheDirty.caches[stack_id].keys() if l_id == layer_id]
            #dirty_entries = filter( lambda (l_id, t_id): l_id == layer_id, self._layerCacheDirty.caches[stack_id].keys() )
            for entry in dirty_entries:
                del self._layerCacheDirty.caches[stack_id][entry]

    def layerTimestamp(self, stack_id, layer_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)]

    def addStack( self, stack_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCache.add( stack_id )
        self._tileCacheDirty.add( stack_id, default_factory=lambda:True )
        self._layerCache.add( stack_id )
        self._layerCacheDirty.add( stack_id, default_factory=lambda:True )
        self._layerCacheTimestamp.add( stack_id, default_factory=float )


    def touchStack( self, stack_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._tileCache.touch( stack_id )
        self._tileCacheDirty.touch( stack_id )
        self._layerCache.touch( stack_id )
        self._layerCacheDirty.touch( stack_id )
        self._layerCacheTimestamp.touch( stack_id )


    def updateTileIfNecessary( self, stack_id, layer_id, tile_id, req_timestamp, img):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        if req_timestamp > self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)]:
            self._layerCache.caches[stack_id][(layer_id, tile_id)] = img
            self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = False
            self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)] = req_timestamp
            
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
            self._tileCacheDirty.caches[stack_id][tile_id] = True


class TileProvider( QObject ):
    """
    Note: Throughout this class, the terms 'layer', 'ImageSource', and 'ims' are used interchangeably.
    """
    
    Tile = collections.namedtuple('Tile', ['id',             # tile number
                                           'qimg',           # composited tile as a QImage
                                           'qgraphicsitems', # list of QGraphicsItems to be displayed over the tile
                                           'rectF',          # The patch dimensions (see Tiling class, above)
                                           'progress'])      # How 'complete' the composite tile is
                                                             # (depending on how many layers are still dirty)
    
    sceneRectChanged = pyqtSignal( QRectF )

    @property
    def axesSwapped(self):
        return self._axesSwapped

    @axesSwapped.setter
    def axesSwapped(self, value):
        self._axesSwapped = value

    def __init__( self, tiling, stackedImageSources, cache_size=100,
                  request_queue_size=100000, n_threads=2,
                  parent=None ):
        """
        Keyword Arguments:
        cache_size                -- maximal number of encountered stacks
                                     to cache, i.e. slices if the imagesources
                                     draw from slicesources (default 10)
        request_queue_size        -- maximal number of request to queue up (default 100000)
        n_threads                 -- maximal number of request threads; this determines the
                                     maximal number of simultaneously running requests
                                     to the pixelpipeline (default: 2)
        parent                    -- QObject
    
        """
    
        QObject.__init__( self, parent = parent )

        self.tiling = tiling
        self.axesSwapped = False
        self._sims = stackedImageSources
        self._request_queue_size = request_queue_size
        self._n_threads = n_threads

        self._current_stack_id = self._sims.stackId
        self._cache = _TilesCache(self._current_stack_id, self._sims,
                                  maxstacks=cache_size)

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.sizeChanged.connect(self._onSizeChanged)
        self._sims.orderChanged.connect(self._onOrderChanged)
        self._sims.stackIdChanged.connect(self._onStackIdChanged)

        self._keepRendering = True
    
    @property
    def cache_size(self):
        return self._cache.maxstacks
    
    def set_cache_size(self, new_size):
        self._cache.set_maxstacks(new_size)

    def getTiles( self, rectF ):
        '''Get tiles in rect and request a refresh.

        Returns tiles intersecting with rectF immediately and requests
        a refresh of these tiles. Next time you call this function the
        tiles may be already (partially) updated. If you want to wait
        until the rendering is fully complete, call join().

        '''
        self.requestRefresh( rectF )
        tile_nos = self.tiling.intersected( rectF )
        stack_id = self._current_stack_id
        
        for tile_no in tile_nos:
            with self._cache:
                qimg, progress = self._cache.tile(stack_id, tile_no)
                qgraphicsitems = self._cache.graphicsitem_layers(stack_id, tile_no)
            yield TileProvider.Tile(
                tile_no,
                qimg,
                qgraphicsitems,
                QRectF(self.tiling.imageRects[tile_no]),
                progress)

    def waitForTiles(self, rectF=QRectF()):
        """
        This function is for testing purposes only.
        Block until all tiles intersecting the given rect are complete.
        """
        finished = False
        while not finished:
            finished = True
            tiles = self.getTiles(rectF)
            for tile in tiles:
                finished &= tile.progress >= 1.0

    def requestRefresh( self, rectF, stack_id=None, prefetch=False, layer_indexes=None ):
        '''Requests tiles to be refreshed.

        Returns immediately. Call join() to wait for
        the end of the rendering.

        '''
        stack_id = stack_id or self._current_stack_id
        tile_nos = self.tiling.intersected( rectF )
        for tile_no in tile_nos:
            self._refreshTile( stack_id, tile_no, prefetch, layer_indexes )

    def prefetch( self, rectF, through, layer_indexes=None ):
        '''Request fetching of tiles in advance.

        Returns immediately. Prefetch will commence after all regular
        tiles are refreshed (see requestRefresh() and getTiles() ).
        The prefetch is reset when the 'through' value of the slicing
        changes. Several calls to prefetch are handeled in Fifo
        order.

        '''
        if self.cache_size == 0:
            return

        stack_id = (self._current_stack_id[0], tuple(enumerate(through)))
        with self._cache:
            if stack_id not in self._cache:
                self._cache.addStack(stack_id)
                self._cache.touchStack( self._current_stack_id )

        self.requestRefresh(rectF, stack_id, prefetch=True, layer_indexes=layer_indexes)

    def _refreshTile( self, stack_id, tile_no, prefetch=False, layer_indexes=None ):
        """
        Trigger a refresh of a particular tile.
        
        In the common case**, this function does the following:
        
        For every layer in the patch specified by (stackid, tile_no):
            
            1. Blend the layers (ims) -- in their current, 
               (possibly incomplete) state -- into a composite tile,
               and update the tile cache with it.
            
            2. Then, for dirty layers *that are actually visible*,
               create a request to fetch their data.
            
            3. Submit all the layer requests to the thread pool.
        
        **Less common cases:
             - In 'prefetch' mode: don't bother rendering composite tile, just fetch the layers.
             - For 'direct' layers, don't submit the request to the threadpool,
               just execute it immediately.
        """
        layers = self._sims.viewImageSources()
        if layer_indexes:
            layers = map( lambda i: layers[i], layer_indexes )
        
        if not self.axesSwapped:
            # Who came up with this transform?
            transform = QTransform(0,1,0,
                                   1,0,0,
                                   1,1,1)
        else:
            transform = QTransform().rotate(90).scale(1,-1)
        transform *= self.tiling.data2scene

        try:
            with self._cache:
                if not self._cache.tileDirty( stack_id, tile_no ):
                    return

            if not prefetch:
                with self._cache:
                    self._cache.setTileDirty(stack_id, tile_no, False)

                # Blend all (available) layers into the composite tile
                # and store it in the tile cache.
                tile_img = self._blendTile( stack_id, tile_no )
                with self._cache:
                    self._cache.setTile(stack_id, tile_no, tile_img,
                                        self._sims.viewVisible(),
                                        self._sims.viewOccluded())

            # refresh dirty layer tiles
            need_reblend = False
            for ims in layers:
                with self._cache:
                    layer_dirty = self._cache.layerDirty(stack_id, ims, tile_no)

                # Don't bother fetching layers that are not visible or not dirty.
                if not ( layer_dirty and 
                         not self._sims.isOccluded(ims) and
                         self._sims.isVisible(ims) ):
                    continue

                rect = self.tiling.imageRects[tile_no]
                dataRect = self.tiling.scene2data.mapRect(rect)

                try:
                    # Create the request object right now, from the main thread.
                    ims_req = ims.request(dataRect, stack_id[1])
                except IndeterminateRequestError:
                    # In ilastik, the viewer is still churning even as the user might be changing settings in the UI.
                    # Settings changes can cause 'slot not ready' errors during graph setup.
                    # Those errors are not really a problem, but we don't want to hide them from developers
                    # So, we show the exception (in the log), but we don't kill the thread.
                    sys.excepthook( *sys.exc_info() )
                    continue

                timestamp = time.time()
                fetch_fn = partial( self._fetch_tile_layer, timestamp, ims, transform, tile_no, stack_id, ims_req, self._cache )

                if ims.direct and not prefetch:
                    # The ImageSource 'ims' is fast (it has the direct flag set to true),
                    # so we process the request synchronously here.
                    # This improves the responsiveness for layers that have the data readily available.
                    fetch_fn()
                    need_reblend = True
                else:
                    # Tasks with 'smaller' priority values are processed first.
                    # We want non-prefetch tasks to take priority (False < True)
                    # and then more recent tasks to take priority (more recent -> process first)
                    priority = (prefetch, -timestamp)
                    submit_to_threadpool( fetch_fn, priority )
                    

            if need_reblend:
                # We synchronously fetched at least one direct layer.
                # We can immediately re-blend the composite tile.
                tile_img = self._blendTile( stack_id, tile_no )
                with self._cache:
                    self._cache.setTile(stack_id, tile_no,
                                        tile_img, self._sims.viewVisible(),
                                        self._sims.viewOccluded() )
        except KeyError:
            pass

    def _blendTile( self, stack_id, tile_nr): 
        """
        Blend all of the QImage layers of the patch
        specified by (stack_id, tile_nr) into a single QImage.
        """
        qimg = None
        p = None
        for i, (visible, layerOpacity, layerImageSource) in enumerate(reversed(self._sims)):
            image_type = layerImageSource.image_type()
            if issubclass(image_type, QGraphicsItem):
                with self._cache:
                    patch = self._cache.layer(stack_id, layerImageSource, tile_nr )
                if patch is not None:
                    assert isinstance(patch, image_type), \
                        "This ImageSource is producing a type of image that is not consistent with it's declared image_type()"
                    # This is a QGraphicsItem, so we don't blend it into the final tile.
                    # (The ImageScene will just draw it on top of everything.)
                    # But this is a convenient place to update the opacity/visible state.
                    if patch.opacity() != layerOpacity or patch.isVisible() != visible:
                        patch.setOpacity(layerOpacity)
                        patch.setVisible(visible)
                    patch.setZValue(i)  # The sims ("stacked image sources") are ordered from 
                                        # top-to-bottom (see imagepump.py), but in Qt,
                                        # higher Z-values are shown on top.
                                        # Note that the current loop is iterating in reverse order.
                continue

            # No need to fetch non-visible image tiles.
            if not visible or layerOpacity == 0.0:
                continue

            with self._cache:
                patch = self._cache.layer(stack_id, layerImageSource, tile_nr )
            
            # patch might be a QGraphicsItem instead of QImage,
            # in which case it is handled separately,
            # not composited into the tile.

            if patch is not None:
                assert isinstance(patch, QImage), \
                    "Unknown tile layer type: {}. Expected QImage or QGraphicsItem".format(type(patch))
                if qimg is None:
                    qimg = QImage(self.tiling.imageRects[tile_nr].size(), QImage.Format_ARGB32_Premultiplied)
                    qimg.fill(0xffffffff) # Use a hex constant instead.
                    p = QPainter(qimg)
                p.setOpacity(layerOpacity)
                p.drawImage(0,0, patch)
        
        if p is not None:
            p.end()

        return qimg

    def _fetch_tile_layer(self, timestamp, ims, transform, tile_nr, stack_id, ims_req, cache):
        """
        Fetch a single tile from a layer (ImageSource).
        
        Parameters
        ----------
        timestamp
            The timestamp at which ims_req was created
        ims
            The layer (image source) we're fetching from
        transform
            The transform to apply to the fetched data, before storing it in the cache
        tile_nr
            The ID of the fetched tile
        stack_id
            The stack ID of the tile we're fetching (e.g. which T-slice and Z-slice this tile belongs to) 
        ims_req
            A request object (e.g. GrayscaleImageRequest) with a wait() method that produces an item of 
            the appropriate type for the layer (i.e. either a QImage or a QGraphicsItem)
        cache
            The value of self._cache at the time the ims_req was created.
            (The cache can be replaced occasionally. See TileProvider._onSizeChanged().)
        """
        try:
            try:
                with cache:
                    layerTimestamp = cache.layerTimestamp(stack_id, ims, tile_nr)
            except KeyError:
                # May not be a timestamp yet (especially when prefetching)
                layerTimestamp = 0

            tile_rect = QRectF( self.tiling.imageRects[tile_nr] )

            if timestamp > layerTimestamp:
                img = ims_req.wait()
                if isinstance(img, QImage):
                    img = img.transformed(transform)
                elif isinstance(img, QGraphicsItem):
                    # FIXME: It *seems* like applying the same transform to QImages and QGraphicsItems
                    #        makes sense here, but for some strange reason it isn't right.
                    #        For QGraphicsItems, it seems obvious that this is the correct transform.
                    #        I do not understand the formula that produces 'transform', which is used for QImage tiles.
                    img.setTransform(QTransform.fromTranslate(tile_rect.left(), tile_rect.top()), combine=True)
                    img.setTransform(self.tiling.data2scene, combine=True)
                else:
                    assert False, "Unexpected image type: {}".format( type(img) )

                with cache:
                    try:
                        cache.updateTileIfNecessary(stack_id, ims, tile_nr, timestamp, img)
                    except KeyError:
                        pass

                if stack_id == self._current_stack_id \
                        and cache is self._cache:
                    self.sceneRectChanged.emit( tile_rect )
        except BaseException:
            sys.excepthook( *sys.exc_info() )


    
    def _onLayerDirty(self, dirtyImgSrc, dataRect ):
        """
        Called when one of the image sources we depend on has become dirty.
        Mark the appropriate entries in our tile/layer caches as dirty.
        """
        # Clip the dataRect to the boundaries of the tiling, to ensure 
        # that the 'fast path' below is active when appropriate.
        # (datasources are permitted to mark wider dirty regions than the
        # scene boundaries, but the roi outside the scene bounds is just ignored.)
        tileshape = self.tiling.sliceShape

        datastart = ( max(0, dataRect.left()),
                      max(0, dataRect.top()) )

        datastop = ( min(tileshape[0], dataRect.x() + dataRect.width()),  # Don't use right()!
                     min(tileshape[1], dataRect.y() + dataRect.height())) # Don't use bottom()!

        dataRect = QRect( datastart[0],
                          datastart[1],
                          datastop[0] - datastart[0],
                          datastop[1] - datastart[1] )
        
        sceneRect = self.tiling.data2scene.mapRect(dataRect)
        if dirtyImgSrc not in self._sims.viewImageSources():
            return
        
        visibleAndNotOccluded = self._sims.isVisible( dirtyImgSrc ) \
                                and not self._sims.isOccluded( dirtyImgSrc )

        # Is EVERYTHING dirty?
        if not sceneRect.isValid() or dataRect == QRect(0,0,*self.tiling.sliceShape):
            # Everything is dirty.
            # This is a FAST PATH for quickly setting all tiles dirty.
            # (It makes a HUGE difference for very large tiling scenes.)
            with self._cache:
                self._cache.setLayerDirtyAllTiles(dirtyImgSrc)
                if visibleAndNotOccluded:
                    self._cache.setAllTilesDirty()
        else:
            # Slow path: Mark intersecting tiles as dirty.
            with self._cache:
                for tile_no in self.tiling.intersected(sceneRect):
                    self._cache.setLayerDirtyAllStacks(dirtyImgSrc, tile_no, True)
                    if visibleAndNotOccluded:
                        self._cache.setTileDirtyAllStacks(tile_no, True)
        if visibleAndNotOccluded:
            self.sceneRectChanged.emit( QRectF(sceneRect) )

    def _onStackIdChanged( self, oldId, newId ):
        """
        When the current 'stacked image source' has changed it's 'stack id'.
        The 'stack id' changes when the user scrolls to a new plane.
        When that happens, we keep all of our caches for the old plane,
        but we add (if necesssary) a new set of caches for all the tiles
        that will be shown in the new plane.
        """
        with self._cache:
            if newId in self._cache:
                self._cache.touchStack( newId )
            else:
                self._cache.addStack( newId )
        self._current_stack_id = newId
        self.sceneRectChanged.emit(QRectF())

    def _onVisibleChanged(self, ims, visible):
        """
        Called when one of the image sources we depend on has changed it's visibility.
        All tiles will need to be re-rendered (i.e. blended from layers).
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        if not self._sims.isOccluded( ims ):
            self.sceneRectChanged.emit(QRectF())

    def _onOpacityChanged(self, ims, opacity):
        """
        Called when one of the image sources we depend on has changed it's opacity.
        All tiles will need to be re-rendered (i.e. blended from layers).
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        if self._sims.isVisible( ims ) and not self._sims.isOccluded( ims ):
            self.sceneRectChanged.emit(QRectF())

    def _onSizeChanged(self):
        """
        Called when the StackedImageSources object we depend on has changed it's size.
        This is rare, but it means that the entire tile cache is obsolete.
        """
        self._cache = _TilesCache(self._current_stack_id, self._sims,
                                  maxstacks=self.cache_size)
        self.sceneRectChanged.emit(QRectF())

    def _onOrderChanged(self):
        """
        Called when the order of ImageSource objects the StackedImageSources
        (on which we depend) has changed.  The tiles all need to be re-rendered.
        """
        with self._cache:
            self._cache.setAllTilesDirty()
        self.sceneRectChanged.emit(QRectF())

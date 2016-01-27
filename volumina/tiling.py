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

#SciPy
import numpy

#PyQt
from PyQt4.QtCore import QRect, QRectF, QMutex, QObject, pyqtSignal
from PyQt4.QtGui import QImage, QPainter, QTransform

#volumina
from patchAccessor import PatchAccessor
import volumina
from volumina.pixelpipeline.asyncabcs import IndeterminateRequestError
from volumina.utility import log_exception

from concurrent.futures.thread import ThreadPoolExecutor, _WorkItem
from concurrent.futures import _base
import Queue

import logging
logger = logging.getLogger(__name__)



class RenderTask(_WorkItem):
    def __init__(self, f, prefetch, timestamp,
            tile_provider, ims, transform, tile_nr, stack_id, image_req,
            cache):
        super(RenderTask, self).__init__(f, self._render, [], {})

        self.prefetch = prefetch
        self.timestamp = timestamp

        self.tile_provider = tile_provider
        self.ims = ims
        self.transform = transform
        self.tile_nr = tile_nr
        self.stack_id = stack_id
        self.image_req = image_req
        self.timestamp = timestamp
        self.cache = cache

    def _render(self, *args, **kwds):
        """
        Render tile.

        Arguments are ignored. The function signature is preserved to
        match the convention used in the base class.
        """
        # Make sure the current thread has a name that excepthooks will recognize
        # (If this is a new thread in the threadpool, we need to set the name.)
        if not threading.current_thread().name.startswith("TileProvider"):
            threading.current_thread().name = "TileProvider-" + str( threading.current_thread().ident )
        
        try:
            try:
                with self.cache:
                    layerTimestamp = self.cache.layerTimestamp(self.stack_id,
                        self.ims, self.tile_nr)
            except KeyError:
                pass

            if self.timestamp > layerTimestamp:
                img = self.image_req.wait()
                img = img.transformed(self.transform)
                try:
                    with self.cache:
                        self.cache.updateTileIfNecessary(self.stack_id,
                            self.ims, self.tile_nr, self.timestamp, img)
                except KeyError:
                    pass

                if self.stack_id == self.tile_provider._current_stack_id \
                        and self.cache is self.tile_provider._cache:
                    self.tile_provider.sceneRectChanged.emit( QRectF(
                        self.tile_provider.tiling.imageRects[self.tile_nr]))
        except BaseException:
            sys.excepthook( *sys.exc_info() )

    def __lt__(self, other):
        """
        Compare two RenderTasks, where smallest has higher priority.

        Regular render tasks have higher priority than prefetch tasks. A task
        with higher timestamp has higher priority.
        """
        assert isinstance(self, RenderTask) and isinstance(other, RenderTask), \
            "Can't compare {} with {}".format( type(self), type(other) )
        res = cmp(self.prefetch, other.prefetch)
        if res != 0:
            return res
        # note reversed order for timestamp
        return cmp(other.timestamp, self.timestamp)


class RenderTaskExecutor(ThreadPoolExecutor):
    def __init__(self, max_workers):
        super(RenderTaskExecutor, self).__init__(max_workers)
        self._work_queue = Queue.PriorityQueue()

    def submit(self, *args):
        with self._shutdown_lock:
            if self._shutdown:
                raise RuntimeError('cannot schedule new futures after shutdown')

            f = _base.Future()
            w = RenderTask(f, *args)

            self._work_queue.put(w)
            self._adjust_thread_count()
            return f


renderer_pool = None

def get_render_pool():
    global renderer_pool
    if renderer_pool is None:
        renderer_pool = RenderTaskExecutor(6)
    return renderer_pool

class Tiling(object):
    '''Tiling.__init__()

    Arguments:
    sliceShape -- (width, height)
    data2scene -- QTransform from data to image coordinates (default:
                  identity transform)
    blockSize  -- base tile size: blockSize x blockSize (default 256)
    overlap    -- overlap between tiles positive number prevents rendering
                  artifacts between tiles for certain zoom levels (default 1)

    '''

    def __init__(self, sliceShape, data2scene=QTransform(),
                 blockSize=256, overlap=0, overlap_draw=1e-3,
                 name="Unnamed Tiling"):
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
    def __init__( self, first_uid, default_factory=lambda:None,
                  maxcaches=None ):
        self._maxcaches = maxcaches
        self.caches = OrderedDict()
        self.add( first_uid, default_factory=default_factory)

    def add( self, uid, default_factory=lambda:None ):
        if uid not in self.caches:
            cache = defaultdict(default_factory)
            self.caches[uid] = cache
        else:
            raise Exception('MultiCache.add: uid %s is already in use' % str(uid))

        # remove oldest cache, if necessary
        old_uid = None
        if self._maxcaches and len(self.caches) > self._maxcaches:
            old_uid, v = self.caches.popitem(False) # removes item in LIFO order
        return old_uid

    def touch( self, uid ):
        c = self.caches[uid]
        del self.caches[uid]
        self.caches[uid] = c

class _TilesCache( object ):
    def __init__(self, first_stack_id, sims, maxstacks=None):
        self._lock = threading.Lock()
        self._sims = sims

        kwargs = {'first_uid' : first_stack_id,
                  'maxcaches' : maxstacks}
        self._tileCache = _MultiCache(default_factory=lambda: (None, 0.), **kwargs)
        self._tileCacheDirty = _MultiCache(default_factory=lambda: True, **kwargs)
        self._layerCache = _MultiCache(**kwargs)
        self._layerCacheDirty = _MultiCache(default_factory=lambda: True, **kwargs)
        self._layerCacheTimestamp = _MultiCache(default_factory=float, **kwargs)

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
            if numpy.count_nonzero(visibleAndNotOccluded) > 0:
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

    def setLayer( self, stack_id, layer_id, tile_id, img ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._layerCache.caches[stack_id][(layer_id, tile_id)] = img


    def layerDirty(self, stack_id, layer_id, tile_id ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        return self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)]

    def setLayerDirty( self, stack_id, layer_id, tile_id, b ):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = b

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

    def setLayerTimestamp( self, stack_id, layer_id, tile_id, time):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)] = time


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


    def updateTileIfNecessary( self, stack_id, layer_id, tile_id,
                               req_timestamp, img):
        assert self._lock.locked(), "You must claim the _TileCache via a context manager before calling this function."
        if req_timestamp > self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)]:
            self._layerCache.caches[stack_id][(layer_id, tile_id)] = img
            self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = False
            self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)] = req_timestamp
            self._tileCacheDirty.caches[stack_id][tile_id] = True


class TileProvider( QObject ):
    Tile = collections.namedtuple('Tile', 'id qimg rectF progress tiling')
    sceneRectChanged = pyqtSignal( QRectF )


    '''TileProvider __init__

    Keyword Arguments:
    cache_size                -- maximal number of encountered stacks
                                 to cache, i.e. slices if the imagesources
                                 draw from slicesources (default 10)
    request_queue_size        -- maximal number of request to queue up (default 100000)
    n_threads                 -- maximal number of request threads; this determines the
                                 maximal number of simultaneously running requests
                                 to the pixelpipeline (default: 2)
    layerIdChange_means_dirty -- layerId changes invalidate the cache; by default only
                                 stackId changes do that (default False)
    parent                    -- QObject

    '''

    @property
    def axesSwapped(self):
        return self._axesSwapped

    @axesSwapped.setter
    def axesSwapped(self, value):
        self._axesSwapped = value

    def __init__( self, tiling, stackedImageSources, cache_size=100,
                  request_queue_size=100000, n_threads=2,
                  layerIdChange_means_dirty=False, parent=None ):
        QObject.__init__( self, parent = parent )

        self.tiling = tiling
        self.axesSwapped = False
        self._sims = stackedImageSources
        self._cache_size = cache_size
        self._request_queue_size = request_queue_size
        self._n_threads = n_threads
        self._layerIdChange_means_dirty = layerIdChange_means_dirty

        self._current_stack_id = self._sims.stackId
        self._cache = _TilesCache(self._current_stack_id, self._sims,
                                  maxstacks=self._cache_size)

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.sizeChanged.connect(self._onSizeChanged)
        self._sims.orderChanged.connect(self._onOrderChanged)
        self._sims.stackIdChanged.connect(self._onStackIdChanged)
        if self._layerIdChange_means_dirty:
            self._sims.layerIdChanged.connect(self._onLayerIdChanged)

        self._keepRendering = True

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
            yield TileProvider.Tile(
                tile_no,
                qimg,
                QRectF(self.tiling.imageRects[tile_no]),
                progress,
                self.tiling)

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

    def requestRefresh( self, rectF ):
        '''Requests tiles to be refreshed.

        Returns immediately. Call join() to wait for
        the end of the rendering.

        '''
        tile_nos = self.tiling.intersected( rectF )
        for tile_no in tile_nos:
            stack_id = self._current_stack_id
            self._refreshTile( stack_id, tile_no )

    def prefetch( self, rectF, through ):
        '''Request fetching of tiles in advance.

        Returns immediately. Prefetch will commence after all regular
        tiles are refreshed (see requestRefresh() and getTiles() ).
        The prefetch is reset when the 'through' value of the slicing
        changes. Several calls to prefetch are handeled in Fifo
        order.

        '''
        if self._cache_size > 1:
            stack_id = (self._current_stack_id[0], enumerate(through))
            with self._cache:
                if stack_id not in self._cache:
                    self._cache.addStack(stack_id)
                    self._cache.touchStack( self._current_stack_id )
            tile_nos = self.tiling.intersected( rectF )
            for tile_no in tile_nos:
                self._refreshTile( stack_id, tile_no, prefetch=True )

    def _refreshTile( self, stack_id, tile_no, prefetch=False ):
        if not self.axesSwapped:
            transform = QTransform(0,1,0,1,0,0,1,1,1)
        else:
            transform = QTransform().rotate(90).scale(1,-1)
        transform *= self.tiling.data2scene

        try:
            with self._cache:
                tile_dirty = self._cache.tileDirty( stack_id, tile_no )
            if tile_dirty:
                if not prefetch:
                    with self._cache:
                        self._cache.setTileDirty(stack_id, tile_no, False)
                    img = self._renderTile( stack_id, tile_no )
                    with self._cache:
                        self._cache.setTile(stack_id, tile_no, img,
                                            self._sims.viewVisible(),
                                            self._sims.viewOccluded())

                # refresh dirty layer tiles
                for ims in self._sims.viewImageSources():
                    with self._cache:
                        layer_dirty = self._cache.layerDirty(stack_id, ims, tile_no)
                    if layer_dirty \
                       and not self._sims.isOccluded(ims) \
                       and self._sims.isVisible(ims):

                        rect = self.tiling.imageRects[tile_no]
                        dataRect = self.tiling.scene2data.mapRect(rect)
                        try:
                            ims_req = ims.request(dataRect, stack_id[1])
                        except IndeterminateRequestError:
                            sys.excepthook( *sys.exc_info() )
                        else:
                            if ims.direct and not prefetch:
                                # The ImageSource 'ims' is fast (it has the
                                # direct flag set to true) so we process
                                # the request synchronously here. This
                                # improves the responsiveness for layers
                                # that have the data readily available.
                                start = time.time()
                                img = ims_req.wait()
    
                                img = img.transformed(transform)
                                stop = time.time()
    
                                ims._layer.timePerTile(stop-start,
                                                       self.tiling.imageRects[tile_no])
    
                                with self._cache:
                                    self._cache.updateTileIfNecessary(
                                        stack_id, ims, tile_no, time.time(), img )
                                img = self._renderTile( stack_id, tile_no )
                                with self._cache:
                                    self._cache.setTile(stack_id, tile_no,
                                                        img, self._sims.viewVisible(),
                                                        self._sims.viewOccluded() )
                            else:
                                pool = get_render_pool()
                                pool.submit(prefetch, time.time(),
                                        self, ims, transform, tile_no,
                                        stack_id, ims_req, self._cache)
        except KeyError:
            pass

    def _renderTile( self, stack_id, tile_nr): 
        qimg = None
        p = None
        for i, v in enumerate(reversed(self._sims)):
            visible, layerOpacity, layerImageSource = v
            if not visible:
                continue

            with self._cache:
                patch = self._cache.layer(stack_id, layerImageSource, tile_nr )
            if patch is not None:
                if qimg is None:
                    qimg = QImage(self.tiling.imageRects[tile_nr].size(), QImage.Format_ARGB32_Premultiplied)
                    qimg.fill(0xffffffff) # Use a hex constant instead.
                    p = QPainter(qimg)
                p.setOpacity(layerOpacity)
                p.drawImage(0,0, patch)
        
        if p is not None:
            p.end()

        return qimg
    
    def _onLayerDirty(self, dirtyImgSrc, dataRect ):
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
                for ims in self._sims.viewImageSources():
                    self._cache.setLayerDirtyAllTiles(ims)
                if visibleAndNotOccluded:
                    self._cache.setAllTilesDirty()
        else:
            # Slow path: Mark intersecting tiles as dirty.
            with self._cache:
                for tile_no in self.tiling.intersected(sceneRect):
                    for ims in self._sims.viewImageSources():
                        self._cache.setLayerDirtyAllStacks(ims, tile_no, True)
                    if visibleAndNotOccluded:
                        self._cache.setTileDirtyAllStacks(tile_no, True)
        if visibleAndNotOccluded:
            self.sceneRectChanged.emit( QRectF(sceneRect) )

    def _onStackIdChanged( self, oldId, newId ):
        with self._cache:
            if newId in self._cache:
                self._cache.touchStack( newId )
            else:
                self._cache.addStack( newId )
        self._current_stack_id = newId
        self.sceneRectChanged.emit(QRectF())

    def _onLayerIdChanged( self, ims, oldId, newId ):
        if self._layerIdChange_means_dirty:
            self._onLayerDirty( ims, QRect() )

    def _onVisibleChanged(self, ims, visible):
        with self._cache:
            self._cache.setAllTilesDirty()
        if not self._sims.isOccluded( ims ):
            self.sceneRectChanged.emit(QRectF())

    def _onOpacityChanged(self, ims, opacity):
        with self._cache:
            self._cache.setAllTilesDirty()
        if self._sims.isVisible( ims ) and not self._sims.isOccluded( ims ):
            self.sceneRectChanged.emit(QRectF())

    def _onSizeChanged(self):
        self._cache = _TilesCache(self._current_stack_id, self._sims,
                                  maxstacks=self._cache_size)
        self.sceneRectChanged.emit(QRectF())

    def _onOrderChanged(self):
        with self._cache:
            self._cache.setAllTilesDirty()
        self.sceneRectChanged.emit(QRectF())

import time
import collections
import warnings
from collections import deque, defaultdict, OrderedDict
from Queue import Queue, Empty, Full, LifoQueue, PriorityQueue

from threading import Thread, Event, Lock

import numpy
from PyQt4.QtCore import QRect, QRectF, QMutex, QPointF, Qt, QSizeF, QObject, pyqtSignal, QThread, QEvent, QCoreApplication
from PyQt4.QtGui import QImage, QPainter, QTransform

from patchAccessor import PatchAccessor



#*******************************************************************************
# I m a g e T i l e                                                            * 
#*******************************************************************************

class ImageTile(object):
    def __init__(self, rect):
        self._mutex = QMutex()
        self.image  = QImage(rect.width(), rect.height(), 
                             QImage.Format_ARGB32_Premultiplied)
        self.image.fill(0)

        self._topLeft = rect.topLeft()

        #Whenever the underlying data changes, the data version is incremented.
        #By comparing the data version to the image and request version, it can
        #be determined if the content of this tile is recent or needs to be
        #re-computed.
        
        #version of the data
        self.dataVer = 0
        
        #version of self.image
        #
        #If self.imgVer < self.dataVer, the image needs to be re-computed
        #from the new data.
        self.imgVer  = -1
        
        #version of the request that has been generated to update the contents
        #of self.image
        #
        #If self.reqVer == self.dataVer, a request is currently running that will
        #eventually replace self.image with the new data.
        self.reqVer  = -2
    
    def clear(self):
        self.image.fill(0)

    def paint(self, painter):
        self.lock()
        painter.drawImage(self._topLeft, self.image)
        self.unlock()

    def lock(self):
        self._mutex.lock()
    def unlock(self):
        self._mutex.unlock()



class Tiling(object):
    '''Tiling.__init__()

    Arguments:
    sliceShape -- (width, height)
    data2scene -- QTransform from data to image coordinates (default: identity transform)
    blockSize  -- base tile size: blockSize x blockSize (default 256)
    overlap    -- overlap between tiles positive number prevents rendering
                  artifacts between tiles for certain zoom levels (default 1)

    '''
    def __init__(self, sliceShape, data2scene, blockSize=256, overlap=0, overlap_draw = 1e-3, name="Unnamed Tiling"):
        self.blockSize = blockSize
        self.overlap = overlap
        self._patchAccessor = PatchAccessor(sliceShape[0], sliceShape[1], blockSize=self.blockSize)
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

        self.offset = 50

        self.setData2scene(data2scene)

    def setData2scene(self, data2scene):
        self.data2scene = data2scene
        self.scene2data, isInvertible = data2scene.inverted()
        assert isInvertible

        for patchNr in range(self._patchAccessor.patchCount):
            #the patch accessor uses the data coordinate system
            #
            #because the patch is drawn on the screen, its holds coordinates
            #corresponding to Qt's QGraphicsScene's system, which need to be
            #converted to scene coordinates
            
            #the image rectangle includes an overlap margin
            imageRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, self.overlap))

            #the patch rectangle has per default no overlap
            patchRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, 0))

            # add a little overlap when the overlap_draw setting is activated
            if self._overlap_draw != 0:
                patchRectF  = QRectF(patchRectF.x()-self._overlap_draw,     patchRectF.y()-self._overlap_draw, \
                                   patchRectF.width()+2*self._overlap_draw, patchRectF.height()+2*self._overlap_draw)

            patchRect  = QRect(round(patchRectF.x()),     round(patchRectF.y()), \
                               round(patchRectF.width()), round(patchRectF.height()))
        
            #the image rectangles of neighboring patches can overlap slightly, to account
            #for inaccuracies in sub-pixel rendering of many ImagePatch objects
            imageRect   = QRect(round(imageRectF.x()),     round(imageRectF.y()), \
                                round(imageRectF.width()), round(imageRectF.height()))

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

    def intersectedF(self, rectF):
        if not rectF.isValid():
            return range(len(self.imageRectFs))
        i = []
        for patchNr, patchRectF in enumerate(self.tileRectFs):
            if rectF.intersects(patchRectF):
                i.append(patchNr)
        return i

    def intersected(self, rect):
        if not rect.isValid():
            return range(len(self.imageRects))
        i = []
        for patchNr, patchRect in enumerate(self.tileRects):
            if rect.intersects(patchRect):
                i.append(patchNr)
        return i

    def __len__(self):
        return len(self.imageRectFs)
            
#*******************************************************************************
# T i l e d I m a g e L a y e r                                                * 
#*******************************************************************************

class TiledImageLayer(object):
    def __init__(self, tiling):
        self._imageTiles = {}
        self._tiling = tiling

    def __getitem__(self, i):
        if i not in self._imageTiles.keys():
            self._imageTiles[i] = ImageTile(self._tiling.imageRects[i])
        return self._imageTiles[i]

    def __iter__(self):
        for i in range(len(self._tiling)):
            yield self[i]

class _MultiCache( object ):
    def __init__( self, first_uid, default_factory=lambda:None, maxcaches=None ):
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


from functools import wraps
def synchronous( tlockname ):
    """A decorator to place an instance based lock around a method """

    def _synched(func):
        @wraps(func)
        def _synchronizer(self,*args, **kwargs):
            tlock = self.__getattribute__( tlockname)
            tlock.acquire()
            try:
                return func(self, *args, **kwargs)
            finally:
                tlock.release()
        return _synchronizer
    return _synched

    

class _TilesCache( object ):
    def __init__(self, first_stack_id, sims, maxstacks=None):
        self._lock = Lock()
        self._sims = sims

        self._tileCache = _MultiCache(first_stack_id, maxcaches=maxstacks, default_factory=lambda:(None,0.))
        self._tileCacheDirty = _MultiCache(first_stack_id, default_factory=lambda:True, maxcaches=maxstacks)
        self._layerCache = _MultiCache(first_stack_id,  maxcaches=maxstacks)
        self._layerCacheDirty = _MultiCache(first_stack_id, default_factory=lambda:True, maxcaches=maxstacks)
        self._layerCacheTimestamp = _MultiCache(first_stack_id, default_factory=float, maxcaches=maxstacks)

    @synchronous('_lock')
    def __contains__( self, stack_id ):
        return stack_id in self._tileCache.caches

    @synchronous('_lock')
    def __len__( self ):
        return len(self._tileCache.caches)

    @synchronous('_lock')
    def tile( self, stack_id, tile_id ):
        return self._tileCache.caches[stack_id][tile_id]
    @synchronous('_lock')
    def setTile( self, stack_id, tile_id, img, stack_visible, stack_occluded ):
        if len(stack_visible) > 0:
            visible = numpy.asarray(stack_visible)
            occluded = numpy.asarray(stack_occluded)
            visibleAndNotOccluded = numpy.logical_and(visible, numpy.logical_not(occluded))
            if numpy.count_nonzero(visibleAndNotOccluded) > 0:
                dirty = numpy.asarray([self._layerCacheDirty.caches[stack_id][(ims, tile_id)] for ims in self._sims.viewImageSources()])
                progress = 1.-numpy.count_nonzero(numpy.logical_and(dirty, visibleAndNotOccluded) == True)/float(numpy.count_nonzero(visibleAndNotOccluded))
            else:
                progress = 1.0
        else:
            progress = 1.0
        self._tileCache.caches[stack_id][tile_id] = (img, progress)

    @synchronous('_lock')
    def tileDirty( self, stack_id, tile_id ):
        return self._tileCacheDirty.caches[stack_id][tile_id]
    @synchronous('_lock')
    def setTileDirty( self, stack_id, tile_id, b):
        self._tileCacheDirty.caches[stack_id][tile_id] = b
    @synchronous('_lock')
    def setTileDirtyAll( self, tile_id, b):
        for stack_id in self._tileCacheDirty.caches:
            self._tileCacheDirty.caches[stack_id][tile_id] = b

    @synchronous('_lock')
    def layer(self, stack_id, layer_id, tile_id ):
        return self._layerCache.caches[stack_id][(layer_id,tile_id)]
    @synchronous('_lock')
    def setLayer( self, stack_id, layer_id, tile_id, img ):
        self._layerCache.caches[stack_id][(layer_id, tile_id)] = img

    @synchronous('_lock')
    def layerDirty(self, stack_id, layer_id, tile_id ):
        return self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)]
    @synchronous('_lock')
    def setLayerDirty( self, stack_id, layer_id, tile_id, b ):
        self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = b
    @synchronous('_lock')
    def setLayerDirtyAll( self, layer_id, tile_id, b ):
        for stack_id in self._layerCacheDirty.caches:
            self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = b

    @synchronous('_lock')
    def layerTimestamp(self, stack_id, layer_id, tile_id ):
        return self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)]
    @synchronous('_lock')
    def setLayerTimestamp( self, stack_id, layer_id, tile_id, time):
        self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)] = time

    @synchronous('_lock')    
    def addStack( self, stack_id ):
        self._tileCache.add( stack_id )
        self._tileCacheDirty.add( stack_id, default_factory=lambda:True )
        self._layerCache.add( stack_id )
        self._layerCacheDirty.add( stack_id, default_factory=lambda:True )
        self._layerCacheTimestamp.add( stack_id, default_factory=float )

    @synchronous('_lock')
    def touchStack( self, stack_id ):
        self._tileCache.touch( stack_id )
        self._tileCacheDirty.touch( stack_id )
        self._layerCache.touch( stack_id )
        self._layerCacheDirty.touch( stack_id )
        self._layerCacheTimestamp.touch( stack_id )

    @synchronous('_lock')
    def updateTileIfNecessary( self, stack_id, layer_id, tile_id, req_timestamp, img):
        if req_timestamp > self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)]:
            self._layerCache.caches[stack_id][(layer_id, tile_id)]  = img         
            self._layerCacheDirty.caches[stack_id][(layer_id, tile_id)] = False
            self._layerCacheTimestamp.caches[stack_id][(layer_id, tile_id)] = req_timestamp        
            self._tileCacheDirty.caches[stack_id][tile_id] = True



class TileProvider( QObject ):
    THREAD_HEARTBEAT = 0.2

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
    def __init__( self, tiling,
                  stackedImageSources,
                  cache_size = 100,
                  request_queue_size = 100000,
                  n_threads = 2,
                  layerIdChange_means_dirty=False,
                  parent=None ):
        QObject.__init__( self, parent = parent )

        self.tiling = tiling
        self._axesAreSwapped = False
        self._sims = stackedImageSources
        self._cache_size = cache_size
        self._request_queue_size = request_queue_size
        self._n_threads = n_threads
        self._layerIdChange_means_dirty = layerIdChange_means_dirty

        self._current_stack_id = self._sims.stackId
        self._cache = _TilesCache(self._current_stack_id, self._sims, maxstacks=self._cache_size)

        self._dirtyLayerQueue = LifoQueue(self._request_queue_size)
        self._prefetchQueue = Queue(self._request_queue_size)

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.sizeChanged.connect(self._onSizeChanged)
        self._sims.orderChanged.connect(self._onOrderChanged)
        self._sims.stackIdChanged.connect(self._onStackIdChanged)
        if self._layerIdChange_means_dirty:
            self._sims.layerIdChanged.connect(self._onLayerIdChanged)

        self._keepRendering = True
        
        self._dirtyLayerThreads = [Thread(target=self._dirtyLayersWorker) for i in range(self._n_threads)]
        for thread in self._dirtyLayerThreads:
            thread.daemon = True
        [ thread.start() for thread in self._dirtyLayerThreads ]

    def setAxesSwapped(self, swapped):
        self._axesAreSwapped = True

    def getTiles( self, rectF ):
        '''Get tiles in rect and request a refresh.

        Returns tiles intersecting with rectF immediately and requests a refresh
        of these tiles. Next time you call this function the tiles may be already
        (partially) updated. If you want to wait until the rendering is fully complete,
        call join().

        '''
        self.requestRefresh( rectF )
        tile_nos = self.tiling.intersectedF( rectF )
        stack_id = self._current_stack_id
        for tile_no in tile_nos:
            qimg, progress = self._cache.tile(stack_id, tile_no)
            t = TileProvider.Tile(tile_no,
                     qimg,
                     QRectF(self.tiling.imageRects[tile_no]),
                     progress,
                     self.tiling)
            yield t

    def requestRefresh( self, rectF ):
        '''Requests tiles to be refreshed.

        Returns immediately. Call join() to wait for
        the end of the rendering.

        '''
        tile_nos = self.tiling.intersectedF( rectF )
        for tile_no in tile_nos:
            stack_id = self._current_stack_id
            self._refreshTile( stack_id, tile_no )

    def prefetch( self, rectF, through ):
        '''Request fetching of tiles in advance.

        Returns immediately. Prefetch will commence after
        all regular tiles are refreshed (see requestRefresh() and
        getTiles() ). The prefetch is reset when the 'through'
        value of the slicing changes. Several calls to prefetch
        are handeled in Fifo order.

        '''
        if self._cache_size > 1:
            stack_id = (self._current_stack_id[0], through)
            if stack_id not in self._cache:
                self._cache.addStack(stack_id)
                self._cache.touchStack( self._current_stack_id )
            tile_nos = self.tiling.intersectedF( rectF )
            for tile_no in tile_nos:
                self._refreshTile( stack_id, tile_no, prefetch=True )

    def join( self ):
        '''Wait until all refresh request are processed.

        Blocks until no refresh request pending anymore and all rendering
        finished.

        '''
        return self._dirtyLayerQueue.join()


    def notifyThreadsToStop( self ):
        '''Signals render threads to stop.

        Call this method at the end of the lifetime of
        a TileProvider instance. Otherwise the garbage collector will
        not clean up the instance (even if you call del).

        '''
        self._keepRendering = False

    def threadsAreNotifiedToStop( self ):
        '''Check if NotifyThreadsToStop() was called at least once.'''
        return not self._keepRendering

    def joinThreads( self, timeout=None ):
        '''Wait until all threads terminated.

        Without calling notifyThreadsToStop, threads will never
        terminate. 

        Arguments:
        timeout -- timeout in seconds as a floating point number
        
        '''
        for thread in self._dirtyLayerThreads:
            thread.join( timeout )

    def aliveThreads( self ):
        '''Return a map of thread identifiers and their alive status.

        All threads are alive until notifyThreadsToStop() is
        called. After that, they start dying. Call joinThreads() to wait
        for the last thread to die.
        
        '''
        at = {}
        for thread in self._dirtyLayerThreads:
            if thread.ident:
                at[thread.ident] = thread.isAlive()
        return at

    def _dirtyLayersWorker( self ):
        while self._keepRendering:
            # Save reference to the queue in case self._dirtyLayerQueue reassigned during this pass.
            # See onSizeChanged()
            dirtyLayerQueue = self._dirtyLayerQueue
            prefetchQueue = self._prefetchQueue
            
            try:
                try:
                    ims, t, tile_nr, stack_id, image_req, timestamp, cache = dirtyLayerQueue.get_nowait()
                    queue = dirtyLayerQueue
                except Empty:
                    try:
                        ims, t, tile_nr, stack_id, image_req, timestamp, cache = prefetchQueue.get_nowait()
                        queue = prefetchQueue
                    except Empty:
                        try:
                            ims, t, tile_nr, stack_id, image_req, timestamp, cache = dirtyLayerQueue.get(True, self.THREAD_HEARTBEAT)
                            queue = dirtyLayerQueue
                        except Empty:
                            continue
            except TypeError:
                #the TypeError occurs when the queue
                #is already None when the thread is being shut down
                #on program exit.
                #This avoids a lot of warnings.
                continue

            try:
                if timestamp > cache.layerTimestamp( stack_id, ims, tile_nr ):
                    img = image_req.wait()
                    img = img.transformed(t)
                    cache.updateTileIfNecessary( stack_id, ims, tile_nr, timestamp, img )
                    if stack_id == self._current_stack_id and cache is self._cache:
                        self.sceneRectChanged.emit(QRectF(self.tiling.imageRects[tile_nr]))
            except KeyError:
                pass
            finally:
                queue.task_done()

    def _refreshTile( self, stack_id, tile_no, prefetch=False ):
        if not self._axesAreSwapped:
            t = QTransform(0,1,0,1,0,0,1,1,1)
        else:
            t = QTransform().rotate(90).scale(1,-1)
        t = t*self.tiling.data2scene
        
        try:
            if self._cache.tileDirty( stack_id, tile_no ):
                if not prefetch:
                    self._cache.setTileDirty(stack_id, tile_no, False)
                    img = self._renderTile( stack_id, tile_no )
                    self._cache.setTile( stack_id, tile_no, img, self._sims.viewVisible(), self._sims.viewOccluded() )

                # refresh dirty layer tiles 
                for ims in self._sims.viewImageSources():
                    if self._cache.layerDirty(stack_id, ims, tile_no) and not self._sims.isOccluded(ims) and self._sims.isVisible(ims):

                        rect = self.tiling.imageRects[tile_no]
                        dataRect = self.tiling.scene2data.mapRect(rect)
                        ims_req = ims.request(dataRect, stack_id[1])
                        if ims.direct:
                            #The ImageSource 'ims' is fast (it has the direct flag set to true)
                            #so we process the request synchronously here.
                            #This improves the responsiveness for layers that have the data readily available.
                            start = time.time() 
                            img = ims_req.wait()
                            
                            img = img.transformed(t)
                            stop = time.time()
                            
                            ims._layer.timePerTile(stop-start, self.tiling.imageRects[tile_no])
                            
                            self._cache.updateTileIfNecessary( stack_id, ims, tile_no, time.time(), img )
                            img = self._renderTile( stack_id, tile_no )
                            self._cache.setTile( stack_id, tile_no, img, self._sims.viewVisible(), self._sims.viewOccluded() )
                        else:
                            req = (ims,
                                   t,
                                   tile_no,
                                   stack_id,
                                   ims_req,
                                   time.time(),
                                   self._cache)
                            try:
                                if prefetch:
                                    self._prefetchQueue.put_nowait( req )
                                else:
                                    self._dirtyLayerQueue.put_nowait( req )
                            except Full:
                                warnings.warn("Request queue full. Dropping tile refresh request. Increase queue size!")
        except KeyError:
            pass

    def _renderTile( self, stack_id, tile_nr ):
        qimg = QImage(self.tiling.imageRects[tile_nr].size(), QImage.Format_ARGB32_Premultiplied)
        qimg.fill(Qt.white)

        p = QPainter(qimg)
        for i, v in enumerate(reversed(self._sims)):
            visible, layerOpacity, layerImageSource = v
            if not visible:
                continue

            patch = self._cache.layer(stack_id, layerImageSource, tile_nr )
            if patch is not None:
                p.setOpacity(layerOpacity)
                p.drawImage(0,0, patch)
        p.end()
        return qimg

    def _onLayerDirty(self, dirtyImgSrc, dataRect ):
        sceneRect = self.tiling.data2scene.mapRect(dataRect)
        if dirtyImgSrc in self._sims.viewImageSources():
            visibleAndNotOccluded = self._sims.isVisible( dirtyImgSrc ) and not self._sims.isOccluded( dirtyImgSrc )
            for tile_no in xrange(len(self.tiling)):
                #and invalid rect means everything is dirty
                if not sceneRect.isValid() or self.tiling.tileRects[tile_no].intersected( sceneRect ):
                    for ims in self._sims.viewImageSources():
                        self._cache.setLayerDirtyAll(ims, tile_no, True)
                    if visibleAndNotOccluded:
                        self._cache.setTileDirtyAll(tile_no, True)
            if visibleAndNotOccluded:
                self.sceneRectChanged.emit( QRectF(sceneRect) )

    def _onStackIdChanged( self, oldId, newId ):
        if newId in self._cache:
            self._cache.touchStack( newId )
        else:
            self._cache.addStack( newId )
        self._current_stack_id = newId
        self._prefetchQueue = Queue(self._request_queue_size)
        self.sceneRectChanged.emit(QRectF())

    def _onLayerIdChanged( self, ims, oldId, newId ):
        if self._layerIdChange_means_dirty:
            self._onLayerDirty( ims, QRect() )

    def _onVisibleChanged(self, ims, visible):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        if not self._sims.isOccluded( ims ):
            self.sceneRectChanged.emit(QRectF())

    def _onOpacityChanged(self, ims, opacity):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        if self._sims.isVisible( ims ) and not self._sims.isOccluded( ims ):        
            self.sceneRectChanged.emit(QRectF())

    def _onSizeChanged(self):
        self._cache = _TilesCache(self._current_stack_id, self._sims, maxstacks=self._cache_size)
        self._dirtyLayerQueue = LifoQueue(self._request_queue_size)
        self._prefetchQueue = Queue(self._request_queue_size)
        self.sceneRectChanged.emit(QRectF())
        
    def _onOrderChanged(self):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        self.sceneRectChanged.emit(QRectF())

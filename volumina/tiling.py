import time
import collections
from collections import deque, defaultdict, OrderedDict
from Queue import Queue, Empty, LifoQueue, PriorityQueue

from threading import Thread, Event, Lock

import numpy
from PyQt4.QtCore import QRect, QRectF, QMutex, QPointF, Qt, QSizeF, QObject, pyqtSignal, QThread, QEvent, QCoreApplication
from PyQt4.QtGui import QImage, QPainter

from patchAccessor import PatchAccessor
from imageSceneRendering import ImageSceneRenderThread



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
    # base tile size: blockSize x blockSize
    blockSize = 32
    #
    # overlap between tiles 
    # positive number prevents rendering artifacts between tiles for certain zoom levels
    overlap = 1

    @property
    def imageRects( self ):
        return self._imageRect

    def __init__(self, sliceShape, data2scene):
        patchAccessor = PatchAccessor(sliceShape[0], sliceShape[1], blockSize=self.blockSize)

        self._imageRectF = []
        self.rectF = []
        self._imageRect  = []
        self.rect  = []
        self.sliceShape = sliceShape

        for patchNr in range(patchAccessor.patchCount):
            #the patch accessor uses the data coordinate system
            #
            #because the patch is drawn on the screen, its holds coordinates
            #corresponding to Qt's QGraphicsScene's system, which need to be
            #converted to scene coordinates
            
            #the image rectangle includes an overlap margin
            imageRectF = data2scene.mapRect(patchAccessor.patchRectF(patchNr, self.overlap))
            
            #the patch rectangle has no overlap
            patchRectF = data2scene.mapRect(patchAccessor.patchRectF(patchNr, 0))

            patchRect  = QRect(round(patchRectF.x()),     round(patchRectF.y()), \
                               round(patchRectF.width()), round(patchRectF.height()))
        
            #the image rectangles of neighboring patches can overlap slightly, to account
            #for inaccuracies in sub-pixel rendering of many ImagePatch objects
            imageRect   = QRect(round(imageRectF.x()),     round(imageRectF.y()), \
                                round(imageRectF.width()), round(imageRectF.height()))

            self._imageRectF.append(imageRectF)
            self.rectF.append(patchRectF)
            self._imageRect.append(imageRect)
            self.rect.append(patchRect)
  
    def boundingRectF(self):
        p = self.rectF[-1]
        return QRectF(0,0, p.x()+p.width(), p.y()+p.height())

    def containsF(self, point):
        for i, p in enumerate(self.rectF):
            if p.contains(point):
                return i

    def intersectedF(self, rectF):
        if not rectF.isValid():
            return range(len(self._imageRectF))
        i = []
        for patchNr, patchRectF in enumerate(self.rectF):
            if rectF.intersects(patchRectF):
                i.append(patchNr)
        return i

    def intersected(self, rect):
        if not rect.isValid():
            return range(len(self._imageRect))
        i = []
        for patchNr, patchRect in enumerate(self.rect):
            if rect.intersects(patchRect):
                i.append(patchNr)
        return i

    def __len__(self):
        return len(self._imageRectF)
            
#*******************************************************************************
# T i l e d I m a g e L a y e r                                                * 
#*******************************************************************************

class TiledImageLayer(object):
    def __init__(self, tiling):
        self._imageTiles = []
        for patchNr in range(len(tiling)):
            self._imageTiles.append( ImageTile(tiling._imageRect[patchNr]) )
    def __getitem__(self, i):
        return self._imageTiles[i]
    def __iter__(self):
        return self._imageTiles.__iter__()



class _MultiCache( object ):
    def __init__( self, first_uid, shape=(1,), dtype=object, fill_with=None, maxcaches=None ):
        self._maxcaches = maxcaches
        self._caches = OrderedDict()
        self.add( first_uid, shape, dtype, fill_with )

    def __iter__( self ):
        return self._caches.iterkeys()

    def __contains__( self, uid ):
        return uid in self._caches

    def __len__( self ):
        return len(self._caches)

    def add( self, uid, shape=(1,), dtype=object, fill_with=None ):
        if uid not in self:
            cache = numpy.empty(shape, dtype)
            cache[:] = fill_with
            self._caches[uid] = cache
        else:
            raise Exception('MultiCache.add: uid %s is already in use' % str(uid))

        # remove oldest cache, if necessary
        old_uid = None
        if self._maxcaches and len(self._caches) > self._maxcaches:
            old_uid, v = self._caches.popitem(False) # removes item in LIFO order
        return old_uid

    def getAt( self, uid, key ):
        '''raises KeyError if uid or key is invalid'''
        return self._caches[uid][key]

    def setAt( self, uid, key, value ):
        '''raises KeyError if uid or key is invalid'''
        self._caches[uid][key] = value

    def __getitem__( self, uid ):
        return self._caches[uid]



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
    def __init__(self, first_stack_id, n_layer, n_tiles, maxstacks=None):
        self._lock = Lock()

        self._n_layer = n_layer
        self._n_tiles = n_tiles
        self._compositeCache = _MultiCache(first_stack_id, self._n_tiles, dtype = object,maxcaches=maxstacks)
        self._compositeCacheDirty = _MultiCache(first_stack_id, self._n_tiles, dtype = bool, fill_with=True, maxcaches=maxstacks)
        self._layerCache = _MultiCache(first_stack_id, (self._n_layer, self._n_tiles), dtype = object, maxcaches=maxstacks)
        self._layerCacheDirty = _MultiCache(first_stack_id, (self._n_layer, self._n_tiles), dtype = bool, fill_with=True, maxcaches=maxstacks)
        self._layerCacheTimestamp = _MultiCache(first_stack_id, (self._n_layer, self._n_tiles), dtype = float, fill_with=0., maxcaches=maxstacks)
    
    @synchronous('_lock')
    def __contains__( self, stack_id ):
        return stack_id in self._compositeCache

    @synchronous('_lock')
    def __len__( self ):
        return len(self._compositeCache)

    @synchronous('_lock')
    def composite( self, tile_no, stack_id ):
        return self._compositeCache.getAt(stack_id, tile_no)

    @synchronous('_lock')
    def setComposite( self, stack_id, tile_no, img, visible ):
        visible = numpy.asarray(visible)
        dirty = self._layerCacheDirty[stack_id][:,tile_no]
        assert(visible.size == dirty.size)
        progress = numpy.count_nonzero(numpy.logical_and(dirty, visible) == False)/float(dirty.size)
        self._compositeCache.setAt(stack_id, tile_no, (img, progress))

    @synchronous('_lock')
    def compositeDirty( self, tile_no, stack_id ):
        return self._compositeCacheDirty.getAt(stack_id, tile_no)

    @synchronous('_lock')
    def setCompositeDirty( self, tile_no, b, stack_id ):
        self._compositeCacheDirty.setAt(stack_id, tile_no, b)

    @synchronous('_lock')
    def setCompositeDirtyAll( self, tile_no, b):
        for stack_id in self._compositeCacheDirty:
            self._compositeCacheDirty.setAt(stack_id, tile_no, b)

    @synchronous('_lock')
    def inLayer(self, layer_no, tile_no, stack_id ):
        return self._layerCache.getAt(stack_id, (layer_no, tile_no))

    @synchronous('_lock')
    def setInLayer( self, layer_no, tile_no, value, stack_id ):
        self._layerCache.setAt(stack_id, (layer_no, tile_no), value)

    @synchronous('_lock')
    def inLayerDirty(self, layer_no, tile_no, stack_id ):
        return self._layerCacheDirty.getAt(stack_id, (layer_no, tile_no))
    @synchronous('_lock')
    def setInLayerDirty( self, layer_no, tile_no, value, stack_id ):
        self._layerCacheDirty.setAt(stack_id, (layer_no, tile_no), value)

    @synchronous('_lock')
    def inLayerTimestamp(self, layer_no, tile_no, stack_id ):
        return self._layerCacheTimestamp.getAt(stack_id, (layer_no, tile_no))
    @synchronous('_lock')
    def setInLayerTimestamp( self, layer_no, tile_no, value, stack_id ):
        self._layerCacheTimestamp.setAt(stack_id, (layer_no, tile_no), value)

    @synchronous('_lock')    
    def addStack( self, stack_id ):
        self._compositeCache.add( stack_id, self._n_tiles, dtype = object )
        self._compositeCacheDirty.add( stack_id, self._n_tiles, dtype = bool, fill_with=True )
        self._layerCache.add(stack_id, (self._n_layer, self._n_tiles), dtype = object)
        self._layerCacheDirty.add(stack_id, (self._n_layer, self._n_tiles), dtype = bool, fill_with=True)
        self._layerCacheTimestamp.add(stack_id, (self._n_layer, self._n_tiles), dtype = float, fill_with=0.)

    @synchronous('_lock')
    def updateTileIfNecessary( self, layer_nr, tile_nr, stack_id, req_timestamp, img):
        if req_timestamp > self._layerCacheTimestamp.getAt(stack_id, (layer_nr, tile_nr)):
            self._layerCache.setAt(stack_id, (layer_nr, tile_nr), img)                               
            self._layerCacheDirty.setAt(stack_id, (layer_nr, tile_nr), False)        
            self._layerCacheTimestamp.setAt(stack_id, (layer_nr, tile_nr), req_timestamp)        
            self._compositeCacheDirty.setAt(stack_id, tile_nr, True)

class LazyTileProvider( QObject ):
    N_THREADS = 2

    Tile = collections.namedtuple('Tile', 'id qimg rectF progress tiling') 
    changed = pyqtSignal( QRectF )

    def __init__( self, tiling, stackedImageSources, parent=None ):
        QObject.__init__( self, parent = parent )
        self._MAXSTACKS = 10

        self.isFrozen = False

        self.tiling = tiling
        self._sims = stackedImageSources
        self._shape = (len(self._sims), len(self.tiling))

        self._current_stack_id = self._sims.syncedId
        self._cache = _TilesCache(self._current_stack_id, len(self._sims), len(self.tiling), maxstacks=self._MAXSTACKS)
        self._clock = Lock()

        self._dirtyLayerQueue = LifoQueue()

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.syncedIdChanged.connect(self._onSyncedIdChanged)
        self._sims.stackChanged.connect(self._onStackChanged)
        #self._sims.aboutToResize.connect(self._onAboutToResize)
        #self._sims.resizeFinished.connect(self._onResizeFinished)

        self._keepRendering = True
        
        self._dirtyLayerThreads = [Thread(target=self._dirtyLayersWorker) for i in range(self.N_THREADS)]
        [ thread.start() for thread in self._dirtyLayerThreads ]

    def getTiles( self, rectF ):
        tile_nos = self.tiling.intersectedF( rectF )

        for tile_no in tile_nos:
            stack_id = self._current_stack_id
            self._refreshTile( tile_no, stack_id )
            qimg, progress = self._cache.composite(tile_no, stack_id)
            t = LazyTileProvider.Tile(tile_no,
                     qimg,
                     QRectF(self.tiling.imageRects[tile_no]),
                     progress,
                     self.tiling)
            yield t

    def freeze( self ):
        raise NotImplementedError
        self.isFrozen = True
    
    def settleAndFreeze( self, timeout=None ):
        raise NotImplementedError
        self.freeze()

    def unfreeze( self ):
        raise NotImplementedError
        self.isFrozen = False

    def notifyThreadsToStop( self ):
        self._keepRendering = False

    def _dirtyLayersWorker( self ):
        while self._keepRendering:
            try:
                layer_nr, tile_nr, stack_id, image_req, timestamp = self._dirtyLayerQueue.get(True, 1)
            except Empty:
                continue
            try:
                if timestamp > self._cache.inLayerTimestamp( layer_nr, tile_nr, stack_id ):
                    img = image_req.wait()
                    self._cache.updateTileIfNecessary( layer_nr, tile_nr, stack_id, timestamp, img )
                    if stack_id == self._current_stack_id:
                        self.changed.emit(QRectF(self.tiling.imageRects[tile_nr]))
            except KeyError:
                pass

    def _refreshTile( self, tile_no, stack_id ):
        try:
            if stack_id in self._cache and self._cache.compositeDirty( tile_no, stack_id ):
                self._cache.setCompositeDirty(tile_no, False, stack_id)
                img = self._renderTile(tile_no, stack_id )
                self._cache.setComposite( stack_id, tile_no, img, self._sims.viewVisible() )
                
                # refresh dirty layer tiles        
                for layer_nr in xrange(len(self._sims)):
                    if self._cache.inLayerDirty(layer_nr, tile_no, stack_id):
                        req = (layer_nr,
                               tile_no,
                               stack_id,
                               self._sims.getImageSource(layer_nr).request(self.tiling.imageRects[tile_no]),
                               time.time())
                        self._dirtyLayerQueue.put( req )
        except KeyError:
            pass

    def _renderTile( self, tile_nr, stack_id ):
        qimg = QImage(self.tiling.imageRects[tile_nr].size(), QImage.Format_ARGB32_Premultiplied)
        qimg.fill(0)

        p = QPainter(qimg)
        for i, v in enumerate(reversed(self._sims)):
            visible, layerOpacity, layerImageSource = v
            if not visible:
                continue
            
            layer_nr = len(self._sims) - i - 1
            patch = self._cache.inLayer(layer_nr, tile_nr, stack_id )
            if patch is not None:
                p.setOpacity(layerOpacity)
                p.drawImage(0,0, patch)
        p.end()
        return qimg

    def _onLayerDirty(self, layerNr, rect):
        tile_nos = self.tiling.intersectedF( QRectF(rect) )
        for tile_no in tile_nos:
            for layer_no in xrange(len(self._sims)):
                self._cache.setInLayerDirty(layer_no, tile_no, True, self._current_stack_id)
            self._cache.setCompositeDirty(tile_no, True, self._current_stack_id)
        self.changed.emit(QRectF(rect))

    def _onSyncedIdChanged( self, oldId, newId ):
        if newId not in self._cache:
            self._cache.addStack( newId )
        self._current_stack_id = newId
        self.changed.emit(QRectF())

    def _onVisibleChanged(self, layerNr, visible):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setCompositeDirtyAll(tile_no, True)
        self.changed.emit(QRectF())

    def _onOpacityChanged(self, layerNr, opacity):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setCompositeDirtyAll(tile_no, True)
        self.changed.emit(QRectF())

    def _onStackChanged(self):
        #FIXME FIXME FIXME
        print "onStackChanged!"
        shape = (len(self._sims), len(self.tiling))
        if shape == self._shape:
            raise NotImplementedError
        else:
            self._cache = _TilesCache(self._current_stack_id, len(self._sims), len(self.tiling), maxstacks=self._MAXSTACKS)
            self._shape = shape
        

    def _onResizeFinished(self, newSize):
        raise NotImplementedError
        if self._renderThread:
              self._renderThread.start(self.tiling)

    def _onAboutToResize(self, newSize):
        raise NotImplementedError
        if self._renderThread:
          self.reshapeRequests()
          assert not self._renderThread.isRunning()

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
    def __init__( self, first_uid, default_factory=lambda:None, maxcaches=None ):
        self._maxcaches = maxcaches
        self._caches = OrderedDict()
        self.add( first_uid, default_factory=default_factory)

    def __iter__( self ):
        return iter(self._caches.keys())

    def __contains__( self, uid ):
        return uid in self._caches

    def __len__( self ):
        return len(self._caches)

    def add( self, uid, default_factory=lambda:None ):
        if uid not in self:
            cache = defaultdict(default_factory)
            self._caches[uid] = cache
        else:
            raise Exception('MultiCache.add: uid %s is already in use' % str(uid))

        # remove oldest cache, if necessary
        old_uid = None
        if self._maxcaches and len(self._caches) > self._maxcaches:
            old_uid, v = self._caches.popitem(False) # removes item in LIFO order
        return old_uid

    def getAt( self, uid, key ):
        '''raises KeyError if uid is invalid'''
        return self._caches[uid][key]

    def setAt( self, uid, key, value ):
        '''raises KeyError if uid is invalid'''
        self._caches[uid][key] = value



import inspect
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

        self._tileCache = _MultiCache(first_stack_id, maxcaches=maxstacks)
        self._tileCacheDirty = _MultiCache(first_stack_id, default_factory=lambda:True, maxcaches=maxstacks)
        self._layerCache = _MultiCache(first_stack_id,  maxcaches=maxstacks)
        self._layerCacheDirty = _MultiCache(first_stack_id, default_factory=lambda:True, maxcaches=maxstacks)
        self._layerCacheTimestamp = _MultiCache(first_stack_id, default_factory=float, maxcaches=maxstacks)
    
    @synchronous('_lock')
    def __contains__( self, stack_id ):
        return stack_id in self._tileCache

    @synchronous('_lock')
    def __len__( self ):
        return len(self._tileCache)

    @synchronous('_lock')
    def tile( self, stack_id, tile_id ):
        return self._tileCache.getAt(stack_id, tile_id)
    @synchronous('_lock')
    def setTile( self, stack_id, tile_id, img, stack_visible ):
        visible = numpy.asarray(stack_visible)
        dirty = numpy.asarray([self._layerCacheDirty.getAt(stack_id, (ims, tile_id)) for ims in self._sims.viewImageSources()])
        progress = numpy.count_nonzero(numpy.logical_and(dirty, visible) == False)/float(dirty.size)
        self._tileCache.setAt(stack_id, tile_id, (img, progress))

    @synchronous('_lock')
    def tileDirty( self, stack_id, tile_id ):
        return self._tileCacheDirty.getAt(stack_id, tile_id)
    @synchronous('_lock')
    def setTileDirty( self, stack_id, tile_id, b):
        self._tileCacheDirty.setAt(stack_id, tile_id, b)
    @synchronous('_lock')
    def setTileDirtyAll( self, tile_id, b):
        for stack_id in self._tileCacheDirty:
            self._tileCacheDirty.setAt(stack_id, tile_id, b)

    @synchronous('_lock')
    def layer(self, stack_id, layer_id, tile_id ):
        return self._layerCache.getAt(stack_id, (layer_id, tile_id))
    @synchronous('_lock')
    def setLayer( self, stack_id, layer_id, tile_id, img ):
        self._layerCache.setAt(stack_id, (layer_id, tile_id), img)

    @synchronous('_lock')
    def layerDirty(self, stack_id, layer_id, tile_id ):
        return self._layerCacheDirty.getAt(stack_id, (layer_id, tile_id))
    @synchronous('_lock')
    def setLayerDirty( self, stack_id, layer_id, tile_id, b ):
        self._layerCacheDirty.setAt(stack_id, (layer_id, tile_id), b)

    @synchronous('_lock')
    def layerTimestamp(self, stack_id, layer_id, tile_id ):
        return self._layerCacheTimestamp.getAt(stack_id, (layer_id, tile_id))
    @synchronous('_lock')
    def setLayerTimestamp( self, stack_id, layer_id, tile_id, time):
        self._layerCacheTimestamp.setAt(stack_id, (layer_id, tile_id), time)

    @synchronous('_lock')    
    def addStack( self, stack_id ):
        self._tileCache.add( stack_id )
        self._tileCacheDirty.add( stack_id, default_factory=lambda:True )
        self._layerCache.add( stack_id )
        self._layerCacheDirty.add( stack_id, default_factory=True )
        self._layerCacheTimestamp.add( stack_id, default_factory=float )

    @synchronous('_lock')
    def updateTileIfNecessary( self, stack_id, layer_id, tile_id, req_timestamp, img):
        if req_timestamp > self._layerCacheTimestamp.getAt(stack_id, (layer_id, tile_id)):
            self._layerCache.setAt(stack_id, (layer_id, tile_id), img)         
            self._layerCacheDirty.setAt(stack_id, (layer_id, tile_id), False)
            self._layerCacheTimestamp.setAt(stack_id, (layer_id, tile_id), req_timestamp)        
            self._tileCacheDirty.setAt(stack_id, tile_id, True)



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

        self._current_stack_id = self._sims.syncedId
        self._cache = _TilesCache(self._current_stack_id, self._sims, maxstacks=self._MAXSTACKS)

        self._dirtyLayerQueue = LifoQueue()

        self._sims.layerDirty.connect(self._onLayerDirty)
        self._sims.visibleChanged.connect(self._onVisibleChanged)
        self._sims.opacityChanged.connect(self._onOpacityChanged)
        self._sims.syncedIdChanged.connect(self._onSyncedIdChanged)
        self._sims.stackChanged.connect(self._onStackChanged)
        self._sims.orderChanged.connect(self._onOrderChanged)

        self._keepRendering = True
        
        self._dirtyLayerThreads = [Thread(target=self._dirtyLayersWorker) for i in range(self.N_THREADS)]
        [ thread.start() for thread in self._dirtyLayerThreads ]

    def getTiles( self, rectF ):
        tile_nos = self.tiling.intersectedF( rectF )

        for tile_no in tile_nos:
            stack_id = self._current_stack_id
            self._refreshTile( tile_no, stack_id )
            qimg, progress = self._cache.tile(stack_id, tile_no)
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
                ims, tile_nr, stack_id, image_req, timestamp = self._dirtyLayerQueue.get(True, 1)
            except Empty:
                continue
            try:
                if timestamp > self._cache.layerTimestamp( stack_id, ims, tile_nr ):
                    img = image_req.wait()
                    self._cache.updateTileIfNecessary( stack_id, ims, tile_nr, timestamp, img )
                    if stack_id == self._current_stack_id:
                        self.changed.emit(QRectF(self.tiling.imageRects[tile_nr]))
            except KeyError:
                pass

    def _refreshTile( self, tile_no, stack_id ):
        try:
            if stack_id in self._cache and self._cache.tileDirty( stack_id, tile_no ):
                self._cache.setTileDirty(stack_id, tile_no, False)
                img = self._renderTile(tile_no, stack_id )
                self._cache.setTile( stack_id, tile_no, img, self._sims.viewVisible() )
                
                # refresh dirty layer tiles        
                for ims in self._sims.viewImageSources():
                    if self._cache.layerDirty(stack_id, ims, tile_no):
                        req = (ims,
                               tile_no,
                               stack_id,
                               ims.request(self.tiling.imageRects[tile_no]),
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
            
            patch = self._cache.layer(stack_id, layerImageSource, tile_nr )
            if patch is not None:
                p.setOpacity(layerOpacity)
                p.drawImage(0,0, patch)
        p.end()
        return qimg

    def _onLayerDirty(self, layerNr, rect):
        tile_nos = self.tiling.intersectedF( QRectF(rect) )
        for tile_no in tile_nos:
            for ims in self._sims.viewImageSources():
                self._cache.setLayerDirty(self._current_stack_id, ims, tile_no, True)
            self._cache.setCompositeDirty(self._current_stack_id, tile_no, True)
        self.changed.emit(QRectF(rect))

    def _onSyncedIdChanged( self, oldId, newId ):
        if newId not in self._cache:
            self._cache.addStack( newId )
        self._current_stack_id = newId
        self.changed.emit(QRectF())

    def _onVisibleChanged(self, layerNr, visible):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        self.changed.emit(QRectF())

    def _onOpacityChanged(self, layerNr, opacity):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        self.changed.emit(QRectF())

    def _onStackChanged(self):
        print "onStackChanged!"
        # FIXME
        self._cache = _TilesCache(self._current_stack_id, self._sims, maxstacks=self._MAXSTACKS)
        self.changed.emit(QRectF())
        
    def _onOrderChanged(self):
        for tile_no in xrange(len(self.tiling)):
            self._cache.setTileDirtyAll(tile_no, True)
        self.changed.emit(QRectF())

    def _onResizeFinished(self, newSize):
        # FIXME
        raise NotImplementedError
        if self._renderThread:
              self._renderThread.start(self.tiling)

    def _onAboutToResize(self, newSize):
        # FIXME
        raise NotImplementedError
        if self._renderThread:
          self.reshapeRequests()
          assert not self._renderThread.isRunning()

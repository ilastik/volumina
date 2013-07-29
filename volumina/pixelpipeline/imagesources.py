#Python
import logging
import time
import warnings

try:
    import volumina
    from volumina.colorama import Fore, Back, Style
except:
    from colorama import Fore, Back, Style


from PyQt4.QtCore import QObject, QRect, pyqtSignal, QMutex
from PyQt4.QtGui import QImage, QColor
from qimage2ndarray import gray2qimage, array2qimage, alpha_view, rgb_view, byte_view
from asyncabcs import SourceABC, RequestABC
from volumina.slicingtools import is_bounded, slicing2rect, rect2slicing, slicing2shape, is_pure_slicing
from volumina.config import cfg
import numpy as np

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False

#*******************************************************************************
# I m a g e S o u r c e                                                        *
#*******************************************************************************

class ImageSource( QObject ):
    '''Partial implemented base class for image sources

    Signals:
    isDirty -- a rectangular region has changed; transmits
               an empty QRect if the whole image is dirty

    '''

    isDirty = pyqtSignal( QRect )

    def __init__( self, guarantees_opaqueness = False, parent = None, direct=False ):
        ''' direct: whether this request will be computed synchronously in the GUI thread (direct=True)
                    or whether the request will be put on a worker queue to be computed in a worker thread
                    (direct=False).
                    Only use direct=True if the layer's data will be immediately available'''
        super(ImageSource, self).__init__( parent = parent )
        self._opaque = guarantees_opaqueness
        self.direct = direct

    def request( self, rect, along_through=None ):
        raise NotImplementedError

    def setDirty( self, slicing ):
        '''Mark a region of the image as dirty.

        slicing -- if one ore more slices in the slicing
                   are unbounded, the whole image is marked dirty;
                   since an image has two dimensions, only the first
                   two slices in the slicing are used

        '''
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        if not is_bounded( slicing ):
            self.isDirty.emit(QRect()) # empty rect == everything is dirty
        else:
            self.isDirty.emit(slicing2rect( slicing ))

    def isOpaque( self ):
        '''Image is opaque everywhere (i.e. no pixel has an alpha value != 255).

        If the ImageSource can give an opaqueness guarantee,
        performance can be improved since layers occluded by this
        source don't have to be rendered in some cases.

        Warning: Can cause rendering bugs: In doubt return False.

        '''
        return self._opaque
assert issubclass(ImageSource, SourceABC)

#*******************************************************************************
# G r a y s c a l e I m a g e S o u r c e                                      *
#*******************************************************************************

class GrayscaleImageSource( ImageSource ):
    loggingName = __name__ + ".GrayscaleImageSource"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arraySource2D, layer ):
        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(GrayscaleImageSource, self).__init__( guarantees_opaqueness = True, direct=layer.direct )
        self._arraySource2D = arraySource2D

        self._layer = layer
        
        self._arraySource2D.isDirty.connect(self.setDirty)
        self._layer.normalizeChanged.connect(lambda: self.setDirty((slice(None,None), slice(None,None))))

    def request( self, qrect, along_through=None ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  GrayscaleImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return GrayscaleImageRequest( req, self._layer.normalize[0], direct=self.direct )
assert issubclass(GrayscaleImageSource, SourceABC)

class GrayscaleImageRequest( object ):
    loggingName = __name__ + ".GrayscaleImageRequest"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arrayrequest, normalize=None, direct=False ):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._normalize = normalize
        self.direct = direct
        
    def wait(self):
        return self.toImage()
        
    def toImage( self ):
        t = time.time()
       
        tWAIT = time.time()
        self._arrayreq.wait()
        tWAIT = 1000.0*(time.time()-tWAIT)
        
        tAR = time.time()
        a = self._arrayreq.getResult()
        tAR = 1000.0*(time.time()-tAR)
        
        assert a.ndim == 2, "GrayscaleImageRequest.toImage(): result has shape %r, which is not 2-D" % (a.shape,)
       
        normalize = self._normalize 
        if not normalize:
            normalize = [0,255]
            
        aCopy = a.copy()
        
        #
        # new conversion
        #
        tImg = None
        if _has_vigra and hasattr(vigra.colors, 'gray2qimage_ARGB32Premultiplied'):
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            n = np.asarray(self._normalize, dtype=a.dtype)
            vigra.colors.gray2qimage_ARGB32Premultiplied(a, byte_view(img), np.asarray(self._normalize, dtype=a.dtype))
            tImg = 1000.0*(time.time()-tImg)
        else:
            self.logger.warning("using slow image creation function")
            tImg = time.time()
            if self._normalize:
                #clipping has been implemented in this commit,
                #but it is not yet available in the packages obtained via easy_install
                #http://www.informatik.uni-hamburg.de/~meine/hg/qimage2ndarray/diff/fcddc70a6dea/qimage2ndarray/__init__.py
                a = np.clip(aCopy, *self._normalize)
            img = gray2qimage(a, self._normalize)
            ret = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            tImg = 1000.0*(time.time()-tImg)
        
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            tTOT = 1000.0*(time.time()-t)
            self.logger.debug("toImage (%dx%d, normalize=%r) took %f msec. (array req: %f, wait: %f, img: %f)" % (img.width(), img.height(), normalize, tTOT, tAR, tWAIT, tImg))
            
        return img
            
    def notify( self, callback, **kwargs ):
        self._arrayreq.notify(self._onNotify, package = (callback, kwargs))
    
    def _onNotify( self, result, package ):
        img = self.toImage()
        callback = package[0]
        kwargs = package[1]
        callback( img, **kwargs )
assert issubclass(GrayscaleImageRequest, RequestABC)

#*******************************************************************************
# A l p h a M o d u l a t e d I m a g e S o u r c e                            *
#*******************************************************************************

class AlphaModulatedImageSource( ImageSource ):
    def __init__( self, arraySource2D, layer ):
        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(AlphaModulatedImageSource, self).__init__()
        self._arraySource2D = arraySource2D
        self._layer = layer

        self._arraySource2D.isDirty.connect(self.setDirty)

    def request( self, qrect, along_through=None ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  AlphaModulatedImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return AlphaModulatedImageRequest( req, self._layer.tintColor, self._layer.normalize[0] )
assert issubclass(AlphaModulatedImageSource, SourceABC)

class AlphaModulatedImageRequest( object ):
    loggingName = __name__ + ".AlphaModulatedImageRequest"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arrayrequest, tintColor, normalize=(0,255)):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._normalize = normalize
        self._tintColor = tintColor

    def wait(self):
        return self.toImage()

    def toImage( self ):
        t = time.time()
       
        tWAIT = time.time()
        self._arrayreq.wait()
        tWAIT = 1000.0*time.time()-tWAIT
        
        tAR = time.time()
        a = self._arrayreq.getResult()
        tAR = 1000.0*(time.time()-tAR)

        tImg = None
        if _has_vigra and hasattr(vigra.colors, 'gray2qimage_ARGB32Premultiplied'):
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            tintColor = np.asarray([self._tintColor.redF(), self._tintColor.greenF(), self._tintColor.blueF()], dtype=np.float32);
            normalize = np.asarray(self._normalize, dtype=a.dtype)
            vigra.colors.alphamodulated2qimage_ARGB32Premultiplied(a, byte_view(img), tintColor, normalize) 
            tImg = 1000.0*(time.time()-tImg)
        else:
            self.logger.warning("using unoptimized conversion functions")
            tImg = time.time()
            shape = a.shape + (4,)
            d = np.empty(shape, dtype=np.float32)
            d[:,:,0] = a[:,:]*self._tintColor.redF()
            d[:,:,1] = a[:,:]*self._tintColor.greenF()
            d[:,:,2] = a[:,:]*self._tintColor.blueF()
            d[:,:,3] = a[:,:]
            normalize = self._normalize
            img = array2qimage(d, normalize)
            img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)        
            tImg = 1000.0*(time.time()-tImg)
       
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            tTOT = 1000.0*(time.time()-t)
            self.logger.debug("toImage (%dx%d, normalize=%r) took %f msec. (array req: %f, wait: %f, img: %f)" % (img.width(), img.height(), normalize, tTOT, tAR, tWAIT, tImg))
            
        return img
        
        return img
            
    def notify( self, callback, **kwargs ):
        self._arrayreq.notify(self._onNotify, package = (callback, kwargs))
    
    def _onNotify( self, result, package ):
        img = self.toImage()
        callback = package[0]
        kwargs = package[1]
        callback( img, **kwargs )
assert issubclass(AlphaModulatedImageRequest, RequestABC)

#*******************************************************************************
# C o l o r t a b l e I m a g e S o u r c e                                    *
#*******************************************************************************

class ColortableImageSource( ImageSource ):
    def __init__( self, arraySource2D, layer ):
        """ colorTable: a list of QRgba values """

        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(ColortableImageSource, self).__init__(direct=layer.direct)
        self._arraySource2D = arraySource2D
        self._arraySource2D.isDirty.connect(self.setDirty)

        self._layer = layer
        self.updateColorTable()
        self._layer.colorTableChanged.connect(self.updateColorTable)
        self._layer.normalizeChanged.connect(lambda: self.setDirty((slice(None,None), slice(None,None))))

    def updateColorTable(self):
        layerColorTable = self._layer.colorTable
        self._colorTable = np.zeros((len(layerColorTable), 4), dtype=np.uint8)

        for i, c in enumerate(layerColorTable):
            #note that we use qimage2ndarray.byte_view() on a QImage with Format_ARGB32 below.
            #this means that the memory layout actually is B, G, R, A

            if isinstance(c, QColor):
                color = c
            else: 
                color = QColor.fromRgba(c)
            self._colorTable[i,0] = color.blue()
            self._colorTable[i,1] = color.green()
            self._colorTable[i,2] = color.red()
            self._colorTable[i,3] = color.alpha() 
        
        self.isDirty.emit(QRect()) # empty rect == everything is dirty
        
    def request( self, qrect, along_through=None ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  ColortableImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d) = %r" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height(), rect2slicing(qrect)) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return ColortableImageRequest( req, self._colorTable, self._layer.normalize[0], self.direct )
assert issubclass(ColortableImageSource, SourceABC)

class ColortableImageRequest( object ):
    def __init__( self, arrayrequest, colorTable, normalize, direct=False ):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._colorTable = colorTable
        self.direct = direct
        self._normalize = normalize

    def wait(self):
        self._arrayreq.wait()
        return self.toImage()
        
    def toImage( self ):
        a = self._arrayreq.getResult()
        assert a.ndim == 2

        if self._normalize:
            nmin, nmax = self._normalize
            if nmin:
                a = a - nmin
            scale = (len(self._colorTable)-1) / float(nmax - nmin + 1e-35) #if max==min
            if scale != 1.0:
                a = a * scale
            if len(self._colorTable) <= 2**8:
                a = np.asarray( a, dtype=np.uint8 )
            elif len(self._colorTable) <= 2**16:
                a = np.asarray( a, dtype=np.uint16 )
            elif len(self._colorTable) <= 2**32:
                a = np.asarray( a, dtype=np.uint32 )

        # Use vigra if possible (much faster)
        if _has_vigra and hasattr(vigra.colors, 'applyColortable'):
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32)
            if not issubclass( a.dtype.type, np.integer ):
                #FIXME: maybe this should be done in a better way using an operator before the colortable request which properly handles 
                #this problem 
                import warnings
                warnings.warn("Data for colortable layers cannot be float, casting",RuntimeWarning)
                a=a.astype(np.int32)
            vigra.colors.applyColortable(a, self._colorTable, byte_view(img))

        # Without vigra, do it the slow way 
        else:
            if _has_vigra:
                # If this warning is annoying you, try this:
                # warnings.filterwarnings("once")
                warnings.warn("Using slow colortable images.  Upgrade to VIGRA > 1.9 to use faster implementation.")

            #make sure that a has values in range [0, colortable_length)
            a = np.remainder(a, len(self._colorTable))
            #apply colortable
            colortable = np.roll(np.fliplr(self._colorTable), -1, 1) # self._colorTable is BGRA, but array2qimage wants RGBA
            img = colortable[a]
            img = array2qimage(img)

        return img 
            
    def notify( self, callback, **kwargs ):
        self._arrayreq.notify(self._onNotify, package = (callback, kwargs))
    
    def _onNotify( self, result, package ):
        img = self.toImage()
        callback = package[0]
        kwargs = package[1]
        callback( img, **kwargs )
assert issubclass(ColortableImageRequest, RequestABC)

#*******************************************************************************
# R G B A I m a g e S o u r c e                                                *
#*******************************************************************************

class RGBAImageSource( ImageSource ):
    def __init__( self, red, green, blue, alpha, layer, guarantees_opaqueness = False ):
        '''
        If you don't want to set all the channels,
        a ConstantSource may be used as a replacement for
        the missing channels.

        red, green, blue, alpha - 2d array sources

        '''
        self._layer = layer
        channels = [red, green, blue, alpha]
        for channel in channels: 
                assert isinstance(channel, SourceABC) , 'channel has wrong type: %s' % str(type(channel))

        super(RGBAImageSource, self).__init__( guarantees_opaqueness = guarantees_opaqueness )
        self._channels = channels
        for arraySource in self._channels:
            arraySource.isDirty.connect(self.setDirty)

    def request( self, qrect, along_through=None ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  RGBAImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
             + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing( qrect )
        r = self._channels[0].request(s, along_through)
        g = self._channels[1].request(s, along_through)
        b = self._channels[2].request(s, along_through)
        a = self._channels[3].request(s, along_through)
        shape = list( slicing2shape(s) )
        assert len(shape) == 2
        assert all([x > 0 for x in shape])
        return RGBAImageRequest( r, g, b, a, shape, *self._layer._normalize )
assert issubclass(RGBAImageSource, SourceABC)

class RGBAImageRequest( object ):
    def __init__( self, r, g, b, a, shape,
                  normalizeR=None, normalizeG=None, normalizeB=None, normalizeA=None ):
        self._mutex = QMutex()
        self._requests = r, g, b, a
        self._normalize = [normalizeR, normalizeG, normalizeB, normalizeA]
        shape.append(4)
        self._data = np.empty(shape, dtype=np.uint8)
        self._requestsFinished = 4 * [False,]

    def wait(self):
        for req in self._requests:
            req.wait()
        return self.toImage()

    def toImage( self ):
        for i, req in enumerate(self._requests):
            a = self._requests[i].getResult()
            if self._normalize[i] is not None:

                normalize = self._normalize[i]
                a = a.astype(np.float32)
                a = (a - normalize[0])*255.0 / (normalize[1]-normalize[0])
                a[a > 255] = 255
                a[a < 0]   = 0
                a = a.astype(np.uint8)
            self._data[:,:,i] = a
        img = array2qimage(self._data)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)        

    def notify( self, callback, **kwargs ):
        for i in xrange(4):
            self._requests[i].notify(self._onNotify, package = (i, callback, kwargs))

    def _onNotify( self, result, package ):
        channel = package[0]
        self._requestsFinished[channel] = True
        if all(self._requestsFinished):
            img = self.toImage()
        
            callback = package[1]
            kwargs = package[2]
            callback( img, **kwargs )

assert issubclass(RGBAImageRequest, RequestABC)



class RandomImageSource( ImageSource ):
    '''Random noise image for testing and debugging.'''
    def request( self, qrect, along_through=None ):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        shape = slicing2shape( s )
        return RandomImageRequest( shape )
assert issubclass(RandomImageSource, SourceABC)

class RandomImageRequest( object ):
    def __init__( self, shape ):
        self.shape = shape

    def wait(self):
        d = (np.random.random(self.shape) * 255).astype(np.uint8)        
        assert d.ndim == 2
        img = gray2qimage(d)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            
    def notify( self, callback, **kwargs ):
        img = self.wait()
        callback( img, **kwargs )

assert issubclass(RandomImageRequest, RequestABC)

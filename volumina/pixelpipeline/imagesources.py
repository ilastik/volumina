try:
    import volumina
    from volumina.colorama import Fore, Back, Style
except:
    from colorama import Fore, Back, Style


from PyQt4.QtCore import QObject, QRect, pyqtSignal, QMutex
from PyQt4.QtGui import QImage, QColor
from qimage2ndarray import gray2qimage, array2qimage, alpha_view, rgb_view
from asyncabcs import SourceABC, RequestABC
from volumina.slicingtools import is_bounded, slicing2rect, rect2slicing, slicing2shape, is_pure_slicing
from volumina.config import cfg
import numpy as np

#*******************************************************************************
# I m a g e S o u r c e                                                        *
#*******************************************************************************

class ImageSource( QObject ):
    '''Partial implemented base class for image sources

    Signals:
    isDirty -- a rectangular region has changed; transmits
               an empty QRect if the whole image is dirty

    idChanged -- source represents a different image now (oldId, newId);
                 id is some immutable object

    '''

    isDirty = pyqtSignal( QRect )
    idChanged = pyqtSignal( object, object )

    @property
    def id( self ):
        return self.__id

    @id.setter
    def id( self, v):
        old = self.id
        self.__id = v
        self.idChanged.emit(old, v)

    def __init__( self, guarantees_opaqueness = False, parent = None ):
        super(ImageSource, self).__init__( parent = parent )
        self._opaque = guarantees_opaqueness
        self.__id = id(self)

    def request( self, rect ):
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
    def __init__( self, arraySource2D, layer ):
        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(GrayscaleImageSource, self).__init__( guarantees_opaqueness = True )
        self._arraySource2D = arraySource2D
        self.id = arraySource2D.id

        self._layer = layer
        
        self._arraySource2D.isDirty.connect(self.setDirty)
        self._arraySource2D.idChanged.connect(self._onIdChanged)
        self._layer.normalizeChanged.connect(lambda: self.setDirty((slice(None,None), slice(None,None))))

    def request( self, qrect ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  GrayscaleImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s)
        return GrayscaleImageRequest( req, self._layer.normalize[0] )

    def _onIdChanged( self, oldId, newId ):
        self.id = newId
        
assert issubclass(GrayscaleImageSource, SourceABC)

class GrayscaleImageRequest( object ):
    def __init__( self, arrayrequest, normalize=None ):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._normalize = normalize

    def wait(self):
        self._arrayreq.wait()
        return self.toImage()
        
    def toImage( self ):
        a = self._arrayreq.getResult()
        assert a.ndim == 2, "GrayscaleImageRequest.toImage(): result has shape %r, which is not 2-D" % (a.shape,)
        
        normalize = self._normalize 
        if normalize == 'auto':
            p1, p99 = np.percentile(a, [1,99])
            normalize = (p1, p99)
        img = gray2qimage(a, normalize)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            
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
        self.id = arraySource2D.id

        self._arraySource2D.isDirty.connect(self.setDirty)
        self._arraySource2D.idChanged.connect(self._onIdChanged)

    def request( self, qrect ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  AlphaModulatedImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s)
        return AlphaModulatedImageRequest( req, self._layer.tintColor, self._layer.normalize[0] )

    def _onIdChanged( self, oldId, newId ):
        self.id = newId
assert issubclass(AlphaModulatedImageSource, SourceABC)

class AlphaModulatedImageRequest( object ):
    def __init__( self, arrayrequest, tintColor, normalize=(0,255)):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._normalize = normalize
        self._tintColor = tintColor

    def wait(self):
        self._arrayreq.wait()
        return self.toImage()

    def toImage( self ):
        a = self._arrayreq.getResult()
        shape = a.shape + (4,)
        d = np.empty(shape, dtype=np.float32)
        d[:,:,0] = a[:,:]*self._tintColor.redF()
        d[:,:,1] = a[:,:]*self._tintColor.greenF()
        d[:,:,2] = a[:,:]*self._tintColor.blueF()
        d[:,:,3] = a[:,:]

        normalize = self._normalize
        if normalize == 'auto':
            p1, p99 = np.percentile(a, [1,99])
            normalize = (p1, p99)
        img = array2qimage(d, normalize)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)        
            
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
        super(ColortableImageSource, self).__init__()
        self._arraySource2D = arraySource2D
        self.id = arraySource2D.id

        self._arraySource2D.isDirty.connect(self.setDirty)
        self._arraySource2D.idChanged.connect(self._onIdChanged)        

        self._layer = layer        
        self.updateColorTable()
        self._layer.colorTableChanged.connect(self.updateColorTable)

    def updateColorTable(self):
        layerColorTable = self._layer.colorTable
        self._colorTable = np.zeros((len(layerColorTable), 4), dtype=np.uint8)
        for i, c in enumerate(layerColorTable):
            color = QColor.fromRgba(c)
            self._colorTable[i,0] = color.red()
            self._colorTable[i,1] = color.green()
            self._colorTable[i,2] = color.blue()
            self._colorTable[i,3] = color.alpha() 
        
    def request( self, qrect ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  ColortableImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d) = %r" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height(), rect2slicing(qrect)) \
            + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s)
        return ColortableImageRequest( req , self._colorTable)

    def _onIdChanged( self, oldId, newId ):
        self.id = newId
assert issubclass(ColortableImageSource, SourceABC)

class ColortableImageRequest( object ):
    def __init__( self, arrayrequest, colorTable):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._colorTable = colorTable

    def wait(self):
        self._arrayreq.wait()
        return self.toImage()
        
    def toImage( self ):
        a = self._arrayreq.getResult()
        assert a.ndim == 2

        #make sure that a has values in range [0, colortable_length)
        a = np.remainder(a, len(self._colorTable))
        #apply colortable
        img = self._colorTable[a]
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
        self.id = (red.id, green.id, blue.id, alpha.id)
        for arraySource in self._channels:
            arraySource.isDirty.connect(self.setDirty)
        for arraySource in self._channels:
            arraySource.idChanged.connect(self._onIdChanged)

    def request( self, qrect ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print Fore.RED + "  RGBAImageSource '%s' requests (x=%d, y=%d, w=%d, h=%d)" \
            % (self.objectName(), qrect.x(), qrect.y(), qrect.width(), qrect.height()) \
             + Fore.RESET
            volumina.printLock.release()
            
        assert isinstance(qrect, QRect)
        s = rect2slicing( qrect )
        r = self._channels[0].request(s)
        g = self._channels[1].request(s)
        b = self._channels[2].request(s)
        a = self._channels[3].request(s)
        shape = list( slicing2shape(s) )
        assert len(shape) == 2
        assert all([x > 0 for x in shape])
        return RGBAImageRequest( r, g, b, a, shape, *self._layer._normalize )
    def _onIdChanged( self, oldId, newId ):
        self.id = (self._channels[0].id, self._channels[1].id, self._channels[2].id, self._channels[3].id) 
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
                if normalize == 'auto':
                    p1, p99 = np.percentile(a, [1,99])
                    normalize = (p1, p99)
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
    def request( self, qrect ):
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

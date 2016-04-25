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
from volumina.utility import execute_in_main_thread
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

    def __init__( self, name, guarantees_opaqueness = False, parent = None, direct=False ):
        ''' direct: whether this request will be computed synchronously in the GUI thread (direct=True)
                    or whether the request will be put on a worker queue to be computed in a worker thread
                    (direct=False).
                    Only use direct=True if the layer's data will be immediately available'''
        super(ImageSource, self).__init__( parent = parent )
        self._opaque = guarantees_opaqueness
        self.direct = direct
        self.name = name

    def image_type(self):
        """
        Image sources must declare what type of "image" they will produce.
        The two allowed types are QImage and QGraphicsItems (and subclasses).
        """
        return QImage

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
        super(GrayscaleImageSource, self).__init__( layer.name, guarantees_opaqueness = True, direct=layer.direct )
        self._arraySource2D = arraySource2D

        self._layer = layer
        
        self._arraySource2D.isDirty.connect(self.setDirty)
        if hasattr(self._layer, "normalizeChanged"):
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
            
        # FIXME: It is obviously wrong to truncate like this (right?)
        if a.dtype == np.uint64 or a.dtype == np.int64:
            warnings.warn("Truncating 64-bit pixels for display")
            if a.dtype == np.uint64:
                a = np.asanyarray(a, np.uint32)
            elif a.dtype == np.int64:
                a = np.asanyarray(a, np.int32)

        has_no_mask = not np.ma.is_masked(a)

        #
        # new conversion
        #
        tImg = None
        if has_no_mask and _has_vigra and hasattr(vigra.colors, 'gray2qimage_ARGB32Premultiplied'):
            if not self._normalize or \
               self._normalize[0] >= self._normalize[1] or \
               self._normalize == [0, 0]: #FIXME: fix volumina conventions
                n = np.asarray([0, 255], dtype=a.dtype)
            else:
                n = np.asarray(self._normalize, dtype=a.dtype)
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            if not a.flags['C_CONTIGUOUS']:
                a = a.copy()
            vigra.colors.gray2qimage_ARGB32Premultiplied(a, byte_view(img), n)
            tImg = 1000.0*(time.time()-tImg)
        else:
            if has_no_mask:
                self.logger.warning("using slow image creation function")
            tImg = time.time()
            if self._normalize:
                #clipping has been implemented in this commit,
                #but it is not yet available in the packages obtained via easy_install
                #http://www.informatik.uni-hamburg.de/~meine/hg/qimage2ndarray/diff/fcddc70a6dea/qimage2ndarray/__init__.py
                a = np.clip(a, *self._normalize)
            img = gray2qimage(a, self._normalize)
            ret = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            tImg = 1000.0*(time.time()-tImg)
        
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            tTOT = 1000.0*(time.time()-t)
            self.logger.debug("toImage (%dx%d, normalize=%r) took %f msec. (array req: %f, wait: %f, img: %f)" % (img.width(), img.height(), normalize, tTOT, tAR, tWAIT, tImg))
            
        return img
            
assert issubclass(GrayscaleImageRequest, RequestABC)

#*******************************************************************************
# A l p h a M o d u l a t e d I m a g e S o u r c e                            *
#*******************************************************************************

class AlphaModulatedImageSource( ImageSource ):
    def __init__( self, arraySource2D, layer ):
        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(AlphaModulatedImageSource, self).__init__(layer.name)
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
        tWAIT = 1000.0*(time.time()-tWAIT)
        
        tAR = time.time()
        a = self._arrayreq.getResult()
        tAR = 1000.0*(time.time()-tAR)

        has_no_mask = not np.ma.is_masked(a)

        tImg = None
        if has_no_mask and _has_vigra and hasattr(vigra.colors, 'gray2qimage_ARGB32Premultiplied'):
            if not a.flags.contiguous:
                a = a.copy()
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            tintColor = np.asarray([self._tintColor.redF(), self._tintColor.greenF(), self._tintColor.blueF()], dtype=np.float32);
            normalize = np.asarray(self._normalize, dtype=a.dtype)
            if normalize[0] > normalize[1]:
                normalize = None
            vigra.colors.alphamodulated2qimage_ARGB32Premultiplied(a, byte_view(img), tintColor, normalize) 
            tImg = 1000.0*(time.time()-tImg)
        else:
            if has_no_mask:
                self.logger.warning("using unoptimized conversion functions")
            tImg = time.time()
            d = a[..., None].repeat(4, axis=-1)
            d[:,:,0] *= self._tintColor.redF()
            d[:,:,1] *= self._tintColor.greenF()
            d[:,:,2] *= self._tintColor.blueF()

            normalize = self._normalize
            img = array2qimage(d, normalize)
            img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)        
            tImg = 1000.0*(time.time()-tImg)
       
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            tTOT = 1000.0*(time.time()-t)
            self.logger.debug("toImage (%dx%d, normalize=%r) took %f msec. (array req: %f, wait: %f, img: %f)" % (img.width(), img.height(), normalize, tTOT, tAR, tWAIT, tImg))
            
        return img
    
assert issubclass(AlphaModulatedImageRequest, RequestABC)

#*******************************************************************************
# C o l o r t a b l e I m a g e S o u r c e                                    *
#*******************************************************************************

class ColortableImageSource( ImageSource ):
    loggingName = __name__ + ".ColortableImageSource"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arraySource2D, layer ):
        """ colorTable: a list of QRgba values """

        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(ColortableImageSource, self).__init__(layer.name, direct=layer.direct)
        self._arraySource2D = arraySource2D
        self._arraySource2D.isDirty.connect(self.setDirty)

        self._layer = layer
        self.updateColorTable()
        self._layer.colorTableChanged.connect(self.updateColorTable)
        if hasattr(self._layer, "normalizeChanged"):
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
    loggingName = __name__ + ".ColortableImageRequest"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arrayrequest, colorTable, normalize, direct=False ):
        self._mutex = QMutex()
        self._arrayreq = arrayrequest
        self._colorTable = colorTable
        self.direct = direct
        self._normalize = normalize
        assert not normalize or len(normalize) == 2

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
        
        assert a.ndim == 2

        if self._normalize and self._normalize[0] < self._normalize[1]:
            nmin, nmax = self._normalize
            if nmin:
                a = a - nmin
            scale = (len(self._colorTable)-1) / float(nmax - nmin + 1e-35) #if max==min
            if scale != 1.0:
                a = a * scale
            if len(self._colorTable) <= 2**8:
                a = np.asanyarray( a, dtype=np.uint8 )
            elif len(self._colorTable) <= 2**16:
                a = np.asanyarray( a, dtype=np.uint16 )
            elif len(self._colorTable) <= 2**32:
                a = np.asanyarray( a, dtype=np.uint32 )

        # Use vigra if possible (much faster)
        tImg = None
        if _has_vigra and hasattr(vigra.colors, 'applyColortable'):
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32)
            if not issubclass( a.dtype.type, np.integer ):
                raise NotImplementedError()
                #FIXME: maybe this should be done in a better way using an operator before the colortable request which properly handles 
                #this problem 
                warnings.warn("Data for colortable layers cannot be float, casting",RuntimeWarning)
                a = np.asanyarray(a, dtype=np.uint32)

            # If we have a masked array with a non-trivial mask, ensure that mask is made transparent.
            _colorTable = self._colorTable
            if np.ma.is_masked(a):
                # Add transparent color at the beginning of the colortable as needed.
                if (_colorTable[0, 3] != 0):
                    # If label 0 is unused, it can be transparent. Otherwise, the transparent color must be inserted.
                    if (a.min() == 0):
                        # If it will overflow simply promote the type. Unless we have reached the max VIGRA type.
                        if (a.max() == np.iinfo(a.dtype).max):
                            a_new_dtype = np.min_scalar_type(np.iinfo(a.dtype).max + 1)
                            if a_new_dtype <= np.dtype(np.uint32):
                                 a = np.asanyarray(a, dtype=a_new_dtype)
                            else:
                                assert (np.iinfo(a.dtype).max >= len(_colorTable)), \
                                       "This is a very large colortable. If it is indeed needed, add a transparent" + \
                                       " color at the beginning of the colortable for displaying masked arrays."

                                # Try to wrap the max value to a smaller value of the same color.
                                a[a == np.iinfo(a.dtype).max] %= len(_colorTable)

                        # Insert space for transparent color and shift labels up.
                        _colorTable = np.insert(_colorTable, 0, 0, axis=0)
                        a += 1
                    else:
                        # Make sure the first color is transparent.
                        _colorTable = _colorTable.copy()
                        _colorTable[0] = 0

                # Make masked values transparent.
                a = np.ma.filled(a, 0)

            vigra.colors.applyColortable(a, _colorTable, byte_view(img))
            tImg = 1000.0*(time.time()-tImg)

        # Without vigra, do it the slow way 
        else:
            raise NotImplementedError()
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
            
        if self.logger.getEffectiveLevel() >= logging.DEBUG:
            tTOT = 1000.0*(time.time()-t)
            self.logger.debug("toImage (%dx%d) took %f msec. (array req: %f, wait: %f, img: %f)" % (img.width(), img.height(), tTOT, tAR, tWAIT, tImg))

        return img 
    
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

        super(RGBAImageSource, self).__init__(layer.name,  guarantees_opaqueness = guarantees_opaqueness )
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
            a = req.getResult()
            normalize = self._normalize[i]
            if normalize is not None and \
               normalize[0] < normalize[1]:
                a = a.astype(np.float32)
                a = (a - normalize[0])*255.0 / (normalize[1]-normalize[0])
                a[a > 255] = 255
                a[a < 0]   = 0
                a = a.astype(np.uint8)
            self._data[:,:,i] = a
        img = array2qimage(self._data)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)        

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
            
assert issubclass(RandomImageRequest, RequestABC)


##
## Sources that produce QGraphicsItems isntead of QImages
##

from PyQt4.QtCore import Qt, QRect, QRectF, QSize
from PyQt4.QtGui import QGraphicsItem, QColor, QPen, QGraphicsLineItem
from contextlib import contextmanager
 
@contextmanager
def painter_context(painter):
    try:
        painter.save()
        yield
    finally:
        painter.restore()
 
class DummyItem( QGraphicsItem ):
    def __init__(self, rectf, parent=None):
        super( DummyItem, self ).__init__( parent )
        self.rectf = rectf
        self.line = QGraphicsLineItem( self.rectf.x(),
                                       self.rectf.y(),
                                       self.rectf.x() + self.rectf.width(),
                                       self.rectf.y() + self.rectf.height(),
                                       parent=self )
    
     
    def boundingRect(self):
        return self.rectf
     
    def paint(self, painter, option, widget=None):
        with painter_context(painter):
            pen = QPen(painter.pen())
            pen.setWidth(10.0)
            pen.setColor( QColor(255,0,0) )
            painter.setPen(pen)
            shrunken_rectf = self.rectf.adjusted(10,10,-10,-10)
            painter.drawRoundedRect(shrunken_rectf, 50, 50, Qt.RelativeSize)
    
    def mousePressEvent(self, event):
        print "You clicked on rect: {}".format( self.rectf )

    def mouseReleaseEvent(self, event):
        pass
 
class DummyItemRequest(object):
    def __init__(self, arrayreq, rect):
        self.rect = rect
        self._arrayreq = arrayreq
    
    def wait(self):
        array_data = self._arrayreq.wait()
        # Here's where we would do something with the data...
        assert array_data.shape == (self.rect.width(), self.rect.height())
        return execute_in_main_thread(DummyItem, QRectF(self.rect))

class DummyItemSource(ImageSource):
    def __init__( self, arraySource2D ):
        super( DummyItemSource, self ).__init__('dummy item')
        self._arraySource2D = arraySource2D
        
    def request( self, qrect, along_through=None ):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        arrayreq = self._arraySource2D.request(s, along_through)
        return DummyItemRequest(arrayreq, qrect)

class DummyRasterRequest(object):
    """
    For stupid tests.
    Uses DummyItem, but rasterizes it to turn it into a QImage.
    """
    def __init__(self, arrayreq, rect):
        self.rectf = QRectF(rect)
        self._arrayreq = arrayreq
    
    def wait(self):
        array_data = self._arrayreq.wait()
        rectf = self.rectf
        if array_data.handedness_switched: # array_data should be of type slicingtools.ProjectedArray
            rectf = QRectF(rectf.height(), rectf.width())
        
        from PyQt4.QtGui import QPainter
        img = QImage( QSize( self.rectf.width(), self.rectf.height() ), QImage.Format_ARGB32_Premultiplied)
        img.fill(0xffffffff)
        p = QPainter(img)
        p.drawImage(0,0, img)
        DummyItem(self.rectf).paint(p, None)
        return img

class DummyRasterItemSource(ImageSource):
    def request( self, qrect, along_through=None ):
        return DummyRasterRequest(qrect)


from volumina.utility.segmentationEdgesItem import SegmentationEdgesItem, generate_path_items_for_labels
class SegmentationEdgesItemSource(ImageSource):
    def __init__( self, layer, arraySource2D ):
        from volumina.layer import SegmentationEdgesLayer
        assert isinstance(layer, SegmentationEdgesLayer)
        
        super( SegmentationEdgesItemSource, self ).__init__(layer.name)
        self._arraySource2D = arraySource2D
        self._arraySource2D.isDirty.connect(self.setDirty)
        self._layer = layer

    def request( self, qrect, along_through=None ):
        assert isinstance(qrect, QRect)
        # Widen request with a 1-pixel halo, to make sure edges on the tile borders are shown.
        qrect = QRect( qrect.x(), qrect.y(), qrect.width()+1, qrect.height()+1 )
        s = rect2slicing(qrect)
        arrayreq = self._arraySource2D.request(s, along_through)
        return SegmentationEdgesItemRequest(arrayreq, self._layer, qrect)

    def image_type(self):
        return SegmentationEdgesItem

class SegmentationEdgesItemRequest(object):
    def __init__(self, arrayreq, layer, rect):
        self.rect = rect
        self._arrayreq = arrayreq
        self._layer = layer
    
    def wait(self):
        array_data = self._arrayreq.wait()
        
        # We can't make this assertion, because the array request might be expanded
        # with a halo so that the QGraphicsItem can display edges on tile borders.
        #assert array_data.shape == (self.rect.width(), self.rect.height())

        # Do the hard work outside the main thread: Construct the path items
        path_items = generate_path_items_for_labels(self._layer.pen_table, array_data, None)

        def create():
            # All SegmentationEdgesItem(s) associated with this layer will share a common pen table.
            # They react immediately when the pen table is updated.
            graphics_item = SegmentationEdgesItem(path_items, self._layer.pen_table)

            # When the item is clicked, the layer is notified.
            graphics_item.edgeClicked.connect( self._layer.handle_edge_clicked )
            return graphics_item
       
        # We're probably running in a non-main thread right now,
        # but we're only allowed to create QGraphicsItemObjects in the main thread.

        return execute_in_main_thread(create)

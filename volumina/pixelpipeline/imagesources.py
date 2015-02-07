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
                a = np.asanyarray(np.uint32)
            elif a.dtype == np.int64:
                a = np.asanyarray(np.int32)

        has_no_mask = not np.ma.is_masked(a)

        #
        # new conversion
        #
        tImg = None
        if has_no_mask and _has_vigra and hasattr(vigra.colors, 'gray2qimage_ARGB32Premultiplied'):
            if self._normalize is None or \
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
    loggingName = __name__ + ".ColortableImageSource"
    logger = logging.getLogger(loggingName)
    
    def __init__( self, arraySource2D, layer ):
        """ colorTable: a list of QRgba values """

        assert isinstance(arraySource2D, SourceABC), 'wrong type: %s' % str(type(arraySource2D))
        super(ColortableImageSource, self).__init__(direct=layer.direct)
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
        assert normalize is None or len(normalize) == 2

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
                # If there is no transparency color at the beginning of the colortable, add one. Skip otherwise.
                if (_colorTable[0, 3] != 0):
                    _colorTable = _colorTable.copy()  # Must add transparent color. Preserve original colortable.

                    # If label 0 is unused, it can be transparent. Otherwise, the transparent color must be inserted.
                    expand_colorTable = False
                    if (a.min() == 0):
                        expand_colorTable = True
                        # If it will overflow simply promote the type. Otherwise skip. Assume unsigned.
                        if (a.max() == np.iinfo(a.dtype).max):
                            if a.dtype.type == np.uint8:
                                a = np.asarray(a, dtype=np.uint16)
                            elif a.dtype.type == np.uint16:
                                a = np.asarray(a, dtype=np.uint32)
                            elif a.dtype.type == np.uint32:
                                # We have reached the largest type VIGRA supports. Need to free up a label/color.
                                if np.iinfo(a.dtype).max >= len(_colorTable):
                                    # Try to wrap the max value to a smaller value of the same color.
                                    a[a == np.iinfo(a.dtype).max] %= len(_colorTable)
                                else:
                                    assert(False,
                                           "Code for this feature has been added below and \"should\" work"
                                           + " as is. However, it is untested and is believed to be slow because the"
                                           + " size of the colortable is quite large and the number of integers is"
                                           + " believed to be quite large. Check to make sure what you are doing makes"
                                           + " sense. If so, feel free to comment this assert and proceed with caution.")
                                    # Otherwise, drop the first unused color from the colortable and remap everything.

                                    # Find non-consecutive labels. Get a mask for the first skipped label.
                                    a_values = np.unique(a)
                                    a_gap_mask = (np.ediff1d(a_values, to_begin=1) > 1)
                                    a_gap_mask &= (a_gap_mask.cumsum() == 1)

                                    # If this assertion occurs, chances are everything is going really slow.
                                    assert(a_gap_mask.any(),
                                           "Trying to display a masked array using a ColortableImageSource. However, a"
                                           + " a transparent color was not found and it was not possible to easily add"
                                           + " one as all valid integer values are already in use in the image. Add a"
                                           + " transparent color at the beginning of your colortable."
                                    )

                                    # Extract the gap value.
                                    a_gap_value = a_values[a_gap_mask][0]
                                    expand_colorTable = False

                                    # Reduce everything at the non-consecutive value and above by 1.
                                    a -= (a >= a_gap_value)
                                    # Overwrite the unused color by shifting all colors before it up.
                                    # This way we have room for the transparent color at the beginning.
                                    _colorTable[1:a_gap_value] = _colorTable[:a_gap_value-1]

                        a += 1

                    if expand_colorTable:
                        # Add room for one more
                        _colorTable_shape = list(_colorTable.shape)
                        _colorTable_shape[0] += 1
                        _colorTable_shape = tuple(_colorTable_shape)

                        # Create the larger color table.
                        _colorTable = np.empty(_colorTable_shape, dtype=_colorTable.dtype)

                        # Copy the rest of the colors over.
                        _colorTable[1:] = self._colorTable

                    # Make sure the first color is transparent.
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

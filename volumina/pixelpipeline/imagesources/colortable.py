import logging
import time
from typing import TYPE_CHECKING
import warnings

import numpy as np
from past.utils import old_div
from qtpy.QtCore import QRect
from qtpy.QtGui import QColor, QImage
from qimage2ndarray import array2qimage, byte_view

from volumina.pixelpipeline.interface import PlanarSliceSourceABC, RequestABC
from volumina.slicingtools import rect2slicing

from ._base import ImageSource, log_request

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False

if TYPE_CHECKING:
    from volumina.layer import ColortableLayer


logger = logging.getLogger(__name__)


class ColortableImageSource(ImageSource):
    loggingName = __name__ + ".ColortableImageSource"
    logger = logging.getLogger(loggingName)

    def __init__(self, arraySource2D, layer: "ColortableLayer"):
        """colorTable: a list of QRgba values"""

        assert isinstance(arraySource2D, PlanarSliceSourceABC), "wrong type: %s" % str(type(arraySource2D))
        super(ColortableImageSource, self).__init__(layer.name, direct=layer.direct, priority=layer.priority)
        self._arraySource2D = arraySource2D
        self._arraySource2D.isDirty.connect(self.setDirty)

        self._layer = layer
        self.updateColorTable()
        self._layer.colorTableChanged.connect(self.updateColorTable)
        if hasattr(self._layer, "normalizeChanged"):
            self._layer.normalizeChanged.connect(lambda: self.setDirty((slice(None, None), slice(None, None))))

    def updateColorTable(self):
        layerColorTable = self._layer.colorTable
        self._colorTable = np.zeros((len(layerColorTable), 4), dtype=np.uint8)

        for i, c in enumerate(layerColorTable):
            # note that we use qimage2ndarray.byte_view() on a QImage with Format_ARGB32 below.
            # this means that the memory layout actually is B, G, R, A

            if isinstance(c, QColor):
                color = c
            else:
                color = QColor.fromRgba(c)
            self._colorTable[i, 0] = color.blue()
            self._colorTable[i, 1] = color.green()
            self._colorTable[i, 2] = color.red()
            self._colorTable[i, 3] = color.alpha()

        self.isDirty.emit(QRect())  # empty rect == everything is dirty

    @log_request(logger)
    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return ColortableImageRequest(req, self._colorTable, self._layer.normalize[0], self.direct)


class ColortableImageRequest(RequestABC):
    loggingName = __name__ + ".ColortableImageRequest"
    logger = logging.getLogger(loggingName)

    def __init__(self, arrayrequest, colorTable, normalize, direct=False):
        self._arrayreq = arrayrequest
        self._colorTable = colorTable
        self.direct = direct
        self._normalize = normalize
        assert not normalize or len(normalize) == 2

    def wait(self):
        return self.toImage()

    def toImage(self):
        t = time.time()

        tWAIT = time.time()
        a = self._arrayreq.wait()
        tWAIT = 1000.0 * (time.time() - tWAIT)

        assert a.ndim == 2

        if a.dtype == np.bool_:
            a = a.view(np.uint8)

        if self._normalize and self._normalize[0] < self._normalize[1]:
            nmin, nmax = self._normalize
            if nmin:
                a = a - nmin
            scale = old_div((len(self._colorTable) - 1), float(nmax - nmin + 1e-35))  # if max==min
            if scale != 1.0:
                a = a * scale
            if len(self._colorTable) <= 2**8:
                a = np.asanyarray(a, dtype=np.uint8)
            elif len(self._colorTable) <= 2**16:
                a = np.asanyarray(a, dtype=np.uint16)
            elif len(self._colorTable) <= 2**32:
                a = np.asanyarray(a, dtype=np.uint32)

        # Use vigra if possible (much faster)
        tImg = None
        if _has_vigra and hasattr(vigra.colors, "applyColortable"):
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32)
            if not issubclass(a.dtype.type, np.integer):
                raise NotImplementedError()
                # FIXME: maybe this should be done in a better way using an operator before the colortable request which properly handles
                # this problem
                warnings.warn("Data for colortable layers cannot be float, casting", RuntimeWarning)
                a = np.asanyarray(a, dtype=np.uint32)

            # If we have a masked array with a non-trivial mask, ensure that mask is made transparent.
            _colorTable = self._colorTable
            if np.ma.is_masked(a):
                # Add transparent color at the beginning of the colortable as needed.
                if _colorTable[0, 3] != 0:
                    # If label 0 is unused, it can be transparent. Otherwise, the transparent color must be inserted.
                    if a.min() == 0:
                        # If it will overflow simply promote the type. Unless we have reached the max VIGRA type.
                        if a.max() == np.iinfo(a.dtype).max:
                            a_new_dtype = np.min_scalar_type(np.iinfo(a.dtype).max + 1)
                            if a_new_dtype <= np.dtype(np.uint32):
                                a = np.asanyarray(a, dtype=a_new_dtype)
                            else:
                                assert np.iinfo(a.dtype).max >= len(_colorTable), (
                                    "This is a very large colortable. If it is indeed needed, add a transparent"
                                    + " color at the beginning of the colortable for displaying masked arrays."
                                )

                                # Try to wrap the max value to a smaller value of the same color.
                                a[a == np.iinfo(a.dtype).max] %= len(_colorTable)

                        # Insert space for transparent color and shift labels up.
                        _colorTable = np.insert(_colorTable, 0, 0, axis=0)
                        a[:] = a + 1
                    else:
                        # Make sure the first color is transparent.
                        _colorTable = _colorTable.copy()
                        _colorTable[0] = 0

                # Make masked values transparent.
                a = np.ma.filled(a, 0)

            if a.dtype in (np.uint64, np.int64):
                # FIXME: applyColortable() doesn't support 64-bit, so just truncate
                a = a.astype(np.uint32)

            a = vigra.taggedView(a, "xy")
            vigra.colors.applyColortable(a, _colorTable, byte_view(img))
            tImg = 1000.0 * (time.time() - tImg)

        # Without vigra, do it the slow way
        else:
            raise NotImplementedError()
            if _has_vigra:
                # If this warning is annoying you, try this:
                # warnings.filterwarnings("once")
                warnings.warn("Using slow colortable images.  Upgrade to VIGRA > 1.9 to use faster implementation.")

            # make sure that a has values in range [0, colortable_length)
            a = np.remainder(a, len(self._colorTable))
            # apply colortable
            colortable = np.roll(
                np.fliplr(self._colorTable), -1, 1
            )  # self._colorTable is BGRA, but array2qimage wants RGBA
            img = colortable[a]
            img = array2qimage(img)

        if self.logger.isEnabledFor(logging.DEBUG):
            tTOT = 1000.0 * (time.time() - t)
            self.logger.debug(
                "toImage (%dx%d) took %f msec. (array wait: %f, img: %f)"
                % (img.width(), img.height(), tTOT, tWAIT, tImg)
            )

        return img

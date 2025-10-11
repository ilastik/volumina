import logging
import time
from typing import TYPE_CHECKING
import warnings

import numpy as np
from qtpy.QtCore import QRect
from qtpy.QtGui import QImage
from qimage2ndarray import byte_view, gray2qimage

from volumina.pixelpipeline.interface import PlanarSliceSourceABC, RequestABC
from volumina.slicingtools import rect2slicing

from ._base import ImageSource, log_request

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False


if TYPE_CHECKING:
    from volumina.layer import GrayscaleLayer

logger = logging.getLogger(__name__)


class GrayscaleImageSource(ImageSource):
    loggingName = __name__ + ".GrayscaleImageSource"
    logger = logging.getLogger(loggingName)

    def __init__(self, arraySource2D, layer: "GrayscaleLayer"):
        assert isinstance(arraySource2D, PlanarSliceSourceABC), "wrong type: %s" % str(type(arraySource2D))
        super(GrayscaleImageSource, self).__init__(
            layer.name, guarantees_opaqueness=True, direct=layer.direct, priority=layer.priority
        )
        self._arraySource2D = arraySource2D

        self._layer = layer

        self._arraySource2D.isDirty.connect(self.setDirty)
        if hasattr(self._layer, "normalizeChanged"):
            self._layer.normalizeChanged.connect(lambda: self.setDirty((slice(None, None), slice(None, None))))

    @log_request(logger)
    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return GrayscaleImageRequest(req, self._layer.normalize[0], direct=self.direct)


class GrayscaleImageRequest(RequestABC):
    loggingName = __name__ + ".GrayscaleImageRequest"
    logger = logging.getLogger(loggingName)

    def __init__(self, arrayrequest, normalize=None, direct=False):
        self._arrayreq = arrayrequest
        self._normalize = normalize
        self.direct = direct

    def wait(self):
        return self.toImage()

    def toImage(self):
        t = time.time()

        tWAIT = time.time()
        a = self._arrayreq.wait()
        tWAIT = 1000.0 * (time.time() - tWAIT)

        assert a.ndim == 2, "GrayscaleImageRequest.toImage(): result has shape %r, which is not 2-D" % (a.shape,)

        normalize = self._normalize
        if not normalize:
            normalize = [0, 255]

        # FIXME: It is obviously wrong to truncate like this (right?)
        if a.dtype == np.uint64 or a.dtype == np.int64:
            warnings.warn("Truncating 64-bit pixels for display")
            if a.dtype == np.uint64:
                a = np.asanyarray(a, np.uint32)
            elif a.dtype == np.int64:
                a = np.asanyarray(a, np.int32)

        if a.dtype == np.bool_:
            a = a.view(np.uint8)

        has_no_mask = not np.ma.is_masked(a)

        #
        # new conversion
        #
        tImg = None
        if has_no_mask and _has_vigra and hasattr(vigra.colors, "gray2qimage_ARGB32Premultiplied"):
            if (
                not self._normalize or self._normalize[0] >= self._normalize[1] or self._normalize == [0, 0]
            ):  # FIXME: fix volumina conventions
                n = np.asarray([0, 255], dtype=np.float32)
            else:
                n = np.asarray(self._normalize, dtype=np.float32)
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            if not a.flags["C_CONTIGUOUS"]:
                a = a.copy()
            vigra.colors.gray2qimage_ARGB32Premultiplied(a, byte_view(img), n)
            tImg = 1000.0 * (time.time() - tImg)
        else:
            if has_no_mask:
                self.logger.warning("using slow image creation function")
            tImg = time.time()
            if self._normalize:
                # clipping has been implemented in this commit,
                # but it is not yet available in the packages obtained via easy_install
                # http://www.informatik.uni-hamburg.de/~meine/hg/qimage2ndarray/diff/fcddc70a6dea/qimage2ndarray/__init__.py
                a = np.clip(a, *self._normalize)
            img = gray2qimage(a, self._normalize)
            ret = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            tImg = 1000.0 * (time.time() - tImg)

        if self.logger.isEnabledFor(logging.DEBUG):
            tTOT = 1000.0 * (time.time() - t)
            self.logger.debug(
                "toImage (%dx%d, normalize=%r) took %f msec. (array wait: %f, img: %f)"
                % (img.width(), img.height(), normalize, tTOT, tWAIT, tImg)
            )

        return img


# *******************************************************************************

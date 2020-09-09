import logging
import time

import numpy as np
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage
from qimage2ndarray import array2qimage, byte_view

from volumina.pixelpipeline.interface import PlanarSliceSourceABC, RequestABC
from volumina.slicingtools import rect2slicing

from ._base import ImageSource, log_request

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False


logger = logging.getLogger(__name__)


class AlphaModulatedImageSource(ImageSource):
    def __init__(self, arraySource2D, layer):
        assert isinstance(arraySource2D, PlanarSliceSourceABC), "wrong type: %s" % str(type(arraySource2D))
        super(AlphaModulatedImageSource, self).__init__(layer.name)
        self._arraySource2D = arraySource2D
        self._layer = layer

        self._arraySource2D.isDirty.connect(self.setDirty)

    @log_request(logger)
    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        req = self._arraySource2D.request(s, along_through)
        return AlphaModulatedImageRequest(req, self._layer.tintColor, self._layer.normalize[0])


class AlphaModulatedImageRequest(RequestABC):
    loggingName = __name__ + ".AlphaModulatedImageRequest"
    logger = logging.getLogger(loggingName)

    def __init__(self, arrayrequest, tintColor, normalize=(0, 255)):
        self._arrayreq = arrayrequest
        self._normalize = normalize
        self._tintColor = tintColor

    def wait(self):
        return self.toImage()

    def cancel(self):
        self._arrayreq.cancel()

    def toImage(self):
        t = time.time()

        tWAIT = time.time()
        a = self._arrayreq.wait()
        tWAIT = 1000.0 * (time.time() - tWAIT)

        has_no_mask = not np.ma.is_masked(a)

        tImg = None
        if has_no_mask and _has_vigra and hasattr(vigra.colors, "gray2qimage_ARGB32Premultiplied"):
            if not a.flags.contiguous:
                a = a.copy()
            tImg = time.time()
            img = QImage(a.shape[1], a.shape[0], QImage.Format_ARGB32_Premultiplied)
            tintColor = np.asarray(
                [self._tintColor.redF(), self._tintColor.greenF(), self._tintColor.blueF()], dtype=np.float32
            )
            normalize = np.asarray(self._normalize, dtype=np.float32)
            if normalize[0] > normalize[1]:
                normalize = np.array((0.0, 255.0)).astype(np.float32)
            vigra.colors.alphamodulated2qimage_ARGB32Premultiplied(a, byte_view(img), tintColor, normalize)
            tImg = 1000.0 * (time.time() - tImg)
        else:
            if has_no_mask:
                self.logger.warning("using unoptimized conversion functions")
            tImg = time.time()
            d = a[..., None].repeat(4, axis=-1)
            d[:, :, 0] = d[:, :, 0] * self._tintColor.redF()
            d[:, :, 1] = d[:, :, 1] * self._tintColor.greenF()
            d[:, :, 2] = d[:, :, 2] * self._tintColor.blueF()

            normalize = self._normalize
            img = array2qimage(d, normalize)
            img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
            tImg = 1000.0 * (time.time() - tImg)

        if self.logger.isEnabledFor(logging.DEBUG):
            tTOT = 1000.0 * (time.time() - t)
            self.logger.debug(
                "toImage (%dx%d, normalize=%r) took %f msec. (array wait: %f, img: %f)"
                % (img.width(), img.height(), normalize, tTOT, tWAIT, tImg)
            )

        return img

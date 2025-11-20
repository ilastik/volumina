import logging
from typing import TYPE_CHECKING

import numpy as np
from qtpy.QtCore import QRect
from qtpy.QtGui import QImage
from qimage2ndarray import array2qimage

from volumina.pixelpipeline.interface import PlanarSliceSourceABC, RequestABC
from volumina.slicingtools import rect2slicing, slicing2shape

from ._base import ImageSource, log_request

_has_vigra = True
try:
    pass
except ImportError:
    _has_vigra = False

if TYPE_CHECKING:
    from volumina.layer import RGBALayer

logger = logging.getLogger(__name__)


class RGBAImageSource(ImageSource):
    def __init__(self, red, green, blue, alpha, layer: "RGBALayer", guarantees_opaqueness=False):
        """
        If you don't want to set all the channels,
        a ConstantSource may be used as a replacement for
        the missing channels.

        red, green, blue, alpha - 2d array sources

        """
        self._layer = layer
        channels = [red, green, blue, alpha]
        for channel in channels:
            assert isinstance(channel, PlanarSliceSourceABC), "channel has wrong type: %s" % str(type(channel))

        super(RGBAImageSource, self).__init__(
            layer.name, guarantees_opaqueness=guarantees_opaqueness, priority=layer.priority
        )
        self._channels = channels
        for arraySource in self._channels:
            arraySource.isDirty.connect(self.setDirty)

    @log_request(logger)
    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        r = self._channels[0].request(s, along_through)
        g = self._channels[1].request(s, along_through)
        b = self._channels[2].request(s, along_through)
        a = self._channels[3].request(s, along_through)
        shape = list(slicing2shape(s))
        assert len(shape) == 2
        assert all([x > 0 for x in shape])
        return RGBAImageRequest(r, g, b, a, shape, *self._layer._normalize)


class RGBAImageRequest(RequestABC):
    def __init__(self, r, g, b, a, shape, normalizeR=None, normalizeG=None, normalizeB=None, normalizeA=None):
        self._requests = r, g, b, a
        self._normalize = [n or None for n in [normalizeR, normalizeG, normalizeB, normalizeA]]
        shape.append(4)
        self._data = np.empty(shape, dtype=np.uint8)
        self._requestsFinished = 4 * [False]

    def wait(self):
        for req in self._requests:
            req.wait()
        return self.toImage()

    def toImage(self):
        for i, req in enumerate(self._requests):
            a = req.wait()
            normalize = self._normalize[i]
            if normalize is not None and normalize[0] < normalize[1]:
                a = a.astype(np.float32)
                a = (a - normalize[0]) * 255.0 / (normalize[1] - normalize[0])
                a[a > 255] = 255
                a[a < 0] = 0
                a = a.astype(np.uint8)
            self._data[:, :, i] = a
        img = array2qimage(self._data)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)

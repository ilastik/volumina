import logging

import numpy as np
from qtpy.QtCore import QRect
from qtpy.QtGui import QImage
from qimage2ndarray import gray2qimage

from volumina.pixelpipeline.interface import RequestABC
from volumina.slicingtools import rect2slicing, slicing2shape

from ._base import ImageSource

_has_vigra = True
try:
    pass
except ImportError:
    _has_vigra = False


logger = logging.getLogger(__name__)


class RandomImageSource(ImageSource):
    """Random noise image for testing and debugging."""

    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        shape = slicing2shape(s)
        return RandomImageRequest(shape)


class RandomImageRequest(RequestABC):
    def __init__(self, shape):
        self.shape = shape

    def wait(self):
        d = (np.random.random(self.shape) * 255).astype(np.uint8)
        assert d.ndim == 2
        img = gray2qimage(d)
        return img.convertToFormat(QImage.Format_ARGB32_Premultiplied)

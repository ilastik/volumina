import functools

from qtpy.QtCore import QObject, QRect, Signal
from qtpy.QtGui import QImage

from volumina import config
from volumina.pixelpipeline.interface import ImageSourceABC
from volumina.slicingtools import is_bounded, is_pure_slicing, slicing2rect


class ImageSource(QObject, ImageSourceABC):
    """Partial implemented base class for image sources

    Signals:
    isDirty -- a rectangular region has changed; transmits
               an empty QRect if the whole image is dirty

    """

    isDirty = Signal(QRect)

    def __init__(self, name, guarantees_opaqueness=False, parent=None, direct=False, priority: int = 0):
        """direct: whether this request will be computed synchronously in the GUI thread (direct=True)
        or whether the request will be put on a worker queue to be computed in a worker thread
        (direct=False).
        Only use direct=True if the layer's data will be immediately available"""
        super(ImageSource, self).__init__(parent=parent)
        self._opaque = guarantees_opaqueness
        self.direct = direct
        self.name = name
        self._priority = priority

    @property
    def priority(self) -> int:
        """Priority for requests from this image source

        Larger values indicate higher priority.

        See `tileProvider.TileProvider._refreshTile`
        """
        return self._priority

    def image_type(self):
        """
        Image sources must declare what type of "image" they will produce.
        The two allowed types are QImage and QGraphicsItems (and subclasses).
        """
        return QImage

    def request(self, rect, along_through=None):
        raise NotImplementedError

    def setDirty(self, slicing):
        """Mark a region of the image as dirty.

        slicing -- if one ore more slices in the slicing
                   are unbounded, the whole image is marked dirty;
                   since an image has two dimensions, only the first
                   two slices in the slicing are used

        """
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        if not is_bounded(slicing):
            self.isDirty.emit(QRect())  # empty rect == everything is dirty
        else:
            self.isDirty.emit(slicing2rect(slicing))

    def isOpaque(self):
        """Image is opaque everywhere (i.e. no pixel has an alpha value != 255).

        If the ImageSource can give an opaqueness guarantee,
        performance can be improved since layers occluded by this
        source don't have to be rendered in some cases.

        Warning: Can cause rendering bugs: In doubt return False.

        """
        return self._opaque


def log_request(logger):
    def _log_request(func):
        @functools.wraps(func)
        def _wrapper(source: "ImageSource", qrect, *args, **kwargs):
            if config.CONFIG.verbose_pixelpipeline:
                logger.error(
                    "%s '%s' requests (x=%d, y=%d, w=%d, h=%d)",
                    type(source).__qualname__,
                    source.objectName(),
                    qrect.x(),
                    qrect.y(),
                    qrect.width(),
                    qrect.height(),
                )
            return func(source, qrect, *args, **kwargs)

        return _wrapper

    return _log_request

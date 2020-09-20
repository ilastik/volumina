import logging
from contextlib import contextmanager

from PyQt5.QtCore import QRect, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QImage, QPen
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem

from volumina.pixelpipeline.interface import RequestABC
from volumina.slicingtools import rect2slicing
from volumina.utility import execute_in_main_thread

from ._base import ImageSource

logger = logging.getLogger(__name__)


@contextmanager
def painter_context(painter):
    try:
        painter.save()
        yield
    finally:
        painter.restore()


class DummyItem(QGraphicsItem):
    def __init__(self, rectf, parent=None):
        super(DummyItem, self).__init__(parent)
        self.rectf = rectf
        self.line = QGraphicsLineItem(
            self.rectf.x(),
            self.rectf.y(),
            self.rectf.x() + self.rectf.width(),
            self.rectf.y() + self.rectf.height(),
            parent=self,
        )

    def boundingRect(self):
        return self.rectf

    def paint(self, painter, option, widget=None):
        with painter_context(painter):
            pen = QPen(painter.pen())
            pen.setWidth(10.0)
            pen.setColor(QColor(255, 0, 0))
            painter.setPen(pen)
            shrunken_rectf = self.rectf.adjusted(10, 10, -10, -10)
            painter.drawRoundedRect(shrunken_rectf, 50, 50, Qt.RelativeSize)

    def mousePressEvent(self, event):
        print("You clicked on rect: {}".format(self.rectf))

    def mouseReleaseEvent(self, event):
        pass


class DummyItemRequest(RequestABC):
    def __init__(self, arrayreq, rect):
        self.rect = rect
        self._arrayreq = arrayreq

    def wait(self):
        array_data = self._arrayreq.wait()
        # Here's where we would do something with the data...
        assert array_data.shape == (self.rect.width(), self.rect.height())
        return execute_in_main_thread(DummyItem, QRectF(self.rect))


class DummyItemSource(ImageSource):
    def __init__(self, arraySource2D):
        super(DummyItemSource, self).__init__("dummy item")
        self._arraySource2D = arraySource2D

    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        s = rect2slicing(qrect)
        arrayreq = self._arraySource2D.request(s, along_through)
        return DummyItemRequest(arrayreq, qrect)


class DummyRasterRequest(RequestABC):
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
        if array_data.handedness_switched:  # array_data should be of type slicingtools.ProjectedArray
            rectf = QRectF(rectf.height(), rectf.width())

        from PyQt5.QtWidgets import QPainter

        img = QImage(QSize(self.rectf.width(), self.rectf.height()), QImage.Format_ARGB32_Premultiplied)
        img.fill(0xFFFFFFFF)
        p = QPainter(img)
        p.drawImage(0, 0, img)
        DummyItem(self.rectf).paint(p, None)
        return img


class DummyRasterItemSource(ImageSource):
    def __init__(self, arraySource2D):
        super().__init__("dummy item")
        self._arraySource2D = arraySource2D

    def request(self, qrect, along_through=None):
        return DummyRasterRequest(qrect)

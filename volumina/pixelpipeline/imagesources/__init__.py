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
# 		   http://ilastik.org/license/
###############################################################################
from past.utils import old_div
import logging
import time
import warnings
import functools


from PyQt5.QtCore import QObject, QRect, pyqtSignal
from PyQt5.QtGui import QImage, QColor
from qimage2ndarray import gray2qimage, array2qimage, alpha_view, rgb_view, byte_view
from volumina.pixelpipeline.interface import DataSourceABC, ImageSourceABC, PlanarSliceSourceABC, RequestABC
from volumina.slicingtools import is_bounded, slicing2rect, rect2slicing, slicing2shape, is_pure_slicing
from volumina.utility import execute_in_main_thread
import numpy as np
from ._base import ImageSource, log_request
from .grayscale import GrayscaleImageSource
from .alphamodulated import AlphaModulatedImageSource
from .colortable import ColortableImageSource
from .rgba import RGBAImageSource
from .random import RandomImageSource
from .dummy import DummyItemSource, DummyRasterItemSource

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False


logger = logging.getLogger(__name__)

##
## Sources that produce QGraphicsItems isntead of QImages
##

from PyQt5.QtCore import Qt, QRect, QRectF, QSize
from PyQt5.QtWidgets import QGraphicsItem, QGraphicsLineItem
from PyQt5.QtGui import QColor, QPen
from contextlib import contextmanager


from volumina.utility.segmentationEdgesItem import SegmentationEdgesItem, generate_path_items_for_labels


class SegmentationEdgesItemSource(ImageSource):
    def __init__(self, layer, arraySource2D, is_clickable):
        from volumina.layer import SegmentationEdgesLayer

        assert isinstance(layer, SegmentationEdgesLayer)

        super(SegmentationEdgesItemSource, self).__init__(layer.name)
        self._arraySource2D = arraySource2D
        self._arraySource2D.isDirty.connect(self.setDirty)
        self._layer = layer
        self._is_clickable = is_clickable

    def request(self, qrect, along_through=None):
        assert isinstance(qrect, QRect)
        # Widen request with a 1-pixel halo, to make sure edges on the tile borders are shown.
        qrect = QRect(qrect.x(), qrect.y(), qrect.width() + 1, qrect.height() + 1)
        s = rect2slicing(qrect)
        arrayreq = self._arraySource2D.request(s, along_through)
        return SegmentationEdgesItemRequest(arrayreq, self._layer, qrect, self._is_clickable)

    def image_type(self):
        return SegmentationEdgesItem


class SegmentationEdgesItemRequest(RequestABC):
    def __init__(self, arrayreq, layer, rect, is_clickable):
        self.rect = rect
        self._arrayreq = arrayreq
        self._layer = layer
        self._is_clickable = is_clickable

    def wait(self):
        array_data = self._arrayreq.wait()

        # We can't make this assertion, because the array request might be expanded
        # with a halo so that the QGraphicsItem can display edges on tile borders.
        # assert array_data.shape == (self.rect.width(), self.rect.height())

        def create():
            # Construct the path items
            # This *could* be done outside of this create() function (and thus outside of the main thread),
            # but (1) that seems to cause crashes on shutdown,
            # and (2) performance gets worse, not better.
            path_items = generate_path_items_for_labels(
                self._layer.pen_table, self._layer.default_pen, array_data, None
            )

            # All SegmentationEdgesItem(s) associated with this layer will share a common pen table.
            # They react immediately when the pen table is updated.
            graphics_item = SegmentationEdgesItem(
                path_items, self._layer.pen_table, self._layer.default_pen, self._is_clickable
            )

            # When the item is clicked, the layer is notified.
            graphics_item.edgeClicked.connect(self._layer.handle_edge_clicked)
            graphics_item.edgeSwiped.connect(self._layer.handle_edge_swiped)
            return graphics_item

        # We're probably running in a non-main thread right now,
        # but we're only allowed to create QGraphicsItemObjects in the main thread.

        return execute_in_main_thread(create)

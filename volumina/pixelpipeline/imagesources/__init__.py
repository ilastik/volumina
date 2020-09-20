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
from .segmentationedges import SegmentationEdgesItemSource

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

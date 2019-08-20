from __future__ import print_function
from __future__ import absolute_import

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
import sys
import threading
import logging
import weakref
from functools import partial, wraps
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from volumina.pixelpipeline.asyncabcs import RequestABC, SourceABC, IndeterminateRequestError
import volumina
from volumina.slicingtools import is_pure_slicing, slicing2shape, is_bounded, make_bounded, index2slice, sl
from volumina.config import CONFIG
import numpy as np
from future.utils import raise_with_traceback

from .array import ArraySource, ArraySinkSource, RelabelingArraySource
from .constant import ConstantSource
from .minmax import MinMaxSource

try:
    from .lazyflow import LazyflowSource, LazyflowSinkSource
except ImportError:
    pass


class HaloAdjustedDataSource(QObject):
    """
    A wrapper for other datasources.
    For any datasource request, expands the requested ROI by a halo
    and forwards the expanded request to the underlying datasouce object.
    """

    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)

    def __init__(self, rawSource, halo_start_delta, halo_stop_delta, parent=None):
        """
        rawSource: The original datasource that we'll be requesting data from.
        halo_start_delta: For example, to expand by 1 pixel in spatial dimensions only:
                          (0,-1,-1,-1,0)
        halo_stop_delta: For example, to expand by 1 pixel in spatial dimensions only:
                          (0,1,1,1,0)
        """
        super(HaloAdjustedDataSource, self).__init__(parent)
        self._rawSource = rawSource
        self._rawSource.isDirty.connect(self.setDirty)
        self._rawSource.numberOfChannelsChanged.connect(self.numberOfChannelsChanged)

        assert all(s <= 0 for s in halo_start_delta), "Halo start should be non-positive"
        assert all(s >= 0 for s in halo_stop_delta), "Halo stop should be non-negative"
        self.halo_start_delta = halo_start_delta
        self.halo_stop_delta = halo_stop_delta

    @property
    def numberOfChannels(self):
        return self._rawSource.numberOfChannels

    def clean_up(self):
        self._rawSource.clean_up()

    @property
    def dataSlot(self):
        if hasattr(self._rawSource, "_orig_outslot"):
            return self._rawSource._orig_outslot
        else:
            return None

    def dtype(self):
        return self._rawSource.dtype()

    def request(self, slicing):
        slicing_with_halo = self._expand_slicing_with_halo(slicing)
        return self._rawSource.request(slicing_with_halo)

    def setDirty(self, slicing):
        # FIXME: This assumes the halo is symmetric
        slicing_with_halo = self._expand_slicing_with_halo(slicing)
        self.isDirty.emit(slicing_with_halo)

    def __eq__(self, other):
        equal = True
        if other is None:
            return False
        equal &= isinstance(other, type(self))
        equal &= self._rawSource == other._rawSource
        return equal

    def __ne__(self, other):
        return not (self == other)

    def _expand_slicing_with_halo(self, slicing):
        return tuple(
            slice(s.start + halo_start, s.stop + halo_stop)
            for (s, halo_start, halo_stop) in zip(slicing, self.halo_start_delta, self.halo_stop_delta)
        )

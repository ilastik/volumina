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

try:
    from .lazyflow import LazyflowSource, LazyflowSinkSource
except ImportError:
    pass


# *******************************************************************************
# C o n s t a n t R e q u e s t                                                *
# *******************************************************************************


class ConstantRequest(object):
    def __init__(self, result):
        self._result = result

    def wait(self):
        return self._result

    def getResult(self):
        return self._result

    def cancel(self):
        pass

    def submit(self):
        pass

    def adjustPriority(self, delta):
        pass


assert issubclass(ConstantRequest, RequestABC)

# *******************************************************************************
# C o n s t a n t S o u r c e                                                  *
# *******************************************************************************


class ConstantSource(QObject):
    isDirty = pyqtSignal(object)
    idChanged = pyqtSignal(object, object)  # old, new
    numberOfChannelsChanged = pyqtSignal(int)  # Never emitted

    @property
    def constant(self):
        return self._constant

    @property
    def numberOfChannels(self):
        return 1

    @constant.setter
    def constant(self, value):
        self._constant = value
        self.setDirty(sl[:, :, :, :, :])

    def __init__(self, constant=0, dtype=np.uint8, parent=None):
        super(ConstantSource, self).__init__(parent=parent)
        self._constant = constant
        self._dtype = dtype

    def clean_up(self):
        pass

    def id(self):
        return id(self)

    def request(self, slicing, through=None):
        assert is_pure_slicing(slicing)
        assert is_bounded(slicing)
        shape = slicing2shape(slicing)
        result = np.full(shape, self._constant, dtype=self._dtype)
        return ConstantRequest(result)

    def setDirty(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        self.isDirty.emit(slicing)

    def __eq__(self, other):
        if other is None:
            return False
        return self._constant == other._constant

    def __ne__(self, other):
        return not (self == other)

    def dtype(self):
        return self._dtype


assert issubclass(ConstantSource, SourceABC)


class MinMaxUpdateRequest(object):
    def __init__(self, rawRequest, update_func):
        self._rawRequest = rawRequest
        self._update_func = update_func

    def wait(self):
        rawData = self._rawRequest.wait()
        self._result = rawData
        self._update_func(rawData)
        return self._result

    def getResult(self):
        return self._result


assert issubclass(MinMaxUpdateRequest, RequestABC)


class MinMaxSource(QObject):
    """
    A datasource that serves as a normalizing decorator for other datasources.
    """

    isDirty = pyqtSignal(object)
    boundsChanged = pyqtSignal(
        object
    )  # When a new min/max is discovered in the result of a request, this signal is fired with the new (dmin, dmax)
    numberOfChannelsChanged = pyqtSignal(int)

    _delayedBoundsChange = (
        pyqtSignal()
    )  # Internal use only.  Allows non-main threads to start the delayedDirtySignal timer.

    def __init__(self, rawSource, parent=None):
        """
        rawSource: The original datasource whose data will be normalized
        """
        super(MinMaxSource, self).__init__(parent)

        self._rawSource = rawSource
        self._rawSource.isDirty.connect(self.isDirty)
        self._rawSource.numberOfChannelsChanged.connect(self.numberOfChannelsChanged)
        self.reset_bounds()
        self._delayedDirtySignal = QTimer()
        self._delayedDirtySignal.setSingleShot(True)
        self._delayedDirtySignal.setInterval(10)
        self._delayedDirtySignal.timeout.connect(partial(self.setDirty, sl[:, :, :, :, :]))
        self._delayedBoundsChange.connect(self._delayedDirtySignal.start)

    def reset_bounds(self):
        self._bounds = [1e9, -1e9]

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
        rawRequest = self._rawSource.request(slicing)
        return MinMaxUpdateRequest(rawRequest, self._getMinMax)

    def setDirty(self, slicing):
        self.isDirty.emit(slicing)

    def __eq__(self, other):
        equal = True
        if other is None:
            return False
        equal &= isinstance(other, MinMaxSource)
        equal &= self._rawSource == other._rawSource
        return equal

    def __ne__(self, other):
        return not (self == other)

    def _getMinMax(self, data):
        dmin = np.min(data)
        dmax = np.max(data)
        dmin = min(self._bounds[0], dmin)
        dmax = max(self._bounds[1], dmax)
        dirty = False
        if (self._bounds[0] - dmin) > 1e-2:
            dirty = True
        if (dmax - self._bounds[1]) > 1e-2:
            dirty = True

        if dirty:
            self._bounds[0] = dmin
            self._bounds[1] = dmax
            self.boundsChanged.emit(self._bounds)

            # Our min/max have changed, which means we must force the TileProvider to re-request all tiles.
            # If we simply mark everything dirty now, then nothing changes for the tile we just rendered.
            # (It was already dirty.  That's why we are rendering it right now.)
            # And when this data gets back to the TileProvider that requested it, the TileProvider will mark this tile clean again.
            # To ENSURE that the current tile is marked dirty AFTER the TileProvider has stored this data (and marked the tile clean),
            #  we'll use a timer to set everything dirty.
            # This fixes ilastik issue #418

            # Finally, note that before this timer was added, the problem described above occurred at random due to a race condition:
            # Sometimes the 'dirty' signal was processed BEFORE the data (bad) and sometimes it was processed after the data (good),
            # due to the fact that the Qt signals are always delivered in the main thread.
            # Perhaps a better way to fix this would be to store a timestamp in the TileProvider for dirty notifications, which
            # could be compared with the request timestamp before clearing the dirty state for each tile.

            # Signal everything dirty with a timer, as described above.
            self._delayedBoundsChange.emit()

            # Now, that said, we can still give a slightly more snappy response to the OTHER tiles (not this one)
            # if we immediately tell the TileProvider we are dirty.  This duplicates some requests, but that shouldn't be a big deal.
            self.setDirty(sl[:, :, :, :, :])


assert issubclass(MinMaxSource, SourceABC)


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

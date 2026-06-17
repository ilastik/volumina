from functools import partial
from typing import Any, Callable

import numpy as np
from numpy import typing as npt
from qtpy.QtCore import QObject, Signal, QTimer

from volumina.pixelpipeline.interface import DataRequestABC, DataSourceABC, Slice5D
from volumina.slicingtools import sl
from volumina.utility.sparseLazyHistogram import SparseLazyHistogram


class MinMaxUpdateRequest(DataRequestABC):
    def __init__(
        self,
        rawRequest: DataRequestABC,
        update_func: Callable[[npt.NDArray[np.number[Any]]], None],
        commit_func: Callable[[Slice5D], None],
        needs_update_func: Callable[[Any], bool],
        slicing: Slice5D,
    ):
        self._rawRequest = rawRequest
        self._update_func = update_func
        self._commit_func = commit_func
        self._needs_update_func = needs_update_func
        self._slicing = slicing
        self._result = None

    def wait(self):
        rawData = self._rawRequest.wait()

        if self._result is None:
            self._result = rawData
            if self._needs_update_func(self.slicing):
                self._commit_func(self.slicing)
                self._update_func(rawData)

        return self._result


class MinMaxSource(QObject, DataSourceABC):
    """
    A datasource that serves as a normalizing decorator for other datasources.
    """

    isDirty = Signal(object)
    boundsChanged = Signal(
        object
    )  # When a new min/max is discovered in the result of a request, this signal is fired with the new (dmin, dmax)
    numberOfChannelsChanged = Signal(int)
    histogramChanged = Signal()

    _delayedBoundsChange = (
        Signal()
    )  # Internal use only.  Allows non-main threads to start the delayedDirtySignal timer.

    def __init__(self, rawSource: DataSourceABC, parent=None):
        """
        rawSource: The original datasource whose data will be normalized
        """
        super(MinMaxSource, self).__init__(parent)

        self._rawSource = rawSource
        self._rawSource.isDirty.connect(self._handle_dirty)
        self._rawSource.numberOfChannelsChanged.connect(self.numberOfChannelsChanged)
        self.reset_bounds()
        self._delayedDirtySignal = QTimer()
        self._delayedDirtySignal.setSingleShot(True)
        self._delayedDirtySignal.setInterval(10)
        self._delayedDirtySignal.timeout.connect(partial(self.setDirty, sl[:, :, :, :, :]))
        self._delayedBoundsChange.connect(self._delayedDirtySignal.start)

    def reset_bounds(self):
        self._bounds: tuple[int | float, int | float] = (1e9, -1e9)
        self._seen = []
        self._hist = SparseLazyHistogram()

    def _handle_dirty(self, key):
        self.reset_bounds()
        self.isDirty.emit(key)

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

    def _needs_update(self, slicing: Slice5D):
        return slicing not in self._seen

    def request(self, slicing: Slice5D):
        rawRequest = self._rawSource.request(slicing)
        return MinMaxUpdateRequest(
            rawRequest,
            update_func=self._getMinMax,
            commit_func=self._commit_func,
            needs_update_func=self._needs_update,
            slicing=slicing,
        )

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

    def get_histogram(self):
        return self._hist.get_sparse_histogram()

    def _commit_func(self, slicing: Slice5D):
        self._seen.append(slicing)

    def _getMinMax(self, data: npt.NDArray[np.number[Any]]):
        self._hist.update(data)
        dmin, dmax = self._hist.data_range
        dmin = min(self._bounds[0], dmin) if dmin is not None else self._bounds[0]
        dmax = max(self._bounds[1], dmax) if dmax is not None else self._bounds[1]

        dirty = False
        if (self._bounds[0] - dmin) > 1e-2:
            dirty = True
        if (dmax - self._bounds[1]) > 1e-2:
            dirty = True

        if dirty:
            self._bounds = (dmin, dmax)
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

        self.histogramChanged.emit()

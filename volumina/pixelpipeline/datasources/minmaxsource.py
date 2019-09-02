from functools import partial

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, QTimer

from volumina.pixelpipeline.datasources.interface import DataSourceABC, DataRequestABC
from volumina.slicingtools import sl


class MinMaxUpdateRequest(DataRequestABC):
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


class MinMaxSource(QObject, DataSourceABC):
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

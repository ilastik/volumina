from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.datasources.interface import DataSourceABC


class HaloAdjustedDataSource(QObject, DataSourceABC):
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

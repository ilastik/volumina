import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from volumina.pixelpipeline.interface import DataSourceABC, RequestABC
from volumina.slicingtools import is_pure_slicing, index2slice


class ArrayRequest(RequestABC):
    def __init__(self, array, slicing):
        self._array = array
        self._slicing = slicing
        self._result = None

    def wait(self):
        if self._result is None:
            self._result = self._array[self._slicing]
        return self._result

    def cancel(self):
        pass

    def submit(self):
        pass


class ArraySource(QObject, DataSourceABC):
    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)  # Never emitted

    def __init__(self, array):
        super(ArraySource, self).__init__()
        self._array = array

    @property
    def numberOfChannels(self):
        return self._array.shape[-1]

    def clean_up(self):
        self._array = None

    def dtype(self):
        if isinstance(self._array.dtype, type):
            return self._array.dtype
        return self._array.dtype.type

    def request(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("ArraySource: slicing is not pure")
        assert len(slicing) == len(
            self._array.shape
        ), "slicing into an array of shape=%r requested, but slicing is %r" % (slicing, self._array.shape)
        return ArrayRequest(self._array, slicing)

    def setDirty(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        self.isDirty.emit(slicing)

    def __eq__(self, other):
        if other is None:
            return False
        # Use id for efficiency
        return self._array is other._array

    def __ne__(self, other):
        return not (self == other)


class ArraySinkSource(ArraySource):
    eraser_value = None

    def put(self, slicing, subarray):
        """Make an update of the wrapped arrays content.

        Elements with neutral value in the subarray are not written into the
        wrapped array, but the original values are kept.

        """
        assert len(slicing) == len(
            self._array.shape
        ), "slicing into an array of shape=%r requested, but the slicing object is %r" % (slicing, self._array.shape)
        self._array[slicing] = subarray
        pure = index2slice(slicing)
        self.setDirty(pure)


class RelabelingArraySource(ArraySource):
    """Applies a relabeling to each request before passing it on
    Currently, it casts everything to uint8, so be careful."""

    isDirty = pyqtSignal(object)

    def __init__(self, array):
        super(RelabelingArraySource, self).__init__(array)
        self.originalData = array
        self._relabeling = None

    def setRelabeling(self, relabeling):
        """Sets new relabeling vector. It should have a len(relabling) == max(your data)+1
        and give, for each possible data value x, the relabling as relabeling[x]."""
        assert relabeling.dtype == self._array.dtype, "relabeling.dtype=%r != self._array.dtype=%r" % (
            relabeling.dtype,
            self._array.dtype,
        )
        self._relabeling = relabeling
        self.setDirty(5 * (slice(None),))

    def clearRelabeling(self):
        self._relabeling[:] = 0
        self.setDirty(5 * (slice(None),))

    def setRelabelingEntry(self, index, value, setDirty=True):
        """Sets the entry for data value index to value, such that afterwards
        relabeling[index] =  value.

        If setDirty is true, the source will signal dirtyness. If you plan to issue many calls to this function
        in a loop, setDirty to true only on the last call."""
        self._relabeling[index] = value
        if setDirty:
            self.setDirty(5 * (slice(None),))

    def request(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("ArraySource: slicing is not pure")
        assert len(slicing) == len(
            self._array.shape
        ), "slicing into an array of shape=%r requested, but slicing is %r" % (self._array.shape, slicing)
        a = ArrayRequest(self._array, slicing)
        a = a.wait()

        # oldDtype = a.dtype
        if self._relabeling is not None:
            a = self._relabeling[a]
        # assert a.dtype == oldDtype
        return ArrayRequest(a, 5 * (slice(None),))

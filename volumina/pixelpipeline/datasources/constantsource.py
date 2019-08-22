import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from volumina.slicingtools import is_pure_slicing, slicing2shape, is_bounded, sl
from volumina.pixelpipeline.datasources.interface import IDataSource, IDataRequest


class ConstantRequest(IDataRequest):
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


class ConstantSource(QObject, IDataSource):
    isDirty = pyqtSignal(object)
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
        self._cache = {}

    def clean_up(self):
        pass

    def id(self):
        return id(self)

    def request(self, slicing):
        assert is_pure_slicing(slicing)
        assert is_bounded(slicing)
        shape = slicing2shape(slicing)
        key = (shape, self._constant, self._dtype)

        if key not in self._cache:
            result = np.full(shape, self._constant, dtype=self._dtype)
            result.setflags(write=False)
            self._cache[key] = result

        return ConstantRequest(self._cache[key])

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

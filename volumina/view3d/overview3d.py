from os.path import split, join

from PyQt4.QtGui import QWidget
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PyQt4.uic import loadUiType

from numpy import all as np_all

from .meshgenerator import labeling_to_mesh


class Overview3D(QWidget):
    slice_changed = pyqtSignal(int, int)
    reinitialized = pyqtSignal()  # TODO: this is stupid
    dock_status_changed = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        cls, _ = loadUiType(join(split(__file__)[0], "ui/view3d.ui"))
        self._ui = cls()
        self._ui.setupUi(self)

        self._view = self._ui.view
        """:type: GLView"""

        self.reinitialized.emit()

    @staticmethod
    def _adjust_axes(x, y, z):
        return z, y, x

    @property
    def shape(self):
        return self._adjust_axes(*self._view.shape)

    @shape.setter
    def shape(self, shape):
        self._view.shape = self._adjust_axes(*shape)

    @property
    def slice(self):
        return self._adjust_axes(*self._view.slice)

    @slice.setter
    def slice(self, slice_):
        self._view.slice = self._adjust_axes(*slice_)

    @pyqtSlot(bool, name="on_toggle_slice_x_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_y_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_z_clicked")
    def _on_toggle_slice(self, down):
        sender = self.sender()
        self._view.toggle_slice(str(sender.objectName()[-1]), down)

    @pyqtSlot(bool, name="on_dock_clicked")
    def _on_dock_status_changed(self, status):
        self.dock_status_changed.emit(status)

    # TODO: compatibility, remove
    @property
    def qvtk(self):
        return self

    @property
    def renderer(self):
        return self

    def update(self):
        super(Overview3D, self).update()

    def set_volume(self, volume):
        # noinspection PyTypeChecker
        if np_all(volume == 0):
            self._view.toggle_mesh(False)
        else:
            item = labeling_to_mesh(volume)
            self._view.set_mesh(item)

    def toggle_volume(self, show):
        self._view.toggle_mesh(show)

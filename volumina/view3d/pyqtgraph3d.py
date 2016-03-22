from os.path import split, join

from PyQt4.QtGui import QWidget
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PyQt4.uic import loadUiType

from pyqtgraph.opengl import GLViewWidget, MeshData, GLMeshItem, GLBoxItem
from pyqtgraph.functions import isosurface

from numpy import all as npall


def labeling_to_mesh(labeling):
    from datetime import datetime
    from sys import stdout

    start = datetime.now()
    print "generate mesh... ",
    stdout.flush()

    vertices, faces = isosurface(labeling, level=0.5)
    mesh = MeshData(vertices, faces)
    color = [255, 0, 255, 255]
    item = GLMeshItem(meshdata=mesh, color=color, smooth=True,
                      shader="viewNormalColor")
    print "{}s".format((datetime.now() - start).total_seconds())
    return item


class View3D(QWidget):
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
    def _adjust_coords(x, y, z):
        return z, y, x

    @property
    def shape(self):
        return self._adjust_coords(*self._view.shape)

    @shape.setter
    def shape(self, shape):
        self._view.shape = self._adjust_coords(*shape)

    @property
    def slice(self):
        return self._adjust_coords(*self._view.slice)

    @slice.setter
    def slice(self, slice_):
        self._view.slice = self._adjust_coords(*slice_)

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
        super(View3D, self).update()

    def set_volume(self, volume):
        if npall(volume == 0):
            self._view.toggle_mesh(False)
        else:
            item = labeling_to_mesh(volume)
            self._view.set_mesh(item)

    def toggle_volume(self, show):
        self._view.toggle_mesh(show)


class Slices(object):
    BOX_COLORS = ([0, 0, 255, 255],
                  [0, 255, 0, 255],
                  [255, 0, 0, 255])

    def __init__(self, view):
        self._slices = [GLBoxItem() for _ in "xyz"]
        self._axes = [GLBoxItem() for _ in "xyz"]
        self._pos = [0, 0, 0]
        for slice_, color in zip(self._slices, self.BOX_COLORS):
            slice_.setSize(0, 0, 0)
            slice_.setColor(color)
        for axis in self._axes:
            axis.setSize(0, 0, 0)
            axis.setColor([0, 0, 0, 255])
        self._x, self._y, self._z = self._slices
        self._xx, self._yy, self._zz = self._axes
        [view.addItem(item) for item in self]

    def __iter__(self):
        yield self._x
        yield self._y
        yield self._z
        yield self._xx
        yield self._yy
        yield self._zz

    def set_shape(self, x, y, z):
        self._x.setSize(0, y, z)
        self._y.setSize(x, 0, z)
        self._z.setSize(x, y, 0)

        self._xx.setSize(x, 0, 0)
        self._yy.setSize(0, y, 0)
        self._zz.setSize(0, 0, z)

    def move_to(self, x, y, z):
        [item.resetTransform() for item in self]

        self._x.translate(x, 0, 0)
        self._y.translate(0, y, 0)
        self._z.translate(0, 0, z)

        self._xx.translate(0, y, z)
        self._yy.translate(x, 0, z)
        self._zz.translate(x, y, 0)

        self._pos = [x, y, z]

    def toggle(self, axis, visible):
        slice_ = getattr(self, "_{}".format(axis))
        slice_.setVisible(visible)


class GLView(GLViewWidget):
    def __init__(self, parent=None):
        GLViewWidget.__init__(self, parent)
        self.setBackgroundColor([255, 255, 255])
        self._shape = (1, 1, 1)
        self._slice = None
        self._slice_planes = Slices(self)
        self._mesh = None

    def set_mesh(self, mesh):
        if self._mesh is not None:
            self.removeItem(self._mesh)
        self._mesh = mesh
        self.addItem(mesh)

    def toggle_mesh(self, show):
        self._mesh.setVisible(show)

    @property
    def slice(self):
        return self._slice

    @slice.setter
    def slice(self, slice_):
        self._slice_planes.move_to(*slice_)

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, shape):
        x, y, z = self._shape
        self.pan(-x / 2, -y / 2, -z / 2)

        self._shape = shape
        x, y, z = shape

        self._slice_planes.set_shape(x, y, z)

        self.pan(x / 2, y / 2, z / 2)
        self.setCameraPosition(distance=1.5 * max(x, y, z))

    def toggle_slice(self, axis, visible):
        self._slice_planes.toggle(axis, visible)

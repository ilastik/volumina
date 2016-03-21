from os.path import split, join

from PyQt4.QtGui import QWidget
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PyQt4.uic import loadUiType

from pyqtgraph.opengl import GLViewWidget, MeshData, GLMeshItem, GLBoxItem
from pyqtgraph.functions import isosurface


mem = "__nope__"
count = 0


def printm(*args):
    from sys import stdout
    global count
    global mem
    if mem != args:
        count = 0
        stdout.write("\n")
        for arg in args:
            stdout.write(repr(arg))
            stdout.write(" ")
        stdout.write(" 00000")
    count += 1
    mem = args
    stdout.write("\b\b\b\b\b\b {: 5}".format(count))
    stdout.flush()


def printm(*args):
    print args


class Printer(object):
            def __str__(self):
                return "<Printer {}>".format(self.name)

            def __repr__(self):
                return self.__str__()

            def __init__(self, name):
                self.name = name

            def __getattr__(self, item):
                name = "{}.{}".format(self, item)
                printm("get", name)
                return Printer(name)

            def __getitem__(self, item):
                name = "{}[{}]".format(self, repr(item))
                printm(name)
                return Printer(name)

            def __call__(self, *args, **kwargs):
                argn = ",".join(str(i) for i in args)
                kwargn = ",".join("{}={}".format(*i) for i in kwargs.items())
                name = "{}({})".format(self, argn, kwargn)
                printm(name)
                return Printer(name)


def labeling_to_mesh(labeling):
    verts, faces = isosurface(labeling, level=0.5)
    mesh = MeshData(verts, faces)
    item = GLMeshItem(meshdata=mesh)
    return item


class View3D(QWidget):
    slice_changed = pyqtSignal(int, int)
    reinitialized = pyqtSignal()

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
        return -x, -z, -y

    def change_slice(self, slice_):
        self._view.set_slice(*self._adjust_coords(*slice_))

    def __hasattr__(self, item):
        printm("hasattr", item)
        return GLViewWidget.__hasattr__(self, item)

    def add_object(self, obj):
        item = labeling_to_mesh(obj)
        self._view.addItem(item)

    @pyqtSlot(bool, name="on_toggle_slice_x_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_y_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_z_clicked")
    def _on_toggle_slice(self, down):
        sender = self.sender()
        self._view.toggle_slice(str(sender.objectName()[-1]), down)

    @property
    def data_shape(self):
        return self._view.shape

    @data_shape.setter
    def data_shape(self, shape):
        self._view.shape = self._adjust_coords(*shape)

    def add_volume(self, *args):
        pass

    # TODO: compatibility, remove
    changedSlice = slice_changed
    ChangeSlice = change_slice
    AddVolume = add_volume

    @property
    def qvtk(self):
        return self

    @property
    def renderer(self):
        return self

    @property
    def bUndock(self):
        return self._ui.dock

    @property
    def dataShape(self):
        print("dataShape")
        raise "FUCK YOU"


class Slices(object):
    BOX_COLOR = [0, 0, 0, 255]
    AXIS_COLORS = ([255, 0, 0, 255],
                   [0, 0, 255, 255],
                   [0, 255, 0, 255])

    def __init__(self, view):
        self._slices = [GLBoxItem() for _ in "xyz"]
        self._axes = [GLBoxItem() for _ in "xyz"]
        self._pos = [0, 0, 0]
        for slice_ in self._slices:
            slice_.setSize(0, 0, 0)
            slice_.setColor(self.BOX_COLOR)  # black rgba
        for axis, color in zip(self._axes, self.AXIS_COLORS):
            axis.setSize(0, 0, 0)
            axis.setColor(color)
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
        self._slices = Slices(self)

    def toggle_slice(self, axis, visible):
        self._slices.toggle(axis, visible)

    def set_slice(self, x, y, z):
        self._slices.move_to(x, y, z)

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, shape):
        print "Shape", shape
        x, y, z = self._shape
        self.pan(-x / 2, -y / 2, -z / 2)

        self._shape = shape
        x, y, z = shape

        self._slices.set_shape(x, y, z)

        self.pan(x / 2, y / 2, z / 2)
        self.setCameraPosition(distance=-1.5 * min(x, y, z))

    # TODO: compatibility, remove

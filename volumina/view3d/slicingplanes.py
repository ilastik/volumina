from pyqtgraph.opengl import GLBoxItem


class SlicingPlanes(object):
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

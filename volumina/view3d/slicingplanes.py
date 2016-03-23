from pyqtgraph.opengl import GLBoxItem


class SlicingPlanes(object):
    """
    A container class for the 3 opengl box items to indicate the current slice.

    The slicing planes are colored according to the slices in the 2d view:
    blue, green, red (ordered like this because the axes are swapped)

    :ivar Sequence[Sequence[int]] BOX_COLORS: the 3 colors for the boxes, e.g. [r, g, b, a]
    """
    BOX_COLORS = ([0, 0, 255, 255],
                  [0, 255, 0, 255],
                  [255, 0, 0, 255])

    def __init__(self, view):
        """
        Creates the box items and adds them to the 3d view.

        :param GLViewWidget view: the 3d view to add the planes to
        """
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
        """
        Set the shape for all planes

        :param int x: the size of the data set in x direction
        :param int y: the size of the data set in y direction
        :param int z: the size of the data set in z direction
        """
        self._x.setSize(0, y, z)
        self._y.setSize(x, 0, z)
        self._z.setSize(x, y, 0)

        self._xx.setSize(x, 0, 0)
        self._yy.setSize(0, y, 0)
        self._zz.setSize(0, 0, z)

    def move_to(self, x, y, z):
        """
        Move the slice planes to the given position

        This is called whenever the user changes the slice in the 2d views.
        Either by scrolling or dragging a slice indicator.

        :param int x: the x coordinate
        :param int y: the y coordinate
        :param int z: the z coordinate
        """
        [item.resetTransform() for item in self]

        self._x.translate(x, 0, 0)
        self._y.translate(0, y, 0)
        self._z.translate(0, 0, z)

        self._xx.translate(0, y, z)
        self._yy.translate(x, 0, z)
        self._zz.translate(x, y, 0)

        self._pos = [x, y, z]

    def toggle(self, axis, visible):
        """
        Toggle the display of a specific slicing plane

        :param str axis: the corresponding axis for the plane to toggle ("x", "y", "z")
        :param bool visible: shows the plane if True otherwise hide the plane
        """
        slice_ = getattr(self, "_{}".format(axis))
        slice_.setVisible(visible)

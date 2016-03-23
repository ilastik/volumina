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
        self._pos = 0, 0, 0
        self._max = 0, 0, 0
        for slice_, color in zip(self._slices, self.BOX_COLORS):
            slice_.setSize(0, 0, 0)
            slice_.setColor(color)
        for axis in self._axes:
            axis.setSize(0, 0, 0)
            axis.setColor([0, 0, 0, 255])
        self._x, self._y, self._z = self._slices
        self._xx, self._yy, self._zz = self._axes
        [view.addItem(item) for item in self]

        self._selection = None
        self._selected_axis = None

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
        self._max = x - 1, y - 1, z - 1

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
        if x < 0 or y < 0 or z < 0 or x > self._max[0] or y > self._max[1] or z > self._max[2]:
            return

        [item.resetTransform() for item in self]

        self._x.translate(x, 0, 0)
        self._y.translate(0, y, 0)
        self._z.translate(0, 0, z)

        self._xx.translate(0, y, z)
        self._yy.translate(x, 0, z)
        self._zz.translate(x, y, 0)

        self._pos = x, y, z

    @property
    def position(self):
        """
        The slicing position

        :rtype: Tuple[Union[float, int], Union[float, int], Union[float, int]]
        """
        return self._pos

    def toggle(self, axis, visible):
        """
        Toggle the display of a specific slicing plane.

        :param str axis: the corresponding axis for the plane to toggle ("x", "y", "z")
        :param bool visible: shows the plane if True otherwise hide the plane
        """
        slice_ = getattr(self, "_{}".format(axis))
        slice_.setVisible(visible)

    def select(self, item):
        """
        Select the clicked item if it is a slicing plane.

        :param GLGraphicsItem item: the item so check and select
        """
        for axis, plane in enumerate((self._x, self._y, self._z)):
            if item is plane:
                r, g, b, a = item.color()
                item.setColor([r/2, g/2, b/2, a])
                item.update()
                self._selection = item
                self._selected_axis = axis
                return

    def release(self):
        """
        Clear the currently selected slicing plane
        """
        if self._selection is not None:
            r, g, b, a = self._selection.color()
            self._selection.setColor([r*2, g*2, b*2, a])
            self._selection.update()
        self._selection = None

    def drag(self, *coords):
        """
        Drag the currently selected slicing plane to the given coordinates

        Only one coordinate will be used depending on the slicing plane

        :param Tuple[float, float, float] coords: the x, y, z coordinates
        """
        pos = list(self._pos)
        pos[self._selected_axis] += coords[self._selected_axis]
        self.move_to(*pos)

    def has_selection(self):
        """
        Check if a slicing plane is currently selected

        :rtype: bool
        """
        return self._selection is not None

from pyqtgraph.opengl import GLMeshItem, MeshData


def make_arrow(color):
    """
    Create an axis arrow mesh and wrap it in a GLMeshItem.

    :param Sequence[float] color: the color for the arrow, e.g. [r, g, b, a]
    """
    mesh = MeshData.cylinder(10, 10)
    item = GLMeshItem(meshdata=mesh, color=color)
    return item


def make_center():
    """
    Create a marker for the center and wrap it in a GLMeshItem.
    """
    mesh = MeshData.sphere(10, 10, 1)
    item = GLMeshItem(meshdata=mesh, color=[0.4, 0.4, 0.4, 1])
    return item


class AxesSymbols(object):
    """
    Container class for the 3 coordinate axis indicators

    :ivar float RADIUS_SCALE: the factor to scale the axis arrow's radius depending on the data set's shape
    :ivar float LENGTH_SCALE: the factor to scale the axis arrow's length depending on the data set's shape
    """
    RADIUS_SCALE = 1 / 40.0
    LENGTH_SCALE = 1 / 2.0

    def __init__(self, view):
        """
        Create the axis arrows and add them to the 3d view

        :param GLViewWidget view: the 3d view to add the planes to
        """
        self._x = make_arrow([0, 0, 1, 1])
        self._y = make_arrow([0, 1, 0, 1])
        self._z = make_arrow([1, 0, 0, 1])
        self._center = make_center()

        self._y.rotate(-90, 1, 0, 0)
        self._z.rotate(90, 0, 1, 0)

        [view.addItem(arrow) for arrow in self._x, self._y, self._z, self._center]

    def set_shape(self, x, y, z):
        """
        Set the shape for all arrows

        The length and radius of the axis is determined by the shortest dimension.

        :param int x: the size of the data set in x direction
        :param int y: the size of the data set in y direction
        :param int z: the size of the data set in z direction
        """
        shortest = min(x, y, z)
        radius = shortest * self.RADIUS_SCALE
        length = shortest * self.LENGTH_SCALE

        self._x.scale(radius / 2, radius / 2, length)
        self._y.scale(radius, radius, length)
        self._z.scale(radius / 2, radius / 2, length)
        self._center.scale(radius + 1, radius + 1, radius + 1)

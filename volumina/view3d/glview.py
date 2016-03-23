from pyqtgraph.opengl import GLViewWidget

from .slicingplanes import SlicingPlanes
from .axessymbols import AxesSymbols


class GLView(GLViewWidget):
    """
    The actual 3D view seen in the bottom right corner of ilastik.

    This class handles all the 3d drawing including slicing planes and axis arrows.

    Note: this class is referenced by name in ui/view3d.ui as volumina.view3d.glview.GLView
    For the promotion to work this path may not change. If if does, the promotion in the ui file
    has to be altered.
    """

    def __init__(self, parent=None):
        GLViewWidget.__init__(self, parent)
        self.setBackgroundColor([1, 1, 1])
        self._shape = (1, 1, 1)
        self._slice = None
        self._slice_planes = SlicingPlanes(self)
        self._arrows = AxesSymbols(self)
        self._mesh = None

    def set_mesh(self, mesh):
        """
        Sets the mesh to render in this view

        The old mesh is remove first

        :param GLMeshItem mesh: the mesh to render
        """
        if self._mesh is not None:
            self.removeItem(self._mesh)
        self._mesh = mesh
        self.addItem(mesh)

    def toggle_mesh(self, show):
        """
        Toggle the display of the mesh.

        :param bool show: True to show and False to hide
        """
        self._mesh.setVisible(show)

    @property
    def slice(self):
        """
        Get the current slice represented by the slicing planes in this view.

        not used right now, as the slice cannot be changed easily in pyqtgraph.
        """
        return self._slice

    @slice.setter
    def slice(self, slice_):
        """
        Change the current slice and move the slicing planes accordingly.

        :param Sequence[int] slice_: x, y, z for the new slicing position
        """
        self._slice_planes.move_to(*slice_)

    @property
    def shape(self):
        return self._shape

    @shape.setter
    def shape(self, shape):
        """
        Set the shape for the slicing planes.

        :param Sequence[int] shape: x, y, z for the new dimensions of the slicing planes
        """
        x, y, z = self._shape
        self.pan(-x / 2, -y / 2, -z / 2)

        self._shape = shape
        x, y, z = shape

        self._slice_planes.set_shape(x, y, z)
        self._arrows.set_shape(x, y, z)

        self.pan(x / 2, y / 2, z / 2)
        self.setCameraPosition(distance=1.5 * max(x, y, z))

    def toggle_slice(self, axis, visible):
        """
        Toggle the visibility of a given slicing plane.

        :param str axis: identifier for the slicing plane to hide ("x", "y", "z")
        :param bool visible: True to show, False to hide
        """
        self._slice_planes.toggle(axis, visible)

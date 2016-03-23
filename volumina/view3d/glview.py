from pyqtgraph.opengl import GLViewWidget

from .slicingplanes import SlicingPlanes
from .axessymbols import AxesSymbols


class GLView(GLViewWidget):
    """
    Note: this class is referenced by name in ui/view3d.ui as volumina.view3d.glview.GLView

    For the promotion to work this path may not change. If if does, the promotion in the ui file
    has to be altered
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
        self._arrows.set_shape(x, y, z)

        self.pan(x / 2, y / 2, z / 2)
        self.setCameraPosition(distance=1.5 * max(x, y, z))

    def toggle_slice(self, axis, visible):
        self._slice_planes.toggle(axis, visible)

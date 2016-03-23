from pyqtgraph.opengl import GLViewWidget

from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QVector4D

from volumina.view3d.slicingplanes import SlicingPlanes
from volumina.view3d.axessymbols import AxesSymbols


class GLView(GLViewWidget):
    """
    The actual 3D view seen in the bottom right corner of ilastik.

    This class handles all the 3d drawing including slicing planes and axis arrows.

    Note: this class is referenced by name in ui/view3d.ui as volumina.view3d.glview.GLView
    For the promotion to work this path may not change. If if does, the promotion in the ui file
    has to be altered.

    signal:
        slice_changed: emitted when the user dragged one of the slicing planes
    """
    slice_changed = pyqtSignal()

    def __init__(self, parent=None):
        GLViewWidget.__init__(self, parent)
        self.setBackgroundColor([1, 1, 1])
        self._shape = (1, 1, 1)
        self._slice_planes = SlicingPlanes(self)
        self._arrows = AxesSymbols(self)
        self._mesh = None

        self._mouse_pos = None

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
        """
        return self._slice_planes.position

    @slice.setter
    def slice(self, slice_):
        """
        Change the current slice and move the slicing planes accordingly.

        :param Sequence[int] slice_: x, y, z for the new slicing position
        """
        self._slice_planes.move_to(*slice_)

    def set_shape(self, shape):
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

    shape = property(fset=set_shape)

    def toggle_slice(self, axis, visible):
        """
        Toggle the visibility of a given slicing plane.

        :param str axis: identifier for the slicing plane to hide ("x", "y", "z")
        :param bool visible: True to show, False to hide
        """
        self._slice_planes.toggle(axis, visible)

    def mouseMoveEvent(self, event):
        """
        The Qt event handler when the mouse is dragged.

        If a slice plane is selected the slice plane is dragged otherwise the scene is rotated.

        :param QMouseEvent event: the qt mouse event
        """
        if self._slice_planes.has_selection():
            x, y = event.x(), event.y()
            m = self.viewMatrix()
            dx = x - self._mouse_pos[0]
            dy = y - self._mouse_pos[1]
            vec = QVector4D(dx, -dy, 0, 0) * m
            dx, dy, dz = vec.x(), vec.y(), vec.z()
            self._mouse_pos = x, y
            self._slice_planes.drag(dx, dy, dz)
            self.slice_changed.emit()
        else:
            return GLViewWidget.mouseMoveEvent(self, event)

    def mousePressEvent(self, event):
        """
        The Qt event handler when the mouse is pressed down

        If a slicing plane was clicked select it and save the mouse position.
        Otherwise pass the event to the parent class.

        :param QMouseEvent event: the qt mouse event
        """
        x, y = event.x(), event.y()
        hits = self.itemsAt((x - 10, y - 10, 20, 20))
        if hits:
            self._mouse_pos = x, y
            self._slice_planes.select(hits[0])
        return GLViewWidget.mousePressEvent(self, event)

    def mouseReleaseEvent(self, event):
        """
        The Qt event handler when the mouse is released

        Release potentially selected slicing planes.
        Then pass the event to the parent class

        :param QMouseEvent event: the qt mouse event
        """
        self._slice_planes.release()
        return GLViewWidget.mousePressEvent(self, event)

from pyqtgraph.opengl import GLViewWidget

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QVector4D
from PyQt5.QtWidgets import QLabel

from volumina.view3d.slicingplanes import SlicingPlanes
from volumina.view3d.axessymbols import AxesSymbols
from volumina.utility import PreferencesManager
import volumina.config

import logging

logger = logging.getLogger(__name__)


class GLViewReal(GLViewWidget):
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
        self.setBackgroundColor(PreferencesManager().get("GLView", "backgroundColor", default=[255, 255, 255]))
        self._shape = (1, 1, 1)
        self._slice_planes = SlicingPlanes(self)
        self._arrows = AxesSymbols(self)

        self._mouse_pos = None

        self._meshes = {}
        # Make sure the layout stays the same no matter if the 3D widget is on/off
        size_policy = self.sizePolicy()
        size_policy.setRetainSizeWhenHidden(True)
        self.setSizePolicy(size_policy)

    def add_mesh(self, name, mesh=None):
        """
        Add a mesh to the 3d view

        If the mesh is cached it is simply shown. Otherwise it needs to be provided by the
        mesh parameter. The mesh parameter will always override the cached version if present.

        :param int name: the object's name
        :param Optional[GLMeshItem] mesh: the mesh item to store/override
        """
        if mesh is None:
            self._meshes[name].show()
        else:
            if name in self._meshes:
                self.removeItem(self._meshes[name])
            self._meshes[name] = mesh
            self.addItem(mesh)

    def remove_mesh(self, name):
        """
        Removes the mesh by its name from the view.

        It is cached so the next call to add_mesh will show it again

        :param str name: the object's name
        """
        self._meshes[name].hide()

    def is_cached(self, name):
        """
        Check if the given name is cached.

        :param str name: the name to check
        :rtype: bool
        """
        return name in self._meshes

    def invalidate_cache(self, name):
        """
        Remove the mesh by the given name from the cache to force an update.

        Also removes the mesh from the scene.

        :param str name: the name for the mesh
        """
        mesh = self._meshes.pop(name, None)
        if mesh is not None:
            self.removeItem(mesh)

    @property
    def visible_meshes(self):
        """
        Get the list of all visible meshes by label.

        :rtype: List[int]
        """
        return [key for key, value in self._meshes.items() if value.visible()]

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


class GLViewMock(QLabel):
    slice_changed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setText(
            "3D widget disabled via $HOME/.voluminarc or environment variable" "<pre>FEATURES_USE_OPENGL_WIDGET</pre>"
        )

    def add_mesh(self, name, mesh=None):
        pass

    def remove_mesh(self, name):
        pass

    def is_cached(self, name):
        return False

    def invalidate_cache(self, name):
        pass

    @property
    def visible_meshes(self):
        return []

    @property
    def slice(self):
        return (0, 0, 0)

    @slice.setter
    def slice(self, slice_):
        pass

    def set_shape(self, shape):
        pass

    shape = property(fset=set_shape)

    def toggle_slice(self, axis, visible):
        pass


if volumina.config.Config.show_3d_widget:
    GLView = GLViewReal
else:
    GLView = GLViewMock

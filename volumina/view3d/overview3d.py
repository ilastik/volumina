from os.path import split, join

from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.uic import loadUiType


class Overview3D(QWidget):
    """
    This class is the 3D widget seen in the bottom right corner in ilastik.

    It is basically a container for the actual 3D view, a busy progress bar and some buttons.
    The buttons are:
        toggle_slice_x: QToolButton, to toggle the display of the x slicing plane
        toggle_slice_y: QToolButton, to toggle the display of the y slicing plane
        toggle_slice_z: QToolButton, to toggle the display of the z slicing plane
        dock: QToolButton, to toggle the docking status of the widget
    The progress bar:
        progress: QProgressBar
        It is used to indicate whether a numpy volume is converted into a mesh right now
    The 3d view:
        view: volumina.view3d.glview.GLView (promoted from QGraphicsView)
        It displays the slicing planes and the labeling in 3d

    slots:
        slice_changed: emitted when the user changes the slicing in the 3d view
        reinitialized: probably obsolete, used to indicate to some containers that this view is ready?
        dock_status_changed: indicates that the dock button was toggled
    """
    slice_changed = pyqtSignal()
    reinitialized = pyqtSignal()  # TODO: this should not be necessary: remove
    dock_status_changed = pyqtSignal(bool)

    def __init__(self, *args, **kwargs):
        super(QWidget, self).__init__(*args, **kwargs)
        cls, _ = loadUiType(join(split(__file__)[0], "ui/view3d.ui"))
        self._ui = cls()
        self._ui.setupUi(self)

        self._view = self._ui.view
        self._progress = self._ui.progress
        self._progress.setVisible(False)  # this can't be set in QDesigner for some reason
        self._mesh_generator_thread = None  # the thread need to be stored so it doesn't get destroyed when out of scope

        self.reinitialized.emit()  # TODO: this should not be necessary: remove
        self._view.slice_changed.connect(self.slice_changed)

    @staticmethod
    def _adjust_axes(x, y, z):
        """
        The axes in ilastik are flipped so we need to adjust the order here.
        """
        return x, y, z

    def set_shape(self, shape):
        """
        Set the shape for the 3d view.

        When changed the slicing planes in the 3d view will be resized.
        """
        self._view.shape = self._adjust_axes(*shape)

    shape = property(fset=set_shape)

    @property
    def slice(self):
        """
        Get the current slice from the 3d view.

        not used right now, as the slice cannot be changed easily in pyqtgraph.
        """
        return self._adjust_axes(*self._view.slice)

    @slice.setter
    def slice(self, slice_):
        """
        Set the current slice for the 3d view.

        Setting the slice will move the slice planes in the 3d view.
        """
        self._view.slice = self._adjust_axes(*slice_)

    def add_object(self, name, object_=None):
        """
        Add an object to the 3d view

        See glview.GLView.add_mesh for more details.

        :param str name: the name to identify the object
        :param Optional[GLMeshItem] object_: the object to add
        """
        self._view.add_mesh(name, object_)

    def remove_object(self, name):
        """
        Remove the object with the given name from the 3d view.

        :param str name: the identifying name
        """
        self._view.remove_mesh(name)

    def invalidate_object(self, name):
        """
        Remove the object with the given name fron the cache in the 3d view

        :param str name: the identifying name
        """
        self._view.invalidate_cache(name)

    def has_object(self, name):
        """
        Check if the object given by the name is cached

        :rtype: bool
        """
        return self._view.is_cached(name)

    @property
    def visible_objects(self):
        """
        Get the label of all currently visible objects in the 3d view.

        :rtype: Set[int]
        """
        return set(self._view.visible_meshes)

    @pyqtSlot(bool, name="on_toggle_slice_x_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_y_clicked")
    @pyqtSlot(bool, name="on_toggle_slice_z_clicked")
    def _on_toggle_slice(self, down):
        """
        The slot for the slice plane toggle button presses.

        When a toggle slice button is pressed the corresponding slice plane is toggled in the 3d view.
        """
        sender = self.sender()
        self._view.toggle_slice(str(sender.objectName()[-1]), down)

    @pyqtSlot(bool, name="on_dock_clicked")
    def _on_dock_status_changed(self, status):
        """
        The slot for the dock status button.

        When the button is toggled the corresponding signal is emitted.
        This simply "forwards" the dock.clicked signal to the containing class's signal.
        """
        self.dock_status_changed.emit(status)

    def set_busy(self, busy):
        """
        Set the busy state for this widget.

        Setting it to busy will show the progress bar.
        :param bool busy: True or False for the busy state
        """
        self._progress.setVisible(busy)

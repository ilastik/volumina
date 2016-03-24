from os.path import split, join

from PyQt4.QtGui import QWidget
from PyQt4.QtCore import pyqtSignal, pyqtSlot
from PyQt4.uic import loadUiType

from numpy import all as np_all

from .meshgenerator import MeshGenerator


class Overview3D(QWidget):
    """
    This class is the 3D widget seen in the bottom right corner in ilastik.

    It is basically a container for the actual 3D view, a busy progress bar and some buttons.
    The buttons are:
        toggle_slice_x: QToolButton, to toggle the display of the x slicing plane
        toggle_slice_y: QToolButton, to toggle the display of the y slicing plane
        toggle_slice_z: QToolButton, to toggle the display of the z slicing plane
        anaglyph: QToolButton, to toggle anaglyph 3D mode (not implemented right now)
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
        return z, y, x

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

    def set_volume(self, volume):
        """
        Set the volume to render for the 3d view.

        Uses the volume to generate a mesh from it. The generation is moved to a separate thread.
        While the thread is running the busy progress bar is shown on this window.
        When the generation finished the mesh is displayed in the 3d view and the progress bar is hidden.

        An empty volume will simply remove the current mesh.

        :param numpy.ndarray volume: the volume containing the labels for each object and 0 for background
        """
        # noinspection PyTypeChecker
        if np_all(volume == 0):
            self._view.toggle_mesh(False)
        else:
            self._set_busy(True)
            self._mesh_generator_thread = MeshGenerator(self._on_generator_finish, volume)

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

    def _set_busy(self, busy):
        """
        Set the busy state for the viewer.

        When busy the progress bar is shown.
        """
        self._progress.setVisible(busy)

    def _on_generator_finish(self, mesh):
        """
        Slot for the mesh generator thread.

        When the mesh generator finished this slot is called.
        The busy state is cancelled and the generated mesh is send to the 3d view.
        """
        self._set_busy(False)
        self._view.set_mesh(mesh)

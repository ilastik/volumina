from pyqtgraph.functions import isosurface
from pyqtgraph.opengl import MeshData, GLMeshItem

from PyQt4.QtCore import QThread, pyqtSignal


class MeshGenerator(QThread):
    """
    This class wraps the mesh generation in a thread to avoid locking the ui.

    signal:
        mesh_generated: emitted when the generation finished, passed the generated mesh
    """
    mesh_generated = pyqtSignal(object)

    def __init__(self, receiver, labeling):
        """
        Create the thread, connect the signals and start immediately

        :param Callable[[object], None] receiver: the slot to send the mesh to when finished
        :param numpy.ndarray labeling: the numpy array containing the labeling to convert into a mesh
        """
        super(MeshGenerator, self).__init__()
        self.mesh_generated.connect(receiver)
        self.start()
        self._labeling = labeling

    def run(self):
        """
        This does the actual mesh generation.

        The labeling is converted into a mesh which is then wrapped in a GLMeshItem.
        After that the mesh_generated signal is emitted.
        """
        vertices, faces = isosurface(self._labeling, level=0.5)
        mesh = MeshData(vertices, faces)
        color = [255, 0, 255, 255]
        item = GLMeshItem(meshdata=mesh, color=color, smooth=True,
                          shader="viewNormalColor")
        self.mesh_generated.emit(item)

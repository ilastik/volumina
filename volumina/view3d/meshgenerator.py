from pyqtgraph.functions import isosurface
from pyqtgraph.opengl import MeshData, GLMeshItem

from PyQt4.QtCore import QThread, pyqtSignal


def labeling_to_mesh(labeling):
    """
    Generate the isosurface of a labeling

    :param numpy.ndarray labeling: the labeling to convert
    :rtype: MeshData
    """
    vertices, faces = isosurface(labeling, level=0.5)
    return MeshData(vertices, faces)


def mesh_to_obj(mesh, path):
    """
    Write the mesh to .obj

    :param MeshData mesh: the mesh to save
    :param str path: the path for the file
    """
    with open(path, "w") as fout:
        fout.write("o <placeholder>\n")

        for vertex in mesh.vertexes():
            fout.write("v {} {} {}\n".format(*vertex))

        for normal in mesh.vertexNormals():
            fout.write("vn {} {} {}\n".format(*normal))

        for vertex, normal in zip(mesh.vertexes("faces"), mesh.vertexNormals("faces")):
            fout.write("f {}//{} {}//{} {}//{}\n".format(sum(zip(vertex, normal), ())))


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
        mesh = labeling_to_mesh(self._labeling)
        item = GLMeshItem(meshdata=mesh, smooth=True,
                          shader="viewNormalColor")
        self.mesh_generated.emit(item)

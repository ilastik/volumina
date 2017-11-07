from os.path import split, join

from numpy import where

from pyqtgraph.opengl import MeshData, GLMeshItem
from pyqtgraph.opengl.shaders import ShaderProgram, VertexShader, FragmentShader

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QDialog
from PyQt5.uic import loadUiType


try:
    from marching_cubes import march
except ImportError:
    from skimage.measure import correct_mesh_orientation, marching_cubes_lewiner

    def march(volume, _):
        verts, faces, normals, values = marching_cubes_lewiner(volume, 1)
        faces = correct_mesh_orientation(volume, verts, faces)
        return verts, None, faces


ShaderProgram('toon', [
    VertexShader("""
        varying vec3 normal;

        void main() {
            normal = gl_Normal;
            gl_Position = gl_ModelViewProjectionMatrix * gl_Vertex;

            gl_FrontColor = gl_Color;
            gl_BackColor = gl_Color;
        }
    """),
    FragmentShader("""
        varying vec3 normal;

        void main() {
            vec3 light = normalize(vec3(1.0, -1.0, -1.0));
            float intensity;

            intensity = (dot(light, normalize(normal)) + 1) / 2;

            //gl_FragColor = max(round(intensity * 3), 0.3) / 3 * gl_Color / 2;
            gl_FragColor = intensity * gl_Color;
        }
    """)
])


def labeling_to_mesh(labeling, labels):

    for label in labels:
        vertices, normals, faces = march(where(labeling == label, 2, 0).astype(int).T, 4)
        data = MeshData(vertices, faces)
        if normals is not None:
            data._vertexNormals = normals
        
        yield label, data


def mesh_to_obj(mesh, path, name):
    """
    Write the mesh to .obj

    :param MeshData mesh: the mesh to save
    :param str path: the path for the file
    :param str name: the name for the object
    """
    with open(path, "w") as fout:
        fout.write("o {}\n".format(name))

        for vertex in mesh.vertexes():
            fout.write("v {} {} {}\n".format(*vertex))

        for normal in mesh.vertexNormals():
            fout.write("vn {} {} {}\n".format(*normal))

        for index in mesh.faces():
            fout.write("f {0}//{0} {1}//{1} {2}//{2}\n".format(*(i + 1 for i in index)))


class MeshGenerator(QThread):
    """
    This class wraps the mesh generation in a thread to avoid locking the ui.

    signal:
        mesh_generated: emitted when the generation finished, passes the label/name and generated mesh
    """
    mesh_generated = pyqtSignal(object, object)

    def __init__(self, receiver, labeling, labels, name_mapping=None):
        """
        Create the thread, connect the signals and start immediately

        :param Callable[[object], None] receiver: the slot to send the mesh to when finished
        :param numpy.ndarray labeling: the numpy array containing the labeling to convert into a mesh
        :param Iterable[int] labels: the labels to include
        :param Mapping[int, str] name_mapping: an optional mapping to rename the labels
        """
        super(MeshGenerator, self).__init__()
        self.mesh_generated.connect(receiver)
        self.start()
        self._labeling = labeling
        self._labels = labels
        self._mapping = name_mapping or {}

    def run(self):
        """
        This does the actual mesh generation.

        The labeling is converted into a mesh which is then wrapped in a GLMeshItem.
        For each generated mesh the signal mesh_generated is emitted containing the label/name and mesh.

        When finished the signal mesh_generated is emitted again with label 0 and mesh None
        """
        for label, mesh in labeling_to_mesh(self._labeling, self._labels):
            item = GLMeshItem(meshdata=mesh, smooth=True,
                              shader="toon")
            self.mesh_generated.emit(self._mapping.get(label, label), item)
        self.mesh_generated.emit(0, None)


class MeshGeneratorDialog(QDialog):
    """
    The Dialog to display the busy state when exporting .obj files

    signals:
        finished: emitted when the export is finished. Passes the generated MeshData
    """
    finished = pyqtSignal(object)

    def __init__(self, parent=None):
        super(MeshGeneratorDialog, self).__init__(parent)
        form, _ = loadUiType(join(split(__file__)[0], "ui/extract.ui"))
        self._ui = form()
        self._ui.setupUi(self)

        self._thread = None
        self._mesh = None

    def run(self, volume):
        """
        Start the export thread which will notify the dialog when finished.

        :param numpy.ndarray volume: the volume to export
        """
        self._thread = MeshGenerator(self._mesh_generated, volume, [1])
        self._thread.start()

    def _mesh_generated(self, _, mesh):
        """
        The slot when the export is finished.

        As the generator emits several times the result is
        accumulated here to match the interface in the gui.
        """
        if mesh is None:
            assert self._mesh is not None, "No mesh generated"
            self._thread.wait()
            self.finished.emit(self._mesh)
            self.close()
        else:
            assert self._mesh is None, "Too many meshes generated"
            self._mesh = mesh.opts["meshdata"]

from pyqtgraph.functions import isosurface
from pyqtgraph.opengl import MeshData, GLMeshItem
from pyqtgraph.opengl.shaders import ShaderProgram, VertexShader, FragmentShader

from PyQt4.QtCore import QThread, pyqtSignal


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
        uniform vec3 light = normalize(vec3(1.0, -1.0, -1.0));
        varying vec3 normal;

        void main() {
            float intensity;

            intensity = (dot(light, normalize(normal)) + 1) / 2;

            gl_FragColor = max(round(intensity * 3), 0.3) / 3 * gl_Color / 2;
            gl_FragColor += intensity / 2 * gl_Color;
        }
    """)
])


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
                          shader="toon")
        self.mesh_generated.emit(item)

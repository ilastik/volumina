from pyqtgraph.functions import isosurface
from pyqtgraph.opengl import MeshData, GLMeshItem


def labeling_to_mesh(labeling):
    from datetime import datetime
    from sys import stdout

    start = datetime.now()
    print "generate mesh... ",
    stdout.flush()

    vertices, faces = isosurface(labeling, level=0.5)
    mesh = MeshData(vertices, faces)
    color = [255, 0, 255, 255]
    item = GLMeshItem(meshdata=mesh, color=color, smooth=True,
                      shader="viewNormalColor")
    print "{}s".format((datetime.now() - start).total_seconds())
    return item

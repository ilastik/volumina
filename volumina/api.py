"""High-level API.

"""
from pixelpipeline.imagepump import ImagePump
from volumina.pixelpipeline.datasources import *
from volumina.layer import *
from volumina.layerstack import LayerStackModel
from volumina.volumeEditor import VolumeEditor
from volumina.volumeEditorWidget import VolumeEditorWidget
from volumina.widgets.layerwidget import LayerWidget

from volumina.viewer import Viewer

from PyQt4.QtGui import QApplication
import sys

def viewerApp():
    app = QApplication(sys.argv)
    v = Viewer()
    return (v, app)

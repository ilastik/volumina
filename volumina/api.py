"""High-level API.

"""
from pixelpipeline.imagepump import ImagePump
from volumina.pixelpipeline.datasources import *
from volumina.layer import *
from volumina.layerstack import LayerStackModel
from volumina.widgets.layerwidget import LayerWidget

# Do NOT import these here because they prevent the volumina.NO3D flag from working properly
#from volumina.volumeEditorWidget import VolumeEditorWidget
#from volumina.volumeEditor import VolumeEditor

from volumina.viewer import Viewer, ClickableSegmentationLayer

from PyQt4.QtGui import QApplication
import sys

def viewerApp():
    app = QApplication(sys.argv)
    v = Viewer()
    return (v, app)

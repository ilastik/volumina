# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

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

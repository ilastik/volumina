###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#		   http://ilastik.org/license/
###############################################################################
"""High-level API.

"""
from __future__ import absolute_import
from .pixelpipeline.imagepump import ImagePump
from volumina.pixelpipeline.datasources import *
from volumina.layer import *
from volumina.layerstack import LayerStackModel
from volumina.widgets.layerwidget import LayerWidget

# Do NOT import these here because they prevent the volumina.NO3D flag from working properly
#from volumina.volumeEditorWidget import VolumeEditorWidget
#from volumina.volumeEditor import VolumeEditor

from volumina.viewer import Viewer, ClickableSegmentationLayer

from PyQt5.QtWidgets import QApplication
import sys

def viewerApp():
    app = QApplication(sys.argv)
    v = Viewer()
    return (v, app)

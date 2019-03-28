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
# 		   http://ilastik.org/license/
###############################################################################
from PyQt5.QtDesigner import QPyDesignerCustomWidgetPlugin
from PyQt5.QtWidgets import QPixmap, QIcon

import numpy

###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.graph import Graph
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False


from volumina.volumeEditor import VolumeEditor
from volumina.volumeEditorWidget import VolumeEditorWidget
from volumina.pixelpipeline.datasources import ArraySource
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer


class PyVolumeEditorWidgetPlugin(QPyDesignerCustomWidgetPlugin):
    def __init__(self, parent=None):
        QPyDesignerCustomWidgetPlugin.__init__(self)
        self.initialized = False

    def initialize(self, core):
        if self.initialized:
            return
        self.initialized = True

    def isInitialized(self):
        return self.initialized

    def createWidget(self, parent):
        a = (numpy.random.random((1, 100, 200, 300, 1)) * 255).astype(numpy.uint8)
        source = ArraySource(a)
        layerstack = LayerStackModel()
        layerstack.append(GrayscaleLayer(source))

        editor = VolumeEditor(layerstack, labelsink=None, parent=self)
        widget = VolumeEditorWidget(parent=parent)
        if not _has_lazyflow:
            widget.setEnabled(False)
        widget.init(editor)
        editor.dataShape = a.shape
        return widget

    def name(self):
        return "VolumeEditorWidget"

    def group(self):
        return "ilastik widgets"

    def icon(self):
        return QIcon(QPixmap(16, 16))

    def toolTip(self):
        return ""

    def whatsThis(self):
        return ""

    def isContainer(self):
        return False

    def domXml(self):
        return '<widget class="VolumeEditorWidget" name="volumeEditorWidget">\n' "</widget>\n"

    def includeFile(self):
        return "volumina.volumeEditorWidget"

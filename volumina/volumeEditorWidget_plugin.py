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

from PyQt4.QtDesigner import QPyDesignerCustomWidgetPlugin
from PyQt4.QtGui import QPixmap, QIcon

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

    def __init__(self, parent = None):
        QPyDesignerCustomWidgetPlugin.__init__(self)
        self.initialized = False
        
    def initialize(self, core):
        if self.initialized:
            return
        self.initialized = True

    def isInitialized(self):
        return self.initialized
    
    def createWidget(self, parent):
        a = (numpy.random.random((1,100,200,300,1))*255).astype(numpy.uint8)
        source = ArraySource(a)
        layerstack = LayerStackModel()
        layerstack.append( GrayscaleLayer( source ) )

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
        return QIcon(QPixmap(16,16))
                           
    def toolTip(self):
        return ""
    
    def whatsThis(self):
        return ""
    
    def isContainer(self):
        return False
    
    def domXml(self):
        return (
               '<widget class="VolumeEditorWidget" name=\"volumeEditorWidget\">\n'
               "</widget>\n"
               )
    
    def includeFile(self):
        return "volumina.volumeEditorWidget"

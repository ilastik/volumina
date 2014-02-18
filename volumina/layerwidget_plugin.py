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
from PyQt4.QtGui import QPixmap, QIcon, QColor

from volumina.widgets.layerwidget import LayerWidget
from volumina.layerstack import LayerStackModel, Layer

class PyLayerWidgetPlugin(QPyDesignerCustomWidgetPlugin):

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
        model = LayerStackModel()
        
        o1 = Layer()
        o1.name = "Fancy Layer"
        o1.opacity = 0.5
        model.append(o1)
        
        o2 = Layer()
        o2.name = "Some other Layer"
        o2.opacity = 0.25
        model.append(o2)
        
        o3 = Layer()
        o3.name = "Invisible Layer"
        o3.opacity = 0.15
        o3.visible = False
        model.append(o3)
        
        o4 = Layer()
        o4.name = "Fancy Layer II"
        o4.opacity = 0.95
        model.append(o4)
        
        o5 = Layer()
        o5.name = "Fancy Layer III"
        o5.opacity = 0.65
        model.append(o5)
    
        view = LayerWidget(parent, model)
        view.updateGeometry()
        
        return view
    
    def name(self):
        return "LayerWidget"

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
               '<widget class="LayerWidget" name=\"layerWidget\">\n'
               "</widget>\n"
               )
    
    def includeFile(self):
        return "volumina.widgets.layerwidget"

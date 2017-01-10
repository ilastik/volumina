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
#Python
import os

#PyQt
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from functools import partial

#===----------------------------------------------------------------------------------------------------------------===

class GrayscaleLayerDialog(QDialog):
    def __init__(self, layer, parent=None):
        QDialog.__init__(self, parent)
        p = os.path.split(os.path.abspath(__file__))[0]
        uic.loadUi(p+"/ui/grayLayerDialog.ui", self)
        self.setLayername(layer.name)
        def dbgPrint(a, b):
            layer.set_normalize(0, (a,b))
            print "normalization changed to [%d, %d]" % (a,b)

        def autoRange(state):
            if state == 2:
                self.grayChannelThresholdingWidget.setValue(layer.normalize[0][0], layer.normalize[0][1]) #update gui
                layer.set_normalize(0,None)
                self.grayChannelThresholdingWidget.setEnabled(False)
            if state == 0:
                self.grayChannelThresholdingWidget.setEnabled(True)
                layer.set_normalize(0,layer.normalize[0])
        self.grayChannelThresholdingWidget.setRange(layer.range[0][0], 
                                                    layer.range[0][1])
        self.grayChannelThresholdingWidget.setValue(layer.normalize[0][0], 
                                                    layer.normalize[0][1])
        self.grayChannelThresholdingWidget.valueChanged.connect(dbgPrint)
        self.grayAutoRange.stateChanged.connect(autoRange)
        self.grayAutoRange.setCheckState(layer._autoMinMax[0]*2)
        
    def setLayername(self, n):
        self._layerLabel.setText("<b>%s</b>" % n)
    
class RGBALayerDialog(QDialog):
    def __init__(self, layer, parent=None):
        QDialog.__init__(self, parent)
        p = os.path.split(os.path.abspath(__file__))[0]
        uic.loadUi(p+"/ui/rgbaLayerDialog.ui", self)
        self.setLayername(layer.name)

        if layer.datasources[0] == None:
            self.showRedThresholds(False)
        if layer.datasources[1] == None:
            self.showGreenThresholds(False)
        if layer.datasources[2] == None:
            self.showBlueThresholds(False)
        if layer.datasources[3] == None:
            self.showAlphaThresholds(False)

        def dbgPrint(layerIdx, a, b):
            layer.set_normalize(layerIdx, (a, b))
            print "normalization changed for channel=%d to [%d, %d]" % (layerIdx, a,b)

        self.redChannelThresholdingWidget.setRange(layer.range[0][0], layer.range[0][1])
        self.greenChannelThresholdingWidget.setRange(layer.range[1][0], layer.range[1][1])
        self.blueChannelThresholdingWidget.setRange(layer.range[2][0], layer.range[2][1])
        self.alphaChannelThresholdingWidget.setRange(layer.range[3][0], layer.range[3][1])

        self.redChannelThresholdingWidget.setValue(layer.normalize[0][0], layer.normalize[0][1])
        self.greenChannelThresholdingWidget.setValue(layer.normalize[1][0], layer.normalize[1][1])
        self.blueChannelThresholdingWidget.setValue(layer.normalize[2][0], layer.normalize[2][1])
        self.alphaChannelThresholdingWidget.setValue(layer.normalize[3][0], layer.normalize[3][1])

        self.redChannelThresholdingWidget.valueChanged.connect(  partial(dbgPrint, 0))
        self.greenChannelThresholdingWidget.valueChanged.connect(partial(dbgPrint, 1))
        self.blueChannelThresholdingWidget.valueChanged.connect( partial(dbgPrint, 2))
        self.alphaChannelThresholdingWidget.valueChanged.connect(partial(dbgPrint, 3))

        def redAutoRange(state):
            if state == 2:
                self.redChannelThresholdingWidget.setValue(layer.normalize[0][0], layer.normalize[0][1]) #update gui
                layer.set_normalize(0, None) # set to auto
                self.redChannelThresholdingWidget.setEnabled(False)
            if state == 0:
                self.redChannelThresholdingWidget.setEnabled(True)
                layer.set_normalize(0,layer.normalize[0])
        def greenAutoRange(state):
            if state == 2:
                self.greenChannelThresholdingWidget.setValue(layer.normalize[1][0], layer.normalize[1][1]) #update gui
                layer.set_normalize(1, None) # set to auto
                self.greenChannelThresholdingWidget.setEnabled(False)
            if state == 0:
                self.greenChannelThresholdingWidget.setEnabled(True)
                layer.set_normalize(1,layer.normalize[1])
        def blueAutoRange(state):
            if state == 2:
                self.blueChannelThresholdingWidget.setValue(layer.normalize[2][0], layer.normalize[2][1]) #update gui
                layer.set_normalize(2, None) # set to auto
                self.blueChannelThresholdingWidget.setEnabled(False)
            if state == 0:
                self.blueChannelThresholdingWidget.setEnabled(True)
                layer.set_normalize(2,layer.normalize[2])
        def alphaAutoRange(state):
            if state == 2:
                self.alphaChannelThresholdingWidget.setValue(layer.normalize[3][0], layer.normalize[3][1]) #update gui
                layer.set_normalize(3, None) # set to auto
                self.alphaChannelThresholdingWidget.setEnabled(False)
            if state == 0:
                self.alphaChannelThresholdingWidget.setEnabled(True)
                layer.set_normalize(3,layer.normalize[3])
        self.redAutoRange.stateChanged.connect(redAutoRange)
        self.redAutoRange.setCheckState(layer._autoMinMax[0]*2)
        self.greenAutoRange.stateChanged.connect(greenAutoRange)
        self.greenAutoRange.setCheckState(layer._autoMinMax[1]*2)
        self.blueAutoRange.stateChanged.connect(blueAutoRange)
        self.blueAutoRange.setCheckState(layer._autoMinMax[2]*2)
        self.alphaAutoRange.stateChanged.connect(alphaAutoRange)
        self.alphaAutoRange.setCheckState(layer._autoMinMax[3]*2)

        self.resize(self.minimumSize())
    
    def showRedThresholds(self, show):
        self.redChannel.setVisible(show)
    def showGreenThresholds(self, show):
        self.greenChannel.setVisible(show)
    def showBlueThresholds(self, show):
        self.blueChannel.setVisible(show)
    def showAlphaThresholds(self, show):
        self.alphaChannel.setVisible(show)
    
    def setLayername(self, n):
        self._layerLabel.setText("<b>%s</b>" % n)
 
#===----------------------------------------------------------------------------------------------------------------===
#=== __name__ == "__main__"                                                                                         ===
#===----------------------------------------------------------------------------------------------------------------===
        
if __name__ == "__main__":
    import optparse
    import sys
    from PyQt5.QtWidgets import QApplication
     
    parser = optparse.OptionParser()
    parser.add_option("--gray", action="store_true")
    parser.add_option("--rgb",  action="store_true")
    (options, args) = parser.parse_args()
    
    app = QApplication([])
    if options.gray:
        l = GrayscaleLayerDialog()
    elif options.rgb:
        l = RGBALayerDialog()
    else:
        print parser.usage
        sys.exit()
    l.show()
    app.exec_()

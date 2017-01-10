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
from os import path

#PyQt
from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget, QButtonGroup

#===----------------------------------------------------------------------------------------------------------------===

class ThresholdingWidget(QWidget):
    valueChanged = pyqtSignal(int, int)
    
    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
            
        p = path.split(__file__)[0]
        if not p:
            p = "."
        
        uic.loadUi(p+"/ui/thresholdingWidget.ui", self)
        self.setRange(0,255)
        
        self._minSlider.valueChanged.connect(self._onMinSliderMoved)
        self._maxSlider.valueChanged.connect(self._onMaxSliderMoved)
    
    def _onMinSliderMoved(self, v):
        if v >= self._maxSlider.value():
            if v < self._maxSlider.maximum():
                self._maxSlider.setValue(v+1)
            else:
                self._minSlider.setValue(v-1)
        self.valueChanged.emit(self._minSlider.value(), self._maxSlider.value())
    
    def _onMaxSliderMoved(self, v):
        if v <= self._minSlider.value():
            if v > self._minSlider.minimum():
                self._minSlider.setValue(v-1)
            else:
                self._maxSlider.setValue(self._minSlider.minimum()+1)
        self.valueChanged.emit(self._minSlider.value(), self._maxSlider.value())
    
    def setLayername(self, n):
        self._layerLabel.setText("Layer <b>%s</b>" % n)
        
    def setRange(self, minimum, maximum):
        self._minSlider.setRange(minimum, maximum)
        self._minSpin.setRange(minimum, maximum)
        self._maxSlider.setRange(minimum, maximum)
        self._maxSpin.setRange(minimum, maximum)
        self._minSpin.setSuffix("/%d" % maximum)
        self._maxSpin.setSuffix("/%d" % maximum)
        self._minSlider.setValue(minimum)
        self._maxSlider.setValue(maximum)
        self._minSpin.setValue(minimum)
        self._maxSpin.setValue(maximum)

    def setValue(self, minimum, maximum):
        self._minSlider.setValue(minimum)
        self._maxSlider.setValue(maximum)
        self._minSpin.setValue(minimum)
        self._maxSpin.setValue(maximum)
        
#===----------------------------------------------------------------------------------------------------------------===
#=== __name__ == "__main__"                                                                                         ===
#===----------------------------------------------------------------------------------------------------------------===

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    app = QApplication([])
    w = ThresholdingWidget()
    w.show()
    app.exec_()

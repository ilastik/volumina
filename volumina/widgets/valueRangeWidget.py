import os

from PyQt4.QtGui import QWidget, QDoubleSpinBox
from PyQt4.QtCore import QRegExp, Qt, QTimer, pyqtSignal
from PyQt4 import uic
import numpy

class ValueRangeWidget(QWidget):

    changedSignal = pyqtSignal()

    def __init__(self, parent = None, dtype = numpy.float):
        super(ValueRangeWidget, self).__init__(parent)
        self._initUic()
        self.allValid = True
        self.minBox.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.maxBox.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.minBox.setKeyboardTracking(False)
        self.maxBox.setKeyboardTracking(False)
        self.boxes = [self.minBox, self.maxBox]
        self.minBox.valueChanged.connect(self.onChangedMinBox)
        self.maxBox.valueChanged.connect(self.onChangedMaxBox)
        self.setDType(dtype)
    
    def setLabels(self, minLabel, maxLabel):
        self.minBox.setPrefix(minLabel)
        self.maxBox.setPrefix(maxLabel)

    def setDType(self, dtype):
        typeLimits = []
        machineLimits = []
        if numpy.issubdtype(dtype, numpy.float):
            typeLimits.append(numpy.finfo(dtype).min)
            typeLimits.append(numpy.finfo(dtype).max)
            machineLimits.append(numpy.finfo(numpy.float).min)
            machineLimits.append(numpy.finfo(numpy.float).max)
            for box in self.boxes:
                box.setDecimals(2)
                box.setSingleStep(0.01)
        else:
            typeLimits.append(numpy.iinfo(dtype).min)
            typeLimits.append(numpy.iinfo(dtype).max)
            machineLimits.append(numpy.iinfo(numpy.uint).min)
            machineLimits.append(numpy.iinfo(numpy.uint).max)
            for box in self.boxes:
                box.setDecimals(0)
                box.setSingleStep(1)

        for box in self.boxes: 
            box.setRange(machineLimits[0],machineLimits[1])
            #box.setRange(typeLimits[0],typeLimits[1])
        
        self.setLimits(typeLimits[0], typeLimits[1])


    def onChangedMinBox(self,val):
        if val >= self.maxBox.value():
            self.minBox.setValue(val)
            self.maxBox.setValue(val + self.maxBox.singleStep())
        if val < self.softLimits[0]:
            self.minBox.setValue(self.softLimits[0])
        self.validateRange()
        self.changedSignal.emit()

    def onChangedMaxBox(self,val):
        if val > self.softLimits[1]:
            self.maxBox.setValue(self.softLimits[1])
        if self.maxBox.value() <= self.minBox.value():
            self.minBox.setValue(self.maxBox.value() - self.minBox.singleStep())
        self.validateRange()
        #self.printLimits()
        self.changedSignal.emit()

    def printLimits(self):
        print self.softLimits

    def validateRange(self):
        validCheck = [True, True]
        if self.minBox.value() < self.softLimits[0]:
            validCheck[0] = False
        if self.maxBox.value() < self.softLimits[0]:
            validCheck[1] = False
        if self.minBox.value() >= self.softLimits[1]:
            validCheck[0] = False
        if self.maxBox.value() > self.softLimits[1]:
            validCheck[1] = False
        #if not self.maxBox.value() > self.minBox.value():
        #    validCheck[1] = False

        for i,box in enumerate(self.boxes):
            if validCheck[i]:
                box.setStyleSheet("QDoubleSpinBox {background-color: white;}")
                #self.setBackgroundColor("white", [i])
                #box.setButtonSymbols(QDoubleSpinBox.NoButtons)
            else:
                self.setBackgroundColor("red", [i])
                #box.setStyleSheet("QDoubleSpinBox {background-color: red;}")
                #box.setButtonSymbols(QDoubleSpinBox.UpDownArrows)

        self.allValid = all(validCheck)


    def setBackgroundColor(self, color, boxnumber = [0,1]):
        for i in boxnumber:
            self.boxes[i].setStyleSheet("QDoubleSpinBox {background-color: %s}" % color)
        

    def setLimits(self, _min, _max):
        if _min + self.minBox.singleStep() >  _max:
            raise RuntimeError("limits have to differ")
        self.softLimits = [_min, _max]
        self.setValues(_min, _max)
        self.validateRange()

    def setValues(self, val1, val2):
        self.minBox.setValue(val1)
        self.maxBox.setValue(val2)

    def getValues(self):
        return [self.minBox.value(), self.maxBox.value()]
        
    def makeValid(self):
        if not self.maxBox.value() > self.minBox.value():
            self.maxBox.setValue(self.minBox.value() + self.maxBox.singleStep())

    def _initUic(self):
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        uic.loadUi(p+"ui/valueRangeWidget.ui", self)


if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    app = QApplication(list())
   
    d = ValueRangeWidget()
    d.setDType(numpy.uint8)
    d.makeValid()
    d.setLimits(20,40)
    d.show()
    app.exec_()

    

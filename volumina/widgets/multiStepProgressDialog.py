import os

from PyQt4 import uic
from PyQt4.QtGui import QDialog, QDialogButtonBox

class MultiStepProgressDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        self._initUic()
        
        self._numberOfSteps = 1
        self._currentStep = 0
        self._steps = []
        self._update()

    def setNumberOfSteps(self, n):
        assert n >= 1
        self._numberOfSteps = n
        self._currentStep = 0
        self._update()
    
    def setSteps(self, steps):
        self._steps = steps
        self.setNumberOfSteps(len(self._steps))
    
    def finishStep(self):
        self._currentStep = self._currentStep + 1
        self._update()
        if self._currentStep == self._numberOfSteps:
            self.buttonBox.button(QDialogButtonBox.Ok).setText("Finished!")
            self.buttonBox.button(QDialogButtonBox.Cancel).hide()
            self.currentStepProgress.setValue(100)

    
    def _update(self):
        self.currentStepProgress.setValue(0)
        self.overallProgress.setMinimum(0)
        self.overallProgress.setMaximum(self._numberOfSteps)
        self.overallProgress.setFormat("step %d of %d" % (self._currentStep, self._numberOfSteps))

        self.overallProgress.setValue(self._currentStep)
        self._updateCurrentStepLabel()
    
    def setStepProgress(self, x):
        self.currentStepProgress.setValue(x)
    
    def _updateCurrentStepLabel(self):
        self.currentStepLabel.setText("ETA: %f min" % (42.42))

    def _initUic(self):
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        uic.loadUi(p+"ui/multiStepProgressDialog.ui", self)
        

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    app = QApplication(list())
   
    d = MultiStepProgressDialog()
    d.setNumberOfSteps(5)
    d.show()
    app.exec_()

    

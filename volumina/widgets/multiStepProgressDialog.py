import os, time

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
        self.time1 = time.time()
        self.times = []
    
    def setSteps(self, steps):
        self._steps = steps
        self.setNumberOfSteps(len(self._steps))
    
    def finishStep(self):
        self._currentStep = self._currentStep + 1
        self._update()
        if self._currentStep == self._numberOfSteps:
            self.buttonBox.button(QDialogButtonBox.Ok).setText("Finished!")
            self.buttonBox.button(QDialogButtonBox.Ok).show()
            self.buttonBox.button(QDialogButtonBox.Cancel).hide()
            self.currentStepProgress.setValue(100)

    def setFailed(self):
        self.failedLabel.show()
        self.buttonBox.button(QDialogButtonBox.Cancel).show()
        self.buttonBox.button(QDialogButtonBox.Cancel).setText("Bummer")

    def _update(self):
        self.currentStepProgress.setValue(0)
        self.overallProgress.setMinimum(0)
        self.overallProgress.setMaximum(self._numberOfSteps)
        self.overallProgress.setFormat("step %d of %d" % (self._currentStep, self._numberOfSteps))

        self.overallProgress.setValue(self._currentStep)
    
    def setStepProgress(self, x):
        oldx = self.currentStepProgress.value()
        self.time2 = time.time()
        self.currentStepProgress.setValue(x)
        if x - oldx > 0:
            timeLeft = (100 - x) * (self.time2 - self.time1) / (x - oldx)
            self._updateCurrentStepLabel( timeLeft)
        self.time1 = self.time2
    
    def _updateCurrentStepLabel(self, singlet):
        self.times.append(singlet)
        t = sum(self.times) / len(self.times)
        if len(self.times) > 5:
            self.times.pop(0)
        if t < 120:
            self.currentStepLabel.setText("ETA: %.02f sec" % (t))
        else:
            self.currentStepLabel.setText("ETA: %.02f min" % (t / 60))

    def _initUic(self):
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        uic.loadUi(p+"ui/multiStepProgressDialog.ui", self)
        self.buttonBox.button(QDialogButtonBox.Ok).hide()
        self.failedLabel.hide()
        

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    app = QApplication(list())
   
    d = MultiStepProgressDialog()
    d.setNumberOfSteps(5)
    d.show()
    app.exec_()

    

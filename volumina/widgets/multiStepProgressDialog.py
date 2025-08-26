from __future__ import division

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
from past.utils import old_div
import os, time

from qtpy import uic
from qtpy.QtWidgets import QDialog, QDialogButtonBox


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
            self._updateCurrentStepLabel(timeLeft)
        self.time1 = self.time2

    def _updateCurrentStepLabel(self, singlet):
        self.times.append(singlet)
        t = old_div(sum(self.times), len(self.times))
        if len(self.times) > 5:
            self.times.pop(0)
        if t < 120:
            self.currentStepLabel.setText("Estimated time left: %.02f sec" % (t))
        else:
            self.currentStepLabel.setText("Estimated time left: %.02f min" % (old_div(t, 60)))

    def _initUic(self):
        p = os.path.split(__file__)[0] + "/"
        if p == "/":
            p = "." + p
        uic.loadUi(p + "ui/multiStepProgressDialog.ui", self)
        self.buttonBox.button(QDialogButtonBox.Ok).hide()
        self.failedLabel.hide()


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    import vigra, numpy

    app = QApplication(list())

    d = MultiStepProgressDialog()
    d.setNumberOfSteps(5)
    d.show()
    app.exec_()

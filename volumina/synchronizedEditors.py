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
from PyQt5.QtWidgets import QWidget, QGridLayout, QSizePolicy
from PyQt5.QtCore import Qt
from imageEditorComponents import PositionModelImage


class SynchronizedEditors(QWidget):
    def __init__(self):

        super(SynchronizedEditors, self).__init__()

        self._layout = QGridLayout()

        @property
        def layout(self):
            return self._layout

        @layout.setter
        def layout(self, layout):
            self._layout = layout

        self.initUI()

    def initUI(self):

        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setLayout(self._layout)
        self.show()

    def addEditorWidget(self, imageEditorWidget, position=(0, 0)):

        self.checkPosition(position)
        self._layout.addWidget(imageEditorWidget, position[0], position[1])

    def checkPosition(self, position):

        widget = self._layout.itemAtPosition(position[0], position[1])
        if widget:
            freePos = self.getFreePosition()
            self._layout.removeItem(widget)
            self._layout.addItem(widget, freePos[0], freePos[1])

    def getFreePosition(self):
        i = 0
        j = 0
        while self._layout.itemAtPosition(i, j):
            while i > j:
                if self._layout.itemAtPosition(i, j):
                    break
                j = j + 1
            i = i + 1
        return (i, j)

    def link(self, iEWidget1, iEWidget2):
        iEWidget2._imageEditor.posModel = iEWidget1._imageEditor.posModel
        self._saveShape = iEWidget1._imageEditor.posModel.shape

    def unlink(self, iEWidget1, iEWidget2):
        shape = iEWidget1._imageEditor.posModel.shape
        iEWidget1._imageEditor.posModel = PositionModelImage()
        iEWidget2._imageEditor.posModel = PositionModelImage()
        iEWidget1._imageEditor.posModel.shape = shape
        iEWidget2._imageEditor.posModel.shape = shape


if __name__ == "__main__":
    # make the program quit on Ctrl+C
    import sys
    import signal
    from PyQt5.QtWidgets import QApplication, QPushButton, QVBoxLayout
    from imageEditorWidget import TestWidget

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)

    wrapper = QWidget()
    layout = QVBoxLayout()
    wrapper.setLayout(layout)

    synEditors = SynchronizedEditors()

    layout.addWidget(synEditors)

    test = TestWidget()
    iEWidget1 = test.makeWidget()
    iEWidget2 = test.makeWidget()
    iEWidget3 = test.makeWidget()

    button = QPushButton("Link")
    button.setCheckable(True)
    button.setChecked(False)

    def onLinkToggled(checked):
        if checked:
            synEditors.link(iEWidget1, iEWidget2)
        else:
            synEditors.unlink(iEWidget1, iEWidget2)

    button.toggled.connect(onLinkToggled)

    layout.addWidget(button)

    synEditors.addEditorWidget(iEWidget1)
    synEditors.addEditorWidget(iEWidget2)

    wrapper.show()
    app.exec_()

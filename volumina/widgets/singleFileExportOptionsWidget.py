from __future__ import print_function

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
import os
import sys

from qtpy import uic
from qtpy.QtCore import Qt, QEvent
from qtpy.QtWidgets import QWidget, QFileDialog


class SingleFileExportOptionsWidget(QWidget):
    def __init__(self, parent, extension, file_filter):
        super(SingleFileExportOptionsWidget, self).__init__(parent)
        uic.loadUi(os.path.splitext(__file__)[0] + ".ui", self)

        self._extension = extension
        self._file_filter = file_filter

        self.filepathEdit.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Apply the new path if the user presses
        #  'enter' or clicks outside the filepath editbox
        if watched == self.filepathEdit:
            if event.type() == QEvent.FocusOut or (
                event.type() == QEvent.KeyPress and (event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return)
            ):
                newpath = self.filepathEdit.text()
                self._filepathSlot.setValue(newpath)
        return False

    def initSlots(self, filepathSlot, fullPathOutputSlot):
        self._filepathSlot = filepathSlot
        self._fullPathOutputSlot = fullPathOutputSlot
        self.fileSelectButton.clicked.connect(self._browseForFilepath)

    def showEvent(self, event):
        super(SingleFileExportOptionsWidget, self).showEvent(event)
        self.updateFromSlots()

    def updateFromSlots(self):
        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            file_path = os.path.splitext(file_path)[0] + "." + self._extension
            self.filepathEdit.setText((file_path))

            # Re-configure the slot in case we changed the extension
            self._filepathSlot.setValue(file_path)

    def _browseForFilepath(self):
        starting_dir = os.path.expanduser("~")
        if self._fullPathOutputSlot.ready():
            starting_dir = os.path.split(self._fullPathOutputSlot.value)[0]

        dlg = QFileDialog(self, "Export Location", starting_dir, self._file_filter)
        dlg.setDefaultSuffix(self._extension)
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        if not dlg.exec_():
            return

        exportPath = dlg.selectedFiles()[0]
        self._filepathSlot.setValue(exportPath)
        self.filepathEdit.setText(exportPath)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators.ioOperators import OpNpyWriter

    op = OpNpyWriter(graph=Graph())

    app = QApplication([])
    w = SingleFileExportOptionsWidget(None, "npy", "numpy files (*.npy)")
    w.initSlot(op.Filepath)
    w.show()
    app.exec_()

    print("Selected Filepath: {}".format(op.Filepath.value))

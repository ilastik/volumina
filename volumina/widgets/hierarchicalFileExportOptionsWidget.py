###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2024, the ilastik developers
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
from typing import Tuple

from qtpy import uic
from qtpy.QtCore import Signal, Qt, QEvent
from qtpy.QtWidgets import QWidget, QFileDialog, QLabel


class HierarchicalFileExportOptionsWidget(QWidget):
    pathValidityChange = Signal(bool)

    def __init__(self, parent, file_extensions: Tuple[str, ...], extension_description: str):
        super().__init__(parent)
        uic.loadUi(os.path.splitext(__file__)[0] + ".ui", self)
        self.file_extensions = file_extensions
        self.default_extension = file_extensions[0]
        self.extension_description = extension_description

        self.settings_are_valid = True

        self.filepathEdit.textEdited.connect(lambda: self._handleTextEdited(self.filepathEdit))
        if self.default_extension == ".zarr":
            self.datasetLabel.setVisible(False)
            self.datasetEdit.setVisible(False)
            self.datasetEdit.setEnabled(False)
            axisorder_label = QLabel(
                'Axis order: OME-Zarr axes are always tczyx ("transpose" setting above is ignored)'
            )
            self.gridLayout.addWidget(axisorder_label, 1, 0, 1, 3)
        else:
            self.datasetEdit.textEdited.connect(lambda: self._handleTextEdited(self.datasetEdit))

    def initSlots(self, filepathSlot, datasetNameSlot, fullPathOutputSlot):
        self._filepathSlot = filepathSlot
        self._datasetNameSlot = datasetNameSlot
        self._fullPathOutputSlot = fullPathOutputSlot
        self.fileSelectButton.clicked.connect(self._browseForFilepath)

        self.filepathEdit.installEventFilter(self)
        self.datasetEdit.installEventFilter(self)

    def showEvent(self, event):
        super().showEvent(event)
        self.updateFromSlots()

    def eventFilter(self, watched, event):
        # Apply the new path/dataset if the user presses 'enter'
        #  or clicks outside the path/dataset edit box.
        if event.type() == QEvent.FocusOut or (
            event.type() == QEvent.KeyPress and (event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return)
        ):
            if watched == self.datasetEdit:
                self._applyDataset()
            if watched == self.filepathEdit:
                self._applyFilepath()
        return False

    def _applyDataset(self):
        was_valid = self.settings_are_valid
        datasetName = self.datasetEdit.text()
        self._datasetNameSlot.setValue(str(datasetName))
        self.settings_are_valid = str(datasetName) != ""
        if self.settings_are_valid != was_valid:
            self.pathValidityChange.emit(self.settings_are_valid)

    def _applyFilepath(self):
        filepath = self.filepathEdit.text()
        self._filepathSlot.setValue(filepath)
        # TODO: Check for valid path format and signal validity

    def _handleTextEdited(self, watched):
        if watched == self.datasetEdit:
            self._applyDataset()
        if watched == self.filepathEdit:
            self._applyFilepath()

    def updateFromSlots(self):
        was_valid = self.settings_are_valid
        if self._datasetNameSlot.ready():
            dataset_name = self._datasetNameSlot.value
            self.datasetEdit.setText(dataset_name)
            self.path_is_valid = dataset_name != ""

        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            file_path, ext = os.path.splitext(file_path)
            if ext not in self.file_extensions:
                file_path += self.default_extension
            else:
                file_path += ext
            self.filepathEdit.setText(file_path)

            # Re-configure the file slot in case we changed the extension
            self._filepathSlot.setValue(file_path)

        if was_valid != self.path_is_valid:
            self.pathValidityChange.emit(self.settings_are_valid)

    def _browseForFilepath(self):
        from lazyflow.utility import PathComponents

        if self._fullPathOutputSlot.ready():
            starting_dir = PathComponents(self._fullPathOutputSlot.value).externalDirectory
        else:
            starting_dir = os.path.expanduser("~")

        dlg = QFileDialog(self, "Export Location", starting_dir, self.extension_description)

        dlg.setDefaultSuffix(self.default_extension.lstrip("."))
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        if not dlg.exec_():
            return

        exportPath = dlg.selectedFiles()[0]
        self.filepathEdit.setText(exportPath)
        self._filepathSlot.setValue(exportPath)


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication
    from lazyflow.graph import Graph, Operator, InputSlot

    class OpMock(Operator):
        Filepath = InputSlot(value="~/something.h5")
        DatasetName = InputSlot(value="volume/data")
        FullPath = InputSlot(value="~/")

        def setupOutputs(self):
            pass

        def execute(self, *args):
            pass

        def propagateDirty(self, *args):
            pass

    op = OpMock(graph=Graph())

    app = QApplication([])
    w = HierarchicalFileExportOptionsWidget(None, (".h5",), "H5 Files (*.h5)")
    w.initSlots(op.Filepath, op.DatasetName, op.FullPath)
    w.show()
    app.exec_()

    print("Selected Filepath: {}".format(op.Filepath.value))
    print("Selected Dataset: {}".format(op.DatasetName.value))

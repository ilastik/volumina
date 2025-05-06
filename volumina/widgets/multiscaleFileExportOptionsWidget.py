###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2025, the ilastik developers
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

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtWidgets import QWidget, QFileDialog


class MultiscaleFileExportOptionsWidget(QWidget):
    pathValidityChange = pyqtSignal(bool)  # Needed to satisfy expected interface

    def __init__(self, parent):
        super().__init__(parent)
        uic.loadUi(os.path.splitext(__file__)[0] + ".ui", self)
        self.file_extensions = (".zarr",)
        self.default_extension = ".zarr"
        self.extension_description = "Zarr files (*.zarr)"

        # We need to watch the textEdited signal because Qt has a bug that causes the OK button
        #  to receive it's click event BEFORE the LineEdit receives its FocusOut event.
        # (That is, we can't just watch for FocusOut events and disable the button before the click.)
        self.filepathEdit.textEdited.connect(lambda: self._handleTextEdited(self.filepathEdit))

    def initSlots(self, filepathSlot, fullPathOutputSlot, targetScalesSlot, exportImageSlot):
        self._filepathSlot = filepathSlot
        self._fullPathOutputSlot = fullPathOutputSlot
        self._targetScalesSlot = targetScalesSlot
        self._exportImageSlot = exportImageSlot
        self.fileSelectButton.clicked.connect(self._browseForFilepath)

        self.filepathEdit.installEventFilter(self)

    def showEvent(self, event):
        super().showEvent(event)
        self.updateFromSlots()

    def eventFilter(self, watched, event):
        # Apply the new path if the user presses 'enter'
        #  or clicks outside the path edit box.
        if (
            event.type() == QEvent.FocusOut
            or (event.type() == QEvent.KeyPress and (event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return))
            and watched == self.filepathEdit
        ):
            self._applyFilepath()
        return False

    def _applyFilepath(self):
        filepath = self.filepathEdit.text()
        self._filepathSlot.setValue(filepath)
        # TODO: Check for valid path format and signal validity

    def _handleTextEdited(self, watched):
        if watched == self.filepathEdit:
            self._applyFilepath()

    def updateFromSlots(self):
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

        if self._targetScalesSlot.ready():
            interpolation_text = "Interpolation: Default (Linear)"
            interpolation_order = self._exportImageSlot.meta.get("appropriate_interpolation_order")
            if interpolation_order == 0:
                interpolation_text = "Interpolation: Nearest-neighbor"
            elif interpolation_order == 1:
                interpolation_text = "Interpolation: Linear"
            self.scalingInterpolationLabel.setText(interpolation_text)

            # scales are OrderedDict[str, OrderedDict[Axiskey, int]] (multiscalesStore.Multiscales)
            scales = self._targetScalesSlot.value
            scales_html = "<p>Scales generated:</p><ul>"
            for scale_key, tagged_shape in scales.items():
                scales_html += f"<li><b>{scale_key}</b>: "
                for axis_key, axis_value in tagged_shape.items():
                    scales_html += f"{axis_key}: {axis_value}, "
                scales_html = scales_html[:-2] + "</li>"
            scales_html += "</ul>"
            self.scalesOutputLabel.setText(scales_html)

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

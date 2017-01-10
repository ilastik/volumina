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
import os
import re

from PyQt5 import uic
from PyQt5.QtCore import pyqtSignal, Qt, QEvent
from PyQt5.QtWidgets import QWidget, QFileDialog

from volumina.utility import encode_from_qstring, decode_to_qstring

try:
    from lazyflow.operators.ioOperators import OpStackWriter
    _has_lazyflow = True
except:
    _has_lazyflow = False

class StackExportFileOptionsWidget(QWidget):
    pathValidityChange = pyqtSignal(bool)
    
    def __init__(self, parent, extension):
        global _has_lazyflow
        assert _has_lazyflow, "This widget requires lazyflow to be installed."
        super( StackExportFileOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        self._extension = extension

        self.directoryEdit.installEventFilter(self)
        self.filePatternEdit.installEventFilter(self)

        self.settings_are_valid = True

    def eventFilter(self, watched, event):
        # Apply the new path if the user presses 
        #  'enter' or clicks outside the filepath editbox
        if watched == self.directoryEdit or watched == self.filePatternEdit:
            if event.type() == QEvent.FocusOut or \
               ( event.type() == QEvent.KeyPress and \
                 ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return) ):
                self._updateFromGui()
        return False

    def initSlots(self, filepathSlot, imageSlot):
        self._filepathSlot = filepathSlot
        self._imageSlot = imageSlot
        self.selectDirectoryButton.clicked.connect( self._browseForFilepath )
        imageSlot.notifyMetaChanged( self._updateDescription )
        self._updateDescription()

    def showEvent(self, event):
        super(StackExportFileOptionsWidget, self).showEvent(event)
        self._updatePathsFromSlot()
    
    def _updatePathsFromSlot(self):
        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            directory, filename_pattern = os.path.split( file_path )
            filename_pattern = os.path.splitext(filename_pattern)[0]

            # Auto-insert the {slice_index} field
            if re.search("{slice_index(:.*)?}", filename_pattern) is None:
                filename_pattern += '_{slice_index}'

            self.directoryEdit.setText( decode_to_qstring(directory) )
            self.filePatternEdit.setText( decode_to_qstring(filename_pattern + '.' + self._extension) )
            
            # Re-configure the slot in case we changed the extension
            file_path = os.path.join( directory, filename_pattern ) + '.' + self._extension            
            self._filepathSlot.setValue( file_path )

    def _updateDescription(self, *args):
        if not self._imageSlot.ready():
            self.descriptionLabel.setText("")
            return
        tagged_shape = self._imageSlot.meta.getTaggedShape()
        axes = OpStackWriter.get_nonsingleton_axes_for_tagged_shape(tagged_shape)
        step_axis = axes[0].upper()
        image_axes = "".join(axes[1:]).upper()
        description = "{} {} Images (Stacked across {})".format( tagged_shape[axes[0]], image_axes, step_axis )
        self.descriptionLabel.setText( description )

    def _browseForFilepath(self):
        starting_dir = os.path.expanduser("~")
        if self._filepathSlot.ready():
            starting_dir = os.path.split(self._filepathSlot.value)[0]
        
        export_dir = QFileDialog.getExistingDirectory( self, "Export Directory", starting_dir )
        if export_dir.isNull():
            return

        self.directoryEdit.setText( export_dir )
        self._updateFromGui()

    def _updateFromGui(self):
        export_dir = encode_from_qstring( self.directoryEdit.text() )
        filename_pattern = encode_from_qstring( self.filePatternEdit.text() )
        export_path = os.path.join( export_dir, filename_pattern )
        self._filepathSlot.setValue( export_path )
        
        old_valid_state = self.settings_are_valid

        if re.search("{slice_index(:.*)?}", export_path):
            self.settings_are_valid = True
            self.filePatternEdit.setStyleSheet("QLineEdit {background-color: white}" )
        else:
            self.settings_are_valid = False
            self.filePatternEdit.setStyleSheet("QLineEdit {background-color: red}" )

        if old_valid_state != self.settings_are_valid:
            self.pathValidityChange.emit( self.settings_are_valid )

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators.ioOperators import OpFormattedDataExport

    opDataExport = OpFormattedDataExport(graph=Graph())
    opDataExport.OutputFilenameFormat.setValue( '/home/bergs/hello.png' )

    app = QApplication([])
    w = StackExportFileOptionsWidget(None, 'png')
    w.initSlots( opDataExport.OutputFilenameFormat, opDataExport.ImageToExport )
    w.show()
    app.exec_()

    #print "Selected Filepath: {}".format( opExportSlot.ExportPath.value )



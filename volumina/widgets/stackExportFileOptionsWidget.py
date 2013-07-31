import os
import re

from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal, Qt, QEvent
from PyQt4.QtGui import QWidget, QFileDialog

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
                filename_pattern += '{slice_index}'

            self.directoryEdit.setText( directory )
            self.filePatternEdit.setText( filename_pattern + '.' + self._extension )
            
            # Re-configure the slot in case we changed the extension
            file_path = os.path.join( directory, filename_pattern ) + '.' + self._extension            
            self._filepathSlot.setValue( str(file_path) )

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
        export_dir = str( self.directoryEdit.text() )
        filename_pattern = str( self.filePatternEdit.text() )
        export_path = os.path.join( str(export_dir), filename_pattern )
        self._filepathSlot.setValue( str(export_path) )
        
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
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators.ioOperators import OpExportSlot

    opExportSlot = OpExportSlot(graph=Graph())
    opExportSlot.OutputFilenameFormat.setValue( '/home/bergs/hello.png' )

    app = QApplication([])
    w = StackExportFileOptionsWidget(None, 'png')
    w.initSlot(opExportSlot.OutputFilenameFormat)
    w.show()
    app.exec_()

    #print "Selected Filepath: {}".format( opExportSlot.ExportPath.value )



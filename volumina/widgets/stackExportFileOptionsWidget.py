import os
import re

from PyQt4 import uic
from PyQt4.QtCore import Qt, QEvent
from PyQt4.QtGui import QWidget, QFileDialog

class StackExportFileOptionsWidget(QWidget):
    
    def __init__(self, parent, extension):
        super( StackExportFileOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        self._extension = extension

        self.directoryEdit.installEventFilter(self)
        self.filePatternEdit.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Apply the new path if the user presses 
        #  'enter' or clicks outside the filepath editbox
        if watched == self.directoryEdit or watched == self.filePatternEdit:
            if event.type() == QEvent.FocusOut or \
               ( event.type() == QEvent.KeyPress and \
                 ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return) ):
                self._updateFromGui()
        return False

    def initSlot(self, filepathSlot):
        self._filepathSlot = filepathSlot
        self.selectDirectoryButton.clicked.connect( self._browseForFilepath )

    def showEvent(self, event):
        super(StackExportFileOptionsWidget, self).showEvent(event)
        self._updateFromSlot()
    
    def _updateFromSlot(self):
        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            directory, filename_pattern = os.path.split( file_path )
            filename_pattern = os.path.splitext(filename_pattern)[0]

            # Auto-insert the {slice_index} field
            if 'slice_index' not in filename_pattern:
                filename_pattern += '{slice_index}'

            self.directoryEdit.setText( directory )
            self.filePatternEdit.setText( filename_pattern + '.' + self._extension )
            
            # Re-configure the slot in case we changed the extension
            file_path = os.path.join( directory, filename_pattern ) + '.' + self._extension            
            self._filepathSlot.setValue( str(file_path) )
    
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
        
        if re.search('{slice_index.*}', export_path):
            self.filePatternEdit.setStyleSheet("QLineEdit {background-color: white}" )
        else:
            self.filePatternEdit.setStyleSheet("QLineEdit {background-color: red}" )

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



import os

from PyQt4 import uic
from PyQt4.QtCore import Qt, QEvent
from PyQt4.QtGui import QWidget, QFileDialog

class SingleFileExportOptionsWidget(QWidget):
    
    def __init__(self, parent, extension, file_filter):
        super( SingleFileExportOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        self._extension = extension
        self._file_filter = file_filter

        self.filepathEdit.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Apply the new path if the user presses 
        #  'enter' or clicks outside the filepathe editbox
        if watched == self.filepathEdit:
            if event.type() == QEvent.FocusOut or \
               ( event.type() == QEvent.KeyPress and \
                 ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return) ):
                newpath = self.filepathEdit.text()
                self._filepathSlot.setValue( str(newpath) )
        return False

    def initSlot(self, filepathSlot):        
        self._filepathSlot = filepathSlot
        self.fileSelectButton.clicked.connect( self._browseForFilepath )

    def showEvent(self, event):
        super(SingleFileExportOptionsWidget, self).showEvent(event)
        self.updateFromSlot()
        
    def updateFromSlot(self):
        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            file_path = os.path.splitext(file_path)[0] + "." + self._extension
            self.filepathEdit.setText( file_path )
            
            # Re-configure the slot in case we changed the extension
            self._filepathSlot.setValue( str(file_path) )
    
    def _browseForFilepath(self):
        starting_dir = os.path.expanduser("~")
        if self._filepathSlot.ready():
            starting_dir = os.path.split(self._filepathSlot.value)[0]
        
        dlg = QFileDialog( self, "Export Location", starting_dir, self._file_filter )
        dlg.setDefaultSuffix(self._extension)
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        if not dlg.exec_():
            return
        
        exportPath = dlg.selectedFiles()[0]
        self._filepathSlot.setValue( str(exportPath) )
        self.filepathEdit.setText( exportPath )

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators.ioOperators import OpNpyWriter

    op = OpNpyWriter(graph=Graph())

    app = QApplication([])
    w = SingleFileExportOptionsWidget(None, "npy", "numpy files (*.npy)")
    w.initSlot(op.Filepath)
    w.show()
    app.exec_()

    print "Selected Filepath: {}".format( op.Filepath.value )



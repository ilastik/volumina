import os
from functools import partial

from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal, Qt, QEvent
from PyQt4.QtGui import QWidget, QFileDialog

from volumina.utility import encode_from_qstring, decode_to_qstring

class Hdf5ExportFileOptionsWidget(QWidget):
    pathValidityChange = pyqtSignal(bool)
    
    def __init__(self, parent):
        super( Hdf5ExportFileOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )
        
        self.settings_are_valid = True

        # We need to watch the textEdited signal because Qt has a bug that causes the OK button 
        #  to receive it's click event BEFORE the LineEdit receives its FocusOut event.  
        # (That is, we can't just watch for FocusOut events and disable the button before the click.) 
        self.datasetEdit.textEdited.connect( lambda: self._handleTextEdited(self.datasetEdit) )
        
    def initSlots(self, filepathSlot, datasetNameSlot):
        self._filepathSlot = filepathSlot
        self._datasetNameSlot = datasetNameSlot
        self.fileSelectButton.clicked.connect( self._browseForFilepath )

        self.filepathEdit.installEventFilter(self)
        self.datasetEdit.installEventFilter( self )

    def showEvent(self, event):
        super(Hdf5ExportFileOptionsWidget, self).showEvent(event)
        self.updateFromSlots()
        
    def eventFilter(self, watched, event):
        # Apply the new path/dataset if the user presses 'enter' 
        #  or clicks outside the path/dataset edit box.
        if event.type() == QEvent.FocusOut or \
           ( event.type() == QEvent.KeyPress and \
             ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return) ):
            if watched == self.datasetEdit:
                self._applyDataset()
            if watched == self.filepathEdit:
                self._applyFilepath()
        return False

    def _applyDataset(self):
        was_valid = self.settings_are_valid
        datasetName = self.datasetEdit.text()
        self._datasetNameSlot.setValue( str(datasetName) )
        self.settings_are_valid = ( str(datasetName) != "" )
        if self.settings_are_valid != was_valid:
            self.pathValidityChange.emit( self.settings_are_valid )

    def _applyFilepath(self):
        filepath = self.filepathEdit.text()
        self._filepathSlot.setValue( encode_from_qstring(filepath) )
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
            self.datasetEdit.setText( dataset_name )
            self.path_is_valid = ( dataset_name != "" )

        if self._filepathSlot.ready():
            file_path = self._filepathSlot.value
            file_path, ext = os.path.splitext(file_path)
            if ext != ".h5" and ext != ".hdf5":
                file_path += ".h5"
            else:
                file_path += ext
            self.filepathEdit.setText( decode_to_qstring(file_path) )
            
            # Re-configure the file slot in case we changed the extension
            self._filepathSlot.setValue( file_path )

        if was_valid != self.path_is_valid:
            self.pathValidityChange.emit( self.settings_are_valid )

    def _browseForFilepath(self):
        starting_dir = os.path.expanduser("~")
        if self._filepathSlot.ready():
            starting_dir = os.path.split(self._filepathSlot.value)[0]
        
        dlg = QFileDialog( self, "Export Location", starting_dir, "HDF5 Files (*.h5 *.hdf5)" )
        
        dlg.setDefaultSuffix("h5")
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        if not dlg.exec_():
            return
        
        exportPath = dlg.selectedFiles()[0]
        self.filepathEdit.setText( exportPath )
        self._filepathSlot.setValue( encode_from_qstring(exportPath) )

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph, Operator, InputSlot

    class OpMock(Operator):
        Filepath = InputSlot(value='~/something.h5')
        DatasetName = InputSlot(value='volume/data')
        
        def setupOutputs(self): pass
        def execute(self, *args): pass
        def propagateDirty(self, *args): pass
    
    op = OpMock( graph=Graph() )

    app = QApplication([])
    w = Hdf5ExportFileOptionsWidget(None)
    w.initSlots( op.Filepath, op.DatasetName )
    w.show()
    app.exec_()

    print "Selected Filepath: {}".format( op.Filepath.value )
    print "Selected Dataset: {}".format( op.DatasetName.value )



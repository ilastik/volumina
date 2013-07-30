import re
import os
import collections

from PyQt4 import uic
from PyQt4.QtCore import pyqtSignal
from PyQt4.QtGui import QWidget

from singleFileExportOptionsWidget import SingleFileExportOptionsWidget
from hdf5ExportFileOptionsWidget import Hdf5ExportFileOptionsWidget
from stackExportFileOptionsWidget import StackExportFileOptionsWidget

try:
    from lazyflow.operators.ioOperators import OpExportSlot
    _has_lazyflow = True
except:
    _has_lazyflow = False

class MultiformatSlotExportFileOptionsWidget(QWidget):
    formatValidityChange = pyqtSignal(bool)
    
    def __init__(self, parent):
        global _has_lazyflow
        assert _has_lazyflow, "This widget can't be used unless you have lazyflow installed."
        super( MultiformatSlotExportFileOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )
        self._valid_selection = True
        self.formatErrorLabel.setVisible(False)

    def initExportOp(self, opDataExport):
        self._opDataExport = opDataExport

        opDataExport.FormatSelectionIsValid.notifyDirty( self._handleFormatValidChange )
        
        self.hdf5OptionsWidget = Hdf5ExportFileOptionsWidget( self )
        self.hdf5OptionsWidget.initSlots( opDataExport.OutputFilenameFormat,
                                          opDataExport.OutputInternalPath )

        self.npyOptionsWidget = SingleFileExportOptionsWidget( self, "npy", "numpy files (*.npy)" )
        self.npyOptionsWidget.initSlot( opDataExport.OutputFilenameFormat )

        # Specify our supported formats and their associated property widgets
        # TODO: Explicitly reconcile this with the opDataExport.FORMATS
        self._format_option_editors = \
            collections.OrderedDict([ ('hdf5', self.hdf5OptionsWidget),
                                      ('npy', self.npyOptionsWidget) ])

        for fmt in OpExportSlot._2d_formats:
            widget = SingleFileExportOptionsWidget( self, fmt.extension, "{ext} files (*.{ext})".format( ext=fmt.extension ))
            widget.initSlot( opDataExport.OutputFilenameFormat )
            self._format_option_editors[fmt.name] = widget

        for fmt in OpExportSlot._3d_sequence_formats:
            widget = StackExportFileOptionsWidget( self, fmt.extension )
            widget.initSlots( opDataExport.OutputFilenameFormat, opDataExport.ImageToExport )
            self._format_option_editors[fmt.name] = widget

        # Populate the format combo
        for file_format, widget in self._format_option_editors.items():
            self.formatCombo.addItem( file_format )

        # Populate the stacked widget
        # (Some formats use the same options widget; eliminate repeats first)
        all_widgets = set( self._format_option_editors.values() )
        for widget in all_widgets:
            self.stackedWidget.addWidget( widget )
        
        self.formatCombo.currentIndexChanged.connect( self._handleFormatChange )

        # Determine starting format
        index = self.formatCombo.findText(opDataExport.OutputFormat.value)
        self.formatCombo.setCurrentIndex(index)
        self._handleFormatChange(index)
        
    def _handleFormatChange(self, index):
        file_format = str( self.formatCombo.currentText() )
        option_widget = self._format_option_editors[file_format]
        self._opDataExport.OutputFormat.setValue( file_format )

        # Auto-remove any instance of 'slice_index' from the 
        #  dataset path if the user switches to a non-sequence type
        # TODO: This is a little hacky.  Could be fixed by defining an ABC for 
        #       file option widgets with a 'repair path' method or something 
        #       similar, but that seems like overkill for now.
        export_path = str( self._opDataExport.OutputFilenameFormat.value )
        if not isinstance(option_widget, StackExportFileOptionsWidget) \
           and re.search('{slice_index.*}', export_path):
            try:
                from lazyflow.utility import format_known_keys
                export_path = format_known_keys(export_path, { 'slice_index':1234567890 } )
                export_path = export_path.replace('1234567890', '')
            except:
                pass
            else:
                self._opDataExport.OutputFilenameFormat.setValue( export_path )

        # Show the new option widget
        self.stackedWidget.setCurrentWidget( option_widget )
    
    def _handleFormatValidChange(self, *args):
        old_valid = self._valid_selection
        self._valid_selection = self._opDataExport.FormatSelectionIsValid.value
        self.formatErrorLabel.setVisible(not self._valid_selection)
        if self._valid_selection != old_valid:
            self.formatValidityChange.emit(self._valid_selection)

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph, Operator, InputSlot
    from lazyflow.operators.ioOperators import OpFormattedDataExport

    class OpMock(Operator):
        OutputFilenameFormat = InputSlot(value='~/something.h5')
        OutputInternalPath = InputSlot(value='volume/data')
        OutputFormat = InputSlot(value='hdf5')
        FormatSelectionIsValid = InputSlot(value=True) # Normally an output slot
        
        def setupOutputs(self): pass
        def execute(self, *args): pass
        def propagateDirty(self, *args): pass
    
    op = OpFormattedDataExport( graph=Graph() )

    app = QApplication([])
    w = MultiformatSlotExportFileOptionsWidget(None)
    w.initExportOp(op)
    w.show()
    app.exec_()

    print "Selected Filepath: {}".format( op.OutputFilenameFormat.value )
    print "Selected Dataset: {}".format( op.OutputInternalPath.value )




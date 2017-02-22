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
except ImportError:
    _has_lazyflow = False

try:
    from dvidVolumeExportOptionsWidget import DvidVolumeExportOptionsWidget
    _supports_dvid = True
except ImportError:
    _supports_dvid = False

class MultiformatSlotExportFileOptionsWidget(QWidget):
    formatValidityChange = pyqtSignal(str) # str
    pathValidityChange = pyqtSignal(bool)
    
    def __init__(self, parent):
        global _has_lazyflow
        assert _has_lazyflow, "This widget can't be used unless you have lazyflow installed."
        super( MultiformatSlotExportFileOptionsWidget, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )
        self._selection_error_msg = ""
        self._valid_path = True
        self.formatErrorLabel.setVisible(False)

    def initExportOp(self, opDataExport):
        self._opDataExport = opDataExport

        opDataExport.FormatSelectionErrorMsg.notifyDirty( self._handleFormatValidChange )
        
        # Specify our supported formats and their associated property widgets
        self._format_option_editors = collections.OrderedDict()

        # HDF5
        for fmt in ('hdf5', 'compressed hdf5'):
            hdf5OptionsWidget = Hdf5ExportFileOptionsWidget( self )
            hdf5OptionsWidget.initSlots( opDataExport.OutputFilenameFormat,
                                         opDataExport.OutputInternalPath )
            hdf5OptionsWidget.pathValidityChange.connect( self._handlePathValidityChange )
            self._format_option_editors[fmt] = hdf5OptionsWidget

        # Numpy
        npyOptionsWidget = SingleFileExportOptionsWidget( self, "npy", "numpy files (*.npy)" )
        npyOptionsWidget.initSlot( opDataExport.OutputFilenameFormat )
        self._format_option_editors['npy'] = npyOptionsWidget

        # DVID
        if _supports_dvid:
            dvidOptionsWidget = DvidVolumeExportOptionsWidget( self )
            dvidOptionsWidget.initSlot( opDataExport.OutputFilenameFormat )
            self._format_option_editors['dvid'] = dvidOptionsWidget

        # All 2D image formats
        for fmt in OpExportSlot._2d_formats:
            widget = SingleFileExportOptionsWidget( self, fmt.extension, "{ext} files (*.{ext})".format( ext=fmt.extension ))
            widget.initSlot( opDataExport.OutputFilenameFormat )
            self._format_option_editors[fmt.name] = widget

        # Sequences of 2D images
        for fmt in OpExportSlot._3d_sequence_formats:
            widget = StackExportFileOptionsWidget( self, fmt.extension )
            widget.initSlots( opDataExport.OutputFilenameFormat, opDataExport.ImageToExport )
            widget.pathValidityChange.connect( self._handlePathValidityChange )
            self._format_option_editors[fmt.name] = widget

        # Multipage TIFF
        multipageTiffWidget = SingleFileExportOptionsWidget( self, "tiff", "TIFF files (*.tif *tiff)" )
        multipageTiffWidget.initSlot( opDataExport.OutputFilenameFormat )
        self._format_option_editors["multipage tiff"] = multipageTiffWidget
        
        # Sequence of Multipage TIFF
        multipageTiffSequenceWidget = StackExportFileOptionsWidget( self, "tiff" )
        multipageTiffSequenceWidget.initSlots( opDataExport.OutputFilenameFormat, opDataExport.ImageToExport )
        multipageTiffSequenceWidget.pathValidityChange.connect( self._handlePathValidityChange )
        self._format_option_editors["multipage tiff sequence"] = multipageTiffSequenceWidget

        # DEBUG ONLY: blockwise hdf5
        blockwiseHdf5OptionsWidget = SingleFileExportOptionsWidget( self, "json", "Blockwise Volume description (*.json)" )
        blockwiseHdf5OptionsWidget.initSlot( opDataExport.OutputFilenameFormat )
        self._format_option_editors['blockwise hdf5'] = blockwiseHdf5OptionsWidget

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
        
        self._handlePathValidityChange()
    
    def _handleFormatValidChange(self, *args):
        old_err = self._selection_error_msg
        self._selection_error_msg = self._opDataExport.FormatSelectionErrorMsg.value
        self.formatErrorLabel.setVisible(self._selection_error_msg is not None)
        self.formatErrorLabel.setText( '<font color="red">' + self._selection_error_msg + '</font>' )

        if self._selection_error_msg != old_err:
            self.formatValidityChange.emit( self._selection_error_msg )

    def _handlePathValidityChange(self):
        old_valid = self._valid_path
        if hasattr( self.stackedWidget.currentWidget(), 'settings_are_valid' ):
            self._valid_path = self.stackedWidget.currentWidget().settings_are_valid
        else:
            self._valid_path = True

        if old_valid != self._valid_path:
            self.pathValidityChange.emit( self._valid_path )

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph, Operator, InputSlot
    from lazyflow.operators.ioOperators import OpFormattedDataExport

    class OpMock(Operator):
        OutputFilenameFormat = InputSlot(value='~/something.h5')
        OutputInternalPath = InputSlot(value='volume/data')
        OutputFormat = InputSlot(value='hdf5')
        FormatSelectionErrorMsg = InputSlot(value=True) # Normally an output slot
        
        def setupOutputs(self): pass
        def execute(self, *args): pass
        def propagateDirty(self, *args): pass
    
    import numpy as np
    import vigra
    
    data = np.zeros((100,200,10), dtype=np.uint8)
    data = vigra.taggedView(data, 'yxc')
    op = OpFormattedDataExport( graph=Graph() )
    
    op.Input.setValue(data)
    op.TransactionSlot.setValue(True)
    

    app = QApplication([])
    w = MultiformatSlotExportFileOptionsWidget(None)
    w.initExportOp(op)
    w.show()
    app.exec_()

    print "Selected Filepath: {}".format( op.OutputFilenameFormat.value )
    print "Selected Dataset: {}".format( op.OutputInternalPath.value )




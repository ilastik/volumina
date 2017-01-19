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
from builtins import str
import os
import collections
from functools import partial

import numpy

from PyQt5 import uic
from PyQt5.QtCore import Qt, QObject, QEvent
from PyQt5.QtWidgets import QDialog, QDialogButtonBox
from PyQt5.QtGui import QValidator

try:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
    _has_lazyflow = True
except:
    _has_lazyflow = False

#**************************************************************************
# Model operator interface ABC
#**************************************************************************
if _has_lazyflow:
    class ExportOperatorABC(Operator):
        """
        The export dialog is designed to work with any operator that satisfies this ABC interface.
        """
        # Operator.__metaclass__ already inherits ABCMeta
        # __metaclass__ = ABCMeta
        
        # The original image, which we'll transform and export.
        Input = InputSlot()
    
        # See OpFormattedDataExport for details
        TransactionSlot = InputSlot()
    
        # Subregion params
        RegionStart = InputSlot(optional=True)
        RegionStop = InputSlot(optional=True)
    
        # Normalization params    
        InputMin = InputSlot(optional=True)
        InputMax = InputSlot(optional=True)
        ExportMin = InputSlot(optional=True)
        ExportMax = InputSlot(optional=True)
    
        ExportDtype = InputSlot(optional=True)
        OutputAxisOrder = InputSlot(optional=True)
        
        # File settings
        OutputFilenameFormat = InputSlot(value='RESULTS_{roi}') # A format string allowing {roi}, {x_start}, {x_stop}, etc.
        OutputInternalPath = InputSlot(value='exported_data')
        OutputFormat = InputSlot(value='hdf5')
    
        ConvertedImage = OutputSlot() # Preprocessed image, BEFORE axis reordering
        ImageToExport = OutputSlot() # Preview of the pre-processed image that will be exported
        ExportPath = OutputSlot() # Location of the saved file after export is complete.
        FormatSelectionErrorMsg = OutputSlot()
    
        @classmethod
        def __subclasshook__(cls, C):
            # Must have all the required input and output slots.
            if cls is ExportOperatorABC:
                for slot in cls.inputSlots:
                    if not hasattr(C, slot.name) or not isinstance(getattr(C, slot.name), InputSlot):
                        return False
                for slot in cls.outputSlots:
                    if not hasattr(C, slot.name) or not isinstance(getattr(C, slot.name), OutputSlot):
                        return False
                return True
            return NotImplemented

#**************************************************************************
# DataExportOptionsDlg
#**************************************************************************
class DataExportOptionsDlg(QDialog):
    
    def __init__(self, parent, opDataExport):
        """
        Constructor.
        
        :param parent: The parent widget
        :param opDataExport: The operator to configure.  The operator is manipulated LIVE, so supply a 
                             temporary operator that can be discarded in case the user clicked 'cancel'.
                             If the user clicks 'OK', then copy the slot settings from the temporary op to your real one.
        """
        global _has_lazyflow
        assert _has_lazyflow, "This widget requires lazyflow."
        super( DataExportOptionsDlg, self ).__init__(parent)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        self._opDataExport = opDataExport
        assert isinstance( opDataExport, ExportOperatorABC ), \
            "Cannot use {} as an export operator.  "\
            "It doesn't match the required interface".format( type(opDataExport) )

        self._okay_conditions = {}

        # Connect the 'transaction slot'.
        # All slot changes will occur immediately
        opDataExport.TransactionSlot.setValue(True)

        # Init child widgets
        self._initMetaInfoWidgets()
        self._initSubregionWidget()
        self._initDtypeConversionWidgets()
        self._initRenormalizationWidgets()
        self._initAxisOrderWidgets()
        self._initFileOptionsWidget()

        # See self.eventFilter()
        self.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Ignore 'enter' keypress events, since the user may just be entering settings.
        # The user must manually click the 'OK' button to close the dialog.
        if watched == self and \
           event.type() == QEvent.KeyPress and \
           ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return):
            return True
        return False

    def _set_okay_condition(self, name, status):
        self._okay_conditions[name] = status
        all_okay = all( self._okay_conditions.values() )
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled( all_okay )

    #**************************************************************************
    # Input/Output Meta-info (display only)
    #**************************************************************************
    def _initMetaInfoWidgets(self):
        ## Input/output meta-info display widgets
        opDataExport = self._opDataExport
        self.inputMetaInfoWidget.initSlot( opDataExport.Input )
        self.outputMetaInfoWidget.initSlot( opDataExport.ImageToExport )

    #**************************************************************************
    # Subregion roi
    #**************************************************************************
    def _initSubregionWidget(self):
        opDataExport = self._opDataExport
        inputAxes = opDataExport.Input.meta.getAxisKeys()

        shape = opDataExport.Input.meta.shape
        start = (None,) * len( shape )
        stop = (None,) * len( shape )

        if opDataExport.RegionStart.ready():
            start = opDataExport.RegionStart.value
        if opDataExport.RegionStop.ready():
            stop = opDataExport.RegionStop.value

        self.roiWidget.initWithExtents( inputAxes, shape, start, stop )
        
        def _handleRoiChange(newstart, newstop):
            if not self.isVisible() or not opDataExport.Input.ready():
                # Can happen if we're still listening to slot changes after we've been closed.
                return
            # Unfortunately, we have to handle a special case here:
            # If the user's previous subregion produced a singleton axis,
            #  then he may have dropped that axis using the 'transpose' edit box.
            # However, if the user is now manipulating the roi again, we need to check to see if that singleton axis was expanded.
            # If it was, then we need to reset the axis order again.  It's no longer valid to drop the axis (it's not a singleton any more.)
            tagged_input_shape = opDataExport.Input.meta.getTaggedShape()
            tagged_output_shape = opDataExport.ImageToExport.meta.getTaggedShape()
            missing_axes = set( tagged_input_shape.keys() ) - set( tagged_output_shape.keys() )
            for axis in missing_axes:
                index = list(tagged_input_shape.keys()).index( axis )
                if (stop[index] is None and tagged_input_shape[axis] > 1) \
                or (stop[index] is not None and stop[index] - start[index] > 1):
                    self.axisOrderCheckbox.setChecked(False)
                    break

            # Configure the operator for the new subregion.
            opDataExport.RegionStart.setValue( newstart )
            opDataExport.RegionStop.setValue( newstop )

        self.roiWidget.roiChanged.connect( _handleRoiChange )

    #**************************************************************************
    # Dtype conversion
    #**************************************************************************
    def _initDtypeConversionWidgets(self):
        def _selectDefaultDtype():
            dtype = self._opDataExport.ImageToExport.meta.dtype
            index = self.dtypeCombo.findData( dtype.__name__ )
            self.dtypeCombo.setCurrentIndex( index )
    
        def _handleConvertDtypeChecked():
            checked = self.convertDtypeCheckbox.isChecked()
            self.dtypeCombo.setEnabled( checked )
            if not checked:
                self._opDataExport.ExportDtype.disconnect()
                _selectDefaultDtype()

        self.convertDtypeCheckbox.toggled.connect( _handleConvertDtypeChecked )
        dtypes = collections.OrderedDict([ ( "unsigned 8-bit",   "uint8" ),
                                           ( "unsigned 16-bit", "uint16" ),
                                           ( "unsigned 32-bit", "uint32" ),
                                           ( "unsigned 64-bit", "uint64" ),
                                           ( "signed 8-bit",     "int8" ),
                                           ( "signed 16-bit",   "int16" ),
                                           ( "signed 32-bit",   "int32" ),
                                           ( "signed 64-bit",   "int64" ),
                                           ( "floating 32-bit", "float32" ),
                                           ( "floating 64-bit", "float64" ) ])
        for name, dtype in list(dtypes.items()):
            self.dtypeCombo.addItem( name, dtype )

        def _handleDtypeSelected():
            # The dtype combo selection changed.  Update the operator to match.
            index = self.dtypeCombo.currentIndex()
            dtype_string = str( self.dtypeCombo.itemData(index) )
            dtype = numpy.dtype(dtype_string).type
            self._opDataExport.ExportDtype.setValue( dtype )
    
        self.dtypeCombo.currentIndexChanged.connect( _handleDtypeSelected )
        self.dtypeCombo.setEnabled( False )

        # Set the starting setting according to the operator.
        _selectDefaultDtype()
        dtype = self._opDataExport.ImageToExport.meta.dtype
        if dtype != self._opDataExport.Input.meta.dtype:
            self.convertDtypeCheckbox.setChecked(True)
            self.dtypeCombo.setEnabled( True )

    #**************************************************************************
    # Renormalization
    #**************************************************************************
    def _initRenormalizationWidgets(self):
        opDataExport = self._opDataExport
        dtype = opDataExport.Input.meta.dtype
        if opDataExport.InputMax.ready():
            drange = ( opDataExport.InputMin.value, opDataExport.InputMax.value )
        else:
            drange = opDataExport.Input.meta.drange or default_drange( dtype )

        def _handleRangeChange():
            if not self.renormalizeCheckbox.isChecked() or not opDataExport.Input.ready():
                return
            # Update the operator with the new settings
            input_drange = self.inputValueRange.getValues()
            output_drange = self.outputValueRange.getValues()
            
            # Use transaction slot to ensure atomicity of these settings
            opDataExport.TransactionSlot.disconnect()
            opDataExport.InputMin.setValue( input_drange[0] )
            opDataExport.InputMax.setValue( input_drange[1] )
            opDataExport.ExportMin.setValue( output_drange[0] )
            opDataExport.ExportMax.setValue( output_drange[1] )
            opDataExport.TransactionSlot.setValue(True)

        def _setDefaultInputRange():
            self.inputValueRange.setDType( dtype )
            self.inputValueRange.setLimits( *dtype_limits(dtype) )
            self.inputValueRange.setValues( *drange )

        def _updateOutputRangeForNewDtype(output_dtype):
            self.outputValueRange.setDType( output_dtype )
            self.outputValueRange.setLimits( *dtype_limits( output_dtype ) )
            self.outputValueRange.setValues( *default_drange( output_dtype ) )

        def _handleRenormalizeChecked( checked ):
            self.inputValueRange.setEnabled( checked )
            self.outputValueRange.setEnabled( checked )
            if checked:
                output_dtype = opDataExport.ImageToExport.meta.dtype
                _setDefaultInputRange()
                _updateOutputRangeForNewDtype(output_dtype)
                _handleRangeChange()
            else:
                # Clear the gui
                self.inputValueRange.setBlank()
                self.outputValueRange.setBlank()
                # Clear the operator slots
                # Use transaction slot to ensure atomicity of these settings
                opDataExport.TransactionSlot.disconnect()
                opDataExport.InputMin.disconnect()
                opDataExport.InputMax.disconnect()
                opDataExport.ExportMin.disconnect()
                opDataExport.ExportMax.disconnect()
                opDataExport.TransactionSlot.setValue(True)

        # Init gui with default values
        _updateOutputRangeForNewDtype( opDataExport.ImageToExport.meta.dtype )
            
        # Update gui with settings from the operator (if any)
        if opDataExport.InputMax.ready():
            self.renormalizeCheckbox.setChecked( True )
            self.inputValueRange.setEnabled( True )
            self.outputValueRange.setEnabled( True )
            self.inputValueRange.setValues( *drange )
        else:
            self.renormalizeCheckbox.setChecked( False )
            self.inputValueRange.setEnabled( False )
            self.outputValueRange.setEnabled( False )
            self.inputValueRange.setBlank()
            self.outputValueRange.setBlank()

        if opDataExport.ExportMax.ready():
            self.outputValueRange.setValues( opDataExport.ExportMin.value, opDataExport.ExportMax.value )

        # Subscribe to user changes
        self.inputValueRange.changedSignal.connect( _handleRangeChange )
        self.outputValueRange.changedSignal.connect( _handleRangeChange )
        self.renormalizeCheckbox.toggled.connect( _handleRenormalizeChecked )

        def _handleOutputDtypeChange(*args):
            """
            The output slot dtype changed.
            Update the normalization gui controls with the appropriate limits.
            """
            output_dtype = self._opDataExport.ImageToExport.meta.dtype
            if output_dtype != self.outputValueRange.dtype and self.renormalizeCheckbox.isChecked():
                _updateOutputRangeForNewDtype(output_dtype)

        # Update the output range widget whenever the output dtype changes.
        opDataExport.ImageToExport.notifyMetaChanged( _handleOutputDtypeChange )

    #**************************************************************************
    # Axis order
    #**************************************************************************
    def _initAxisOrderWidgets(self):
        if self._opDataExport.OutputAxisOrder.ready():
            self.axisOrderCheckbox.setChecked( Qt.Checked )
            self.outputAxisOrderEdit.setText( self._opDataExport.OutputAxisOrder.value )
            
        def _handleNewAxisOrder():
            new_order = str( self.outputAxisOrderEdit.text() )
            validator_state, _, _ = self.outputAxisOrderEdit.validator().validate( new_order, 0 )
            if validator_state == QValidator.Acceptable:
                self._opDataExport.OutputAxisOrder.setValue( new_order )

        def _handleAxisOrderChecked( checked ):
            self.outputAxisOrderEdit.setEnabled( checked )
            default_order = "".join( self._opDataExport.Input.meta.getAxisKeys() )
            self.outputAxisOrderEdit.setText( default_order )
            if checked:
                _handleNewAxisOrder()
            else:
                self._opDataExport.OutputAxisOrder.disconnect()
                self._updateAxisOrderColor(False)
        
        self.outputAxisOrderEdit.editingFinished.connect( _handleNewAxisOrder )
        self.outputAxisOrderEdit.textChanged.connect( partial(self._updateAxisOrderColor, True) )
        self.outputAxisOrderEdit.setValidator( DataExportOptionsDlg._AxisOrderValidator( self, self._opDataExport.ConvertedImage ) )
        self.outputAxisOrderEdit.installEventFilter( DataExportOptionsDlg._AxisOrderEventFilter(self) )
        self.axisOrderCheckbox.toggled.connect( _handleAxisOrderChecked )
        
    def _updateAxisOrderColor(self, allow_intermediate):
        checked = self.axisOrderCheckbox.isChecked()
        text = self.outputAxisOrderEdit.text()
        state, _, _ = self.outputAxisOrderEdit.validator().validate( text, 0 )
        invalidAxes = (checked and state != QValidator.Acceptable and not allow_intermediate)
        self._set_okay_condition('axis order', not invalidAxes)
        if invalidAxes:
            self.outputAxisOrderEdit.setStyleSheet("QLineEdit {background-color: red}" )
        else:
            self.outputAxisOrderEdit.setStyleSheet("QLineEdit {background-color: white}" )

    class _AxisOrderEventFilter(QObject):
        def __init__(self, parent):
            super( DataExportOptionsDlg._AxisOrderEventFilter, self ).__init__(parent)

        def eventFilter(self, watched, event):
            # Watch for focus-out events and 'enter' keypresses
            if event.type() == QEvent.FocusOut or \
               ( event.type() == QEvent.KeyPress and \
                 ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return) ):
                self.parent()._updateAxisOrderColor( allow_intermediate=False )    
            return False

    class _AxisOrderValidator(QValidator):
        def __init__(self, parent, inputSlot):
            super( DataExportOptionsDlg._AxisOrderValidator, self ).__init__(parent)
            self._inputSlot = inputSlot
        
        def validate(self, userAxes, pos):
            taggedShape = self._inputSlot.meta.getTaggedShape()
            inputAxes = list(taggedShape.keys())
            inputSet = set(inputAxes)
            userSet = set(str(userAxes))
            
            # Ensure all user axes appear in the input
            if not (userSet <= inputSet):
                return (QValidator.Invalid, userAxes, pos)
            
            # Ensure no repeats
            if len(userSet) != len(userAxes):
                return (QValidator.Invalid, userAxes, pos)
            
            # If missing non-singleton axes, maybe intermediate entry
            # (It's okay to omit singleton axes)
            for key in (inputSet - userSet):
                if taggedShape[key] != 1:
                    return (QValidator.Intermediate, userAxes, pos)
            
            return (QValidator.Acceptable, userAxes, pos)

    #**************************************************************************
    # File format and options
    #**************************************************************************
    def _initFileOptionsWidget(self):
        opDataExport = self._opDataExport
        self.exportFileOptionsWidget.initExportOp( opDataExport )
        def set_okay_from_format_error(error_msg):
            self._set_okay_condition('file format', error_msg == "")
        self.exportFileOptionsWidget.formatValidityChange.connect( set_okay_from_format_error )
        self.exportFileOptionsWidget.pathValidityChange.connect( partial(self._set_okay_condition, 'file path') )
        
#**************************************************************************
# Helper functions
#**************************************************************************
def default_drange(dtype):
    if numpy.issubdtype(dtype, numpy.integer):
        return dtype_limits(dtype)
    if numpy.issubdtype(dtype, numpy.floating):
        return (0.0, 1.0)
    raise RuntimeError( "Unknown dtype: {}".format( dtype ) )

def dtype_limits(dtype):
    if numpy.issubdtype(dtype, numpy.integer):
        return (numpy.iinfo(dtype).min, numpy.iinfo(dtype).max)
    if numpy.issubdtype(dtype, numpy.floating):
        return (numpy.finfo(dtype).min, numpy.finfo(dtype).max)
    raise RuntimeError( "Unknown dtype: {}".format( dtype ) )

#**************************************************************************
# Quick debug
#**************************************************************************
if __name__ == "__main__":
    import vigra
    from PyQt5.QtWidgets import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators.ioOperators import OpFormattedDataExport

    data = numpy.zeros( (10,20,30,3), dtype=numpy.float32 )
    data = vigra.taggedView(data, 'xyzc')

    op = OpFormattedDataExport( graph=Graph() )
    op.Input.setValue( data )
    op.TransactionSlot.setValue(True)

    app = QApplication([])
    w = DataExportOptionsDlg(None, op)
    w.show()
    
    app.exec_()

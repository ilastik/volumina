#Python
from functools import partial

#Qt
from PyQt4.QtCore import pyqtSignal, QObject
from PyQt4.QtGui import QMessageBox

#volumina
from dataExportOptionsDlg import DataExportOptionsDlg
from multiStepProgressDialog import MultiStepProgressDialog

###
### lazyflow
###
_has_lazyflow = True
try:
    from lazyflow.graph import Graph
    from lazyflow.request import Request
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False


def get_settings_and_export_layer(layer, parent_widget=None):
    """
    Prompt the user for layer export settings, and perform the layer export.
    """
    sourceTags = [True for l in layer.datasources]
    for i, source in enumerate(layer.datasources):
        if not hasattr(source, "dataSlot"):
             sourceTags[i] = False
    if not any(sourceTags):
        raise RuntimeError("can not export from a non-lazyflow data source (layer=%r, datasource=%r)" % (type(layer), type(layer.datasources[0])) )


    if not _has_lazyflow:
        raise RuntimeError("lazyflow not installed") 
    import lazyflow
    dataSlots = [slot.dataSlot for (slot, isSlot) in
                 zip(layer.datasources, sourceTags) if isSlot is True]

    opStackChannels = lazyflow.operators.OpMultiArrayStacker(dataSlots[0].getRealOperator().parent)
    for slot in dataSlots:
        assert isinstance(slot, lazyflow.graph.Slot), "slot is of type %r" % (type(slot))
        assert isinstance(slot.getRealOperator(), lazyflow.graph.Operator), "slot's operator is of type %r" % (type(slot.getRealOperator()))
    opStackChannels.AxisFlag.setValue("c")
    opStackChannels.Images.resize(len(dataSlots))
    for i,islot in enumerate(opStackChannels.Images):
        islot.connect(dataSlots[i])

    # Create an operator to do the work
    from lazyflow.operators.ioOperators import OpFormattedDataExport
    opExport = OpFormattedDataExport( parent=opStackChannels.parent )
    opExport.OutputFilenameFormat.setValue( layer.name )
    opExport.Input.connect( opStackChannels.Output )
    opExport.TransactionSlot.setValue(True)
    
    # Use this dialog to populate the operator's slot settings
    settingsDlg = DataExportOptionsDlg( parent_widget, opExport )

    # If user didn't cancel, run the export now.
    if ( settingsDlg.exec_() == DataExportOptionsDlg.Accepted ):
        helper = ExportHelper( parent_widget )
        helper.run(opExport)
        
    # Clean up our temporary operators
    opExport.cleanUp()
    opStackChannels.cleanUp()


class ExportHelper(QObject):
    """
    Executes a layer export in the background, shows a progress dialog, and displays errors (if any).
    """
    # This signal is used to ensure that request 
    #  callbacks are executed in the gui thread
    _forwardingSignal = pyqtSignal( object )

    def _handleForwardedCall(self, fn):
        # Execute the callback
        fn()
    
    def __init__(self, parent):
        super( ExportHelper, self ).__init__(parent)
        self._forwardingSignal.connect( self._handleForwardedCall )

    def run(self, opExport):
        """
        Start the export and return immediately (after showing the progress dialog).
        
        :param opExport: The export object to execute.
                         It must have a 'run_export()' method and a 'progressSignal' member.
        """
        progressDlg = MultiStepProgressDialog(parent=self.parent())
        progressDlg.setNumberOfSteps(1)
        
        def _forwardProgressToGui(progress):
            self._forwardingSignal.emit( partial( progressDlg.setStepProgress, progress ) )
        opExport.progressSignal.subscribe( _forwardProgressToGui )
    
        def _onFinishExport( *args ): # Also called on cancel
            self._forwardingSignal.emit( progressDlg.finishStep )
    
        def _onFail( exc, exc_info ):
            import traceback
            traceback.print_tb(exc_info[2])
            msg = "Failed to export layer due to the following error:\n{}".format( exc )
            self._forwardingSignal.emit( partial(QMessageBox.critical, self.parent(), "Export Failed", msg) )
            self._forwardingSignal.emit( progressDlg.setFailed )

        # Use a request to execute in the background    
        req = Request( opExport.run_export )
        req.notify_cancelled( _onFinishExport )
        req.notify_finished( _onFinishExport )
        req.notify_failed( _onFail )

        # Allow cancel.
        progressDlg.rejected.connect( req.cancel )

        # Start the export
        req.submit()

        # Execute the progress dialog
        # (We can block the thread here because the QDialog spins up its own event loop.)
        progressDlg.exec_()

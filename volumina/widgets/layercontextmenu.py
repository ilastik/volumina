#Python
from functools import partial

#Qt
from PyQt4.QtCore import Qt
from PyQt4.QtGui import QMenu, QAction, QDialog, QHBoxLayout, QTableWidget, QSizePolicy, QTableWidgetItem, QColor

#volumina
from volumina.layer import ColortableLayer, GrayscaleLayer, RGBALayer, ClickableColortableLayer
from layerDialog import GrayscaleLayerDialog, RGBALayerDialog
from exportDlg import ExportDialog

#===----------------------------------------------------------------------------------------------------------------===

###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.graph import Graph
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False

def _add_actions_grayscalelayer( layer, menu ):
    def adjust_thresholds_callback():
        dlg = GrayscaleLayerDialog(layer, menu.parent())
        dlg.show()
        
    adjThresholdAction = QAction("Adjust thresholds", menu)
    adjThresholdAction.triggered.connect(adjust_thresholds_callback)
    menu.addAction(adjThresholdAction)

def _add_actions_rgbalayer( layer, menu ): 
    def adjust_thresholds_callback():
        dlg = RGBALayerDialog(layer, menu.parent())
        dlg.show()

    adjThresholdAction = QAction("Adjust thresholds", menu)
    adjThresholdAction.triggered.connect(adjust_thresholds_callback)
    menu.addAction(adjThresholdAction)
 
class LayerColortableDialog(QDialog):
    def __init__(self, layer, parent=None):
        super(LayerColortableDialog, self).__init__(parent=parent)
        
        h = QHBoxLayout(self)
        t = QTableWidget(self)
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)       
        t.setRowCount(len(layer._colorTable))
        t.setColumnCount(1)
        t.setVerticalHeaderLabels(["%d" %i for i in range(len(layer._colorTable))])
        
        for i in range(len(layer._colorTable)): 
            item = QTableWidgetItem(" ")
            t.setItem(i,0, item);
            item.setBackgroundColor(QColor.fromRgba(layer._colorTable[i]))
            item.setFlags(Qt.ItemIsSelectable)
        
        h.addWidget(t)
    
def _add_actions_colortablelayer( layer, menu ): 
    def adjust_colortable_callback():
        dlg = LayerColortableDialog(layer, menu.parent())
        dlg.exec_()
        
    adjColortableAction = QAction("Change colortable", menu)
    adjColortableAction.triggered.connect(adjust_colortable_callback)
    menu.addAction(adjColortableAction)
    if layer.colortableIsRandom:
        randomizeColors = QAction("Randomize colors", menu)
        randomizeColors.triggered.connect(layer.randomizeColors)
        menu.addAction(randomizeColors)

def _add_actions( layer, menu ):
    if isinstance(layer, GrayscaleLayer):
        _add_actions_grayscalelayer( layer, menu )
    elif isinstance( layer, RGBALayer ):
        _add_actions_rgbalayer( layer, menu )
    elif isinstance( layer, ColortableLayer ) or isinstance( layer, ClickableColortableLayer ):
        pass
        #This feature is currently not implemented
        #_add_actions_colortablelayer( layer, menu )

def layercontextmenu( layer, pos, parent=None, volumeEditor = None ):
    '''Show a context menu to manipulate properties of layer.

    layer -- a volumina layer instance
    pos -- QPoint 

    '''
    def onExport():
        sourceTags = [True for l in layer.datasources]
        for i, source in enumerate(layer.datasources):
            if not hasattr(source, "dataSlot"):
                 sourceTags[i] = False
        if not any(sourceTags):
            raise RuntimeError("can not export from a non-lazyflow data source (layer=%r, datasource=%r)" % (type(layer), type(layer.datasources[0])) )


        expDlg = ExportDialog(parent = menu, layername = layer.name)
        if not _has_lazyflow:
            raise RuntimeError("lazyflow not installed") 
        import lazyflow
        dataSlots = [slot.dataSlot for (slot, isSlot) in
                     zip(layer.datasources, sourceTags) if isSlot is True]
        op = lazyflow.operators.OpMultiArrayStacker(dataSlots[0].getRealOperator())
        for slot in dataSlots:
            assert isinstance(slot, lazyflow.graph.Slot), "slot is of type %r" % (type(slot))
            assert isinstance(slot.getRealOperator(), lazyflow.graph.Operator), "slot's operator is of type %r" % (type(slot.getRealOperator()))
        op.AxisFlag.setValue("c")
        op.Images.resize(len(dataSlots))
        for i,islot in enumerate(op.Images):
            islot.connect(dataSlots[i])
        expDlg.setInput(op.Output)

        expDlg.show()
        
    menu = QMenu("Menu", parent)
    title = QAction("%s" % layer.name, menu)
    title.setEnabled(False)
    
    export = QAction("Export...",menu)
    export.setStatusTip("Export Layer...")
    export.triggered.connect(onExport)
    
    menu.addAction(title)
    menu.addAction(export)
    menu.addSeparator()
    _add_actions( layer, menu )

    menu.addSeparator()
    for name, callback in layer.contexts:
        action = QAction(name, menu)
        action.triggered.connect(callback)
        menu.addAction(action)

    menu.exec_(pos)    

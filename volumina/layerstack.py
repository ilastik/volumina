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
import functools
from PyQt5.QtCore import QAbstractListModel, QItemSelectionModel, pyqtSignal, QModelIndex, Qt, QTimer

from volumina.layer import Layer



class LayerStackModel(QAbstractListModel):
    canMoveSelectedUp = pyqtSignal("bool")
    canMoveSelectedDown = pyqtSignal("bool")
    canDeleteSelected = pyqtSignal("bool")
    
    orderChanged = pyqtSignal()
    layerAdded = pyqtSignal( Layer, int ) # is now in row
    layerRemoved = pyqtSignal( Layer, int ) # was in row
    stackCleared = pyqtSignal()
        
    def __init__(self, parent = None):
        QAbstractListModel.__init__(self, parent)
        self._layerStack = []
        self.selectionModel = QItemSelectionModel(self)
        self.selectionModel.selectionChanged.connect(self.updateGUI)
        self.selectionModel.selectionChanged.connect(self._onSelectionChanged)
        self._movingRows = False
        QTimer.singleShot(0, self.updateGUI)
        
        def _handleRemovedLayer(layer):
            # Layerstacks *own* the layers they hold, and thus are 
            #  responsible for cleaning them up when they are removed:
            layer.clean_up()
        self.layerRemoved.connect( _handleRemovedLayer )

    ####
    ## High level API to manipulate the layerstack
    ###
    
    def __len__(self):
        return self.rowCount()
        
    def __repr__(self):
        return "<LayerStackModel: layerStack='%r'>" % (self._layerStack,)  
    
    def __getitem__(self, i):
        return self._layerStack[i]
    
    def __iter__(self):
        return self._layerStack.__iter__()
    
    def layerIndex(self, layer):
        #note that the 'index' function already has a different implementation
        #from Qt side
        return self._layerStack.index(layer)

    def findMatchingIndex(self, func):
        """Call the given function with each layer and return the index of the first layer for which f is True."""
        for index, layer in enumerate(self._layerStack):
            if func(layer):
                return index
        raise ValueError("No matching layer in stack.")

    def append(self, data):
        self.insert(0, data)
   
    def clear(self):
        if len(self) > 0:
            self.removeRows(0,len(self))
            self.stackCleared.emit()

    def insert(self, index, data):
        """
        Insert a layer into this layer stack, which *takes ownership* of the layer.
        """
        assert isinstance(data, Layer), "Only Layers can be added to a LayerStackModel"
        self.insertRow(index)
        self.setData(self.index(index), data)
        if self.selectedRow() >= 0:
            self.selectionModel.select(self.index(self.selectedRow()), QItemSelectionModel.Deselect)
        self.selectionModel.select(self.index(index), QItemSelectionModel.Select)
        
        data.changed.connect(functools.partial(self._onLayerChanged, self.index(index)))
        index = self._layerStack.index(data)
        self.layerAdded.emit(data, index)

        self.updateGUI()

    def selectRow( self, row ):
        already_selected_rows = self.selectionModel.selectedRows()
        if len(already_selected_rows) == 1 and row == already_selected_rows[0]:
            # Nothing to do if this row is already selected
            return
        self.selectionModel.clear()
        self.selectionModel.setCurrentIndex( self.index(row), QItemSelectionModel.SelectCurrent)

    def deleteSelected(self):
        num_rows = len(self.selectionModel.selectedRows())
        assert num_rows == 1, "Can't delete selected row: {} layers are currently selected.".format( num_rows )
        row = self.selectionModel.selectedRows()[0]
        layer = self._layerStack[row.row()]
        assert not layer._cleaned_up, "This layer ({}) has already been cleaned up.  Shouldn't it already be removed from the layerstack?".format( layer.name )
        self.removeRow(row.row())
        if self.rowCount() > 0:
            self.selectionModel.select(self.index(0), QItemSelectionModel.Select)
        self.layerRemoved.emit( layer, row.row() )
        self.updateGUI()
        
    def moveSelectedUp(self):
        assert len(self.selectionModel.selectedRows()) == 1
        row = self.selectionModel.selectedRows()[0]
        if row.row() != 0:
            oldRow = row.row()
            newRow = oldRow - 1
            self._moveToRow(oldRow, newRow)
    

    def moveSelectedDown(self):
        assert len(self.selectionModel.selectedRows()) == 1
        row = self.selectionModel.selectedRows()[0]
        if row.row() != self.rowCount() - 1:
            oldRow = row.row()
            newRow = oldRow + 1
            self._moveToRow(oldRow, newRow)
            
    def moveSelectedToTop(self):
        assert len(self.selectionModel.selectedRows()) == 1
        row = self.selectionModel.selectedRows()[0]
        if row.row() != 0:
            oldRow = row.row()
            newRow = 0
            self._moveToRow(oldRow, newRow)
    
    def moveSelectedToBottom(self):
        assert len(self.selectionModel.selectedRows()) == 1
        row = self.selectionModel.selectedRows()[0]
        if row.row() != self.rowCount() - 1:
            oldRow = row.row()
            newRow = self.rowCount() - 1
            self._moveToRow(oldRow, newRow)

    def moveSelectedToRow(self, newRow):
        assert len(self.selectionModel.selectedRows()) == 1
        row = self.selectionModel.selectedRows()[0]
        if row.row() != newRow:
            oldRow = row.row()
            self._moveToRow(oldRow, newRow)

    def _moveToRow(self, oldRow, newRow):
        d = self._layerStack[oldRow]
        self.removeRow(oldRow)
        self.insertRow(newRow)
        self.setData(self.index(newRow), d)
        self.selectionModel.select(self.index(newRow), QItemSelectionModel.Select)
        self.orderChanged.emit()
        self.updateGUI()
    ####
    ## Low level API. To add, remove etc. layers use the high level API from above.
    ####
 
    def updateGUI(self):
        self.canMoveSelectedUp.emit(self.selectedRow()>0)
        self.canMoveSelectedDown.emit(self.selectedRow()<self.rowCount()-1)
        self.canDeleteSelected.emit(self.rowCount() > 0)
        self.wantsUpdate()
        
    def selectedRow(self):
        selected = self.selectionModel.selectedRows()
        if len(selected) == 1:
            return selected[0].row()
        return -1
    
    def selectedIndex(self):
        row = self.selectedRow()
        if row >= 0:
            return self.index(self.selectedRow())
        else:
            return QModelIndex()
    
    def rowCount(self, parent = QModelIndex()):
        if not parent.isValid():
            return len(self._layerStack)
        return 0
    
    def insertRows(self, row, count, parent = QModelIndex()):
        '''Insert empty rows in the stack. 
        
        DO NOT USE THIS METHOD TO INSERT NEW LAYERS!
        Always use the insert() or append() method.
        
        '''
        if parent.isValid():
            return False
        oldRowCount = self.rowCount()
        #for some reason, row can be negative!
        beginRow = max(0,row)
        endRow   = min(beginRow+count-1, len(self._layerStack))
        self.beginInsertRows(parent, beginRow, endRow) 
        while(beginRow <= endRow):
            self._layerStack.insert(row, Layer(datasources=[]))
            beginRow += 1
        self.endInsertRows()
        assert self.rowCount() == oldRowCount+1, "oldRowCount = %d, self.rowCount() = %d" % (oldRowCount, self.rowCount())
        return True
            
    def removeRows(self, row, count, parent = QModelIndex()):
        '''Remove rows from the stack. 
        
        DO NOT USE THIS METHOD TO REMOVE LAYERS!
        Use the deleteSelected() method instead.
        
        '''

        if parent.isValid():
            return False
        if row+count <= 0 or row >= len(self._layerStack):
            return False
        oldRowCount = self.rowCount()
        beginRow = max(0,row)
        endRow   = min(row+count-1, len(self._layerStack)-1)
        self.beginRemoveRows(parent, beginRow, endRow)
        while(beginRow <= endRow):
            del self._layerStack[row]
            beginRow += 1
        self.endRemoveRows()
        return True
    
    def flags(self, index):
        defaultFlags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled
        if index.isValid():
            return Qt.ItemIsDragEnabled | defaultFlags
        else:
            return Qt.ItemIsDropEnabled | defaultFlags
    
    def supportedDropActions(self):
        return Qt.MoveAction

    def data(self, index, role = Qt.DisplayRole):
        if not index.isValid():
            return None
        if index.row() > len(self._layerStack):
            return None
        
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self._layerStack[index.row()]
        elif role == Qt.ToolTipRole:
            return self._layerStack[index.row()].toolTip()
        else:
            return None
    
    def setData(self, index, value, role = Qt.EditRole):
        '''Replace one layer with another. 
        
        DO NOT USE THIS METHOD TO INSERT NEW LAYERS!
        Use deleteSelected() followed by insert() or append().
        
        '''
        if role == Qt.EditRole:
            layer = value
            if not isinstance(value, Layer):
                layer = value.toPyObject()
            self._layerStack[index.row()] = layer
            self.dataChanged.emit(index, index)
            return True
        elif role == Qt.ToolTipRole:
            self._layerStack[index.row()].setToolTip()
            return True
        return False
            
    
    def headerData(self, section, orientation, role = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return "Column %r" % section
        else:
            return "Row %r" % section
        
    def wantsUpdate(self):
        self.layoutChanged.emit()

    def _onLayerChanged( self, idx ):
        self.dataChanged.emit(idx, idx)
        self.updateGUI()
        
    def _onSelectionChanged(self, selected, deselected):
        for idx in deselected.indexes():
            self[idx.row()].setActive(False) 
        for idx in selected.indexes():
            self[idx.row()].setActive(True) 

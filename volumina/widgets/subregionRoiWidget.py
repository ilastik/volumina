import collections
from PyQt4.QtCore import Qt, pyqtSignal, QEvent
from PyQt4.QtGui import QSpinBox, QTableWidget, QTableWidgetItem

class RoiSpinBox(QSpinBox):
    """
    QSpinBox with a special display when it's disabled.
    """
    def __init__(self, parent, min_, max_, default):
        """
        min and max are the range, default is used when the spinbox is enabled.
        """
        super( RoiSpinBox, self ).__init__(parent)
        self._default = default
        self._true_min = min_
        self._true_max = max_
        self.setRange( min_, max_ )
        self.setEnabled(False)
        self.valueChanged.connect( self._handleNewValue )

    def setPartner(self, partner):
        self._partner = partner

    def _handleNewValue(self, value):
        # Adjust our partner's allowed range to ensure it never crosses our value.
        partner_min = self._partner._true_min
        partner_max = self._partner._true_max
        if value < self._partner.value():
            partner_min = max( partner_min, value+1 )
        else:
            partner_max = min( partner_max, value-1 )
        self._partner.setRange( partner_min, partner_max )

    def changeEvent(self, event ):
        """
        Overridden from QWidget.
        Set special text '--' when widget is disabled.
        """
        if event.type() == QEvent.EnabledChange:
            if self.isEnabled():
                self.setSpecialValueText('')
                self.setValue( self._default )
            else:
                self.setSpecialValueText('--')
                self.setValue( self.minimum() ) # minimum() is the 'special value'

class SubregionRoiWidget( QTableWidget ):
    """
    Provides the controls for a user to specify a subregion of interest for export.
    If the user doesn't specify a range for an axis, the roi we emit will include 'None' entries.
    This is useful for cases where you may be specifying a roi in multiple images of different sizes.
    """
    #: emit(tuple, tuple), tuples may contain 'None' to indicate 'full range'
    roiChanged = pyqtSignal(object, object)
    
    def __init__(self, parent):
        super( SubregionRoiWidget, self ).__init__(parent)
        self.setColumnCount( 3 )
        self.setHorizontalHeaderLabels(["range", "[start,", "stop)"])
        #self.resizeColumnToContents(0)
        self._roi = None
        self._boxes = collections.OrderedDict()

        self.itemChanged.connect( self._handleItemChanged )
        self.itemClicked.connect( self._handleItemClicked )
        
        self._handling_click = False
    
    def initWithExtents(self, axes, shape):
        tagged_shape = collections.OrderedDict( zip(axes, shape) )
        self._tagged_shape = tagged_shape
        self.setRowCount( len(tagged_shape) )
        self.setVerticalHeaderLabels( tagged_shape.keys() )

        for row, (axis_key, extent) in enumerate(tagged_shape.items()):
            # Init 'full' checkbox
            checkbox_item = QTableWidgetItem("All")
            checkbox_item.setCheckState( Qt.Checked )
            checkbox_item.setFlags( Qt.ItemFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled) )
            self.setItem(row, 0, checkbox_item)

            # Init min/max spinboxes
            startBox = RoiSpinBox(self, 0, extent-1, 0 )
            stopBox = RoiSpinBox(self, 1, extent, extent )
            
            startBox.setPartner( stopBox )
            stopBox.setPartner( startBox )

            startBox.valueChanged.connect( self._updateRoi )
            stopBox.valueChanged.connect( self._updateRoi )

            self.setCellWidget( row, 1, startBox )
            self.setCellWidget( row, 2, stopBox )
            
            self._boxes[axis_key] = (checkbox_item, startBox, stopBox)
        
    def _updateRoi(self):
        checkboxes, min_boxes, max_boxes = zip( *self._boxes.values() )
        box_starts = map( RoiSpinBox.value, min_boxes )
        box_stops = map( RoiSpinBox.value, max_boxes )
        checkbox_flags = map( lambda cbox: cbox.checkState() == Qt.Checked, checkboxes )

        # For 'full range' axes, replace box value with the full extent value
        start = tuple( None if use_full else b for use_full, b in zip( checkbox_flags, box_starts ) )
        stop  = tuple( None if use_full else b for use_full, b in zip( checkbox_flags, box_stops ) )
        
        roi = (start, stop)
        if roi != self._roi:
            self._roi = roi
            self.roiChanged.emit( *roi )
    
    def _handleItemChanged(self, item):
        if not self._handling_click:
            if len(self._boxes) == 0:
                return
            checkboxes, min_boxes, max_boxes = zip( *self._boxes.values() )
            if item in checkboxes:
                self._handling_click = True
                # Because we auto-toggle the checkbox in _handleItemClicked, we have to UNTOGGLE it here
                if item.checkState() == Qt.Checked:
                    new_state = Qt.Unchecked
                else:
                    new_state = Qt.Checked
                item.setCheckState( new_state )
                self._handling_click = False
    
    def _handleItemClicked(self, item):
        if len(self._boxes) == 0:
            return
        checkboxes, min_boxes, max_boxes = zip( *self._boxes.values() )
        if item in checkboxes:
            self._handling_click = True
            row = checkboxes.index(item)
            if item.checkState() == Qt.Checked:
                new_state = Qt.Unchecked
            else:
                new_state = Qt.Checked
            item.setCheckState( new_state )
            min_boxes[row].setEnabled( item.checkState() == Qt.Unchecked )
            max_boxes[row].setEnabled( item.checkState() == Qt.Unchecked )
            self._handling_click = False

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication
    
    app = QApplication([])
    w = SubregionRoiWidget(None)
    w.initWithExtents( 'xyz', (10,20,30) )
    w.show()

    app.exec_()


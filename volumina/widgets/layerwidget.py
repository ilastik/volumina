import warnings
from PyQt4.QtCore import pyqtSignal, Qt, QEvent, QRect, QSize, QTimer, QPoint
from PyQt4.QtGui import QStyledItemDelegate, QWidget, QListView, QStyle, \
                        QPainter, QItemSelectionModel, QFontMetrics, QFont,\
                        QPalette, QMouseEvent, QLabel, QGridLayout, QPixmap, \
                        QSpinBox, QApplication

from volumina.layer import Layer
from volumina.layerstack import LayerStackModel
from layercontextmenu import layercontextmenu

class FractionSelectionBar( QWidget ):
    fractionChanged = pyqtSignal(float)

    def __init__( self, initial_fraction=1., parent=None ):
        super(FractionSelectionBar, self).__init__( parent=parent )
        self._fraction = initial_fraction
        self._lmbDown = False

    def fraction( self ):
        return self._fraction

    def setFraction( self, value ):
        if value == self._fraction:
            return
        if(value < 0.):
            value = 0.
            warnings.warn("FractionSelectionBar.setFraction(): value has to be between 0. and 1. (was %s); setting to 0." % str(value))
        if(value > 1.):
            value = 1.
            warnings.warn("FractionSelectionBar.setFraction(): value has to be between 0. and 1. (was %s); setting to 1." % str(value))
        self._fraction = float(value)
        self.update()

    def mouseMoveEvent(self, event):
        if self._lmbDown:
            self.setFraction(self._fractionFromPosition( event.posF() ))
            self.fractionChanged.emit(self._fraction)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        self._lmbDown = True
        self.setFraction(self._fractionFromPosition( event.posF() ))
        self.fractionChanged.emit(self._fraction)

    def mouseReleaseEvent(self, event):
        self._lmbDown = False

    def paintEvent( self, ev ):
        painter = QPainter(self)

        # calc bar offset
        y_offset =(self.height() - self._barHeight()) // 2
        ## prevent negative offset
        y_offset = 0 if y_offset < 0 else y_offset

        # frame around fraction indicator
        painter.setBrush(self.palette().dark())
        painter.save()
        ## no fill color
        b = painter.brush(); b.setStyle(Qt.NoBrush); painter.setBrush(b)
        painter.drawRect(
            QRect(QPoint(0, y_offset),
                  QSize(self._barWidth(), self._barHeight())))
        painter.restore()

        # fraction indicator
        painter.drawRect(
            QRect(QPoint(0, y_offset),
                  QSize(self._barWidth()*self._fraction, self._barHeight())))

    def sizeHint( self ):
        return QSize(100, 10)

    def minimumSizeHint( self ):
        return QSize(1, 3)

    def _barWidth( self ):
        return self.width()-1

    def _barHeight( self ):
        return self.height()-1

    def _fractionFromPosition( self, pointf ):
        frac = pointf.x() / self.width()
        # mouse has left the widget
        if frac < 0.:
            frac = 0.
        if frac > 1.:
            frac = 1.
        return frac

class ToggleEye( QLabel ):
    activeChanged = pyqtSignal( bool )

    def __init__( self, parent=None ):
        super(ToggleEye, self).__init__( parent=parent )
        self._active = True
        self._eye_open = QPixmap(":icons/icons/stock-eye-20.png")
        self._eye_closed = QPixmap(":icons/icons/stock-eye-20-gray.png")
        self.setPixmap(self._eye_open)

    def active( self ):
        return self._active

    def setActive( self, b ):
        if b == self._active:
            return
        self._active = b
        if b:
            self.setPixmap(self._eye_open)
        else:
            self.setPixmap(self._eye_closed)

    def toggle( self ):
        if self.active():
            self.setActive( False )
        else:
            self.setActive( True )

    def mousePressEvent( self, ev ):
        self.toggle()
        self.activeChanged.emit( self._active )

class LayerItemWidget( QWidget ):
    @property
    def layer(self):
        return self._layer
    @layer.setter
    def layer(self, layer):
        if self._layer:
            self._layer.changed.disconnect(self._updateState)
        self._layer = layer
        self._updateState()
        self._layer.changed.connect(self._updateState)

    def __init__( self, parent=None ):
        super(LayerItemWidget, self).__init__( parent=parent )
        self._layer = None

        self._font = QFont(QFont().defaultFamily(), 9)
        self._fm = QFontMetrics( self._font )
        self.bar = FractionSelectionBar( initial_fraction = 0. )
        self.bar.setFixedHeight(10)
        self.nameLabel = QLabel( parent=self )
        self.nameLabel.setFont( self._font )
        self.nameLabel.setText( "None" )
        self.opacityLabel = QLabel( parent=self )
        self.opacityLabel.setAlignment(Qt.AlignRight)
        self.opacityLabel.setFont( self._font )
        self.opacityLabel.setText( u"\u03B1=%0.1f%%" % (100.0*(self.bar.fraction())))
        self.toggleEye = ToggleEye( parent=self )
        self.toggleEye.setActive(False)
        self.toggleEye.setFixedWidth(35)
        self.toggleEye.setToolTip("Visibility")
        self.channelSelector = QSpinBox( parent=self )
        self.channelSelector.setFrame( False )
        self.channelSelector.setFont( self._font )
        self.channelSelector.setMaximumWidth( 35 )
        self.channelSelector.setAlignment(Qt.AlignRight)
        self.channelSelector.setToolTip("Channel")
        self.channelSelector.setVisible(False)

        self._layout = QGridLayout( self )
        self._layout.addWidget( self.toggleEye, 0, 0 )
        self._layout.addWidget( self.nameLabel, 0, 1 )
        self._layout.addWidget( self.opacityLabel, 0, 2 )
        self._layout.addWidget( self.channelSelector, 1, 0)
        self._layout.addWidget( self.bar, 1, 1, 1, 2 )

        self._layout.setColumnMinimumWidth( 0, 35 )
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(5,2,5,2)

        self.setLayout( self._layout )

        self.bar.fractionChanged.connect( self._onFractionChanged )
        self.toggleEye.activeChanged.connect( self._onEyeToggle )
        self.channelSelector.valueChanged.connect( self._onChannelChanged )

    def mousePressEvent( self, ev ):
        super(LayerItemWidget, self).mousePressEvent( ev )

    def _onFractionChanged( self, fraction ):
        if self._layer and (fraction != self._layer.opacity):
            self._layer.opacity = fraction

    def _onEyeToggle( self, active ):
        if self._layer and (active != self._layer.visible):
            
            if self._layer._allowToggleVisible:
                self._layer.visible = active
            else:
                self.toggleEye.setActive(True)

    def _onChannelChanged( self, channel ):
        if self._layer and (channel != self._layer.channel):
            self._layer.channel = channel

    def _updateState( self ):
        if self._layer:
            self.toggleEye.setActive(self._layer.visible)
            self.bar.setFraction( self._layer.opacity )
            self.opacityLabel.setText( u"\u03B1=%0.1f%%" % (100.0*(self.bar.fraction())))
            self.nameLabel.setText( self._layer.name )
            
            if self._layer.numberOfChannels > 1:
                self.channelSelector.setVisible( True )
                self.channelSelector.setMaximum( self._layer.numberOfChannels - 1 )
                self.channelSelector.setValue( self._layer.channel )
            else:
                self.channelSelector.setVisible( False )
                self.channelSelector.setMaximum( self._layer.numberOfChannels - 1)
                self.channelSelector.setValue( self._layer.channel )
            self.update()

class LayerDelegate(QStyledItemDelegate):
    def __init__(self, layersView, listModel, parent = None):
        QStyledItemDelegate.__init__(self, parent=parent)
        self.currentIndex = -1
        self._view = layersView
        self._w = LayerItemWidget()
        self._listModel = listModel
        self._listModel.rowsAboutToBeRemoved.connect(self.handleRemovedRows)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def paint(self, painter, option, index):
        if option.state & QStyle.State_Selected:
            modelIndex = index.row()
            if modelIndex != self.currentIndex:
                model = index.model()
                self.currentIndex = modelIndex
                model.wantsUpdate()

        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            pic = QPixmap( option.rect.width(), option.rect.height() )
            w = self._w
            w.layer = layer
            w.setGeometry( option.rect )
            w.setPalette( option.palette )
            
            # Manually set alternating background colors for the rows
            if index.row() % 2 == 0:
                itemBackgroundColor = self.parent().palette().color(QPalette.Base)
            else:
                itemBackgroundColor = self.parent().palette().color(QPalette.AlternateBase)
            pallete = w.palette()
            pallete.setColor( QPalette.Window, itemBackgroundColor )
            w.setPalette(pallete)
            w.render(pic)            
            painter.drawPixmap( option.rect, pic )
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

    def sizeHint(self, option, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            self._w.layer = layer
            self._w.channelSelector.setVisible(True)
            return self._w.sizeHint()
        else:
            return QStyledItemDelegate.sizeHint(self, option, index)

    def createEditor(self, parent, option, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            editor = LayerItemWidget(parent=parent)
            editor.setAutoFillBackground(True)
            editor.setPalette( option.palette )
            editor.setBackgroundRole(QPalette.Highlight)
            editor.layer = layer
            return editor
        else:
            QStyledItemDelegate.createEditor(self, parent, option, index)

    def setEditorData(self, editor, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            editor.layer = layer
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            model.setData(index, editor.layer)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def handleRemovedRows(self, parent, start, end):
        for row in range(start, end):
            itemData = self._listModel.itemData( self._listModel.index(row) )
            layer = itemData[Qt.EditRole].toPyObject()
            assert isinstance(layer, Layer)

class LayerWidget(QListView):
    def __init__(self, parent = None, model=None):
        QListView.__init__(self, parent)

        if model is None:
            model = LayerStackModel()
        self.init(model)

    def init(self, listModel):
        self.setModel(listModel)
        self._itemDelegate = LayerDelegate( self, listModel, parent=self )
        self.setItemDelegate(self._itemDelegate)
        self.setSelectionModel(listModel.selectionModel)
        #self.setDragDropMode(self.InternalMove)
        self.installEventFilter(self)
        #self.setDragDropOverwriteMode(False)
        self.model().selectionModel.selectionChanged.connect(self.onSelectionChanged)
        QTimer.singleShot(0, self.selectFirstEntry)


    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up or event.key() == Qt.Key_Down:
            return super(LayerWidget, self).keyPressEvent(event)

        if event.key() == Qt.Key_Right or event.key() == Qt.Key_Left:
            row = self.model().selectedRow()
            if row < 0:
                return
            layer = self.model()[row]

            if event.key() == Qt.Key_Right:
                if layer.opacity < 1.0:
                    layer.opacity = min(1.0, layer.opacity + 0.01)
            elif event.key() == Qt.Key_Left:
                if layer.opacity > 0.0:
                    layer.opacity = max(0.0, layer.opacity - 0.01)

    def resizeEvent(self, e):
        self.updateGUI()
        QListView.resizeEvent(self, e)

    def contextMenuEvent(self, event):
        idx = self.indexAt(event.pos())
        layer = self.model()[idx.row()]

        layercontextmenu( layer, self.mapToGlobal(event.pos()), self )

    def selectFirstEntry(self):
        #self.setEditTriggers(QAbstractItemView.DoubleClicked)
        self.model().selectionModel.setCurrentIndex(self.model().index(0), QItemSelectionModel.SelectCurrent)
        self.updateGUI()

    def updateGUI(self):
        self.openPersistentEditor(self.model().selectedIndex())

    def eventFilter(self, sender, event):
        #http://stackoverflow.com/questions/1224432/
        #how-do-i-respond-to-an-internal-drag-and-drop-operation-using-a-qlistwidget
        if (event.type() == QEvent.ChildRemoved):
            self.onOrderChanged()
        return False

    def onSelectionChanged(self, selected, deselected):
        if len(deselected) > 0:
            self.closePersistentEditor(deselected[0].indexes()[0])
        self.updateGUI()

    def onOrderChanged(self):
        self.updateGUI()

    def mousePressEvent(self, event):
        prevIndex = self.model().selectedIndex()
        newIndex = self.indexAt( event.pos() )
        super(LayerWidget, self).mousePressEvent(event)

        # HACK: The first click merely gives focus to the list item without actually passing the event to it.
        # We'll simulate a mouse click on the item by sending a duplicate pair of QMouseEvent press/release events to the appropriate widget.
        if prevIndex != newIndex and newIndex.row() != -1:
            layer = self.model().itemData(newIndex)[Qt.EditRole].toPyObject()
            assert isinstance(layer, Layer)
            hitWidget = QApplication.widgetAt( event.globalPos() )
            localPos = hitWidget.mapFromGlobal( event.globalPos() )
            hitWidgetPress = QMouseEvent( QMouseEvent.MouseButtonPress, localPos, event.globalPos(), event.button(), event.buttons(), event.modifiers() )
            QApplication.instance().sendEvent(hitWidget, hitWidgetPress)
            hitWidgetRelease = QMouseEvent( QMouseEvent.MouseButtonRelease, localPos, event.globalPos(), event.button(), event.buttons(), event.modifiers() )
            QApplication.instance().sendEvent(hitWidget, hitWidgetRelease)

#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == "__main__":
    #make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    import sys, numpy

    from PyQt4.QtGui import QPushButton, QHBoxLayout, QVBoxLayout
    from volumina.pixelpipeline.datasources import ArraySource

    app = QApplication(sys.argv)

    model = LayerStackModel()

    o1 = Layer()
    o1.name = "Fancy Layer"
    o1.opacity = 0.5
    model.append(o1)

    o2 = Layer()
    o2.name = "Some other Layer"
    o2.opacity = 0.25
    o2.numberOfChannels = 3
    model.append(o2)

    o3 = Layer()
    o3.name = "Invisible Layer"
    o3.opacity = 0.15
    o3.visible = False
    model.append(o3)

    o4 = Layer()
    o4.name = "Fancy Layer II"
    o4.opacity = 0.95
    model.append(o4)

    o5 = Layer()
    o5.name = "Fancy Layer III"
    o5.opacity = 0.65
    model.append(o5)

    o6 = Layer()
    o6.name = "Lazyflow Layer"
    o6.opacity = 1

    testVolume = numpy.random.rand(100,100,100,3).astype('uint8')
    source = [ArraySource(testVolume)]
    o6._datasources = source
    model.append(o6)

    view = LayerWidget(None, model)
    view.show()
    view.updateGeometry()

    w = QWidget()
    lh = QHBoxLayout(w)
    lh.addWidget(view)

    up   = QPushButton('Up')
    down = QPushButton('Down')
    delete = QPushButton('Delete')
    add = QPushButton('Add')
    lv  = QVBoxLayout()
    lh.addLayout(lv)

    lv.addWidget(up)
    lv.addWidget(down)
    lv.addWidget(delete)
    lv.addWidget(add)

    w.setGeometry(100, 100, 800,600)
    w.show()

    up.clicked.connect(model.moveSelectedUp)
    model.canMoveSelectedUp.connect(up.setEnabled)
    down.clicked.connect(model.moveSelectedDown)
    model.canMoveSelectedDown.connect(down.setEnabled)
    delete.clicked.connect(model.deleteSelected)
    model.canDeleteSelected.connect(delete.setEnabled)
    def addRandomLayer():
        o = Layer()
        o.name = "Layer %d" % (model.rowCount()+1)
        o.opacity = numpy.random.rand()
        o.visible = bool(numpy.random.randint(0,2))
        model.append(o)
    add.clicked.connect(addRandomLayer)

    app.exec_()

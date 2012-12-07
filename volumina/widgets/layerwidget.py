from PyQt4.QtGui import QStyledItemDelegate, QWidget, QListView, QStyle, \
                        QAbstractItemView, QPainter, QItemSelectionModel, \
                        QColor, QMenu, QAction, QFontMetrics, QFont, QImage, \
                        QBrush, QPalette, QMouseEvent
from PyQt4.QtCore import pyqtSignal, Qt, QEvent, QRect, QSize, QTimer, \
                         QPoint

from volumina.layer import Layer
from layercontextmenu import layercontextmenu

from os import path
from volumina.layerstack import LayerStackModel
import volumina.icons_rc

#*******************************************************************************
# L a y e r P a i n t e r                                                      *
#*******************************************************************************

class LayerPainter( object ):
    def __init__(self):
        self.layer = None

        self.rect = QRect()

        self.fm = QFontMetrics(QFont())

        self.iconSize = 20
        self.iconXOffset = 5
        self.textXOffset = 5
        self.progressXOffset = self.iconXOffset+self.iconSize+self.textXOffset
        self.progressYOffset = self.iconSize+5
        self.progressHeight = 10

        self.alphaTextWidth = self.fm.boundingRect(u"\u03B1=100.0%").width()

    def sizeHint(self, mode):
       if mode == 'ReadOnly':
           return QSize(1,self.fm.height()+5)
       elif mode == 'Expanded' or mode == 'Editable':
           return QSize(1,self.progressYOffset+self.progressHeight+5)
       else:
           raise RuntimeError("Unknown mode")

    def overEyeIcon(self, x, y):
        #with a sufficiently large height (100)
        #we make sure that the user can also click below the eye to toggle
        #the layer
        return QPoint(x,y) in QRect(self.iconXOffset,0,self.iconSize,100)

    def percentForPosition(self, x, y, parentWidth, checkBoundaries=True):
        """
        For some strange reason, self.rect.width() is sometimes 0 when this is called.
        For that reason, we can't use self._progressWidth and we must pass in the parentWidth as an argument.
        """
        if checkBoundaries and (y < self.progressYOffset or y > self.progressYOffset + self.progressHeight) \
                           or  (x < self.progressXOffset):
            return -1

        percent = (x-self.progressXOffset)/float(parentWidth-self.progressXOffset-10)
        if percent < 0:
            return 0.0
        if percent > 1:
            return 1.0
        return percent

    @property
    def _progressWidth(self):
        return self.rect.width()-self.progressXOffset-10

    def paint(self, painter, rect, palette, mode, isSelected):
        if not self.layer.visible:
            palette.setCurrentColorGroup(QPalette.Disabled)

        self.rect = rect
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)

        painter.setBrush(palette.text())

        if isSelected:
            painter.save()
            painter.setBrush(palette.highlight())
            painter.drawRect(rect)
            painter.restore()

        painter.translate(rect.x(), rect.y())
        painter.setFont(QFont())

        textOffsetX = self.progressXOffset
        textOffsetY = max(self.fm.height()-self.iconSize,0)/2.0+self.fm.height()

        if self.layer.visible:
            painter.drawImage(QRect(self.iconXOffset,0,self.iconSize,self.iconSize), \
                              QImage(":icons/icons/stock-eye-20.png"))
        else:
            painter.drawImage(QRect(self.iconXOffset,0,self.iconSize,self.iconSize), \
                              QImage(":icons/icons/stock-eye-20-gray.png"))

        if self.layer.direct:
            painter.save()
            painter.setBrush(palette.text())
            painter.drawEllipse(self.iconXOffset+self.iconSize/2-2, self.iconSize+3, 4,4 )
            painter.restore()

        #layer name text
        if mode != 'ReadOnly':
            painter.setBrush(palette.highlightedText())
        else:
            painter.setBrush(palette.text())

        #layer name
        painter.drawText(QPoint(textOffsetX, textOffsetY), "%s" % self.layer.name)
        #opacity
        text = u"\u03B1=%0.1f%%" % (100.0*(self.layer.opacity))
        painter.drawText(QPoint(textOffsetX+self._progressWidth-self.alphaTextWidth, textOffsetY), text)


        if mode != 'ReadOnly':
            #frame around percentage indicator
            painter.setBrush(palette.dark())
            painter.save()
            #no fill color
            b = painter.brush(); b.setStyle(Qt.NoBrush); painter.setBrush(b)
            painter.drawRect(QRect(QPoint(self.progressXOffset, self.progressYOffset), \
                                          QSize(self._progressWidth, self.progressHeight)))
            painter.restore()

            #percentage indicator
            painter.drawRect(QRect(QPoint(self.progressXOffset, self.progressYOffset), \
                                          QSize(self._progressWidth*self.layer.opacity, self.progressHeight)))

        painter.restore()

#*******************************************************************************
# L a y e r D e l e g a t e                                                    *
#*******************************************************************************

class LayerDelegate(QStyledItemDelegate):
    def __init__(self, layersView, listModel, parent = None):
        QStyledItemDelegate.__init__(self, parent)
        self.currentIndex = -1
        self._view = layersView
        self._editors = {}
        self._listModel = listModel

        #whether to draw all layers expanded
        self.expandAll = True

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
            layerPainter = LayerPainter()
            layerPainter.layer = layer
            isSelected = option.state & QStyle.State_Selected
            if isSelected:
                painter.fillRect(option.rect, QColor(0,255,0,10))
            if self.expandAll or option.state & QStyle.State_Selected:
                layerPainter.paint(painter, option.rect, option.palette, 'Expanded', isSelected)
            else:
                layerPainter.paint(painter, option.rect, option.palette, 'ReadOnly', False)
        else:
            QStyledItemDelegate.paint(self, painter, option, index)

    def sizeHint(self, option, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            layerPainter = LayerPainter()
            layerPainter.layer = layer
            mode = "Expanded" if self.expandAll or self._view.currentIndex() == index else 'ReadOnly'
            return layerPainter.sizeHint( mode )
        else:
            return QStyledItemDelegate.sizeHint(self, option, index)

    def createEditor(self, parent, option, index):
        layer = index.data().toPyObject()
        if isinstance(layer, Layer):
            editor = LayerEditor(parent)
            self._editors[layer] = editor
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
            if layer in self._editors:
                del self._editors[layer]

    def commitAndCloseEditor(self):
        editor = sender()
        self.commitData.emit(editor)
        self.closeEditor.emit(editor)

#*******************************************************************************
# L a y e r E d i t o r                                                        *
#*******************************************************************************

class LayerEditor(QWidget):
    editingFinished = pyqtSignal()

    def __init__(self, parent = None):
        QWidget.__init__(self, parent)
        self.lmbDown = False
        self.setMouseTracking(True)
        self.setAutoFillBackground(True)
        self._layerPainter = LayerPainter()
        self._layer = None

    @property
    def layer(self):
        return self._layer
    @layer.setter
    def layer(self, layer):
        if self._layer:
            self._layer.changed.disconnect()
        self._layer = layer
        self._layer.changed.connect(self.repaint)
        self._layerPainter.layer = layer

    def minimumSize(self):
        return self.sizeHint()

    def maximumSize(self):
        return self.sizeHint()

    def paintEvent(self, e):
        painter = QPainter(self)
        self._layerPainter.paint(painter, self.rect(), self.palette(), 'Editable', True)

    def mouseMoveEvent(self, event):
        if self.lmbDown:
            opacity = self._layerPainter.percentForPosition(event.x(), event.y(), self.rect().width(), checkBoundaries=False)
            if opacity >= 0:
                self.layer.opacity = opacity
                self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            return

        self.lmbDown = True

        if self._layerPainter.overEyeIcon(event.x(), event.y()):
            self._layer.visible = not self._layer.visible
            self.update()

        opacity = self._layerPainter.percentForPosition(event.x(), event.y(), self.rect().width())
        if opacity >= 0:
            self._layer.opacity = opacity
            self.update()

    def mouseReleaseEvent(self, event):
        self.lmbDown = False

#*******************************************************************************
# L a y e r W i d g e t                                                        *
#*******************************************************************************

class LayerWidget(QListView):
    def __init__(self, parent = None, model=None):

        QListView.__init__(self, parent)

        if model is None:
            model = LayerStackModel()
        self.init(model)

    def init(self, listModel):
        self.setModel(listModel)
        self._itemDelegate = LayerDelegate( self, listModel )
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
        #print "Context menu for layer '%s'" % layer.name

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
        # We'll simulate a mouse click on the item by calling mousePressEvent() and mouseReleaseEvent on the appropriate editor
        if prevIndex != newIndex and newIndex.row() != -1:
            layer = self.model().itemData(newIndex)[Qt.EditRole].toPyObject()
            assert isinstance(layer, Layer)
            editor = self._itemDelegate._editors[layer]
            editorPos = event.pos() - editor.geometry().topLeft()
            editorPress = QMouseEvent( QMouseEvent.MouseButtonPress, editorPos, event.button(), event.buttons(), event.modifiers() )
            editor.mousePressEvent(editorPress)
            editorRelease = QMouseEvent( QMouseEvent.MouseButtonRelease, editorPos, event.button(), event.buttons(), event.modifiers() )
            editor.mouseReleaseEvent(editorRelease)

#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == "__main__":
    #make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    import sys, numpy

    from PyQt4.QtGui import QApplication, QPushButton, QHBoxLayout, QVBoxLayout
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

from __future__ import absolute_import
from __future__ import division

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
# 		   http://ilastik.org/license/
###############################################################################
from builtins import range
from past.utils import old_div
import warnings
from PyQt5.QtCore import pyqtSignal, Qt, QEvent, QRect, QSize, QTimer, QPoint, QItemSelectionModel
from PyQt5.QtGui import QPainter, QFontMetrics, QFont, QPalette, QMouseEvent, QPixmap
from PyQt5.QtWidgets import QStyledItemDelegate, QWidget, QListView, QStyle, QLabel, QGridLayout, QSpinBox, QApplication


from volumina.layer import Layer
from volumina.layerstack import LayerStackModel
from volumina.utility import ShortcutManager
from .layercontextmenu import layercontextmenu


NEXT_CHANNEL_SEQ = "Ctrl+N"
PREV_CHANNEL_SEQ = "Ctrl+P"


class FractionSelectionBar(QWidget):
    fractionChanged = pyqtSignal(float)

    def __init__(self, initial_fraction=1.0, parent=None):
        super(FractionSelectionBar, self).__init__(parent=parent)
        self._fraction = initial_fraction
        self._lmbDown = False

    def fraction(self):
        return self._fraction

    def setFraction(self, value):
        if value == self._fraction:
            return
        if value < 0.0:
            value = 0.0
            warnings.warn(
                "FractionSelectionBar.setFraction(): value has to be between 0. and 1. (was %s); setting to 0."
                % str(value)
            )
        if value > 1.0:
            value = 1.0
            warnings.warn(
                "FractionSelectionBar.setFraction(): value has to be between 0. and 1. (was %s); setting to 1."
                % str(value)
            )
        self._fraction = float(value)
        self.update()

    def mouseMoveEvent(self, event):
        if self._lmbDown:
            self.setFraction(self._fractionFromPosition(event.localPos()))
            self.fractionChanged.emit(self._fraction)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            return
        self._lmbDown = True
        self.setFraction(self._fractionFromPosition(event.localPos()))
        self.fractionChanged.emit(self._fraction)

    def mouseReleaseEvent(self, event):
        self._lmbDown = False

    def paintEvent(self, ev):
        painter = QPainter(self)

        # calc bar offset
        y_offset = (self.height() - self._barHeight()) // 2
        ## prevent negative offset
        y_offset = 0 if y_offset < 0 else y_offset

        # frame around fraction indicator
        painter.setBrush(self.palette().dark())
        painter.save()
        ## no fill color
        b = painter.brush()
        b.setStyle(Qt.NoBrush)
        painter.setBrush(b)
        painter.drawRect(QRect(QPoint(0, y_offset), QSize(self._barWidth(), self._barHeight())))
        painter.restore()

        # fraction indicator
        painter.drawRect(QRect(QPoint(0, y_offset), QSize(self._barWidth() * self._fraction, self._barHeight())))

    def sizeHint(self):
        return QSize(100, 10)

    def minimumSizeHint(self):
        return QSize(1, 3)

    def _barWidth(self):
        return self.width() - 1

    def _barHeight(self):
        return self.height() - 1

    def _fractionFromPosition(self, pointf):
        frac = old_div(pointf.x(), self.width())
        # mouse has left the widget
        if frac < 0.0:
            frac = 0.0
        if frac > 1.0:
            frac = 1.0
        return frac


class ToggleEye(QLabel):
    activeChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super(ToggleEye, self).__init__(parent=parent)
        self._active = True
        self._eye_open = QPixmap(":icons/icons/stock-eye-20.png")
        self._eye_closed = QPixmap(":icons/icons/stock-eye-20-gray.png")
        self.setPixmap(self._eye_open)

    def active(self):
        return self._active

    def setActive(self, b):
        if b == self._active:
            return
        self._active = b
        if b:
            self.setPixmap(self._eye_open)
        else:
            self.setPixmap(self._eye_closed)

    def toggle(self):
        if self.active():
            self.setActive(False)
        else:
            self.setActive(True)

    def mousePressEvent(self, ev):
        self.toggle()
        self.activeChanged.emit(self._active)


class LayerItemWidget(QWidget):
    @property
    def layer(self):
        return self._layer

    @layer.setter
    def layer(self, layer):
        if self._layer:
            try:
                self._layer.changed.disconnect(self._updateState)
            except TypeError:
                # FIXME: It's unclear why this disconnect fails sometimes...
                pass
        self._layer = layer
        self._updateState()
        self._layer.changed.connect(self._updateState)

    def __init__(self, parent=None):
        super(LayerItemWidget, self).__init__(parent=parent)
        self._layer = None

        self._font = QFont(QFont().defaultFamily(), 9)
        self._fm = QFontMetrics(self._font)
        self.bar = FractionSelectionBar(initial_fraction=0.0)
        self.bar.setFixedHeight(10)
        self.nameLabel = QLabel(parent=self)
        self.nameLabel.setFont(self._font)
        self.nameLabel.setText("None")
        self.opacityLabel = QLabel(parent=self)
        self.opacityLabel.setAlignment(Qt.AlignRight)
        self.opacityLabel.setFont(self._font)
        self.opacityLabel.setText(u"\u03B1=%0.1f%%" % (100.0 * (self.bar.fraction())))
        self.toggleEye = ToggleEye(parent=self)
        self.toggleEye.setActive(False)
        self.toggleEye.setFixedWidth(35)
        self.toggleEye.setToolTip("Visibility")
        self.channelSelector = QSpinBox(parent=self)
        self.channelSelector.setFrame(False)
        self.channelSelector.setFont(self._font)
        self.channelSelector.setMaximumWidth(35)
        self.channelSelector.setAlignment(Qt.AlignRight)
        self.channelSelector.setToolTip("Channel")
        self.channelSelector.setVisible(False)

        self._layout = QGridLayout(self)
        self._layout.addWidget(self.toggleEye, 0, 0)
        self._layout.addWidget(self.nameLabel, 0, 1)
        self._layout.addWidget(self.opacityLabel, 0, 2)
        self._layout.addWidget(self.channelSelector, 1, 0)
        self._layout.addWidget(self.bar, 1, 1, 1, 2)

        self._layout.setColumnMinimumWidth(0, 35)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(5, 2, 5, 2)

        self.setLayout(self._layout)

        self.bar.fractionChanged.connect(self._onFractionChanged)
        self.toggleEye.activeChanged.connect(self._onEyeToggle)
        self.channelSelector.valueChanged.connect(self._onChannelChanged)
        self.setUpShortcuts()

    def setUpShortcuts(self):
        mgr = ShortcutManager()
        ActionInfo = ShortcutManager.ActionInfo

        selector = self.channelSelector

        def inc():
            selector.setValue(selector.value() + selector.singleStep())

        def dec():
            selector.setValue(selector.value() - selector.singleStep())

        # Can't pass channelSelector(QSpinBox) as tooltip widget
        # because it doesn't have # separate tooltips for arrows
        mgr.register(NEXT_CHANNEL_SEQ, ActionInfo("Navigation", "Next channel", "Next channel", inc, selector, None))
        mgr.register(PREV_CHANNEL_SEQ, ActionInfo("Navigation", "Prev channel", "Prev channel", dec, selector, None))

    def _onFractionChanged(self, fraction):
        if self._layer and (fraction != self._layer.opacity):
            self._layer.opacity = fraction

    def _onEyeToggle(self, active):
        if self._layer and (active != self._layer.visible):

            if self._layer._allowToggleVisible:
                self._layer.visible = active
            else:
                self.toggleEye.setActive(True)

    def _onChannelChanged(self, channel):
        if self._layer and (channel != self._layer.channel):
            self._layer.channel = channel

    def _updateState(self):
        if self._layer:
            self.toggleEye.setActive(self._layer.visible)
            self.bar.setFraction(self._layer.opacity)
            self.opacityLabel.setText(u"\u03B1=%0.1f%%" % (100.0 * (self.bar.fraction())))
            self.nameLabel.setText(self._layer.name)

            if self._layer.numberOfChannels > 1:
                self.channelSelector.setVisible(True)
                self.channelSelector.setMaximum(self._layer.numberOfChannels - 1)
                self.channelSelector.setValue(self._layer.channel)
            else:
                self.channelSelector.setVisible(False)
                self.channelSelector.setMaximum(self._layer.numberOfChannels - 1)
                self.channelSelector.setValue(self._layer.channel)
            self.update()


class LayerDelegate(QStyledItemDelegate):
    def __init__(self, layersView, listModel, parent=None):
        QStyledItemDelegate.__init__(self, parent=parent)
        self.currentIndex = -1
        self._view = layersView
        self._w = LayerItemWidget()
        self._listModel = listModel
        self._listModel.rowsAboutToBeRemoved.connect(self.handleRemovedRows)

        # We keep a dict of all open editors for easy access.
        # Note that the LayerWidget uses persistent editors.
        # (This is for convenience of testing.)
        # This is also why we don't need to override the paint() method here.
        self._editors = {}

    def sizeHint(self, option, index):
        layer = index.data()
        if isinstance(layer, Layer):
            self._w.layer = layer
            self._w.channelSelector.setVisible(True)
            return self._w.sizeHint()
        else:
            return QStyledItemDelegate.sizeHint(self, option, index)

    def createEditor(self, parent, option, index):
        """
        Create an editor widget.  Note that the LayerWidget always uses persistent editors.
        """
        layer = index.data()
        if isinstance(layer, Layer):
            editor = LayerItemWidget(parent=parent)
            editor.is_editor = True
            # We set a custom objectName for debug and eventcapture testing purposes.
            objName = layer.name
            editor.setObjectName("LayerItemWidget_{}".format(objName))
            editor.setAutoFillBackground(True)
            editor.setPalette(option.palette)
            editor.setBackgroundRole(QPalette.Highlight)
            editor.layer = layer
            self._editors[layer] = editor
            return editor
        else:
            QStyledItemDelegate.createEditor(self, parent, option, index)

    def editorForIndex(self, modelIndex):
        """
        Return the editor (if any) that has already been
        opened for the layer at the given index.
        """
        layer = modelIndex.data()
        try:
            return self._editors[layer]
        except KeyError:
            return None

    def updateAllItemBackgrounds(self):
        """
        Iterate through the entire list of editors (item widgets)
        and give them alternating background colors.
        """
        for row in range(self._listModel.rowCount()):
            index = self._listModel.index(row)
            editor = self.editorForIndex(index)
            if editor is None:
                continue
            if index.row() % 2 == 0:
                itemBackgroundColor = self.parent().palette().color(QPalette.Base)
            else:
                itemBackgroundColor = self.parent().palette().color(QPalette.AlternateBase)
            pallete = editor.palette()
            pallete.setColor(QPalette.Window, itemBackgroundColor)
            editor.setPalette(pallete)

    def onSelectionChanged(self, selected, deselected):
        """
        Since we use persistent editors for every item, we have to handle
        highlighting/highlighting the selected editor ourselves whenever the selection changes.
        """
        if len(deselected) > 0:
            deselected_index = deselected[0].indexes()[0]
            editor = self.editorForIndex(deselected_index)
            if editor is not None:
                editor.setBackgroundRole(QPalette.Window)
        if len(selected) > 0:
            selected_index = selected[0].indexes()[0]
            editor = self.editorForIndex(selected_index)
            if editor is not None:
                editor.setBackgroundRole(QPalette.Highlight)

    def setEditorData(self, editor, index):
        layer = index.data()
        if isinstance(layer, Layer):
            editor.layer = layer
        else:
            QStyledItemDelegate.setEditorData(self, editor, index)

    def setModelData(self, editor, model, index):
        layer = index.data()
        if isinstance(layer, Layer):
            model.setData(index, editor.layer)
        else:
            QStyledItemDelegate.setModelData(self, editor, model, index)

    def handleRemovedRows(self, parent, start, end):
        for row in range(start, end):
            itemData = self._listModel.itemData(self._listModel.index(row))
            layer = itemData[Qt.EditRole]
            del self._editors[layer]
            assert isinstance(layer, Layer)


class LayerWidget(QListView):
    def __init__(self, parent=None, model=None):
        QListView.__init__(self, parent)

        if model is None:
            model = LayerStackModel()
        self.init(model)

    def init(self, listModel):
        self.setModel(listModel)
        self._itemDelegate = LayerDelegate(self, listModel, parent=self)
        self.setItemDelegate(self._itemDelegate)
        self.setSelectionModel(listModel.selectionModel)
        self.model().selectionModel.selectionChanged.connect(self.onSelectionChanged)
        QTimer.singleShot(0, self.selectFirstEntry)

        listModel.dataChanged.connect(self._handleModelDataChanged)
        listModel.layoutChanged.connect(self._handleModelLayoutChanged)

    def _handleModelDataChanged(self, index, index2):
        # Every time the data changes, open a persistent editor for that layer.
        # Using persistent editors allows us to use the eventcapture testing system,
        #  which cannot handle editors disappearing every time a new row is selected.
        self.openPersistentEditor(index)

    def _handleModelLayoutChanged(self):
        # If the order of the items in the list changes,
        #  we need to refresh the alternating light/dark background colors of each widget.
        self._itemDelegate.updateAllItemBackgrounds()

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

    def contextMenuEvent(self, event):
        idx = self.indexAt(event.pos())
        layer = self.model()[idx.row()]

        layercontextmenu(layer, self.mapToGlobal(event.pos()), self)

    def selectFirstEntry(self):
        self.model().selectionModel.setCurrentIndex(self.model().index(0), QItemSelectionModel.SelectCurrent)

    def onSelectionChanged(self, selected, deselected):
        """
        Since we use persistent editors for every item, we have to handle
        highlighting/highlighting the selected editor ourselves whenever the selection changes.
        """
        self._itemDelegate.onSelectionChanged(selected, deselected)


#     This whole function used to be necessary when we didn't use persistent editors.
#     Now that our editors exist permanently, this wacky duplication of mouseevents isn't necessary.
#     In any case, the proper way to do what this function was doing is probably to override
#     QAbstractItemDelegate.editorEvent(), and forward the event from there.
#     def mousePressEvent(self, event):
#         prevIndex = self.model().selectedIndex()
#         newIndex = self.indexAt( event.pos() )
#         super(LayerWidget, self).mousePressEvent(event)
#
#         # HACK: The first click merely gives focus to the list item without actually passing the event to it.
#         # We'll simulate a mouse click on the item by sending a duplicate pair of QMouseEvent press/release events to the appropriate widget.
#         if prevIndex != newIndex and newIndex.row() != -1:
#             layer = self.model().itemData(newIndex)[Qt.EditRole]
#             assert isinstance(layer, Layer)
#             hitWidget = QApplication.widgetAt( event.globalPos() )
#             if hitWidget is None:
#                 return
#             localPos = hitWidget.mapFromGlobal( event.globalPos() )
#             hitWidgetPress = QMouseEvent( QMouseEvent.MouseButtonPress, localPos, event.globalPos(), event.button(), event.buttons(), event.modifiers() )
#             QApplication.instance().sendEvent(hitWidget, hitWidgetPress)
#             hitWidgetRelease = QMouseEvent( QMouseEvent.MouseButtonRelease, localPos, event.globalPos(), event.button(), event.buttons(), event.modifiers() )
#             QApplication.instance().sendEvent(hitWidget, hitWidgetRelease)

# *******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
# *******************************************************************************

if __name__ == "__main__":
    # make the program quit on Ctrl+C
    import signal

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    import sys, numpy

    from PyQt5.QtWidgets import QPushButton, QHBoxLayout, QVBoxLayout
    from volumina.pixelpipeline.datasources import ArraySource, ConstantSource

    app = QApplication(sys.argv)

    model = LayerStackModel()

    o1 = Layer([ConstantSource()])
    o1.name = "Fancy Layer"
    o1.opacity = 0.5
    model.append(o1)

    o2 = Layer([ConstantSource()])
    o2.name = "Some other Layer"
    o2.opacity = 0.25
    o2.numberOfChannels = 3
    model.append(o2)

    o3 = Layer([ConstantSource()])
    o3.name = "Invisible Layer"
    o3.opacity = 0.15
    o3.visible = False
    model.append(o3)

    o4 = Layer([ConstantSource()])
    o4.name = "Fancy Layer II"
    o4.opacity = 0.95
    model.append(o4)

    o5 = Layer([ConstantSource()])
    o5.name = "Fancy Layer III"
    o5.opacity = 0.65
    model.append(o5)

    o6 = Layer([ConstantSource()])
    o6.name = "Lazyflow Layer"
    o6.opacity = 1

    testVolume = numpy.random.rand(100, 100, 100, 3).astype("uint8")
    source = [ArraySource(testVolume)]
    o6._datasources = source
    model.append(o6)

    view = LayerWidget(None, model)
    view.show()
    view.updateGeometry()

    w = QWidget()
    lh = QHBoxLayout(w)
    lh.addWidget(view)

    up = QPushButton("Up")
    down = QPushButton("Down")
    delete = QPushButton("Delete")
    add = QPushButton("Add")
    lv = QVBoxLayout()
    lh.addLayout(lv)

    lv.addWidget(up)
    lv.addWidget(down)
    lv.addWidget(delete)
    lv.addWidget(add)

    w.setGeometry(100, 100, 800, 600)
    w.show()

    up.clicked.connect(model.moveSelectedUp)
    model.canMoveSelectedUp.connect(up.setEnabled)
    down.clicked.connect(model.moveSelectedDown)
    model.canMoveSelectedDown.connect(down.setEnabled)
    delete.clicked.connect(model.deleteSelected)
    model.canDeleteSelected.connect(delete.setEnabled)

    def addRandomLayer():
        o = Layer([ConstantSource()])
        o.name = "Layer %d" % (model.rowCount() + 1)
        o.opacity = numpy.random.rand()
        o.visible = bool(numpy.random.randint(0, 2))
        model.append(o)

    add.clicked.connect(addRandomLayer)

    app.exec_()

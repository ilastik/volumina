from __future__ import absolute_import

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
import numpy
from functools import partial

import qtpy.compat
from qtpy.QtCore import Signal, QObject, QEvent, QPointF, Qt, QTimer
from qtpy.QtGui import QPen, QBrush, QMouseEvent
from qtpy.QtWidgets import QApplication, QGraphicsLineItem, QUndoCommand

from volumina.eventswitch import InterpreterABC
from .navigationController import NavigationInterpreter


# *******************************************************************************
# C r o s s h a i r C o n t r o l e r                                          *
# *******************************************************************************
class DrawLabelCommand(QUndoCommand):
    def __init__(self, parent=None, *, sink, slicing, old_data, labels):
        super().__init__(parent)
        self.__old_data = old_data
        # 0 value is special in labels array. It means there is no data
        self.__labels = labels
        self.__slicing = slicing
        self.__sink = sink

    def redo(self):
        redo_data = numpy.where(self.__labels != 0, self.__labels, self.__old_data)
        redo_data = redo_data.astype(self.__labels.dtype)
        self.__sink.put(self.__slicing, redo_data)

    def undo(self):
        undo_data = self.__old_data

        if self.__sink.eraser_value is not None:
            erase = numpy.where(self.__labels != 0, self.__sink.eraser_value, 0)  # What to do to erase new label fully
            undo_data = numpy.where(self.__old_data, self.__old_data, erase)

        undo_data = undo_data.astype(self.__labels.dtype)
        self.__sink.put(self.__slicing, undo_data)


class CrosshairController(QObject):
    def __init__(self, brushingModel, imageViews):
        QObject.__init__(self, parent=None)
        self._brushingModel = brushingModel
        self._brushingModel.brushSizeChanged.connect(self._setBrushSize)
        self._brushingModel.brushColorChanged.connect(self._setBrushColor)
        self._imageViews = imageViews

    def _setBrushSize(self, size):
        for v in self._imageViews:
            v._crossHairCursor.setBrushSize(size)

    def _setBrushColor(self, color):
        for v in self._imageViews:
            v._crossHairCursor.setColor(color)


# *******************************************************************************
# B r u s h i n g I n t e r p r e t e r                                        *
# *******************************************************************************


class BrushingInterpreter(QObject, InterpreterABC):
    # states
    FINAL = 0
    DEFAULT_MODE = 1

    # FIXME: This state isn't really needed, now that we use a QTimer to manage the double-click case.
    #        (The state machine should be rewritten.)
    MAYBE_DRAW_MODE = 2  # received a single left-click; however, the next event
    # might be a double-click event; therefore the state has
    # not been decided yet
    DRAW_MODE = 3

    @property
    def state(self):
        return self._current_state

    def __init__(self, navigationController, brushingController):
        QObject.__init__(self)
        self._navCtrl = navigationController
        self._navIntr = NavigationInterpreter(navigationController)
        self._brushingCtrl = brushingController
        self._current_state = self.FINAL
        self._temp_erasing = False  # indicates, if user pressed shift
        # for temporary erasing (in
        # contrast to selecting the eraser brush)

        self._lineItems = []  # list of line items that have been
        # added to the qgraphicsscene for drawing indication

        self._lastEvent = None
        self._doubleClickTimer = None

        # clear the temporary line items once they
        # have been pushed to the sink
        self._brushingCtrl.wroteToSink.connect(self.clearLines)

    def start(self):
        if self._current_state == self.FINAL:
            self._navIntr.start()
            self._current_state = self.DEFAULT_MODE
        else:
            pass  # ignore

    def stop(self):
        if self._brushingCtrl._isDrawing:
            for imageview in self._navCtrl._views:
                self._brushingCtrl.endDrawing(imageview.mousePos)
        self._current_state = self.FINAL
        self._navIntr.stop()

    def eventFilter(self, watched, event):
        etype = event.type()

        # Before we steal this event from the scene, check that it is allowing brush strokes
        allow_brushing = True
        for view in self._navCtrl._views:
            # after updating python to 3.9 we encountered exceptions when shutting
            #  ilastik down. Since we don't own the view or the scene, those could
            # get deleted then accessing those would raise.
            if not qtpy.compat.isalive(view):
                continue
            if not (view.scene() and view.scene().allow_brushing):
                return self._navIntr.eventFilter(watched, event)

        if etype == QEvent.MouseButtonDblClick and self._doubleClickTimer is not None:
            # On doubleclick, cancel release handler that normally draws the stroke.
            self._doubleClickTimer.stop()
            self._doubleClickTimer = None
            self._current_state = self.DEFAULT_MODE
            self.onEntry_default(watched, event)

        if self._current_state == self.DEFAULT_MODE:
            if (
                etype == QEvent.MouseButtonPress
                and event.button() == Qt.LeftButton
                and event.modifiers() == Qt.NoModifier
                and self._navIntr.mousePositionValid(watched, event)
            ):
                ### default mode -> maybe draw mode
                self._current_state = self.MAYBE_DRAW_MODE

                # event will not be valid to use after this function exits,
                # so we must make a copy of it instead of just saving the pointer
                self._lastEvent = QMouseEvent(
                    event.type(), event.pos(), event.globalPos(), event.button(), event.buttons(), event.modifiers()
                )

        elif self._current_state == self.MAYBE_DRAW_MODE:
            if etype == QEvent.MouseMove:
                # navigation interpreter also has to be in
                # default mode to avoid inconsistencies
                if self._navIntr.state == self._navIntr.DEFAULT_MODE:
                    ### maybe draw mode -> maybe draw mode
                    self._current_state = self.DRAW_MODE
                    self.onEntry_draw(watched, self._lastEvent)
                    self.onMouseMove_draw(watched, event)
                    return True
                else:
                    self._navIntr.eventFilter(watched, self._lastEvent)
                    return self._navIntr.eventFilter(watched, event)
            elif etype == QEvent.MouseButtonDblClick:
                ### maybe draw mode -> default mode
                self._current_state = self.DEFAULT_MODE
                return self._navIntr.eventFilter(watched, event)
            elif etype == QEvent.MouseButtonRelease:

                def handleRelease(releaseEvent):
                    self._current_state = self.DRAW_MODE
                    self.onEntry_draw(watched, self._lastEvent)
                    self.onExit_draw(watched, releaseEvent)
                    self._current_state = self.DEFAULT_MODE
                    self.onEntry_default(watched, releaseEvent)

                # If this event is part of a double-click, we don't really want to handle it.
                # Typical event sequence is press, release, double-click (not two presses).
                # Instead of handling this right away, set a timer to do the work.
                # We'll cancel the timer if we see a double-click event (see above).
                self._doubleClickTimer = QTimer(self)
                self._doubleClickTimer.setInterval(200)
                self._doubleClickTimer.setSingleShot(True)
                # event will not be valid to use after this function exits,
                # so we must make a copy of it instead of just saving the pointer
                eventCopy = QMouseEvent(event.type(), event.pos(), event.button(), event.buttons(), event.modifiers())
                self._doubleClickTimer.timeout.connect(partial(handleRelease, eventCopy))
                self._doubleClickTimer.start()

                return True

        elif self._current_state == self.DRAW_MODE:
            if etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.onExit_draw(watched, event)
                ### draw mode -> default mode
                self._current_state = self.DEFAULT_MODE
                self.onEntry_default(watched, event)
                return True

            elif etype == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                if self._navIntr.mousePositionValid(watched, event):
                    self.onMouseMove_draw(watched, event)
                    return True
                else:
                    self.onExit_draw(watched, event)
                    ### draw mode -> default mode
                    self._current_state = self.DEFAULT_MODE
                    self.onEntry_default(watched, event)

        # let the navigation interpreter handle common events
        return self._navIntr.eventFilter(watched, event)

    ###
    ### Default Mode
    ###
    def onEntry_default(self, imageview, event):
        pass

    ###
    ### Draw Mode
    ###
    def onEntry_draw(self, imageview, event):
        if QApplication.keyboardModifiers() == Qt.ShiftModifier:
            self._brushingCtrl._brushingModel.setErasing()
            self._temp_erasing = True
        imageview.mousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
        self._brushingCtrl.beginDrawing(imageview, imageview.mousePos)

    def onExit_draw(self, imageview, event):
        self._brushingCtrl.endDrawing(imageview.mousePos)
        if self._temp_erasing:
            self._brushingCtrl._brushingModel.disableErasing()
            self._temp_erasing = False

    def onMouseMove_draw(self, imageview, event):
        self._navIntr.onMouseMove_default(imageview, event)

        o = imageview.scene().data2scene.map(QPointF(imageview.oldX, imageview.oldY))
        n = imageview.scene().data2scene.map(QPointF(imageview.x, imageview.y))

        # Draw temporary line for the brush stroke so the user gets feedback before the data is really updated.
        pen = QPen(
            QBrush(self._brushingCtrl._brushingModel.drawColor),
            self._brushingCtrl._brushingModel.brushSize,
            Qt.SolidLine,
            Qt.RoundCap,
            Qt.RoundJoin,
        )
        line = QGraphicsLineItem(o.x(), o.y(), n.x(), n.y())
        line.setPen(pen)

        imageview.scene().addItem(line)
        line.setParentItem(imageview.scene().dataRectItem)

        self._lineItems.append(line)
        self._brushingCtrl._brushingModel.moveTo(imageview.mousePos)

    def clearLines(self):
        # This is called after the brush stroke is stored to the data.
        # Our temporary line object is no longer needed because the data provides the true pixel labels that were stored.
        lines = self._lineItems
        self._lineItems = []
        for l in lines:
            l.hide()

    def updateCursorPosition(self, *args, **kwargs):
        self._navIntr.updateCursorPosition(*args, **kwargs)


# *******************************************************************************
# B r u s h i n g C o n t r o l e r                                            *
# *******************************************************************************


class BrushingController(QObject):
    wroteToSink = Signal()

    def __init__(self, brushingModel, positionModel, dataSink, *, undoStack):
        QObject.__init__(self, parent=None)
        self._dataSink = dataSink
        self._undoStack = undoStack

        self._brushingModel = brushingModel
        self._brushingModel.brushStrokeAvailable.connect(self._writeIntoSink)
        self._positionModel = positionModel

        self._isDrawing = False
        self._tempErase = False

    def beginDrawing(self, imageview, pos):
        imageview.mousePos = pos
        self._isDrawing = True
        self._brushingModel.beginDrawing(pos, imageview.sliceShape)

    def endDrawing(self, pos):
        self._isDrawing = False
        self._brushingModel.endDrawing(pos)

    def setDataSink(self, dataSink):
        self._dataSink = dataSink

    def _writeIntoSink(self, brushStrokeOffset, labels):
        activeView = self._positionModel.activeView
        slicingPos = self._positionModel.slicingPos
        t, c = self._positionModel.time, self._positionModel.channel

        slicing = [
            slice(int(brushStrokeOffset.x()), int(brushStrokeOffset.x()) + labels.shape[0]),
            slice(int(brushStrokeOffset.y()), int(brushStrokeOffset.y()) + labels.shape[1]),
        ]

        slicing.insert(activeView, slice(int(slicingPos[activeView]), int(slicingPos[activeView] + 1)))

        slicing = (slice(t, t + 1),) + tuple(slicing) + (slice(c, c + 1),)

        # make the labels 5d for correct graph compatibility
        newshape = list(labels.shape)
        newshape.insert(activeView, 1)
        newshape.insert(0, 1)
        newshape.append(1)

        # newlabels = numpy.zeros
        if self._dataSink != None:
            new_labels = labels.reshape(tuple(newshape))
            # Assuming ownership of the data, in case of array sink will be overwritten
            old_data = self._dataSink.request(slicing).wait().copy()

            cmd = DrawLabelCommand(sink=self._dataSink, slicing=slicing, old_data=old_data, labels=new_labels)

            self._undoStack.push(cmd)
            self.wroteToSink.emit()

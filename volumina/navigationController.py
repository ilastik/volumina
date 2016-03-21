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
from __future__ import division
from __future__ import absolute_import
from builtins import range
from PyQt5.QtCore import QObject, QTimer, QEvent, Qt, QPointF, pyqtSignal
from PyQt5.QtGui import QColor, QCursor 

import copy
import warnings
from functools import partial

from .eventswitch import InterpreterABC

from volumina.sliceIntersectionMarker import SliceIntersectionMarker
from volumina.imageScene2D import DirtyIndicator
import volumina

def posView2D(pos3d, axis):
    """convert from a 3D position to a 2D position on the slicing plane
       perpendicular to axis"""
    pos2d = list(copy.deepcopy(pos3d))
    del pos2d[axis]
    return pos2d

#*******************************************************************************
# N a v i g a t i o n I n t e r p r e t e r                                    *
#*******************************************************************************

class NavigationInterpreter(QObject):
    # states
    FINAL = 0
    DEFAULT_MODE = 1
    DRAG_MODE = 2

    @property
    def state( self ):
        return self._current_state

    def __init__(self, navigationcontroller):
        QObject.__init__(self)
        self._navCtrl = navigationcontroller
        self._current_state = self.FINAL

    def start( self ):
        if self._current_state == self.FINAL:
            self._current_state = self.DEFAULT_MODE
        else:
            pass # ignore

    def stop( self ):
        self._current_state = self.FINAL

    def eventFilter( self, watched, event ):
        if not self._navCtrl.enableNavigation:
            return False

        etype = event.type()
        ### the following implements a simple state machine
        if self._current_state == self.DEFAULT_MODE:
            ### default mode -> drag mode

            if    (etype == QEvent.MouseButtonPress and event.button() == Qt.MidButton) \
               or (etype == QEvent.MouseButtonPress and event.modifiers() == Qt.ShiftModifier):
                # self.onExit_default(): call it here, if needed
                self._current_state = self.DRAG_MODE
                self.onEntry_drag( watched, event )
                event.accept()
                return True

            ### actions in default mode
            elif etype == QEvent.MouseMove:
                return self.onMouseMove_default( watched, event )

            elif etype == QEvent.Wheel:
                self.onWheel_default( watched, event )
                event.accept()
                return True

            elif etype == QEvent.MouseButtonDblClick:
                return self.onMouseDoubleClick_default( watched, event )

            elif etype == QEvent.MouseButtonPress:
                return self.onMousePress_default( watched, event )

        elif self._current_state == self.DRAG_MODE:
            ### drag mode -> default mode
            if etype == QEvent.MouseButtonRelease:
                self.onExit_drag( watched, event)
                self._current_state = self.DEFAULT_MODE
                self.onEntry_default( watched, event )
                event.accept()
                return True

            ### actions in drag mode
            elif etype == QEvent.MouseMove:
                self.onMouseMove_drag( watched, event )
                event.accept()
                return True

        event.ignore()
        return False

    def mousePositionValid( self, imageview, event):
        axis = self._navCtrl._model.activeView
        dataCoord2D = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
        newPos = [dataCoord2D.x(), dataCoord2D.y()]
        newPos.insert(axis, self._navCtrl._model.slicingPos[axis])
        if not self._navCtrl._positionValid(newPos):
            return False
        return True

    ###
    ### Default Mode
    ###
    def onEntry_default( self, imageview, event ):
        pass

    def onWheel_default( self, imageview, event ):
        if not imageview.isEnabled():
            return
        navCtrl = self._navCtrl
        k_alt = (event.modifiers() == Qt.AltModifier)
        k_ctrl = (event.modifiers() == Qt.ControlModifier)
        k_shift = (event.modifiers() == Qt.ShiftModifier)
        k_shift_alt = (event.modifiers() == (Qt.ShiftModifier | Qt.AltModifier))
        imageview.mousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))

        sceneMousePos = imageview.mapToScene(event.pos())
        grviewCenter = imageview.mapToScene(imageview.viewport().rect().center())

        sign = 1
        if event.angleDelta().y() < 0:
            sign = -1

        if k_shift_alt:
            navCtrl.changeTimeRelative(sign*10)
        elif k_alt:
            navCtrl.changeSliceRelative(sign*10, navCtrl._views.index(imageview))
        elif k_ctrl:
            mult = max(1, (event.angleDelta().y() // 120))
            scaleFactor = 1.0 + sign*0.1*mult
            imageview.doScale(scaleFactor)
        elif k_shift:
            navCtrl.changeTimeRelative(sign*1)
        else:
            # A single 'step' of a scroll wheel is typically 15 degrees, which Qt represents with angleDelta=120
            # We'll give a little boost so that 1 step is 1 plane, but 3 steps is 4 planes.
            planes = max( 1, ( sign*event.angleDelta().y() // (120*3//4) ) )
            navCtrl.changeSliceRelative(sign*planes, navCtrl._views.index(imageview))

        if k_ctrl:
            mousePosAfterScale = imageview.mapToScene(event.pos())
            offset = sceneMousePos - mousePosAfterScale
            newGrviewCenter = grviewCenter + offset
            imageview.centerOn(newGrviewCenter)
            self.onMouseMove_default( imageview, event )

    def onMouseMove_default( self, imageview, event ):
        if imageview._ticker.isActive():
            #the view is still scrolling
            #do nothing until it comes to a complete stop
            event.ignore()
            return False

        self.updateCursorPosition(imageview, event)
        #do not accept event
        event.ignore()
        return False

    def updateCursorPosition(self, imageview, event):
        """Update the position model's cursor position according to the given event position."""
        imageview.mousePos = mousePos = imageview.mapMouseCoordinates2Data(event.pos())
        imageview.oldX, imageview.oldY = imageview.x, imageview.y
        dataX = imageview.x = mousePos.x()
        dataY = imageview.y = mousePos.y()

        self._navCtrl.positionDataCursor(QPointF(dataX, dataY), self._navCtrl._views.index(imageview))

    def onMousePress_default( self, imageview, event ):
        #make sure that we have the cursor at the correct position
        #before we call the context menu
        self.onMouseMove_default( imageview, event )

        # If the user is clicking on an item in the scene, let it handle this event
        if len( self._itemsAt(imageview, event.pos()) ) > 0:
            return False

        pos = event.pos()
        imageview.customContextMenuRequested.emit( pos )
        event.accept()
        return True

    def _itemsAt(self, imageview, pos):
        """returns all QGraphicsItem under the posistion 'pos', except those managed internally by volumina"""
        itms = imageview.items(pos)
        itms = [x for x in itms if not ( \
                  isinstance(x, volumina.sliceIntersectionMarker.SliceIntersectionMarker) or \
                  isinstance(x, volumina.imageScene2D.DirtyIndicator) or \
                  isinstance(x, volumina.crossHairCursor.CrossHairCursor) or \
                  x is imageview.scene().dataRectItem ) ]
        return itms

    def onMouseDoubleClick_default( self, imageview, event ):
        # If the user is clicking on an item in the scene, let it handle this event
        if len( self._itemsAt(imageview, event.pos()) ) > 0:
            return False

        dataMousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
        self._navCtrl.navigateToPoint(dataMousePos.x(), dataMousePos.y(), self._navCtrl._views.index(imageview))
        event.accept()
        return True

    ###
    ### Drag Mode
    ###
    def onEntry_drag( self, imageview, event ):
        imageview.setCursor(QCursor(Qt.SizeAllCursor))
        imageview._lastPanPoint = event.pos()
        imageview._crossHairCursor.setVisible(False)
        imageview._dragMode = True
        if imageview._ticker.isActive():
            imageview._deltaPan = QPointF(0, 0)

    def onExit_drag( self, imageview, event ):
        imageview.mousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
        imageview.setCursor(QCursor())
        releasePoint = event.pos()
        imageview._lastPanPoint = releasePoint
        imageview._dragMode = False
        imageview._ticker.start(20)

    def onMouseMove_drag( self, imageview, event ):
        imageview._deltaPan = QPointF(event.pos() - imageview._lastPanPoint)
        imageview._panning()
        imageview._lastPanPoint = event.pos()
assert issubclass(NavigationInterpreter, InterpreterABC)

#*******************************************************************************
# N a v i g a t i o n C o n t r o l e r                                        *
#*******************************************************************************

class NavigationController(QObject):
    """
    Controller for navigating through the volume.

    The NavigationContrler object listens to changes
    in a given PositionModel and updates three slice
    views (representing the spatial X, Y and Z slicings)
    accordingly.

    properties:

    indicateSliceIntersection -- whether to show red/green/blue lines
        indicating the position of the other two slice views on each slice
        view

    enableNavigation -- whether the position is allowed to be changed
    """

    navigationEnabled = pyqtSignal(bool)

    @property
    def axisColors( self ):
        return self._axisColors
    @axisColors.setter
    def axisColors( self, colors ):
        self._axisColors = colors
        self._views[0]._sliceIntersectionMarker.setColor(self.axisColors[1], self.axisColors[2])
        self._views[1]._sliceIntersectionMarker.setColor(self.axisColors[0], self.axisColors[2])
        self._views[2]._sliceIntersectionMarker.setColor(self.axisColors[0], self.axisColors[1])
        for axis, v in enumerate(self._views):
            #FIXME: Bad dependency here on hud to be available!
            if v.hud: v.hud.bgColor = self.axisColors[axis]

    @property
    def indicateSliceIntersection(self):
        return self._indicateSliceIntersection
    @indicateSliceIntersection.setter
    def indicateSliceIntersection(self, show):
        self._indicateSliceIntersection = show
        for v in self._views:
            v._sliceIntersectionMarker.setVisible(show)

    @property
    def enableNavigation(self):
        return self._navigationEnabled
    @enableNavigation.setter
    def enableNavigation(self, enabled):
        self._navigationEnabled = enabled
        self.navigationEnabled.emit(enabled)

    def __init__(self, imageView2Ds, imagePumps, positionModel, time = 0, channel = 0, view3d=None):
        QObject.__init__(self)
        assert len(imageView2Ds) == 3

        # init fields
        self._views = imageView2Ds
        self._imagePumps = imagePumps
        self._model = positionModel
        self._beginStackIndex = 0
        self._endStackIndex   = 1
        self._view3d = view3d
        self._navigationEnabled = True
        self.axisColors = [QColor(255,0,0,255), QColor(0,255,0,255), QColor(0,0,255,255)]

    def moveCrosshair(self, newPos, oldPos):
        self._updateCrossHairCursor()

    def navigateToPoint(self, x, y, axis):
        newPos = copy.copy(self._model.slicingPos)
        i,j = posView2D([0,1,2], axis)
        newPos[i] = x
        newPos[j] = y
        if newPos == self._model.slicingPos:
            return
        if not self._positionValid(newPos):
            return

        # pos must not be float.
        self._model.slicingPos = list(map(int, newPos))
        self.panSlicingViews( newPos, [a for a in [0,1,2] if a != axis] )

    def panSlicingViews(self, point3d, axes):
        """
        For each of the given axes, pan the slicing view to the ordinate-abscissa point in point3d,
        but DON'T change the slicing plane.
        """
        for axis, view in enumerate(self._views):
            if axis in axes:
                pos2d = posView2D(point3d, axis)
                dataPoint = QPointF( *pos2d )
                scenePoint = view.scene().data2scene.map(dataPoint)
                view.centerOn( scenePoint )

    def moveSlicingPosition(self, newPos, oldPos):
        for i in range(3):
            if newPos[i] != oldPos[i]:
                self._updateSlice(self._model.slicingPos[i], i)
        self._updateSliceIntersection()

        #when scrolling fast through the stack, we don't want to update
        #the 3d view all the time
        if self._view3d is None:
            return
        def maybeUpdateSlice(oldSlicing):
            if oldSlicing == self._model.slicingPos:
                self._view3d.ChangeSlice(self._model.slicingPos)
        QTimer.singleShot(50, partial(maybeUpdateSlice, self._model.slicingPos))

    def changeTime(self, newTime):
        for i in range(3):
            self._imagePumps[i].syncedSliceSources.setThrough(0, newTime)

    def changeTimeRelative( self, delta ):
        if self._model.shape5D is None or delta == 0:
            return
        cur_t = self._imagePumps[0].syncedSliceSources.through[0]
        new_t = cur_t + delta

        #sanitize
        new_t = 0 if new_t < 0 else new_t
        new_t = self._model.shape5D[0] - 1 if new_t >= self._model.shape5D[0] else new_t
        self._model.time = new_t

    def changeChannel(self, newChannel):
        '''Change channel for all layers simultaneously.

        This function can be used if all layers are synced along the
        channel axis and the new channel value exists for all
        layers. Use 'layerChangeChannel()' otherwise.
        
        '''
        for pump in self._imagePumps:
            if 2 not in pump.syncedSliceSources.getSyncAlong():
                raise RuntimeError("NavigationController.changeChannel: channel axis not synced in all image pumps; can't apply method")
        if self._model.shape is None:
            return
        for i in range(3):
            self._imagePumps[i].syncedSliceSources.setThrough(2, newChannel)

    def layerChangeChannel( self, layer ):
        '''Change the channel for a single layer.

        This function can be used when the layers are not synced along
        the channel axis. Use 'changeChannel()' otherwise.

        '''
        for pump in self._imagePumps:
            for src in pump.layerToSliceSources( layer ):
                src.setThrough(2, layer.channel)
        # Note: we update the slice sources of a layer
        # sequentially. This could cause flickering if there are
        # two or more slice sources per layer (like a RGBA layer). 

    def changeSliceRelative(self, delta, axis):
        if self._model.shape is None:
            return
        """
        Change slice along a certain axis relative to current slice.

        delta -- add delta to current slice position [positive or negative int]
        axis  -- along which axis [0,1,2]
        """

        if delta == 0:
            return
        newSlice = self._model.slicingPos[axis] + delta

        try:
            roi_3d = self._model.parent().cropModel.get_roi_3d()
            minValue = roi_3d[0][axis]
            maxValue = roi_3d[1][axis]
        except:
            minValue = 0
            maxValue = self._model.volumeExtent(axis)

        #sanitize
        newSlice = minValue if newSlice < minValue else newSlice
        newSlice = maxValue-1 if newSlice >= maxValue else newSlice

        newPos = copy.copy(self._model.slicingPos)
        newPos[axis] = newSlice

        cursorPos = copy.copy(self._model.cursorPos)
        cursorPos[axis] = newSlice
        self._model.cursorPos  = cursorPos

        self._model.slicingPos = newPos

    def changeSliceAbsolute(self, value, axis):
        """
        Change slice along a certain axis.

        value -- slice number
        axis  -- along which axis [0,1,2]
        """

        if value < 0 or value > self._model.volumeExtent(axis):
            return
        newPos = copy.copy(self._model.slicingPos)
        newPos[axis] = value
        if not self._positionValid(newPos):
            return

        cursorPos = list(self._model.cursorPos)
        cursorPos[axis] = value
        self._model.cursorPos  = cursorPos

        self._model.slicingPos = newPos

    def settleSlicingPosition(self, settled):
        for v in self._views:
            v.indicateSlicingPositionSettled(settled)


    def positionDataCursor(self, dataCoord2D, axis):
        """
        Change position of the crosshair cursor.
        dataCord2D -- 2D coordinate on the slicing plane perpendicular to axis
                      in data coordinate system
        axis -- perpendicular axis [0,1,2]
        """

        #we get the 2D coordinates x,y from the view that
        #shows the projection perpendicular to axis
        #set this view as active
        self._model.activeView = axis

        newPos = [dataCoord2D.x(), dataCoord2D.y()]
        newPos.insert(axis, self._model.slicingPos[axis])

        if not self._positionValid(newPos):
            return False

        if newPos == self._model.cursorPos:
            return True

        self._model.cursorPos = newPos

        return True

    #private functions ########################################################

    def _updateCrossHairCursor(self):
        dataX, dataY = posView2D(self._model.cursorPos, axis=self._model.activeView)

        self._views[self._model.activeView]._crossHairCursor.showXYPosition(dataX, dataY)
        
        for i, v in enumerate(self._views):
            v._crossHairCursor.setVisible( self._model.activeView == i )

    def _updateSliceIntersection(self):
        for axis, v in enumerate(self._views):
            dataX, dataY = posView2D(self._model.slicingPos, axis)
            v._sliceIntersectionMarker.setPosition( dataX, dataY )

    def _updateSlice(self, num, axis):
        if num < 0 or num >= self._model.volumeExtent(axis):
            raise Exception("NavigationController._setSlice(): invalid slice number = %d not in range [0,%d)" % (num, self._model.volumeExtent(axis)))
        #FIXME: Shouldnt the hud listen to the model changes itself?
        self._views[axis].hud.sliceSelector.setValue(num)

        #re-configure the slice source
        self._imagePumps[axis].syncedSliceSources.setThrough(1,num)

    def _positionValid(self, pos):
        if self._model.shape is None:
            return False
        for i in range(3):
            if pos[i] < 0 or pos[i] >= self._model.shape[i]:
                return False
        return True

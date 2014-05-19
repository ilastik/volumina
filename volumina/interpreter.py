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
from PyQt4.QtCore import QObject, pyqtSignal, QEvent, Qt, QPoint

class ClickReportingInterpreter(QObject):
    rightClickReceived = pyqtSignal(object, QPoint) # list of indexes, global window coordinate of click
    leftClickReceived = pyqtSignal(object, QPoint)  # ditto
    
    def __init__(self, navigationInterpreter, positionModel):
        QObject.__init__(self)
        self.baseInterpret = navigationInterpreter
        self.posModel      = positionModel

    def start( self ):
        self.baseInterpret.start()

    def stop( self ):
        self.baseInterpret.stop()

    def eventFilter( self, watched, event ):
        if event.type() == QEvent.MouseButtonPress:
            pos = [int(i) for i in self.posModel.cursorPos]
            pos = [self.posModel.time] + pos + [self.posModel.channel]

            if event.button() == Qt.LeftButton:
                gPos = watched.mapToGlobal( event.pos() )
                self.leftClickReceived.emit( pos, gPos )
            if event.button() == Qt.RightButton:
                gPos = watched.mapToGlobal( event.pos() )
                self.rightClickReceived.emit( pos, gPos )                

        # Event is always forwarded to the navigation interpreter.
        return self.baseInterpret.eventFilter(watched, event)

    def updateCursorPosition(self, *args, **kwargs):
        self.baseInterpret.updateCursorPosition(*args, **kwargs)

class ClickInterpreter(QObject):
    """Intercepts mouse clicks (right clicks by default) and double
       click events on a layer and calls a given functor with the
       clicked position.

    """
       
    def __init__(self, editor, layer, onClickFunctor, parent=None, right=True, double=True):
        """ editor:         VolumeEditor object
            layer:          Layer instance on which was clicked
            onClickFunctor: a function f(layer, position5D, windowPosition)
            right: If True, intercept right clicks, otherwise intercept left clicks.
        """
        QObject.__init__(self, parent)
        self.baseInterpret = editor.navInterpret
        self.posModel      = editor.posModel
        self._onClick = onClickFunctor
        self._layer = layer
        if right:
            self.button = Qt.RightButton
        else:
            self.button = Qt.LeftButton
        self.double = double

    def start( self ):
        self.baseInterpret.start()

    def stop( self ):
        self.baseInterpret.stop()

    def eventFilter( self, watched, event ):
        etype = event.type()
        handle = False
        if etype == QEvent.MouseButtonPress and event.button() == self.button:
            #print "Clicked {} / {}".format( event.pos(), event.globalPos() )
            handle = True
        if etype == QEvent.MouseButtonDblClick and self.double and event.button() == self.button:
            handle = True
        if etype == QEvent.MouseButtonPress and event.modifiers() == Qt.ShiftModifier:
            handle = False #dragging
        if handle:
            # Ensure that the data cursor position is in the right place
            # (Don't assume that the last mouse-move put it there for us.)
            self.baseInterpret.updateCursorPosition(watched, event)
            pos = self.posModel.cursorPos
            pos = [int(i) for i in pos]
            pos = [self.posModel.time] + pos + [self.posModel.channel]
            self._onClick(self._layer, tuple(pos), event.pos())
            return True
        else:
            return self.baseInterpret.eventFilter(watched, event)

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
#!/usr/bin/env python
# -*- coding: utf-8 -*-

#    Copyright 2010, 2011 C Sommer, C Straehle, U Koethe, FA Hamprecht. All rights reserved.
#
#    Redistribution and use in source and binary forms, with or without modification, are
#    permitted provided that the following conditions are met:
#
#       1. Redistributions of source code must retain the above copyright notice, this list of
#          conditions and the following disclaimer.
#
#       2. Redistributions in binary form must reproduce the above copyright notice, this list
#          of conditions and the following disclaimer in the documentation and/or other materials
#          provided with the distribution.
#
#    THIS SOFTWARE IS PROVIDED BY THE ABOVE COPYRIGHT HOLDERS ``AS IS'' AND ANY EXPRESS OR IMPLIED
#    WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
#    FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE ABOVE COPYRIGHT HOLDERS OR
#    CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
#    CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#    SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
#    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
#    NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
#    ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
#    The views and conclusions contained in the software and documentation are those of the
#    authors and should not be interpreted as representing official policies, either expressed
#    or implied, of their employers.

from qtpy.QtCore import Qt, QPointF, QRectF
from qtpy.QtGui import QPen
from qtpy.QtWidgets import QGraphicsItem

# *******************************************************************************
# C r o s s H a i r C u r s o r                                                *
# *******************************************************************************


class CrossHairCursor(QGraphicsItem):
    """
    A 2D cross-hair cursor centered around a point (x,y) on the scene.
    A cross hair cursor usually follows the mouse cursor and has a color
    and marks the size of the current brush.
    """

    modeYPosition = 0
    modeXPosition = 1
    modeXYPosition = 2

    def boundingRect(self):
        return self.scene().data2scene.mapRect(QRectF(0, 0, self._width, self._height))

    def __init__(self):
        QGraphicsItem.__init__(self)

        self._width = 0
        self._height = 0

        self.penDotted = QPen(Qt.red, 2, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin)
        self.penDotted.setCosmetic(True)

        self.penSolid = QPen(Qt.red, 2)
        self.penSolid.setCosmetic(True)

        self.x = 0
        self.y = 0
        self.brushSize = 0

        self.mode = self.modeXYPosition
        self._enabled = True

    @property
    def enabled(self):
        return self._enabled

    @enabled.setter
    def enabled(self, v):
        if not v:
            self.setVisible(False)
        self._enabled = v

    def setVisible(self, visible):
        # TODO: though the crosshair is hidden, its position is still
        # updated. instead of just hiding it, we should
        # not instantiate it in the first place.
        if self._enabled:
            super(CrossHairCursor, self).setVisible(visible)

    # be careful: QGraphicsItem has a shape() method, which
    # we cannot override, therefore we choose this name
    @property
    def dataShape(self):
        return (self._width, self._height)

    @dataShape.setter
    def dataShape(self, shape2D):
        self._width = shape2D[0]
        self._height = shape2D[1]

    def setColor(self, color):
        self.penDotted = QPen(color, 2, Qt.DotLine, Qt.RoundCap, Qt.RoundJoin)
        self.penDotted.setCosmetic(True)
        self.penSolid = QPen(color, 2)
        self.penSolid.setCosmetic(True)
        self.update()

    def showXPosition(self, x, y):
        """only mark the x position by displaying a line f(y) = x"""
        self.setVisible(True)
        self.mode = self.modeXPosition
        self.setPos(x, y - int(y))

    def showYPosition(self, y, x):
        """only mark the y position by displaying a line f(x) = y"""
        self.setVisible(True)
        self.mode = self.modeYPosition
        self.setPos(x - int(x), y)

    def showXYPosition(self, x, y):
        """mark the (x,y) position by displaying a cross hair cursor
        including a circle indicating the current brush size"""
        self.setVisible(True)
        self.mode = self.modeXYPosition
        self.setPos(x, y)

    def paint(self, painter, option, widget=None):

        painter.save()
        painter.setTransform(self.scene().data2scene * painter.transform())

        painter.setPen(self.penDotted)

        if self.mode == self.modeXPosition:
            painter.drawLine(QPointF(self.x + 0.5, 0), QPointF(self.x + 0.5, self._height))
        elif self.mode == self.modeYPosition:
            painter.drawLine(QPointF(0, self.y), QPointF(self.width, self.y))
        else:
            painter.drawLine(
                QPointF(self.x - 0.5 * self.brushSize - 3, self.y), QPointF(self.x - 0.5 * self.brushSize, self.y)
            )
            painter.drawLine(
                QPointF(self.x + 0.5 * self.brushSize, self.y), QPointF(self.x + 0.5 * self.brushSize + 3, self.y)
            )

            painter.drawLine(
                QPointF(self.x, self.y - 0.5 * self.brushSize - 3), QPointF(self.x, self.y - 0.5 * self.brushSize)
            )
            painter.drawLine(
                QPointF(self.x, self.y + 0.5 * self.brushSize), QPointF(self.x, self.y + 0.5 * self.brushSize + 3)
            )

            painter.setPen(self.penSolid)
            painter.drawEllipse(QPointF(self.x, self.y), 0.5 * self.brushSize, 0.5 * self.brushSize)

        painter.restore()

    def setPos(self, x, y):
        self.x = x
        self.y = y
        self.update()

    def setBrushSize(self, size):
        self.brushSize = size
        self.update()

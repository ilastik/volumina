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

from PyQt4.QtCore import Qt, QRectF, QPointF
from PyQt4.QtGui import QGraphicsItem, QPen

#*******************************************************************************
# S l i c e I n t e r s e c t i o n M a r k e r                                *
#*******************************************************************************

class SliceIntersectionMarker(QGraphicsItem) :
    """
    Marks a line within a ImageView2D/ImageScene2D
    """
    thick_width = 2
    thin_width = 0.5
    _diameter = 4

    def boundingRect(self):
        return self.scene().data2scene.mapRect(QRectF(0,0, self._width, self._height));

    def __init__(self, scene):
        QGraphicsItem.__init__(self, scene=scene)

        self._width = 0
        self._height = 0

        self.thick_penX = QPen(Qt.red, self.thick_width)
        self.thick_penX.setCosmetic(True)

        self.thick_penY = QPen(Qt.green, self.thick_width)
        self.thick_penY.setCosmetic(True)

        self.thin_penX = QPen(Qt.red, self.thin_width)
        self.thin_penX.setCosmetic(True)

        self.thin_penY = QPen(Qt.green, self.thin_width)
        self.thin_penY.setCosmetic(True)

        self.x = 0
        self.y = 0

        self.isVisible = True

    #be careful: QGraphicsItem has a shape() method, which
    #we cannot override, therefore we choose this name
    @property
    def dataShape(self):
        return (self._width, self._height)
    @dataShape.setter
    def dataShape(self, shape2D):
        self._width = shape2D[0]
        self._height = shape2D[1]

    def setPosition(self, x, y):
        self.x = x
        self.y = y
        self.update()


    def _get_diameter(self):
        return self._diameter

    def _set_diameter(self, value):
        self._diameter = value

    diameter = property(_get_diameter, _set_diameter)

    def setPositionX(self, x):
        self.setPosition(x, self.y)

    def setPositionY(self, y):
        self.setPosition(self.x, y)

    def setColor(self, colorX, colorY):
        self.thick_penX = QPen(colorX, self.thick_width)
        self.thick_penX.setCosmetic(True)
        self.thick_penY = QPen(colorY, self.thick_width)
        self.thick_penY.setCosmetic(True)

        self.thin_penX = QPen(colorX, self.thin_width)
        self.thin_penX.setCosmetic(True)
        self.thin_penY = QPen(colorY, self.thin_width)
        self.thin_penY.setCosmetic(True)

        self.update()

    def setVisibility(self, state):
        if state == True:
            self.isVisible = True
        else:
            self.isVisible = False
        self.update()

    def paint(self, painter, option, widget=None):
        if self.isVisible:
            painter.save()
            t = painter.transform()
            painter.setTransform(self.scene().data2scene  * t )

            painter.setPen(self.thin_penY)
            painter.drawLine(QPointF(0.0,self.y), QPointF(self._width, self.y))

            painter.setPen(self.thin_penX)
            painter.drawLine(QPointF(self.x, 0), QPointF(self.x, self._height))

            radius = self.diameter / 2 + 1

            painter.setPen(self.thick_penY)
            painter.drawLine(QPointF(0.0, self.y), QPointF(self.x - radius, self.y))
            painter.drawLine(QPointF(self.x + radius, self.y), QPointF(self._width, self.y))

            painter.setPen(self.thick_penX)
            painter.drawLine(QPointF(self.x, 0), QPointF(self.x, self.y - radius))
            painter.drawLine(QPointF(self.x, self.y + radius), QPointF(self.x, self._height))


            painter.restore()

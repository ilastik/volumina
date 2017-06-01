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
#!/usr/bin/env python
from __future__ import division
from PyQt4.QtCore import pyqtSignal, QObject, Qt, QSize, QPointF, QRectF, \
                         QRect, QPoint, QSizeF
from PyQt4.QtGui  import QPen, QGraphicsScene, QColor, \
                         QImage, QPainter, QGraphicsLineItem, QBrush

import numpy, math
import qimage2ndarray

#*******************************************************************************
# B r u s h i n g M o d e l                                                    *
#*******************************************************************************

class BrushingModel(QObject):
    brushSizeChanged     = pyqtSignal(int)
    brushColorChanged    = pyqtSignal(QColor)
    brushStrokeAvailable = pyqtSignal(QPointF, object)
    drawnNumberChanged   = pyqtSignal(int)

    minBrushSize       = 1
    maxBrushSize       = 61
    defaultBrushSize   = 3
    defaultDrawnNumber = 1
    defaultColor       = Qt.white
    erasingColor       = Qt.black
    erasingNumber      = 100

    def __init__(self, parent=None):
        QObject.__init__(self, parent=parent)
        self.sliceRect = None
        self.bb    = QRect() #bounding box enclosing the drawing
        self.brushSize = self.defaultBrushSize
        self.drawColor = self.defaultColor
        self._temp_color = None
        self._temp_number = None
        self.drawnNumber = self.defaultDrawnNumber

        self.pos = None
        self.erasing = False
        self._hasMoved = False

        self.drawOnto = None

        #an empty scene, where we add all drawn line segments
        #a QGraphicsLineItem, and which we can use to then
        #render to an image
        self.scene = QGraphicsScene()

    def toggleErase(self):
        self.erasing = not(self.erasing)
        if self.erasing:
            self.setErasing()
        else:
            self.disableErasing()

    def setErasing(self):
        self.erasing = True
        self._temp_color = self.drawColor
        self._temp_number = self.drawnNumber
        self.setBrushColor(self.erasingColor)
        self.brushColorChanged.emit(self.erasingColor)
        self.setDrawnNumber(self.erasingNumber)

    def disableErasing(self):
        self.erasing = False
        self.setBrushColor(self._temp_color)
        self.brushColorChanged.emit(self.drawColor)
        self.setDrawnNumber(self._temp_number)

    def setBrushSize(self, size):
        self.brushSize = size
        self.brushSizeChanged.emit(self.brushSize)

    def setDrawnNumber(self, num):
        self.drawnNumber = num
        self.drawnNumberChanged.emit(num)

    def getBrushSize(self):
        return self.brushSize

    def brushSmaller(self):
        b = self.brushSize
        if b > self.minBrushSize:
            self.setBrushSize(b-1)

    def brushBigger(self):
        b = self.brushSize
        if self.brushSize < self.maxBrushSize:
            self.setBrushSize(b+1)

    def setBrushColor(self, color):
        self.drawColor = QColor(color)
        self.brushColorChanged.emit(self.drawColor)

    def beginDrawing(self, pos, sliceRect):
        '''

        pos -- QPointF-like
        '''
        self.sliceRect = sliceRect
        self.scene.clear()
        self.bb = QRect()
        self.pos = QPointF(pos.x(), pos.y())
        self._hasMoved = False

    def endDrawing(self, pos):
        has_moved = self._hasMoved # _hasMoved will change after calling moveTo
        if has_moved:
            self.moveTo(pos)
        else:
            assert(self.pos == pos)
            self.moveTo(QPointF(pos.x()+0.0001, pos.y()+0.0001)) # move a little

        # Qt seems to use strange rules for determining which pixels to set when rendering a brush stroke to a QImage.
        # We seem to get better results if we do the following:
        # 1) Slightly offset the source window because apparently there is a small shift in the data
        # 2) Render the scene to an image that is MUCH larger than the scene resolution (4x by 4x)
        # 3) Downsample each 4x4 patch from the large image back to a single pixel in the final image,
        #     applying some threshold to determine if the final pixel is on or off. 

        tempi = QImage(QSize(4*self.bb.width(), 4*self.bb.height()), QImage.Format_ARGB32_Premultiplied) #TODO: format
        tempi.fill(0)
        painter = QPainter(tempi)
        # Offset the source window.  At first I thought the right offset was 0.5, because 
        #  that would seem to make sure points are rounded to pixel CENTERS, but 
        #  experimentation indicates that 0.25 is slightly better for some reason...
        source_rect = QRectF( QPointF(self.bb.x()+0.25, self.bb.y()+0.25), 
                              QSizeF(self.bb.width(), self.bb.height()) )
        target_rect = QRectF( QPointF(0,0),
                             QSizeF(4*self.bb.width(), 4*self.bb.height()) )
        self.scene.render(painter, target=target_rect, source=source_rect)
        painter.end()

        # Now downsample: convert each 4x4 patch into a single pixel by summing and dividing
        ndarr = qimage2ndarray.rgb_view(tempi)[:,:,0].astype(int)
        ndarr = ndarr.reshape( (ndarr.shape[0],) + (ndarr.shape[1]//4,) + (4,) )
        ndarr = ndarr.sum(axis=-1)
        ndarr = ndarr.transpose()
        ndarr = ndarr.reshape( (ndarr.shape[0],) + (ndarr.shape[1]//4,) + (4,) )
        ndarr = ndarr.sum(axis=-1)
        ndarr = ndarr.transpose()
        ndarr //= 4*4

        downsample_threshold = (7./16)*255
        labels = numpy.where(ndarr>=downsample_threshold, numpy.uint8(self.drawnNumber), numpy.uint8(0))
        labels = labels.swapaxes(0,1)
        assert labels.shape[0] == self.bb.width()
        assert labels.shape[1] == self.bb.height()

        ##
        ## ensure that at least one pixel is label when the brush size is 1
        ##
        ## this happens when the user just clicked without moving
        ## in that case the lineitem will be so tiny, that it won't be rendered
        ## into a single pixel by the code above
        if not has_moved and self.brushSize <= 1 and numpy.count_nonzero(labels) == 0:
            labels[labels.shape[0]//2, labels.shape[1]//2] = self.drawnNumber

        self.brushStrokeAvailable.emit(QPointF(self.bb.x(), self.bb.y()), labels)

    def dumpDraw(self, pos):
        res = self.endDrawing(pos)
        self.beginDrawing(pos, self.sliceRect)
        return res

    def moveTo(self, pos):
        #data coordinates
        oldX, oldY = self.pos.x(), self.pos.y()
        x,y = pos.x(), pos.y()

        line = QGraphicsLineItem(oldX, oldY, x, y)
        line.setPen(QPen( QBrush(Qt.white), self.brushSize, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.scene.addItem(line)
        self._hasMoved = True

        #update bounding Box
        if not self.bb.isValid():
            self.bb = QRect(QPoint(oldX,oldY), QSize(1,1))
        #grow bounding box
        self.bb.setLeft(  min(self.bb.left(),   max(0,                   x-self.brushSize//2-1) ) )
        self.bb.setRight( max(self.bb.right(),  min(self.sliceRect[0]-1, x+self.brushSize//2+1) ) )
        self.bb.setTop(   min(self.bb.top(),    max(0,                   y-self.brushSize//2-1) ) )
        self.bb.setBottom(max(self.bb.bottom(), min(self.sliceRect[1]-1, y+self.brushSize//2+1) ) )

        #update/move position
        self.pos = pos

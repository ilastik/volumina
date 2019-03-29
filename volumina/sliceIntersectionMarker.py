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
from past.utils import old_div
from PyQt5.QtCore import Qt, QRectF, QPointF
from PyQt5.QtWidgets import QGraphicsItem, QApplication
from PyQt5.QtGui import QPen, QCursor

# *******************************************************************************
# S l i c e I n t e r s e c t i o n M a r k e r                                *
# *******************************************************************************


class SliceIntersectionMarker(QGraphicsItem):
    """
    Marks a line within a ImageView2D/ImageScene2D.
    Used within a VolumeEditor to show the current slicing position.
    """

    thick_width = 2
    thin_width = 0.5
    _diameter = 4

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'
        # This 'item' is merely a parent node for child items
        return QRectF()

    def __init__(self, axis, posModel):
        QGraphicsItem.__init__(self)
        self.setFlag(QGraphicsItem.ItemHasNoContents)

        self.axis = axis
        self.posModel = posModel

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

        # These child items do most of the work.
        self._horizontal_marker = SliceMarkerLine(self, "horizontal")
        self._vertical_marker = SliceMarkerLine(self, "vertical")

    # be careful: QGraphicsItem has a shape() method, which
    # we cannot override, therefore we choose this name
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
        self._horizontal_marker.prepareGeometryChange()
        self._vertical_marker.prepareGeometryChange()
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

    def paint(self, painter, option, widget=None):
        pass  # No content.

    def paint_line(self, painter, direction):
        """
        Paint a single line of the slice intersection marker.
        """
        if not self.isVisible:
            return

        painter.save()
        t = painter.transform()
        painter.setTransform(self.scene().data2scene * t)

        # Thin line directly over intersection
        if direction == "horizontal":
            painter.setPen(self.thin_penY)
            painter.drawLine(QPointF(0.0, self.y), QPointF(self._width, self.y))
        else:
            painter.setPen(self.thin_penX)
            painter.drawLine(QPointF(self.x, 0), QPointF(self.x, self._height))

        radius = old_div(self.diameter, 2) + 1

        # Thick line elsewhere
        if direction == "horizontal":
            painter.setPen(self.thick_penY)
            painter.drawLine(QPointF(0.0, self.y), QPointF(self.x - radius, self.y))
            painter.drawLine(QPointF(self.x + radius, self.y), QPointF(self._width, self.y))
        else:
            painter.setPen(self.thick_penX)
            painter.drawLine(QPointF(self.x, 0), QPointF(self.x, self.y - radius))
            painter.drawLine(QPointF(self.x, self.y + radius), QPointF(self.x, self._height))

        painter.restore()


class SliceMarkerLine(QGraphicsItem):
    """
    QGraphicsItem for a single line (horizontal or vertical) of the slice intersection.
    Must be a child of SliceIntersectionMarker.  It can be dragged to change the slicing position.
    """

    def __init__(self, parent, direction):
        assert isinstance(parent, SliceIntersectionMarker)
        assert direction in ("horizontal", "vertical")

        self._parent = parent
        self._direction = direction
        QGraphicsItem.__init__(self, parent)
        self.setAcceptHoverEvents(True)

    def boundingRect(self):
        parent = self._parent
        x, y = parent.x, parent.y
        width, height = parent._width, parent._height
        pen_width_in_view = parent.thick_width

        # This is a little tricky.  The line is always drawn with the same
        #  absolute thickness, REGARDLESS of the view's transform.
        # That is, the line does not appear to be part of the data,
        #  so it doesn't get thinner as we zoom out.  (See QPen.setCosmetic)
        # To compensate for this when determining the line's bounding box within the scene,
        #  we need to know the transform used by the view that is showing this scene.
        # If we didn't do this, our bounding rect would be off by a few pixels.
        # That probably wouldn't be a big deal.
        view = self.scene().views()[0]
        inverted_transform, has_inverse = view.transform().inverted()
        transformed_pen_thickness = inverted_transform.map(QPointF(pen_width_in_view, pen_width_in_view))
        pen_width_in_scene = transformed_pen_thickness.x()

        if self._direction == "horizontal":
            return self.scene().data2scene.mapRect(
                QRectF(0, y - old_div(pen_width_in_scene, 2.0), width, pen_width_in_scene)
            )
        else:
            return self.scene().data2scene.mapRect(
                QRectF(x - old_div(pen_width_in_scene, 2.0), 0, pen_width_in_scene, height)
            )

    def paint(self, painter, option, widget=None):
        # Delegate painting to our parent, since it keeps track of line thickness, etc.
        self._parent.paint_line(painter, self._direction)

    def hoverEnterEvent(self, event):
        # Change the cursor to indicate the line is draggable
        cursor = QCursor(Qt.OpenHandCursor)
        QApplication.instance().setOverrideCursor(cursor)
        self.scene().allow_brushing = False

    def hoverLeaveEvent(self, event):
        # Restore the cursor to its previous state.
        QApplication.instance().restoreOverrideCursor()
        self.scene().allow_brushing = True

    def mouseMoveEvent(self, event):
        new_pos = self.scene().data2scene.map(event.scenePos())
        width, height = self._parent.dataShape

        x = int(new_pos.x() + 0.5)
        y = int(new_pos.y() + 0.5)

        if self._direction == "horizontal":
            # Horizontal line can only move up/down
            x = self._parent.x

            # Clip the Y position to the image boundary
            y = max(0, y)
            y = min(height - 1, y)
        else:
            # Vertical line can only move left/right
            y = self._parent.y

            # Clip the X position to the image boundary
            x = max(0, x)
            x = min(width - 1, x)

        old_slicing_pos = self._parent.posModel.slicingPos
        slicing_pos = [x, y]
        slicing_pos.insert(self._parent.axis, old_slicing_pos[self._parent.axis])
        self._parent.posModel.slicingPos = slicing_pos

    # Note: We must override these or else the default implementation
    #  prevents the mouseMoveEvent() override from working.
    # If we didn't have actual work to do in these functions,
    #  we'd just use empty implementations:
    #
    # def mousePressEvent(self, event): pass
    # def mouseReleaseEvent(self, event): pass

    def mousePressEvent(self, event):
        # Change the cursor to indicate "currently dragging"
        cursor = QCursor(Qt.ClosedHandCursor)
        QApplication.instance().setOverrideCursor(cursor)

    def mouseReleaseEvent(self, event):
        # Restore the cursor to its previous state.
        QApplication.instance().restoreOverrideCursor()

from __future__ import division

# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers
from builtins import range
from past.utils import old_div
import copy
import contextlib
from qtpy.QtCore import Signal, Qt, QObject, QRectF, QPointF
from qtpy.QtGui import QPen, QCursor, QBrush, QColor
from qtpy.QtWidgets import QGraphicsItem, QApplication


class CropExtentsModel(QObject):
    changed = Signal(object)  # list of start/stop coords indexed by axis
    # Note: There is no required ordering for start/stop
    #       (i.e. start could be greater than stop)
    colorChanged = Signal(QColor)
    editableChanged = Signal(bool)
    mouseRelease = Signal()

    @property
    def editable(self):
        return self._editable

    @editable.setter
    def editable(self, flag):
        self._editable = flag

    def setEditable(self, flag):
        self._editable = flag
        self.editableChanged.emit(flag)

    def __init__(self, parent):
        super(CropExtentsModel, self).__init__(parent)
        self._crop_extents = [[None, None], [None, None], [None, None]]
        self._crop_times = [None, None]
        self._scroll_time_outside_crop = False

        self._editable = True

        self.editableChanged.connect(self.onEditableChanged)

    def set_scroll_time_outside_crop(self, flag):
        self._scroll_time_outside_crop = flag
        self.changed.emit(self)

    def get_scroll_time_outside_crop(self):
        return self._scroll_time_outside_crop

    def onEditableChanged(self, flag):
        self._editable = flag

    def get_roi_3d(self):
        """
        Returns the xyz roi: [ (x1,y1,z1), (x2,y2,z2) ]
        """
        ordered_extents = []
        for start, stop in self._crop_extents:
            if start is None or stop is None or start < stop:
                ordered_extents.append((start, stop))
            else:
                ordered_extents.append((stop, start))

        # [(x1,x2), (y1,y2), (z1,z2)] -> [(x1,y1,z1), (x2,y2,z2)]
        roi = list(zip(*ordered_extents))
        return roi

    def get_roi_t(self):
        """
        Returns the t roi: [ t1, t2 ]
        """
        return self._crop_times

    def set_roi_3d(self, roi):
        # Convenience function.
        # Set the extents as a roi
        self.set_crop_extents(list(zip(*roi)))

    def set_roi_t(self, timeRange):
        # Convenience function.
        # Set the crop times
        self.set_crop_times(timeRange)

    def set_volume_shape_3d(self, shape3d):
        # Since the volume size changed,
        # reset the crop extents to a reasonable default.
        for i in range(3):
            self._crop_extents[i][0] = 0
            self._crop_extents[i][1] = shape3d[i]
        self.changed.emit(self)

    def set_time_shape(self, time):
        # Since the volume size changed,
        # reset the crop times to a reasonable default.
        self._crop_times = [0, time]
        self.changed.emit(self)

    def set_volume_shape_3d_cropped(self, starts, stops):
        # Since the volume size changed,
        # reset the crop extents to a reasonable default.
        for i in range(3):
            self._crop_extents[i][0] = starts[i]
            self._crop_extents[i][1] = stops[i]

        self.changed.emit(self)

    def set_time_shape_cropped(self, startT, stopT):
        # Since the volume size changed,
        # reset the crop times to a reasonable default.
        self._crop_times[0] = startT
        self._crop_times[1] = stopT

        self.changed.emit(self)

    def crop_extents(self):
        return copy.deepcopy(self._crop_extents)

    def crop_times(self):
        return copy.deepcopy(self._crop_times)

    def crop_scroll_time_outside_crop(self):
        return copy.deepcopy(self._crop_scroll_time_outside_crop)

    def set_crop_extents(self, crop_extents):
        assert len(crop_extents) == 3
        for e in crop_extents:
            assert len(e) == 2
        self._crop_extents = list(map(list, crop_extents))  # Ensure lists, not tuples
        self.changed.emit(self)

    def set_crop_times(self, crop_times):
        assert len(crop_times) == 2
        self._crop_times = [crop_times[0], crop_times[1]]
        self.changed.emit(self)

    def cropZero(self):
        if self._crop_extents == None:
            return True

        flag = True
        for c in self._crop_extents:
            flag = flag and c[0] == 0 and c[1] == 0

        return flag


class CroppingMarkers(QGraphicsItem):
    PEN_THICKNESS = 1

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'
        # This 'item' is merely a parent node for child items
        return QRectF()

    def __init__(self, axis, crop_extents_model, editable=True):

        self._cropColor = Qt.white

        QGraphicsItem.__init__(self)
        self.setFlag(QGraphicsItem.ItemHasNoContents)
        self.setAcceptHoverEvents(True)
        self.axis = axis
        self.crop_extents_model = crop_extents_model

        self._width = 0
        self._height = 0

        # Add shading item first so crop lines are drawn on top.
        self._shading_item = ExcludedRegionShading(self, self.crop_extents_model)

        self._horizontal0 = CropLine(self, "horizontal", 0)
        self._horizontal1 = CropLine(self, "horizontal", 1)
        self._vertical0 = CropLine(self, "vertical", 0)
        self._vertical1 = CropLine(self, "vertical", 1)

        self.crop_extents_model.changed.connect(self.onExtentsChanged)
        self.crop_extents_model.colorChanged.connect(self.onColorChanged)

        # keeping track which line started mouse move
        self._mouseMoveStartH = -1
        self._mouseMoveStartV = -1
        self._fractionOfDistance = 1

    # be careful: QGraphicsItem has a shape() method, which
    # we cannot override, therefore we choose this name
    @property
    def dataShape(self):
        return (self._width, self._height)

    @dataShape.setter
    def dataShape(self, shape2D):
        self._width = shape2D[0]
        self._height = shape2D[1]

    @property
    def cropColor(self):
        return self._cropColor

    @cropColor.setter
    def cropColor(self, color):
        self._cropColor = color

    @property
    def mouseMoveStartH(self):
        return self._mouseMoveStartH

    @mouseMoveStartH.setter
    def mouseMoveStartH(self, h):
        self._mouseMoveStartH = h

    @property
    def mouseMoveStartV(self):
        return self._mouseMoveStartV

    @mouseMoveStartV.setter
    def mouseMoveStartV(self, v):
        self._mouseMoveStartV = v

    def onExtentsChanged(self, crop_extents_model):
        crop_extents = crop_extents_model.crop_extents()
        crop_extents.pop(self.axis)

        # By default, place cropping lines at 25% and 75%
        if not (None in crop_extents[0] or None in crop_extents[1]):
            self._vertical0.position = crop_extents[0][0]
            self._vertical1.position = crop_extents[0][1]
            self._horizontal0.position = crop_extents[1][0]
            self._horizontal1.position = crop_extents[1][1]

            self.prepareGeometryChange()

    def onColorChanged(self, color):
        self._cropColor = color
        self.prepareGeometryChange()
        self.update()

    def onCropLineMoved(self, direction, index, new_position):
        # Which 3D axis does this crop line correspond to?
        # (Depends on which orthogonal view we belong to.)

        axislookup = [[None, "v", "h"], ["v", None, "h"], ["v", "h", None]]

        axis_3d = axislookup[self.axis].index(direction[0])
        crop_extents_3d = self.crop_extents_model.crop_extents()

        crop_extents_3d[axis_3d][index] = int(new_position)
        self.crop_extents_model.set_crop_extents(crop_extents_3d)

    def mousePressEvent(self, event):
        """
        Moving a corner or line, in this priority order.
        The line(s) indices that started the move are stored in:
        self.mouseMoveStartH and
        self.mouseMoveStartV
        """
        if self.crop_extents_model._editable:
            position = self.scene().data2scene.map(event.scenePos())
            width, height = self.dataShape
            posH0 = self._horizontal0.position
            posH1 = self._horizontal1.position
            posV0 = self._vertical0.position
            posV1 = self._vertical1.position

            positionV = int(position.x() + 0.5)
            positionV = max(0, positionV)
            positionV = min(width, positionV)

            positionH = int(position.y() + 0.5)
            positionH = max(0, positionH)
            positionH = min(height, positionH)

            distV0 = abs(positionV - posV0)
            distV1 = abs(positionV - posV1)
            distH0 = abs(positionH - posH0)
            distH1 = abs(positionH - posH1)
            distV = old_div(abs(posV1 - posV0), self._fractionOfDistance)
            distH = old_div(abs(posH1 - posH0), self._fractionOfDistance)
            dist = distV * distV + distH * distH

            # corners
            if distV0 * distV0 + distH0 * distH0 < dist:
                self.onCropLineMoved("vertical", 0, positionV)
                self.onCropLineMoved("horizontal", 0, positionH)
                self.mouseMoveStartH = 0
                self.mouseMoveStartCornerV = 0
            elif distV1 * distV1 + distH1 * distH1 < dist:
                self.onCropLineMoved("vertical", 1, positionV)
                self.onCropLineMoved("horizontal", 1, positionH)
                self.mouseMoveStartH = 1
                self.mouseMoveStartCornerV = 1
            elif distV0 * distV0 + distH1 * distH1 < dist:
                self.onCropLineMoved("vertical", 0, positionV)
                self.onCropLineMoved("horizontal", 1, positionH)
                self.mouseMoveStartH = 1
                self.mouseMoveStartCornerV = 0
            elif distV1 * distV1 + distH0 * distH0 < dist:
                self.onCropLineMoved("vertical", 1, positionV)
                self.onCropLineMoved("horizontal", 0, positionH)
                self.mouseMoveStartH = 0
                self.mouseMoveStartCornerV = 1

            # lines
            elif distH0 < distH:
                self.onCropLineMoved("horizontal", 0, positionH)
                self.mouseMoveStartH = 0
            elif distH1 < distH:
                self.onCropLineMoved("horizontal", 1, positionH)
                self.mouseMoveStartH = 1
            elif distV0 < distV:
                self.onCropLineMoved("vertical", 0, positionV)
                self.mouseMoveStartV = 0
            elif distV1 < distV:
                self.onCropLineMoved("vertical", 1, positionV)
                self.mouseMoveStartV = 1

            # Change the cursor to indicate "currently dragging"
            cursor = QCursor(Qt.ClosedHandCursor)
            QApplication.instance().setOverrideCursor(cursor)

    def mouseReleaseEvent(self, event):

        if self.crop_extents_model._editable:
            self.mouseMoveStartH = -1
            self.mouseMoveStartV = -1

            # Restore the cursor to its previous state.
            QApplication.instance().restoreOverrideCursor()

    def mouseMoveEvent(self, event):
        """
        Moving a corner or line.
        The line(s) indices that started the move are stored in:
            self.mouseMoveStartH and
            self.mouseMoveStartV
        """

        if self.crop_extents_model._editable:
            position = self.scene().data2scene.map(event.scenePos())
            width, height = self.dataShape

            positionV = int(position.x() + 0.5)
            positionV = max(0, positionV)
            positionV = min(width, positionV)

            positionH = int(position.y() + 0.5)
            positionH = max(0, positionH)
            positionH = min(height, positionH)

            if self.mouseMoveStartH == 0 and self.mouseMoveStartV == 0:
                self.onCropLineMoved("horizontal", 0, positionH)
                self.onCropLineMoved("vertical", 0, positionV)
            elif self.mouseMoveStartH == 1 and self.mouseMoveStartV == 0:
                self.onCropLineMoved("horizontal", 1, positionH)
                self.onCropLineMoved("vertical", 0, positionV)
            elif self.mouseMoveStartH == 0 and self.mouseMoveStartV == 1:
                self.onCropLineMoved("horizontal", 0, positionH)
                self.onCropLineMoved("vertical", 1, positionV)
            elif self.mouseMoveStartH == 1 and self.mouseMoveStartV == 1:
                self.onCropLineMoved("horizontal", 1, positionH)
                self.onCropLineMoved("vertical", 1, positionV)

            elif self.mouseMoveStartH == -1 or self.mouseMoveStartV == -1:
                if self.mouseMoveStartH == 0:
                    self.onCropLineMoved("horizontal", 0, positionH)
                elif self.mouseMoveStartH == 1:
                    self.onCropLineMoved("horizontal", 1, positionH)
                elif self.mouseMoveStartV == 0:
                    self.onCropLineMoved("vertical", 0, positionV)
                elif self.mouseMoveStartV == 1:
                    self.onCropLineMoved("vertical", 1, positionV)


@contextlib.contextmanager
def painter_context(painter):
    try:
        painter.save()
        yield
    finally:
        painter.restore()


class ExcludedRegionShading(QGraphicsItem):
    def __init__(self, parent, crop_extents_model):
        self._parent = parent
        self._crop_extents_model = crop_extents_model
        self._paint_full_frame = False

        super(ExcludedRegionShading, self).__init__(parent)
        crop_extents_model.changed.connect(self.prepareGeometryChange)

    def set_paint_full_frame(self, flag):
        self._paint_full_frame = flag

    def boundingRect(self):
        width, height = self._parent.dataShape
        return QRectF(0.0, 0.0, width, height)

    def paint(self, painter, option, widget=None):
        crop_extents_3d = self._crop_extents_model.crop_extents()
        crop_extents = copy.deepcopy(crop_extents_3d)
        crop_extents.pop(self._parent.axis)

        width, height = self._parent.dataShape
        (left, right), (top, bottom) = crop_extents

        if None in (left, right, top, bottom, width, height):
            # Don't paint if the crop settings aren't initialized yet.
            return

        # Black brush, 50% alpha
        brush = QBrush(QColor(0, 0, 0, 128))

        rects = [(0.0, 0.0, left, top), (0.0, top, left, bottom), (0.0, bottom, left, height), (left, 0.0, right, top)]

        if self._crop_extents_model.get_scroll_time_outside_crop() and self._paint_full_frame:
            rects += [(left, top, right, bottom)]  # middle.

        rects += [
            (left, bottom, right, height),
            (right, 0.0, width, top),
            (right, top, width, bottom),
            (right, bottom, width, height),
        ]

        with painter_context(painter):
            t = painter.transform()
            painter.setTransform(self.scene().data2scene * t)

            for rect_points in rects:
                x1, y1, x2, y2 = rect_points
                p1 = QPointF(x1, y1)
                p2 = QPointF(x2, y2)
                painter.fillRect(QRectF(p1, p2), brush)


class CropLine(QGraphicsItem):
    """
    QGraphicsItem for a single line (horizontal or vertical) of the slice intersection.
    Must be a child of SliceIntersectionMarker.  It can be dragged to change the slicing position.
    """

    def __init__(self, parent, direction, index):
        assert isinstance(parent, CroppingMarkers)
        assert direction in ("horizontal", "vertical")

        self._parent = parent
        self._direction = direction
        self._index = index
        QGraphicsItem.__init__(self, parent)
        self.setAcceptHoverEvents(True)
        self._position = 0
        self._line_thickness = 1

        # keeping track which line started mouse move
        self._mouseMoveStartH = -1
        self._mouseMoveStartV = -1

    @property
    def mouseMoveStartH(self):
        return self._mouseMoveStartH

    @mouseMoveStartH.setter
    def mouseMoveStartH(self, h):
        self._mouseMoveStartH = h

    @property
    def mouseMoveStartV(self):
        return self._mouseMoveStartV

    @mouseMoveStartV.setter
    def mouseMoveStartV(self, v):
        self._mouseMoveStartV = v

    @property
    def position(self):
        return self._position

    @position.setter
    def position(self, new_position):
        self._position = new_position
        self.setToolTip("{}".format(int(new_position)))
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        parent = self._parent
        width, height = parent._width, parent._height
        pen_width_in_view = parent.PEN_THICKNESS
        pen_width_in_scene = determine_pen_thickness_in_scene(self.scene(), pen_width_in_view)

        # Return a bounding rect that's a little larger than the actual line.
        # This makes it easier to grab with the mouse.
        line_thickness = 3 * pen_width_in_scene
        self._line_thickness = 4 * line_thickness

        if self._direction == "horizontal":
            return self.scene().data2scene.mapRect(
                QRectF(0, self._position - old_div(line_thickness, 2.0), width, line_thickness)
            )
        else:
            return self.scene().data2scene.mapRect(
                QRectF(self._position - old_div(line_thickness, 2.0), 0, line_thickness, height)
            )

    def paint(self, painter, option, widget=None):
        """
        Paint a single line of the slice intersection marker.
        """
        width = self._parent._width
        height = self._parent._height
        thickness = self._parent.PEN_THICKNESS

        # Our pen thickness is consistent across zoom levels because the pen is "cosmetic"
        # However, that doesn't ensure a consistent-size dash pattern.
        # Determine the inverse scaling factor from scene to view to set a consistent dash pattern at all scales.
        view = self.scene().views()[0]
        inverted_transform, has_inverse = view.transform().inverted()
        dash_length = old_div(4, inverted_transform.m11())
        dash_length = max(0.5, dash_length)

        # Draw the line with two pens to get a black-and-white dashed line.
        # pen_white = QPen( Qt.white, thickness )
        pen_white = QPen(self._parent._cropColor, thickness)
        pen_white.setDashPattern([dash_length, dash_length])
        pen_white.setCosmetic(True)

        pen_black = QPen(Qt.black, thickness)
        pen_black.setDashPattern([dash_length, dash_length])
        pen_black.setCosmetic(True)
        pen_black.setDashOffset(dash_length)

        with painter_context(painter):
            t = painter.transform()
            painter.setTransform(self.scene().data2scene * t)

            # Draw the line with two pens to get a black-and-white dashed line.
            for pen in [pen_white, pen_black]:
                painter.setPen(pen)

                if self._direction == "horizontal":
                    painter.drawLine(QPointF(0.0, self.position), QPointF(width, self.position))
                else:
                    painter.drawLine(QPointF(self.position, 0.0), QPointF(self.position, height))

    def hoverEnterEvent(self, event):
        if self._parent.crop_extents_model._editable:
            # Change the cursor to indicate the line is draggable
            cursor = QCursor(Qt.OpenHandCursor)
            QApplication.instance().setOverrideCursor(cursor)

    def hoverLeaveEvent(self, event):

        if self._parent.crop_extents_model._editable:
            # Restore the cursor to its previous state.
            QApplication.instance().restoreOverrideCursor()

    def mouseMoveEvent(self, event):
        """
        Moving a line.
        """
        if self._parent.crop_extents_model._editable:
            new_pos = self.scene().data2scene.map(event.scenePos())
            width, height = self._parent.dataShape

            posH0 = self._parent._horizontal0.position
            posH1 = self._parent._horizontal1.position
            posV0 = self._parent._vertical0.position
            posV1 = self._parent._vertical1.position

            positionH = int(new_pos.y() + 0.5)
            positionH = max(0, positionH)
            positionH = min(height, positionH)

            positionV = int(new_pos.x() + 0.5)
            positionV = max(0, positionV)
            positionV = min(width, positionV)

            if posH0 == 0 and self._index == 1 and positionH < 1:
                positionH = 1
            if posV0 == 0 and self._index == 1 and positionV < 1:
                positionV = 1
            if posH1 == height and self._index == 0 and positionH > height - 1:
                positionH = height - 1
            if posV1 == width and self._index == 0 and positionV > width - 1:
                positionV = width - 1

            if self._direction == "horizontal" and self.mouseMoveStartV == 0:
                self._parent.onCropLineMoved(self._direction, self._index, positionH)
                self._parent.onCropLineMoved("vertical", 0, positionV)
            elif self._direction == "horizontal" and self.mouseMoveStartV == 1:
                self._parent.onCropLineMoved(self._direction, self._index, positionH)
                self._parent.onCropLineMoved("vertical", 1, positionV)
            elif self._direction == "vertical" and self.mouseMoveStartH == 0:
                self._parent.onCropLineMoved(self._direction, self._index, positionV)
                self._parent.onCropLineMoved("horizontal", 0, positionH)
            elif self._direction == "vertical" and self.mouseMoveStartH == 1:
                self._parent.onCropLineMoved(self._direction, self._index, positionV)
                self._parent.onCropLineMoved("horizontal", 1, positionH)
            elif self._direction == "horizontal":
                self._parent.onCropLineMoved(self._direction, self._index, positionH)
            elif self._direction == "vertical":
                self._parent.onCropLineMoved(self._direction, self._index, positionV)

    # Note: We must override these or else the default implementation
    #  prevents the mouseMoveEvent() override from working.
    # If we didn't have actual work to do in these functions,
    #  we'd just use empty implementations:
    #
    # def mousePressEvent(self, event): pass
    # def mouseReleaseEvent(self, event): pass

    def mousePressEvent(self, event):
        """
        Selecting a line.
        """

        if self._parent.crop_extents_model._editable:
            new_pos = self.scene().data2scene.map(event.scenePos())
            width, height = self._parent.dataShape

            positionH = int(new_pos.y() + 0.5)
            positionH = max(0, positionH)
            positionH = min(height, positionH)

            positionV = int(new_pos.x() + 0.5)
            positionV = max(0, positionV)
            positionV = min(width, positionV)

            if (
                self._direction == "horizontal"
                and abs(self._parent._vertical0.position - positionV) <= self._line_thickness
            ):
                self.mouseMoveStartH = self._index
                self.mouseMoveStartV = 0
            elif (
                self._direction == "horizontal"
                and abs(self._parent._vertical1.position - positionV) <= self._line_thickness
            ):
                self.mouseMoveStartH = self._index
                self.mouseMoveStartV = 1
            elif (
                self._direction == "vertical"
                and abs(self._parent._horizontal0.position - positionH) <= self._line_thickness
            ):
                self.mouseMoveStartV = self._index
                self.mouseMoveStartH = 0
            elif (
                self._direction == "vertical"
                and abs(self._parent._horizontal1.position - positionH) <= self._line_thickness
            ):
                self.mouseMoveStartV = self._index
                self.mouseMoveStartH = 1

            #  Change the cursor to indicate "currently dragging"
            cursor = QCursor(Qt.ClosedHandCursor)
            QApplication.instance().setOverrideCursor(cursor)

    def mouseReleaseEvent(self, event):

        if self._parent.crop_extents_model._editable:
            self.mouseMoveStartH = -1
            self.mouseMoveStartV = -1

            # Restore the cursor to its previous state.
            QApplication.instance().restoreOverrideCursor()

            self._parent.crop_extents_model.mouseRelease.emit()


def determine_pen_thickness_in_scene(scene, cosmetic_thickness):
    """
    scene: ImageScene2D
    cosmetic_thickness: (float) The width of a cosmetic QPen
    """
    # This is a little tricky.  The line is always drawn with the same
    #  absolute thickness, REGARDLESS of the view's transform.
    # That is, the line does not appear to be part of the data,
    #  so it doesn't get thinner as we zoom out.  (See QPen.setCosmetic)
    # To compensate for this when determining the line's bounding box within the scene,
    #  we need to know the transform used by the view that is showing this scene.
    # If we didn't do this, our bounding rect would be off by a few pixels.
    # That probably wouldn't be a big deal.
    view = scene.views()[0]
    inverted_transform, has_inverse = view.transform().inverted()
    transformed_pen_thickness = inverted_transform.map(QPointF(cosmetic_thickness, cosmetic_thickness))
    pen_width_in_scene = transformed_pen_thickness.x()
    return pen_width_in_scene

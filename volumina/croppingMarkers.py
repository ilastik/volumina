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
import copy
import contextlib
from PyQt4.QtCore import pyqtSignal, Qt, QObject, QRectF, QPointF
from PyQt4.QtGui import QGraphicsItem, QPen, QApplication, QCursor, QBrush, QColor

class CropExtentsModel( QObject ):
    changed = pyqtSignal( object )  # list of start/stop coords indexed by axis: start < stop

    def __init__(self, parent):
        super( CropExtentsModel, self ).__init__( parent )
        self._crop_extents = [ [None, None], [None, None], [None, None] ]

    def get_roi_3d(self):
        """
        Returns the xyz roi: [ (x1,y1,z1), (x2,y2,z2) ]
        """
        ordered_extents = []
        for start, stop in self._crop_extents:
            if start < stop:
                ordered_extents.append( (start, stop) )
            else:
                ordered_extents.append( (stop, start) )

        # [(x1,x2), (y1,y2), (z1,z2)] -> [(x1,y1,z1), (x2,y2,z2)]
        roi = zip( *ordered_extents )
        return roi

    def set_roi_3d(self, roi):
        # Convenience function.
        # Set the extents as a roi
        self.set_crop_extents( zip( *roi ) )

    def set_volume_shape_3d(self, shape3d):
        # Since the volume size changed, 
        # reset the crop extents to a reasonable default.
        for i in range(3):
            self._crop_extents[i][0] = 0
            self._crop_extents[i][1] = shape3d[i]
        self.changed.emit( self )
    
    def crop_extents(self):
        return copy.deepcopy(self._crop_extents)
    
    def set_crop_extents(self, crop_extents):
        assert len(crop_extents) == 3
        for e in crop_extents:
            assert len(e) == 2
        self._crop_extents = map(list, crop_extents) # Ensure lists, not tuples
        self.changed.emit( self )

class CroppingMarkers( QGraphicsItem ):
    PEN_THICKNESS = 1

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'
        # This 'item' is merely a parent node for child items
        return QRectF()

    def __init__(self, scene, axis, crop_extents_model):
        QGraphicsItem.__init__(self, scene=scene)
        self.setFlag(QGraphicsItem.ItemHasNoContents);
        
        self.axis = axis
        self.crop_extents_model = crop_extents_model
        
        self._width = 0
        self._height = 0

        # Add shading item first so crop lines are drawn on top.
        self._shading_item = ExcludedRegionShading( self, self.crop_extents_model )

        self._horizontal0 = CropLine(self, 'horizontal', 0)
        self._horizontal1 = CropLine(self, 'horizontal', 1)
        self._vertical0 = CropLine(self, 'vertical', 0)
        self._vertical1 = CropLine(self, 'vertical', 1)

        self.crop_extents_model.changed.connect( self.onExtentsChanged )
        
    #be careful: QGraphicsItem has a shape() method, which
    #we cannot override, therefore we choose this name
    @property
    def dataShape(self):
        return (self._width, self._height)
    @dataShape.setter
    def dataShape(self, shape2D):
        self._width = shape2D[0]
        self._height = shape2D[1]

    def onExtentsChanged(self, crop_extents_model ):
        crop_extents = crop_extents_model.crop_extents()
        crop_extents.pop(self.axis)
        
        # By default, place cropping lines at 25% and 75%
        self._vertical0.position = crop_extents[0][0]
        self._vertical1.position = crop_extents[0][1]
        self._horizontal0.position = crop_extents[1][0]
        self._horizontal1.position = crop_extents[1][1]
        self.prepareGeometryChange()

    def onCropLineMoved(self, direction, index, new_position):
        # Which 3D axis does this crop line correspond to?
        # (Depends on which orthoview we belong to.)
        axislookup = [[None, 'v', 'h'],
                      ['v', None, 'h'],
                      ['v', 'h', None]]
        axis_3d = axislookup[self.axis].index( direction[0])
        crop_extents_3d = self.crop_extents_model.crop_extents()
        crop_extents_3d[axis_3d][index] = int(new_position)
        self.crop_extents_model.set_crop_extents( crop_extents_3d )

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
        super( ExcludedRegionShading, self ).__init__( parent )
        crop_extents_model.changed.connect( self.prepareGeometryChange )
        
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
        brush = QBrush( QColor(0,0,0,128) )
        
        rects = [ (0.0,    0.0, left,    top),
                  (0.0,    top, left, bottom),
                  (0.0, bottom, left, height),

                  (left,    0.0, right,    top),
                 #(left,    top, right, bottom), # Don't cover the middle.
                  (left, bottom, right, height),

                  (right,    0.0, width,    top),
                  (right,    top, width, bottom),
                  (right, bottom, width, height) ]
        
        with painter_context(painter):
            t = painter.transform()
            painter.setTransform(self.scene().data2scene * t)
            
            for rect_points in rects:
                x1, y1, x2, y2 = rect_points
                p1 = QPointF(x1,y1)
                p2 = QPointF(x2,y2)
                painter.fillRect( QRectF( p1, p2 ), brush )

class CropLine(QGraphicsItem):
    """
    QGraphicsItem for a single line (horizontal or vertical) of the slice intersection.
    Must be a child of SliceIntersectionMarker.  It can be dragged to change the slicing position.
    """
    def __init__(self, parent, direction, index):
        assert isinstance(parent, CroppingMarkers)
        assert direction in ('horizontal', 'vertical')

        self._parent = parent
        self._direction = direction
        self._index = index
        QGraphicsItem.__init__(self, parent)
        self.setAcceptHoverEvents(True)
        
        self._position = 0

    @property
    def position(self):
        return self._position
    
    @position.setter
    def position(self, new_position):
        self._position = new_position
        self.setToolTip( "{}".format( int(new_position) ) )
        self.prepareGeometryChange()
        self.update()

    def boundingRect(self):
        parent = self._parent
        width, height = parent._width, parent._height
        pen_width_in_view = parent.PEN_THICKNESS
        pen_width_in_scene = determine_pen_thickness_in_scene( self.scene(), pen_width_in_view )
        
        # Return a bounding rect that's a little larger than the actual line.
        # This makes it easier to grab with the mouse.
        line_thickness = 3*pen_width_in_scene
        
        if self._direction == 'horizontal':
            return self.scene().data2scene.mapRect( QRectF( 0, self._position - line_thickness/2.0, width, line_thickness ) )
        else:
            return self.scene().data2scene.mapRect( QRectF( self._position - line_thickness/2.0, 0, line_thickness, height ) )

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
        dash_length = 5 * inverted_transform.m11()
        dash_length = max( 0.5, dash_length )

        # Draw the line with two pens to get a black-and-white dashed line.
        pen_white = QPen( Qt.white, thickness )
        pen_white.setDashPattern([dash_length, dash_length])
        pen_white.setCosmetic(True)

        pen_black = QPen( Qt.black, thickness )
        pen_black.setDashPattern([dash_length, dash_length])
        pen_black.setCosmetic(True)
        pen_black.setDashOffset(dash_length)

        with painter_context(painter):
            t = painter.transform()
            painter.setTransform(self.scene().data2scene * t)

            # Draw the line with two pens to get a black-and-white dashed line.
            for pen in [pen_white, pen_black]:
                painter.setPen( pen )
    
                if self._direction == 'horizontal':
                    painter.drawLine( QPointF(0.0, self.position), QPointF(width, self.position) )
                else:
                    painter.drawLine( QPointF(self.position, 0.0), QPointF(self.position, height) )

    def hoverEnterEvent(self, event):
        # Change the cursor to indicate the line is draggable
        cursor = QCursor( Qt.OpenHandCursor )
        QApplication.instance().setOverrideCursor( cursor )
    
    def hoverLeaveEvent(self, event):
        # Restore the cursor to its previous state.
        QApplication.instance().restoreOverrideCursor()

    def mouseMoveEvent(self, event):
        new_pos = self.scene().data2scene.map( event.scenePos() )
        width, height = self._parent.dataShape
        
        if self._direction == 'horizontal':
            minPos = self._parent._horizontal0.position
            maxPos = self._parent._horizontal1.position
            position = int(new_pos.y() + 0.5)
            position = max( 0, position )
            position = min( height, position )
        else:
            minPos = self._parent._vertical0.position
            maxPos = self._parent._vertical1.position
            position = int(new_pos.x() + 0.5)
            position = max( 0, position )
            position = min( width, position )

        if self._index==0: # min crop line
            if position >= maxPos:
                self._parent.onCropLineMoved( self._direction, 1, position )
                position -= 1

        if self._index==1: # max crop line
            if position <= minPos:
                self._parent.onCropLineMoved( self._direction, 0, position )
                position += 1


        self._parent.onCropLineMoved( self._direction, self._index, position )

    # Note: We must override these or else the default implementation  
    #  prevents the mouseMoveEvent() override from working.
    # If we didn't have actual work to do in these functions, 
    #  we'd just use empty implementations:
    # 
    # def mousePressEvent(self, event): pass
    # def mouseReleaseEvent(self, event): pass

    def mousePressEvent(self, event):
        # Change the cursor to indicate "currently dragging"
        cursor = QCursor( Qt.ClosedHandCursor )
        QApplication.instance().setOverrideCursor( cursor )
        
    def mouseReleaseEvent(self, event):
        # Restore the cursor to its previous state.
        QApplication.instance().restoreOverrideCursor()
        
def determine_pen_thickness_in_scene( scene, cosmetic_thickness ):
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
    transformed_pen_thickness = inverted_transform.map( QPointF(cosmetic_thickness, cosmetic_thickness) )
    pen_width_in_scene = transformed_pen_thickness.x()
    return pen_width_in_scene

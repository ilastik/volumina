from collections import defaultdict
import threading
import logging

from PyQt4.Qt import pyqtSignal
from PyQt4.QtCore import Qt, QObject, QRectF, QPointF, QPoint
from PyQt4.QtGui import QApplication, QGraphicsObject, QGraphicsPathItem, QPainterPath, QPen, QColor

from volumina.utility import SignalingDefaultDict, edge_coords_nd, simplify_line_segments

logger = logging.getLogger(__name__)

class SegmentationEdgesItem( QGraphicsObject ):
    """
    A parent item for a collection of SingleEdgeItems.
    """
    edgeClicked = pyqtSignal( tuple ) # id_pair
    
    def __init__(self, path_items, edge_pen_table, parent=None):
        """
        path_items: A dict of { edge_id : SingleEdgeItem }
                    Use generate_path_items_for_labels() to produce this dict.
        
        edge_pen_table: Must be of type SignalingDefaultDict, mapping from id_pair -> QPen.
                        May contain id_pair elements that are not present in the label_img.
                        Such elements are ignored.
                        (It is assumed that edge_pen_table may be shared among several SegmentationEdgeItems)
        
        """
        assert threading.current_thread().name == 'MainThread', \
            "SegmentationEdgesItem objects may only be created in the main thread."
        
        super(SegmentationEdgesItem, self).__init__(parent=parent)
        self.setFlag(QGraphicsObject.ItemHasNoContents)
        
        assert isinstance(edge_pen_table, SignalingDefaultDict)
        self.edge_pen_table = edge_pen_table
        self.edge_pen_table.updated.connect( self.handle_updated_pen_table )
        self.set_path_items(path_items)

    def set_path_items(self, path_items):
        self.path_items = path_items
        for path_item in path_items.values():
            path_item.set_parent(self)

        # Cache the path item keys as a set
        self.path_ids = set(path_items.keys())

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'.
        # This 'item' is merely a parent node for child items.
        # (See QGraphicsObject.ItemHasNoContents.)
        return QRectF()

    def handle_edge_clicked(self, id_pair):
        self.edgeClicked.emit( id_pair )

    def handle_updated_pen_table(self, updated_path_ids):
        updated_path_ids = self.path_ids.intersection(updated_path_ids)
        for id_pair in updated_path_ids:
            self.path_items[id_pair].setPen( self.edge_pen_table[id_pair] )

def generate_path_items_for_labels(edge_pen_table, label_img, simplify_with_tolerance=None):
    # Find edge coordinates.
    # Note: 'x_axis' edges are those found when sweeping along the x axis.
    #       That is, the line separating the two segments will be *vertical*.
    assert label_img.ndim == 2
    x_axis_edge_coords, y_axis_edge_coords = edge_coords_nd(label_img)

    # Populate the path_items dict.
    path_items = {}
    for id_pair in set(x_axis_edge_coords.keys() + y_axis_edge_coords.keys()):
        horizontal_edge_coords = vertical_edge_coords = []
        if id_pair in y_axis_edge_coords:
            horizontal_edge_coords = y_axis_edge_coords[id_pair]
        if id_pair in x_axis_edge_coords:
            vertical_edge_coords = x_axis_edge_coords[id_pair]
        path_items[id_pair] = SingleEdgeItem(id_pair, horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance, initial_pen=edge_pen_table[id_pair])
    return path_items

class SingleEdgeItem( QGraphicsPathItem ):
    """
    Represents a single edge between two superpixels.
    Must be owned by a SegmentationEdgesItem object
    """
    
    def __init__(self, id_pair, horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance=None, initial_pen=None):
        """
        simplify_with_tolerance: If None, no simplification.
                                 If float, use as a tolerance constraint.
                                 Giving 0.0 won't change the appearance of the path, but may reduce the
                                 number of internal points it uses.
        """
        super( SingleEdgeItem, self ).__init__()
        self.parent = None # Should be initialized with set_parent()
        self.id_pair = id_pair

        if not initial_pen:
            initial_pen = QPen()
            initial_pen.setCosmetic(True)
            initial_pen.setCapStyle(Qt.RoundCap)
            initial_pen.setColor(Qt.white)
            initial_pen.setWidth(3)

        self.setPen(initial_pen)
    
        path = QPainterPath( self.path() )

        line_segments = []
        for (x,y) in horizontal_edge_coords:
            line_segments.append( ((x, y+1), (x+1, y+1)) )
        for (x,y) in vertical_edge_coords:
            line_segments.append( ((x+1, y), (x+1, y+1)) )

        if simplify_with_tolerance is None:
            for (start_point, end_point) in line_segments:
                if QPointF(*start_point) != path.currentPosition():
                    path.moveTo(*start_point)
                path.lineTo(*end_point)
        else:
            segments = simplify_line_segments(line_segments, tolerance=simplify_with_tolerance)
            for segment in segments:
                path.moveTo(*segment[0])
                for end_point in segment[1:]:
                    path.lineTo(*end_point)

        self.setPath(path)
        
    def mousePressEvent(self, event):
        event.accept()
        self.parent.handle_edge_clicked( self.id_pair )

    def set_parent(self, parent):
        assert isinstance(parent, SegmentationEdgesItem)
        self.setParentItem(parent)
        self.parent = parent

    ## Default implementation automatically already calls mousePressEvent()...
    #def mouseDoubleClickEvent(self, event):
    #    event.accept()
    #    self.parent.handle_edge_clicked( self.id_pair )

def pop_matching(l, match_f):
    for i, item in enumerate(l):
        if match_f(item):
            del l[i]
            return item
    return None
    
        
class defaultdict_with_key(defaultdict):
    """
    Like defaultdict, but calls default_factory(key) instead of default_factory()
    """
    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError( key )
        ret = self[key] = self.default_factory(key)
        return ret

if __name__ == "__main__":
    import time
    import numpy as np
    from PyQt4.QtGui import QApplication, QGraphicsView, QGraphicsScene, QTransform

    app = QApplication([])

    import h5py
    with h5py.File('/magnetic/data/multicut-testdata/2d/256/Superpixels.h5', 'r') as superpixels_f:
        labels_img = superpixels_f['data'][:]
        labels_img = labels_img[...,0] # drop channel

    default_pen = QPen()
    default_pen.setCosmetic(True)
    default_pen.setCapStyle(Qt.RoundCap)
    default_pen.setColor(Qt.blue)
    default_pen.setWidth(3)

    # Changes to this pen table will be detected automatically in the QGraphicsItem
    pen_table = SignalingDefaultDict(parent=None, default_factory=lambda:default_pen)

    start = time.time()
    path_items = generate_path_items_for_labels(pen_table, labels_img, 0.5)
    print "generate took {}".format(time.time() - start) # 52 ms

    edges_item = SegmentationEdgesItem(path_items, pen_table)
    
    def assign_random_color( id_pair):
        print "handling click..."
        pen = pen_table[id_pair]
        if pen:
            pen = QPen(pen)
        else:
            pen = QPen()
        random_color = QColor( *list( np.random.randint(0,255,(3,)) ) )
        pen.setColor(random_color)
        pen_table[id_pair] = pen        
        
    edges_item.edgeClicked.connect(assign_random_color)
    
    scene = QGraphicsScene()
    scene.addItem(edges_item)
    
    transform = QTransform()
    transform.scale(5.0, 5.0)
    
    view = QGraphicsView(scene)
    view.setTransform(transform)
    view.show()
    view.raise_()         
    app.exec_()

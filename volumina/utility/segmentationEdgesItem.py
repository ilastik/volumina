from collections import defaultdict
import threading
import logging

from PyQt4.Qt import pyqtSignal
from PyQt4.QtCore import Qt, QObject, QRectF
from PyQt4.QtGui import QApplication, QGraphicsObject, QGraphicsPathItem, QPainterPath, QPen, QColor

from volumina.utility import SignalingDefaultDict, edge_coords_nd

logger = logging.getLogger(__name__)

class SegmentationEdgesItem( QGraphicsObject ):
    """
    A parent item for a collection of SingleEdgeItems.
    """
    edgeClicked = pyqtSignal( tuple ) # id_pair
    
    def __init__(self, label_img, edge_pen_table, parent=None):
        """
        label_img: A 2D label image, whose edges will be located.
                   Each edge will be shown as its own QGraphicsPathItem
        
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
        
        # Find edge coordinates.
        # Note: 'x_axis' edges are those found when sweeping along the x axis.
        #       That is, the line separating the two segments will be *vertical*.
        assert label_img.ndim == 2
        x_axis_edge_coords, y_axis_edge_coords = edge_coords_nd(label_img)

        # Populate the path_items dict.
        path_items = defaultdict_with_key(lambda id_pair: SingleEdgeItem(id_pair, self.edge_pen_table[id_pair], parent=self))
        for id_pair, coords_list in x_axis_edge_coords.iteritems():
            path_items[id_pair].add_edge_lines(coords_list, 'vertical')
        for id_pair, coords_list in y_axis_edge_coords.iteritems():
            path_items[id_pair].add_edge_lines(coords_list, 'horizontal')

        self.path_items = path_items

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'.
        # This 'item' is merely a parent node for child items.
        # (See QGraphicsObject.ItemHasNoContents.)
        return QRectF()

    def handle_edge_clicked(self, id_pair):
        self.edgeClicked.emit( id_pair )

    def handle_updated_pen_table(self, id_pair, pen):
        path_item = self.path_items.get(id_pair) # use get() because it's a defaultdict
        if path_item:
            path_item.setPen(pen)

class SingleEdgeItem( QGraphicsPathItem ):
    """
    Represents a single edge between two superpixels.
    Must be owned by a SegmentationEdgesItem object
    """
    
    def __init__(self, id_pair, initial_pen=None, parent=None):
        assert isinstance(parent, SegmentationEdgesItem)
        super( SingleEdgeItem, self ).__init__(parent)
        self.parent = parent
        self.id_pair = id_pair

        if not initial_pen:
            initial_pen = QPen()
            initial_pen.setCosmetic(True)
            initial_pen.setCapStyle(Qt.RoundCap)
            initial_pen.setColor(Qt.white)
            initial_pen.setWidth(3)

        self.setPen(initial_pen)
    
    def add_edge_lines(self, coords_list, line_orientation):
        assert line_orientation in ('horizontal', 'vertical')
        path = QPainterPath(self.path())
        for (x,y) in coords_list: # volumina is in xyz order
            if line_orientation == 'horizontal':
                path.moveTo(x,   y+1)
                path.lineTo(x+1, y+1)
            else:
                path.moveTo(x+1, y)
                path.lineTo(x+1, y+1)
        self.setPath(path)
        
    def mousePressEvent(self, event):
        event.accept()
        self.parent.handle_edge_clicked( self.id_pair )

    ## Default implementation automatically already calls mousePressEvent()...
    #def mouseDoubleClickEvent(self, event):
    #    event.accept()
    #    self.parent.handle_edge_clicked( self.id_pair )
        
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
    import numpy as np
    from PyQt4.QtGui import QApplication, QGraphicsView, QGraphicsScene

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
    edges_item = SegmentationEdgesItem(labels_img, pen_table)

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
    view = QGraphicsView(scene)
    view.show()
    view.raise_()         
    app.exec_()

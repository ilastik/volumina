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
    
    def __init__(self, label_img, edge_colortable, parent=None):
        """
        label_img: A 2D label image, whose edges will be located.
                   Each edge will be shown as its own QGraphicsPathItem
        
        edge_colortable: Must be of type SignalingDefaultDict, mapping from id_pair -> QColor.
                         May contain id_pair elements that are not present in the label_img
                         Such elements are ignored.
                         (It is assumed that edge_colortable may be shared among several SegmentationEdgeItems)
        
        """
        super(SegmentationEdgesItem, self).__init__(parent=parent)
        self.setFlag(QGraphicsObject.ItemHasNoContents)
        
        assert threading.current_thread().name == 'MainThread', \
            "SegmentationEdgesItem objects may only be created in the main thread."
        
        assert isinstance(edge_colortable, SignalingDefaultDict)
        self.edge_colortable = edge_colortable
        self.edge_colortable.updated.connect( self.handle_updated_colortable, Qt.QueuedConnection )
        
        # Find edge coordinates.
        # Note: 'x_axis' edges are those found when sweeping along the x axis.
        #       That is, the line separating the two segments will be *vertical*.
        assert label_img.ndim == 2
        x_axis_edge_coords, y_axis_edge_coords = edge_coords_nd(label_img)

        # Populate the path_items dict.
        path_items = defaultdict_with_key(lambda id_pair: SingleEdgeItem(id_pair, self.edge_colortable[id_pair], parent=self))
        for id_pair, coords_list in x_axis_edge_coords.iteritems():
            path_items[id_pair].add_edge_lines(coords_list, 'vertical')
        for id_pair, coords_list in y_axis_edge_coords.iteritems():
            path_items[id_pair].add_edge_lines(coords_list, 'horizontal')
            
        self.path_items = path_items
        self.selected_edge = None

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'
        # This 'item' is merely a parent node for child items
        return QRectF()

    def highlight_edge(self, id_pair):
        if id_pair in self.path_items:
            self.path_items.highlight()

    def handle_edge_clicked(self, id_pair):
        self.edgeClicked.emit( id_pair )
        
        # For debugging, turn this on to directly show highlighted edges on every click.
        SHOW_DEBUG_HIGHLIGHTING = False
        if SHOW_DEBUG_HIGHLIGHTING:
            logger.debug("You clicked {}".format(id_pair))
            if id_pair == self.selected_edge:
                self.path_items[self.selected_edge].unhighlight()
                self.selected_edge = None
            else:
                self.path_items[self.selected_edge].unhighlight()
                self.path_items[id_pair].highlight()
                self.selected_edge = id_pair

    def handle_updated_colortable(self, id_pair, color):
        path_item = self.path_items.get(id_pair) # use get() because it's a defaultdict
        if path_item:
            path_item.set_color(color)

class SingleEdgeItem( QGraphicsPathItem ):
    """
    Represents a single edge between two superpixels.
    Must be owned by a SegmentationEdgesItem object
    """
    DEFAULT_PEN = QPen()
    DEFAULT_PEN.setCosmetic(True)
    DEFAULT_PEN.setCapStyle(Qt.RoundCap)
    DEFAULT_PEN.setColor(Qt.yellow)
    DEFAULT_PEN.setWidth(3)

    HIGHLIGHTED_PEN = QPen(DEFAULT_PEN)
    HIGHLIGHTED_PEN.setColor(Qt.blue)
    HIGHLIGHTED_PEN.setWidth(6)

    def __init__(self, id_pair, color, parent):
        assert isinstance(parent, SegmentationEdgesItem)
        super( SingleEdgeItem, self ).__init__(parent)
        self.parent = parent
        self.id_pair = id_pair
        
        self.default_pen = QPen(self.DEFAULT_PEN)
        self.highlighed_pen = QPen(self.HIGHLIGHTED_PEN)
        self.setPen(self.default_pen)
        self.set_color(color)

    def set_color(self, color):
        if color:
            self.default_pen = QPen(self.default_pen)
            self.default_pen.setColor( color )

            self.highlighed_pen = QPen(self.default_pen)
            self.highlighed_pen.setColor( color )

            current_pen = QPen( self.pen() )
            current_pen.setColor( color )
            self.setPen( current_pen )
    
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
        self.parent.handle_edge_clicked( self.id_pair )

    def highlight(self):
        self.setPen( self.highlighted_pen )
    
    def unhighlight(self):
        self.setPen( self.default_pen )
        
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

    labels_img = np.load('/Users/bergs/workspace/ilastik-meta/ilastik/seg-slice-256.npy')

    # Changes to this colortable will be detected automatically in the QGraphicsItem
    colortable = SignalingDefaultDict(parent=None, default_factory=lambda:None)
    edges_item = SegmentationEdgesItem(labels_img, colortable)

    def assign_random_color( id_pair ):
        random_color = QColor( *list( np.random.randint(0,255,(3,)) ) )
        colortable[id_pair] = random_color
    edges_item.edgeClicked.connect(assign_random_color)
    
    scene = QGraphicsScene()
    scene.addItem(edges_item)
    view = QGraphicsView(scene)
    view.show()
    view.raise_()         
    app.exec_()

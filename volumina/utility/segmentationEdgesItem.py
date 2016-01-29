from collections import defaultdict

from PyQt4.QtCore import Qt, QRectF
from PyQt4.QtGui import QGraphicsItem, QGraphicsPathItem, QPainterPath, QPen

from volumina.utility.edge_coords import edge_coords_nd

class SegmentationEdgesItem( QGraphicsItem ):
    """
    A parent item for a collection of SingleEdgeItems.
    """
    def __init__(self, label_img, parent=None):
        super(SegmentationEdgesItem, self).__init__(parent=parent)
        self.setFlag(QGraphicsItem.ItemHasNoContents);
        assert label_img.ndim == 2
        
        # Find edge coordinates.
        # Note: 'x_axis' edges are those found when sweeping along the x axis.
        #       That is, the line separating the two segments will be vertical.
        x_axis_edge_coords, y_axis_edge_coords = edge_coords_nd(label_img)

        # Populate the path_items dict.
        path_items = defaultdict_with_key(lambda id_pair: SingleEdgeItem(id_pair, parent=self))
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

    def handle_edge_clicked(self, id_pair):
        #print "You clicked {}".format(id_pair)
        if id_pair == self.selected_edge:
            self.path_items[self.selected_edge].unhighlight()
            self.selected_edge = None
        else:
            self.path_items[self.selected_edge].unhighlight()
            self.path_items[id_pair].highlight()
            self.selected_edge = id_pair

class SingleEdgeItem( QGraphicsPathItem ):
    """
    Represents a single edge between two superpixels.
    Must be owned by a SegmentationEdgesItem object
    """
    default_pen = QPen()
    default_pen.setColor(Qt.yellow)
    default_pen.setCosmetic(True)
    default_pen.setWidth(3)

    highlighted_pen = QPen(default_pen)
    highlighted_pen.setColor(Qt.blue)
    highlighted_pen.setWidth(6)

    def __init__(self, id_pair, parent):
        assert isinstance(parent, SegmentationEdgesItem)
        super( SingleEdgeItem, self ).__init__(parent)
        self.parent = parent
        self.id_pair = id_pair
        self.setPen( self.default_pen )
    
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

    labels_img = np.load('/Users/bergs/workspace/ilastik-meta/ilastik/seg-slice-256.npy')
    edges_item = SegmentationEdgesItem(labels_img)
    
    app = QApplication([])
    scene = QGraphicsScene()
    scene.addItem(edges_item)
    view = QGraphicsView(scene)
    view.show()
    view.raise_()         
    app.exec_()

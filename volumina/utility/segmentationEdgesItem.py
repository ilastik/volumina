from __future__ import print_function
from collections import defaultdict
import threading
import logging

import numpy as np

from qtpy.QtCore import Signal
from qtpy.QtCore import Qt, QObject, QRectF, QPointF, QPoint
from qtpy.QtWidgets import QApplication, QGraphicsObject, QGraphicsPathItem, QGraphicsSceneHoverEvent
from qtpy.QtGui import QPainterPath, QPen, QColor, QPainterPathStroker, QPainter

from volumina.utility import SignalingDict, edge_coords_nd, simplify_line_segments

logger = logging.getLogger(__name__)


class SegmentationEdgesItem(QGraphicsObject):
    """
    A parent item for a collection of SingleEdgeItems.
    """

    edgeClicked = Signal(tuple, object)  # id_pair, QGraphicsSceneMouseEvent
    edgeSwiped = Signal(tuple, object)  # id_pair, QGraphicsSceneMouseEvent

    def __init__(self, path_items, edge_pen_table, default_pen, *, hoverIdChanged=None, parent=None, isClickable=False):
        """
        path_items: A dict of { edge_id : SingleEdgeItem }
                    Use generate_path_items_for_labels() to produce this dict.

        edge_pen_table: Must be of type SignalingDict, mapping from id_pair -> QPen.
                        May contain id_pair elements that are not present in the label_img.
                        Such elements are ignored.
                        (It is assumed that edge_pen_table may be shared among several SegmentationEdgeItems)

        default_pen: What pen to use for id_pairs that are not found in the edge_pen_table
        """
        assert (
            threading.current_thread().name == "MainThread"
        ), "SegmentationEdgesItem objects may only be created in the main thread."

        self.hoverIdChanged = hoverIdChanged
        self.isClickable = isClickable
        super(SegmentationEdgesItem, self).__init__(parent=parent)
        self.setFlag(QGraphicsObject.ItemHasNoContents)

        assert isinstance(edge_pen_table, SignalingDict)
        self.edge_pen_table = edge_pen_table
        self.edge_pen_table.updated.connect(self.handle_updated_pen_table)
        self.set_path_items(path_items)
        self.default_pen = default_pen

    def set_path_items(self, path_items):
        self.path_items = path_items
        for path_item in list(path_items.values()):
            path_item.set_parent(self)

        # Cache the path item keys as a set
        self.path_ids = set(path_items.keys())

    def boundingRect(self):
        # Return an empty rect to indicate 'no content'.
        # This 'item' is merely a parent node for child items.
        # (See QGraphicsObject.ItemHasNoContents.)
        return QRectF()

    def handle_edge_clicked(self, id_pair, event):
        self.edgeClicked.emit(id_pair, event)

    def handle_mouse_drag(self, id_pair, event):
        self.edgeSwiped.emit(id_pair, event)

    def handle_updated_pen_table(self, updated_path_ids):
        updated_path_ids = self.path_ids.intersection(updated_path_ids)
        for id_pair in updated_path_ids:
            item = self.path_items[id_pair]
            pen = self.edge_pen_table.get(id_pair, self.default_pen)
            item.setPen(pen)


def painter_paths_for_labels_PURE_PYTHON(label_img, simplify_with_tolerance=None):
    # Find edge coordinates.
    # Note: 'x_axis' edges are those found when sweeping along the x axis.
    #       That is, the line separating the two segments will be *vertical*.
    assert label_img.ndim == 2
    x_axis_edge_coords, y_axis_edge_coords = edge_coords_nd(label_img)
    # x_axis_edge_coords, y_axis_edge_coords = edgeCoords2D(label_img)

    # Populate the path_items dict.
    painter_paths = {}
    for id_pair in set(list(x_axis_edge_coords.keys()) + list(y_axis_edge_coords.keys())):
        horizontal_edge_coords = vertical_edge_coords = []
        if id_pair in y_axis_edge_coords:
            horizontal_edge_coords = y_axis_edge_coords[id_pair]
        if id_pair in x_axis_edge_coords:
            vertical_edge_coords = x_axis_edge_coords[id_pair]
        painter_paths[id_pair] = painter_path_from_edge_coords(
            horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance
        )

    return painter_paths


try:
    import vigra
    from ilastiktools import line_segments_for_labels

    def painter_paths_for_labels(label_img, simplify_with_tolerance=None):
        if simplify_with_tolerance is not None:
            return painter_paths_for_labels_PURE_PYTHON(label_img, simplify_with_tolerance)
        line_seg_lookup = line_segments_for_labels(vigra.taggedView(label_img, "xy"))
        painter_paths = {}
        for edge_id, line_segments in list(line_seg_lookup.items()):
            point_list = line_segments.reshape(-1, 2)
            painter_paths[edge_id] = arrayToQPath(point_list[:, 0], point_list[:, 1], connect="pairs")
        return painter_paths

except ImportError:
    painter_paths_for_labels = painter_paths_for_labels_PURE_PYTHON

try:
    from ilastiktools import edgeCoords2D

    edge_coords_nd = edgeCoords2D
except ImportError:
    pass


def generate_path_items_for_labels(
    edge_pen_table, default_pen, label_img, simplify_with_tolerance=None, isClickable=False
):
    painter_paths = painter_paths_for_labels(label_img, simplify_with_tolerance)

    path_items = {}
    for id_pair in list(painter_paths.keys()):
        path_items[id_pair] = SingleEdgeItem(
            id_pair,
            painter_paths[id_pair],
            initial_pen=edge_pen_table.get(id_pair, default_pen),
            isClickable=isClickable,
        )
    return path_items


def line_segments_from_edge_coords(horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance=None):
    """
    simplify_with_tolerance: If None, no simplification.
                             If float, use as a tolerance constraint.
                             Giving 0.0 won't change the appearance of the path, but may reduce the
                             number of internal points it uses.
    """
    ## This is what we're doing, but the array-based code below is faster.
    #
    # line_segments = []
    # for (x,y) in horizontal_edge_coords:
    #     line_segments.append( ((x, y+1), (x+1, y+1)) )
    # for (x,y) in vertical_edge_coords:
    #     line_segments.append( ((x+1, y), (x+1, y+1)) )

    # Same as above commented-out code, but faster
    if horizontal_edge_coords:
        horizontal_edge_coords = np.array(horizontal_edge_coords)
    else:
        horizontal_edge_coords = np.ndarray((0, 2), dtype=np.uint32)

    if vertical_edge_coords:
        vertical_edge_coords = np.array(vertical_edge_coords)
    else:
        vertical_edge_coords = np.ndarray((0, 2), dtype=np.uint32)

    num_segments = len(horizontal_edge_coords) + len(vertical_edge_coords)
    line_segments = np.zeros((num_segments, 2, 2), dtype=np.uint32)
    line_segments[: len(horizontal_edge_coords), 0, :] = horizontal_edge_coords + (0, 1)
    line_segments[: len(horizontal_edge_coords), 1, :] = horizontal_edge_coords + (1, 1)
    line_segments[len(horizontal_edge_coords) :, 0, :] = vertical_edge_coords + (1, 0)
    line_segments[len(horizontal_edge_coords) :, 1, :] = vertical_edge_coords + (1, 1)

    if simplify_with_tolerance is not None:
        sequential_points = simplify_line_segments(line_segments, tolerance=simplify_with_tolerance)
        line_segments = []
        for point_list in sequential_points:
            # Since these points are already in order, doubling the size of the point list like this
            # is slightly inefficient, but it simplifies things because we can use the same QPath
            # generation method.
            line_segments += list(zip(point_list[:-1], point_list[1:]))
        line_segments = np.array(line_segments)
    return line_segments


def painter_path_from_edge_coords(horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance=None):
    line_segments = line_segments_from_edge_coords(
        horizontal_edge_coords, vertical_edge_coords, simplify_with_tolerance
    )
    line_segments = line_segments.reshape((-1, 2))
    path = arrayToQPath(line_segments[:, 0], line_segments[:, 1], connect="pairs")
    return path


class SingleEdgeItem(QGraphicsPathItem):
    """
    Represents a single edge between two superpixels.
    Must be owned by a SegmentationEdgesItem object
    """

    def __init__(self, id_pair, painter_path, initial_pen=None, isClickable=False):
        super(SingleEdgeItem, self).__init__()
        self.parent = None  # Should be initialized with set_parent()
        self.id_pair = id_pair
        self._hover = False
        if not initial_pen:
            initial_pen = QPen()
            initial_pen.setCosmetic(True)
            initial_pen.setCapStyle(Qt.RoundCap)
            initial_pen.setColor(Qt.white)
            initial_pen.setWidth(3)

        self.setPen(initial_pen)
        self.setPath(painter_path)
        if isClickable:
            self.setCursor(Qt.PointingHandCursor)

        self._scale = 1

    def shape(self):
        # Adjust active area depending on the zoom level
        stroker = QPainterPathStroker()
        stroker.setWidth(self.pen().width() * self._scale)
        return stroker.createStroke(self.path())

    def hoverEnterEvent(self, event: QGraphicsSceneHoverEvent):
        self.parent.hoverIdChanged.emit(self.id_pair)

    def hoverLeaveEvent(self, event: QGraphicsSceneHoverEvent):
        self.parent.hoverIdChanged.emit(None)

    def mousePressEvent(self, event):
        self.parent.handle_edge_clicked(self.id_pair, event)

    def mouseMoveEvent(self, event):
        """
        Note: ImageScene2D has special behavior to send us mouseMoveEvents that we would otherwise not receive.
              In such cases, the event.pos() may be invalid, so don't use it.
        """
        if event.buttons() != Qt.NoButton:
            self.parent.handle_mouse_drag(self.id_pair, event)

    def handle_id_hover(self, id_pair):
        if self.id_pair == id_pair and not self._hover:
            self._hover = True
            self.update(self.boundingRect())
        elif self.id_pair != id_pair and self._hover:
            self._hover = False
            self.update(self.boundingRect())

    def set_parent(self, parent):
        assert isinstance(parent, SegmentationEdgesItem)
        self.setParentItem(parent)
        self.parent = parent
        if self.parent.hoverIdChanged:
            self.setAcceptHoverEvents(True)
            self.parent.hoverIdChanged.connect(self.handle_id_hover)
        if not self.parent.isClickable:
            self.setAcceptedMouseButtons(Qt.NoButton)

    def paint(self, painter: QPainter, option, widget):
        transform, invertable = painter.worldTransform().inverted()
        if invertable:
            self._scale = transform.m11()

        if self._hover:
            hover_pen = QPen(self.pen())
            hover_pen.setWidth(hover_pen.width() + 2)
            painter.strokePath(self.path(), hover_pen)
        else:
            super().paint(painter, option, widget)

    ## Default implementation automatically already calls mousePressEvent()...
    # def mouseDoubleClickEvent(self, event):
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
            raise KeyError(key)
        ret = self[key] = self.default_factory(key)
        return ret


##
## Copied from PyQtGraph with slight modifications
##
from qtpy import QtWidgets, QtCore
import struct


def arrayToQPath(x, y, connect="all"):
    """Convert an array of x,y coordinats to QPainterPath as efficiently as possible.
    The *connect* argument may be 'all', indicating that each point should be
    connected to the next; 'pairs', indicating that each pair of points
    should be connected, or an array of int32 values (0 or 1) indicating
    connections.
    """

    ## Create all vertices in path. The method used below creates a binary format so that all
    ## vertices can be read in at once. This binary format may change in future versions of Qt,
    ## so the original (slower) method is left here for emergencies:
    # path.moveTo(x[0], y[0])
    # if connect == 'all':
    # for i in range(1, y.shape[0]):
    # path.lineTo(x[i], y[i])
    # elif connect == 'pairs':
    # for i in range(1, y.shape[0]):
    # if i%2 == 0:
    # path.lineTo(x[i], y[i])
    # else:
    # path.moveTo(x[i], y[i])
    # elif isinstance(connect, np.ndarray):
    # for i in range(1, y.shape[0]):
    # if connect[i] == 1:
    # path.lineTo(x[i], y[i])
    # else:
    # path.moveTo(x[i], y[i])
    # else:
    # raise Exception('connect argument must be "all", "pairs", or array')

    ## Speed this up using >> operator
    ## Format is:
    ##    numVerts(i4)   0(i4)
    ##    x(f8)   y(f8)   0(i4)    <-- 0 means this vertex does not connect
    ##    x(f8)   y(f8)   1(i4)    <-- 1 means this vertex connects to the previous vertex
    ##    ...
    ##    0(i4)
    ##
    ## All values are big endian--pack using struct.pack('>d') or struct.pack('>i')

    path = QPainterPath()

    # profiler = debug.Profiler()
    n = x.shape[0]
    # create empty array, pad with extra space on either end
    arr = np.empty(n + 2, dtype=[("x", ">f8"), ("y", ">f8"), ("c", ">i4")])
    # write first two integers
    # profiler('allocate empty')
    byteview = arr.view(dtype=np.ubyte)
    byteview[:12] = 0
    byteview.data[12:20] = struct.pack(">ii", n, 0)
    # profiler('pack header')
    # Fill array with vertex values
    arr[1:-1]["x"] = x
    arr[1:-1]["y"] = y

    # decide which points are connected by lines
    assert connect == "pairs", "I modified this function and now 'pairs' is the only allowed 'connect' option."
    arr[1:-1]["c"][::2] = 1
    arr[1:-1]["c"][1::2] = 0

    # profiler('fill array')
    # write last 0
    lastInd = 20 * (n + 1)
    byteview.data[lastInd : lastInd + 4] = struct.pack(">i", 0)
    # profiler('footer')
    # create datastream object and stream into path

    ## Avoiding this method because QByteArray(str) leaks memory in PySide
    # buf = QtCore.QByteArray(arr.data[12:lastInd+4])  # I think one unnecessary copy happens here

    path.strn = byteview.data[12 : lastInd + 4]  # make sure data doesn't run away
    try:
        buf = QtCore.QByteArray.fromRawData(path.strn)
    except TypeError:
        buf = QtCore.QByteArray(bytes(path.strn))
    # profiler('create buffer')
    ds = QtCore.QDataStream(buf)

    def load_path():
        ds >> path

    # profiler('load')
    load_path()

    return path


if __name__ == "__main__":
    import time
    import numpy as np
    from qtpy.QtGui import QTransform
    from qtpy.QtWidgets import QApplication, QGraphicsView, QGraphicsScene

    app = QApplication([])

    import h5py

    with h5py.File("/magnetic/data/multicut-testdata/2d/256/Superpixels.h5", "r") as superpixels_f:
        labels_img = superpixels_f["data"][:]
        labels_img = labels_img[..., 0]  # drop channel

    default_pen = QPen()
    default_pen.setCosmetic(True)
    default_pen.setCapStyle(Qt.RoundCap)
    default_pen.setColor(Qt.blue)
    default_pen.setWidth(3)

    # Changes to this pen table will be detected automatically in the QGraphicsItem
    pen_table = SignalingDict(None)

    start = time.time()
    path_items = generate_path_items_for_labels(pen_table, default_pen, labels_img, None)
    print("generate took {}".format(time.time() - start))  # 52 ms

    edges_item = SegmentationEdgesItem(path_items, pen_table, default_pen)

    def assign_random_color(id_pair, buttons):
        print("handling click: {}".format(id_pair))
        pen = pen_table[id_pair]
        if pen:
            pen = QPen(pen)
        else:
            pen = QPen()
        random_color = QColor(*list(np.random.randint(0, 255, (3,))))
        pen.setColor(random_color)
        pen_table[id_pair] = pen

    edges_item.edgeClicked.connect(assign_random_color)

    scene = QGraphicsScene()
    scene.addItem(edges_item)

    transform = QTransform()
    transform.scale(2.0, 2.0)

    view = QGraphicsView(scene)
    view.setTransform(transform)
    view.show()
    view.raise_()
    app.exec_()

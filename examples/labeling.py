import numpy
import sys

from volumina.api import Viewer
from volumina.colortables import default16_new
from volumina.pixelpipeline.datasources import ArraySinkSource, ArraySource
from volumina.layer import ColortableLayer, GrayscaleLayer

from PyQt5.QtWidgets import QApplication

SHAPE = (1, 600, 800, 1, 1)  # volumina expects 5d txyzc

data_arr = (255 * numpy.random.random(SHAPE)).astype(numpy.uint8)
label_arr = numpy.zeros(SHAPE, dtype=numpy.uint8)

##-----
app = QApplication(sys.argv)
v = Viewer()


data_src = ArraySource(data_arr)
data_layer = GrayscaleLayer(data_src)
data_layer.name = "Raw"
data_layer.numberOfChannels = 1

label_src = ArraySinkSource(label_arr)
label_layer = ColortableLayer(label_src, colorTable=default16_new, direct=False)
label_layer.name = "Labels"
label_layer.ref_object = None

assert SHAPE == label_arr.shape == data_arr.shape
v.dataShape = SHAPE

v.layerstack.append(data_layer)
v.layerstack.append(label_layer)

v.editor.setLabelSink(label_src)
v.editor.setInteractionMode("brushing")

v.setWindowTitle("streaming viewer")
v.showMaximized()
app.exec_()

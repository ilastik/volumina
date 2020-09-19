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
import numpy
import sys

from volumina.api import Viewer
from volumina.colortables import default16_new
from volumina.pixelpipeline.datasources import ArraySinkSource, ArraySource
from volumina.layer import ColortableLayer, GrayscaleLayer

from PyQt5.QtWidgets import QApplication

SHAPE = (1, 600, 800, 1, 1)  # Volumina expects 5d txyzc

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

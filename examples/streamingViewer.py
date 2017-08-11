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
#		   http://ilastik.org/license/
###############################################################################
import h5py
import numpy

from volumina.api import Viewer
from volumina.pixelpipeline.datasources import LazyflowSource

from lazyflow.graph import Graph
from lazyflow.operators.ioOperators.opStreamingHdf5Reader import OpStreamingHdf5Reader
from lazyflow.operators import OpCompressedCache

from PyQt5.QtWidgets import QApplication

f = h5py.File("raw.h5", 'w')
d = (255*numpy.random.random((100,200,300))).astype(numpy.uint8)
f.create_dataset("raw", data=d)
f.close()

f = h5py.File("seg.h5", 'w')
d = (10*numpy.random.random((100,200,300))).astype(numpy.uint32)
f.create_dataset("seg", data=d)
f.close()

##-----

app = QApplication(sys.argv)
v = Viewer()

graph = Graph()

def mkH5source(fname, gname):
    h5file = h5py.File(fname)
    source = OpStreamingHdf5Reader(graph=graph)
    source.Hdf5File.setValue(h5file)
    source.InternalPath.setValue(gname)

    op = OpCompressedCache( parent=None, graph=graph )
    op.BlockShape.setValue( [100, 100, 100] )
    op.Input.connect( source.OutputImage )

    return op.Output

rawSource = mkH5source("raw.h5", "raw")
segSource = mkH5source("seg.h5", "seg")

v.addGrayscaleLayer(rawSource, name="raw")
v.addColorTableLayer(segSource, name="seg")

v.setWindowTitle("streaming viewer")
v.showMaximized()
app.exec_()

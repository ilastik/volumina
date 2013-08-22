import h5py
import numpy

from volumina.api import Viewer
from volumina.pixelpipeline.datasources import LazyflowSource

from lazyflow.graph import Graph
from lazyflow.operators.ioOperators.opStreamingHdf5Reader import OpStreamingHdf5Reader

from PyQt4.QtGui import QApplication

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

rawFile = h5py.File("raw.h5")
rawSource = OpStreamingHdf5Reader(graph=graph)
rawSource.Hdf5File.setValue(rawFile)
rawSource.InternalPath.setValue("raw")

segFile = h5py.File("seg.h5")
segSource = OpStreamingHdf5Reader(graph=graph)
segSource.Hdf5File.setValue(segFile)
segSource.InternalPath.setValue("seg")

v.addGrayscaleLayer(rawSource.OutputImage, name="raw")
v.addColorTableLayer(segSource.OutputImage, name="seg")

v.setWindowTitle("streaming viewer")
v.showMaximized()
app.exec_()

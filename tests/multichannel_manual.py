from volumina.api import Viewer
from PyQt4.QtGui import QApplication
import numpy

app = QApplication([])
v = Viewer()
a = (255*numpy.random.random((1, 50,60,70,10) )).astype(numpy.uint8)
v.addGrayscaleLayer(a, name="raw")
v.showMaximized()
app.exec_()

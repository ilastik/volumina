#
# This file demonstrates the usefulness of 'direct' mode for layers.
# In direct mode, any requests to the layer are computed synchronously, instead of the request being
# put on a queue to be processed asynchronously in another thread.
# If the data is readily available (for example: numpy array source), this has significant speed advantages.
#

from volumina.api import Viewer
from PyQt4.QtGui import QApplication, QColor, QKeySequence, QShortcut
from PyQt4.QtGui import QPushButton
import numpy
import h5py

from optparse import OptionParser

usage = "usage: %prog <filename.h5/groupname>"
parser = OptionParser(usage)
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("no hdf5 dataset supplied")

x = args[0].find(".h5")
fname = args[0][:x+3] 
gname = args[0][x+4:]

#load data
f = h5py.File(fname, 'r')       
raw = f[gname].value
assert raw.ndim == 3
assert raw.dtype == numpy.uint8
f.close()

app = QApplication([])
v = Viewer()
direct = True

raw.shape = (1,)+raw.shape+(1,)

def addLayers(v, direct):
    l1 = v.addGrayscaleLayer(raw, name="raw direct=%r" % direct, direct=direct)
    l1.visible = direct
    colortable = [QColor(0,0,0,0).rgba(), QColor(255,0,0).rgba()]
    l2 = v.addColorTableLayer((raw>128).astype(numpy.uint8), name="thresh direct=%r" % direct, colortable=colortable, direct=direct)
    l2.visible = direct
    return (l1, l2)

directLayers   = addLayers(v, True)    
indirectLayers = addLayers(v, False)    

b = QPushButton("direct mode (Ctrl+d)")

b.setCheckable(True)
b.setChecked(True)
def onDirectModeToggled(direct):
    for l in directLayers:
        l.visible = direct
    for l in indirectLayers:
        l.visible = not direct
        
b.toggled.connect(onDirectModeToggled)
QShortcut(QKeySequence("Ctrl+d"), b, member=b.click, ambiguousMember=b.click)
v.rightPaneLayout.addWidget(b)
    
v.show()
app.exec_()

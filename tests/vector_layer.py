from volumina.api import Viewer
from volumina.layer import Layer
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
raw = f[gname].value.squeeze()[0:333,:,:]
raw[30:40,40:50,10:20] = 255
raw[60:80,40:50,10:20] = 128
assert raw.ndim == 3
assert raw.dtype == numpy.uint8
f.close()

app = QApplication([])
v = Viewer()

v.editor.showDebugPatches = True

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
 
lg = v.addGrayscaleLayer(raw, name="raw w/ graphics", direct=True)
class ScalableGraphicsSource(object):
    pass
s = ScalableGraphicsSource()
lg.scalableGraphicsSource = s

v.showMaximized()
app.exec_()

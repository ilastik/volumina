#
# Work in progress: Skeletonization
#

from volumina.api import Viewer
from PyQt4.QtGui import QApplication
import numpy
import h5py
from volumina.skeletons import Skeletons, SkeletonInterpreter

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
try:
    f = h5py.File(fname, 'r')       
except:
    raise RuntimeError("Could not load '%s'" % fname)
raw = f[gname].value.squeeze()
assert raw.ndim == 3
assert raw.dtype == numpy.uint8
f.close()

app = QApplication([])
v = Viewer()
direct = True

raw.shape = (1,)+raw.shape+(1,)

l1 = v.addGrayscaleLayer(raw, name="raw", direct=True)

#######################################################################################################################

skeletons = Skeletons()

e = SkeletonInterpreter(v.editor, skeletons, v)
v.editor.eventSwitch.interpreter = e

v.show()
app.exec_()

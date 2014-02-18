# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

#
# Use this file to check that the colortable options in the layer context menu are working
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

l1 = v.addGrayscaleLayer(raw, name="raw", direct=True)
l1.visible = direct
colortable = [QColor(0,0,0,0).rgba(), QColor(255,0,0).rgba(), QColor(0,255,0).rgba(), QColor(0,0,255).rgba()]

s = ((raw/64)).astype(numpy.uint8)
def onClick(layer, pos5D, pos):
    print "here i am: ", pos5D, s[pos5D]
    
l2 = v.addColorTableLayer(s, clickFunctor=onClick, name="thresh", colortable=colortable, direct=direct)
l2.colortableIsRandom = True
l2.zeroIsTransparent = True
l2.visible = False

v.addClickableSegmentationLayer(s, "click it", direct=True)

v.show()
app.exec_()

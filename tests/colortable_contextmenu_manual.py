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
#
# Use this file to check that the colortable options in the layer context menu are working
#

from __future__ import division
from __future__ import print_function
from volumina.api import Viewer
from qtpy.QtGui import QColor, QKeySequence
from qtpy.QtWidgets import QApplication, QPushButton, QShortcut
import numpy
import h5py

from optparse import OptionParser

usage = "usage: %prog <filename.h5/groupname>"
parser = OptionParser(usage)
(options, args) = parser.parse_args()
if len(args) != 1:
    parser.error("no hdf5 dataset supplied")

x = args[0].find(".h5")
fname = args[0][: x + 3]
gname = args[0][x + 4 :]

# load data
f = h5py.File(fname, "r")
raw = f[gname][()]
assert raw.ndim == 3
assert raw.dtype == numpy.uint8
f.close()

app = QApplication([])
v = Viewer()
direct = True

raw.shape = (1,) + raw.shape + (1,)

l1 = v.addGrayscaleLayer(raw, name="raw", direct=True)
l1.visible = direct
colortable = [QColor(0, 0, 0, 0).rgba(), QColor(255, 0, 0).rgba(), QColor(0, 255, 0).rgba(), QColor(0, 0, 255).rgba()]

s = ((raw // 64)).astype(numpy.uint8)


def onClick(layer, pos5D, pos):
    print("here i am: ", pos5D, s[pos5D])


l2 = v.addColorTableLayer(s, clickFunctor=onClick, name="thresh", colortable=colortable, direct=direct)
l2.colortableIsRandom = True
l2.zeroIsTransparent = True
l2.visible = False

v.addClickableSegmentationLayer(s, "click it", direct=True)

v.show()
app.exec_()

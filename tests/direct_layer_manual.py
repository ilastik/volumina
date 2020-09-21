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
# This file demonstrates the usefulness of 'direct' mode for layers.
# In direct mode, any requests to the layer are computed synchronously, instead of the request being
# put on a queue to be processed asynchronously in another thread.
# If the data is readily available (for example: numpy array source), this has significant speed advantages.
#

from volumina.api import Viewer
from PyQt5.QtGui import QColor, QKeySequence
from PyQt5.QtWidgets import QApplication, QPushButton, QShortcut
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
raw = f[gname][()].squeeze()
assert raw.ndim == 3
assert raw.dtype == numpy.uint8
f.close()

app = QApplication([])
v = Viewer()
direct = True

raw.shape = (1,) + raw.shape + (1,)


def addLayers(v, direct):
    l1 = v.addGrayscaleLayer(raw, name="raw direct=%r" % direct, direct=direct)
    l1.visible = direct
    colortable = [QColor(0, 0, 0, 0).rgba(), QColor(255, 0, 0).rgba()]
    l2 = v.addColorTableLayer(
        (raw > 128).astype(numpy.uint8), name="thresh direct=%r" % direct, colortable=colortable, direct=direct
    )
    l2.visible = direct
    return (l1, l2)


directLayers = addLayers(v, True)
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

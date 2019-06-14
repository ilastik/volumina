from __future__ import print_function

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
from builtins import range
from PyQt5.QtCore import QObject

from volumina.skeletons.skeletonsLayer import SkeletonsLayer
from volumina.skeletons.skeletonNode import SkeletonNode


class SkeletonsLayer3D(QObject):
    def __init__(self, editor, skeletons, parent=None):
        super(SkeletonsLayer3D, self).__init__(parent=parent)
        editor.posModel.slicingPositionChanged.connect(self.onSlicingPositionChanged)

        # skeletons.nodePositionChanged.connect(self.onNodePositionChanged)
        # skeletons.nodeSelectionChanged.connect(self.onNodeSelectionChanged)

        skeletons.changed.connect(self.update)

        def onJumpRequested(pos):
            editor.posModel.slicingPos = pos

        skeletons.jumpRequested.connect(onJumpRequested)

        self._skeletons = skeletons
        self._layers = []

        for i in range(3):
            self._layers.append(SkeletonsLayer(self, i, editor.imageScenes[i]))

    def onNodePositionChanged(self, node):
        pass

    def onNodeSelectionChanged(self, node):
        print("XXXXXXXXXXXXXXX selection changed for node=%r to %r" % (node, node.isSelected()))
        for l in self._layers:
            l.update()
        pass

    def addNode(self, pos, axis):
        n = SkeletonNode(pos, axis, self._skeletons)
        self._skeletons.addNode(n)

    def update(self):
        for l in self._layers:
            l.update()

    def onSlicingPositionChanged(self, newPos, oldPos):
        for i in range(3):
            if newPos[i] != oldPos[i]:
                self._layers[i].setAxisIntersect(newPos[i])

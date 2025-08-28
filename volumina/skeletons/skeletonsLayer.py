from __future__ import division

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
from past.utils import old_div
from qtpy.QtCore import QPointF, QRectF, QLineF, Qt
from qtpy.QtGui import QPen, QColor
from qtpy.QtWidgets import QGraphicsObject, QGraphicsRectItem, QGraphicsLineItem

from volumina.skeletons.qGraphicsSkeletonNode import QGraphicsSkeletonNode


class SkeletonsLayer(QGraphicsObject):
    def __init__(self, skeletonsLayer3D, axis, scene):
        super(SkeletonsLayer, self).__init__(parent=None)

        self._scene = scene
        self._scene.skeletonAxis = axis
        self._3d = skeletonsLayer3D
        self._axisIntersect = 0
        self._axis = axis

        self._node2view = (
            dict()
        )  # maps from 3D nodes to the QGraphicsItem that represent their projection on this slicing
        self._edge2view = dict()  # maps from edges to the QGraphicsItem that represents the intersection with this edge

    def setAxisIntersect(self, intersect):
        self._axisIntersect = intersect
        # print "SkeletonsLayer(axis=%d) is updating intersect=%d" % (self._axis, self._axisIntersect)

        nodes, eIntersected, ePlane = self._3d._skeletons.intersect(self._axis, self._axisIntersect)

        # update existing items
        toRemove = []
        for node, item in self._node2view.items():
            if node.pos[self._axis] != self._axisIntersect:
                self._scene.removeItem(item)
                toRemove.append(node)
            elif node.pointF(self._axis) != item.pos():
                item.setPos(self._scene.data2scene.map(node.pointF(self._axis)))
            if node.isSelected() != item.isSelected():
                item.setSelected(node.isSelected())
                assert item.isSelected() == node.isSelected()
            i = 0
            newSize = [0, 0]
            for j in range(3):
                if j == self._axis:
                    continue
                newSize[i] = node.shape[j]
                i += 1
            newRectF = QRectF(0, 0, *newSize)
            newRectF = self._scene.data2scene.mapRect(newRectF)

            item.setRect(
                QRectF(
                    old_div(-newRectF.width(), 2.0),
                    old_div(-newRectF.height(), 2.0),
                    newRectF.width(),
                    newRectF.height(),
                )
            )

        for r in toRemove:
            del self._node2view[r]

        # add new views for nodes
        for n in nodes:
            if n in self._node2view:
                continue

            pos2D = list(n.pos)
            del pos2D[self._axis]

            shape2D = n.shape2D(self._axis)
            itm = QGraphicsSkeletonNode(shape2D, skeletons=self._3d._skeletons, node=n)
            itm.setPos(self._scene.data2scene.map(QPointF(*pos2D)))
            itm.setSelected(n.isSelected())

            self._scene.addItem(itm)
            self._node2view[n] = itm

        for itm in list(self._edge2view.values()):
            self._scene.removeItem(itm)
        self._edge2view = dict()

        for e in ePlane:
            l = QLineF(e[0].pointF(), e[1].pointF())

            c1 = e[0].color()
            c2 = e[1].color()
            assert sys.version_info.major == 2, (
                "Alert! This function has not been "
                "tested under python 3. Please remove this assertion and be wary of any "
                "strnage behavior you encounter"
            )
            mixColor = QColor((c1.red() + c2.red()) // 2, (c1.green() + c2.green()) // 2, (c1.blue() + c2.blue()) // 2)

            line = QGraphicsLineItem(self._scene.data2scene.map(l))
            line.setPen(QPen(mixColor))
            self._scene.addItem(line)
            self._edge2view[e] = line

        for theEdge, e in eIntersected:
            c1 = theEdge[0].color()
            c2 = theEdge[1].color()
            assert sys.version_info.major == 2, (
                "Alert! This function has not been "
                "tested under python 3. Please remove this assertion and be wary of any "
                "strnage behavior you encounter"
            )
            mixColor = QColor((c1.red() + c2.red()) // 2, (c1.green() + c2.green()) // 2, (c1.blue() + c2.blue()) // 2)

            nodeSize = 6
            p = QGraphicsRectItem(old_div(-nodeSize, 2), old_div(-nodeSize, 2), nodeSize, nodeSize)
            pos2D = list(e)
            del pos2D[self._axis]
            p.setPos(self._scene.data2scene.map(QPointF(*pos2D)))
            p.setPen(QPen(mixColor))
            self._scene.addItem(p)
            self._edge2view[e] = p

    def update(self):
        self.setAxisIntersect(self._axisIntersect)

    def updateNodeSelecton(self, node):
        pass

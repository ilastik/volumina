from PyQt4.QtCore import QPointF, QRectF, QLineF, Qt
from PyQt4.QtGui import QGraphicsObject, QGraphicsRectItem, QGraphicsLineItem, QPen, QColor

from volumina.skeletons.qGraphicsSkeletonNode import QGraphicsSkeletonNode

class SkeletonsLayer(QGraphicsObject):
    def __init__(self, skeletonsLayer3D, axis, scene):
        super(SkeletonsLayer, self).__init__(parent=None)
        
        self._scene = scene
        self._scene.skeletonAxis = axis
        self._3d = skeletonsLayer3D 
        self._axisIntersect = 0
        self._axis = axis
        
        self._node2view = dict() #maps from 3D nodes to the QGraphicsItem that represent their projection on this slicing
        self._edge2view = dict() #maps from edges to the QGraphicsItem that represents the intersection with this edge
    
    def setAxisIntersect(self, intersect):
        self._axisIntersect = intersect
        #print "SkeletonsLayer(axis=%d) is updating intersect=%d" % (self._axis, self._axisIntersect)
        
        nodes, eIntersected, ePlane = self._3d._skeletons.intersect(self._axis, self._axisIntersect)
       
        #update existing items 
        toRemove = []
        for node, item in self._node2view.iteritems():
            if node.pos[self._axis] != self._axisIntersect:
                self._scene.removeItem(item)
                toRemove.append(node)
            elif node.pointF(self._axis) != item.pos():
                item.setPos( self._scene.data2scene.map( node.pointF(self._axis) ) )
            if node.isSelected() != item.isSelected():
                item.setSelected(node.isSelected())
                assert item.isSelected() == node.isSelected()
            i = 0 
            newSize = [0,0]
            for j in range(3):
                if j == self._axis:
                    continue
                newSize[i] = node.shape[j] 
                i += 1
            newRectF = QRectF(0,0,*newSize)
            newRectF = self._scene.data2scene.mapRect(newRectF)
            
            item.setRect(QRectF(-newRectF.width()/2.0, -newRectF.height()/2.0, newRectF.width(), newRectF.height()))
            
        for r in toRemove:
            del self._node2view[r]
               
        #add new views for nodes 
        for n in nodes:
            if n in self._node2view:
                continue
            
            pos2D = list(n.pos)
            del pos2D[self._axis]

            shape2D = n.shape2D(self._axis)
            itm = QGraphicsSkeletonNode(shape2D, skeletons=self._3d._skeletons, node = n)
            itm.setPos(self._scene.data2scene.map(QPointF(*pos2D)))
            itm.setSelected(n.isSelected())
            
            self._scene.addItem(itm)
            self._node2view[n] = itm

        for itm in self._edge2view.values():
            self._scene.removeItem(itm) 
        self._edge2view = dict()
        
        for e in ePlane:
            l = QLineF(e[0].pointF(), e[1].pointF())

            c1 = e[0].color()
            c2 = e[1].color()
            mixColor = QColor( (c1.red()+c2.red())/2,
                               (c1.green()+c2.green())/2,
                               (c1.blue()+c2.blue())/2 )

            line = QGraphicsLineItem(self._scene.data2scene.map(l))
            line.setPen(QPen(mixColor))
            self._scene.addItem(line)
            self._edge2view[e] = line
            
        for theEdge, e in eIntersected:
            c1 = theEdge[0].color()
            c2 = theEdge[1].color()
            mixColor = QColor( (c1.red()+c2.red())/2,
                               (c1.green()+c2.green())/2,
                               (c1.blue()+c2.blue())/2 )

            nodeSize = 6
            p = QGraphicsRectItem(-nodeSize/2, -nodeSize/2, nodeSize, nodeSize)
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
    

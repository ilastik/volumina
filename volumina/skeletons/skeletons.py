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

from PyQt4.QtCore import QPointF, QObject, pyqtSignal
from PyQt4.QtGui import QGraphicsItem
import numpy, copy

from skeletonNode import SkeletonNode

class Skeletons(QObject):
   
    changed = pyqtSignal()
    jumpRequested = pyqtSignal(object)
    
    SelectExclusive = 1
    SelectAdd       = 2
    
    AutoAddEdge     = 1
    
    def __init__(self):
        super(Skeletons, self).__init__()
        
        self._nodes = []
        self._edges = []
        
        self._selectedNodes = set()
        self._selectedEdges = set()
        
        self._selectMode = Skeletons.SelectExclusive
        self._edgeMode   = Skeletons.AutoAddEdge
    
    def addNode(self, node, interactive=True):
        self._nodes.append(node)
        if not interactive:
            return
        if self._selectMode == Skeletons.SelectExclusive:
            prevNode = list(self._selectedNodes)[0] if len(self._selectedNodes) > 0 else None
            self._unselectAll()
            self._selectNode(node, True)
           
            if prevNode is not None: 
                self._addEdge(prevNode, node)
        else:
            self._selectNode(node, True)
            
        self.jumpRequested.emit(node.pos) 
        self.changed.emit()
        
    def _addEdge(self, nodeA, nodeB): 
        assert nodeA in self._nodes and nodeB in self._nodes
        self._edges.append( (nodeA, nodeB) )
        
    def setNewNodeShape(self, node, axis, shape):
        node.setNewShape(axis, shape)
        self.changed.emit()
    
    def selectNode(self, node, select):
        print "Skeletons.selectNode(node=%r) = %r" % (node, select)
        
        assert node in self._nodes
        if self._selectMode == Skeletons.SelectExclusive:
            for n in copy.copy(self._selectedNodes):
                print "  setting %r to unselected" % (n,)
                self._selectNode(n, False)
                print "  -> n[]id=%d].isSelected() = ", (id(n), n.isSelected())
                
        if select :
            print "  setting %r to select = %r" % (node, select)
            self._selectNode(node, select)
      
        self.jumpRequested.emit(node.pos) 
        self.changed.emit()
        
    def _unselectAll(self):  
        for node in copy.copy(self._selectedNodes):
            self._selectNode(node, False)
        
    def _selectNode(self, node, select):
        if node.isSelected() != select:
            node.setSelected(select)
            if select:
                self._selectedNodes.add(node)
            else:
                self._selectedNodes.remove(node)
       
    def moveNode(self, node, newPos):
        print "Skeletons: node %r moved to %r" % (node, newPos)
        node.pos = newPos
        self.changed.emit()
        
    def selectEdge(self, edge):
        assert edge in self._edges
        self._selectedEdges.add( edge )
    
    def intersect(self, axis, axisIntersect):
        nodes = []
        edgesIntersected = []
        edgesPlane = []
        assert axis in [0,1,2]
        for n in self._nodes:
            if int(n.pos[axis]) == axisIntersect:
                #print "found node", n
                nodes.append(n)
            else:
                pass
                #print "node ", n, "not interesting"
                
        for e in self._edges:
            A = e[0].pos[axis]
            B = e[1].pos[axis]
            if A > B:
                A,B = B,A
            if A < axisIntersect and B > axisIntersect:
                
                #normal vector of plane
                n = numpy.zeros((3,));
                n[axis] = 1
                
                #point lying on plane
                p0 = numpy.zeros((3,))
                p0[axis] = axisIntersect
                
                l0 = numpy.asarray(e[0].pos) 
                l1 = numpy.asarray(e[1].pos) 
                l = l1 - l0
                
                d = numpy.dot(p0-l0, n)/numpy.dot(l,n)
                
                p = d*l + l0
                
                #print "found edge:", e
                edgesIntersected.append( (e, (float(p[0]), float(p[1]), float(p[2]))) )
            elif A == axisIntersect and A == B:
                #print "found edge lying within plane", e
                edgesPlane.append( e )
        
        return (nodes, edgesIntersected, edgesPlane)
        
if __name__ == "__main__":
    from volumina.skeletons.skeletons import Skeletons
    s = Skeletons()
   
    n1 = SkeletonNode( (10,20,30), 2, s)
    n2 = SkeletonNode( (10,20,40), 2, s)
    n3 = SkeletonNode( (15,25,30), 2, s)
    s.addNode(n1)
    s.addNode(n2)
    s.addNode(n3)
    
    s.intersect(2, 30)
    
    print s.intersect(2, 35)
    
    

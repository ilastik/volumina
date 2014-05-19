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
#		   http://ilastik.org/license/
###############################################################################
from PyQt4.QtCore import QPointF, Qt, QRectF
from PyQt4.QtGui import QGraphicsRectItem, QPen, QBrush, QGraphicsItem, QMenu, QColor

#######################################################################################################################
# ResizeHandle                                                                                                        #
#######################################################################################################################

class ResizeHandle(QGraphicsRectItem):
    def __init__(self, node, constrainAxis):
        size = 1
        super(ResizeHandle, self).__init__(-size/2, -size/2, 2*size, 2*size)
        self._node = node
        self._constrainAxis = constrainAxis
        self._hoverOver = False
        if constrainAxis == 1:
            self._offset = QPointF( 0, self._node.shape[1]/2.0 )
        else:
            self._offset = QPointF( self._node.shape[0]/2.0, 0 )
        self.setPos(self._offset)
        
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable);
        
    def hoverEnterEvent(self, event):
        super(ResizeHandle, self).hoverEnterEvent(event)
        event.setAccepted(True)
        self._hoverOver = True
        self._updateColor();

    def hoverLeaveEvent(self, event):
        super(ResizeHandle, self).hoverLeaveEvent(event)
        self._hoverOver = False
        self._updateColor()
        
    def mouseMoveEvent(self, event):
        print "[view=%d] mouse move event constrained to %r" % (self.scene().skeletonAxis, self._constrainAxis)
        super(ResizeHandle, self).mouseMoveEvent(event)
       
        if self.scene().skeletonAxis == 0:
            axes = [2,1] #hack!
        elif self.scene().skeletonAxis == 1:
            axes = [0,2]
        else:
            axes = [0,1]
        print axes
            
        if self._constrainAxis == 0:
            self.setPos(QPointF(self.pos().x(), 0) )
            self._node._skeletons.setNewNodeShape(self._node, axes[self._constrainAxis], 2*self.pos().x())
        else:
            self.setPos(QPointF(0, self.pos().y()) )
            self._node._skeletons.setNewNodeShape(self._node, axes[self._constrainAxis], 2*self.pos().y())
        
    def _updateColor(self):
        if(self._hoverOver):
            self.setBrush(QBrush(Qt.black))
            self.setPen(QPen(Qt.black))
        else:
            self.setBrush(QBrush(Qt.NoBrush))
            self.setPen(QPen(Qt.black))

#######################################################################################################################
# QGraphicsSkeletonNode                                                                                               #
#######################################################################################################################

class QGraphicsSkeletonNode(QGraphicsRectItem):
    def __init__(self, shape2D, skeletons, node):
        from volumina.skeletons import SkeletonNode
        assert isinstance(node, SkeletonNode)
        
        super(QGraphicsSkeletonNode, self).__init__(-shape2D[0]/2, -shape2D[1]/2, shape2D[0], shape2D[1])

        #we manage our selection ourselves instead of using Qt's selection mechanism
        #self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsMovable);
        self.setFlags(QGraphicsItem.ItemIsMovable);
        
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        
        self._skeletons = skeletons
        self._node = node
        
        self._hoverOver = False
        self._selected = False
        self._resizeHandles = []
        
        self._hoverColor    = QColor(145, 160, 255,128)
        self._normalColor   = self._node.color() #QColor(90, 195, 230,128)
        self._selectedColor = QColor(0,255,0,128)
        
        self._updateColor()

    def setRect(self, rect):
        super(QGraphicsSkeletonNode, self).setRect(rect)
        if len(self._resizeHandles) > 0:
            h0 = self._resizeHandles[0]
            h0.setPos(QPointF(rect.width()/2, 0))
            h1 = self._resizeHandles[1]
            h1.setPos(QPointF(0, rect.height()/2))

    def setNewSize(self, constrainAxis, size):
        print constrainAxis, size
        if constrainAxis == 0:
            w, h = 2*size, self.rect().height()
        else:
            w, h = self.rect().width(), 2*size
            
        self.setRect(QRectF(-w/2, -h/2, w, h))

    #we manage our selection ourselves instead of using Qt's selection mechanism
    def setSelected(self, selected):
        self._selected = selected
        super(QGraphicsSkeletonNode, self).setSelected(selected)
        assert self.isSelected() == selected
        self._updateColor()
       
        if self.scene() is None:
            return
        
        if selected: 
            h = ResizeHandle(self._node, 0)
            h.setParentItem(self)
            self._resizeHandles.append( h )
            
            h = ResizeHandle(self._node, 1)
            h.setParentItem(self)
            self._resizeHandles.append( h )
        else:
            for h in self._resizeHandles:
                self.scene().removeItem(h)
            self._resizeHandles = []
    
    def isSelected(self):
        return self._selected

    def _updateColor(self):
        if(self._hoverOver and not self.isSelected()):
            self.setPen(QPen(self._hoverColor))
            self.setBrush(QBrush(self._hoverColor, Qt.SolidPattern))
        elif(self.isSelected()):
            self.setPen(QPen(self._selectedColor))
            self.setBrush(QBrush(self._selectedColor, Qt.SolidPattern))
        else:
            self.setPen(QPen(self._normalColor))
            self.setBrush(QBrush(self._normalColor, Qt.SolidPattern))
    
    def hoverEnterEvent(self, event):
        super(QGraphicsSkeletonNode, self).hoverEnterEvent(event)
        event.setAccepted(True)
        self._hoverOver = True
        self._updateColor();

    def hoverLeaveEvent(self, event):
        super(QGraphicsSkeletonNode, self).hoverLeaveEvent(event)
        self._hoverOver = False
        self._updateColor()

    def mousePressEvent(self, event):
        self._skeletons.selectNode(self._node, not self.isSelected())

    def mouseReleaseEvent(self, event):
        super(QGraphicsSkeletonNode, self).mouseReleaseEvent(event)
        if Qt.RightButton == event.button():
            menu = QMenu("Node")
            deleteAction = menu.addAction("&Delete")
            
            result = menu.exec_(event.screenPos())
            if result == deleteAction:
                print "want to delete" 
                #FIXME: Implement

    def mouseMoveEvent(self, event):
        if not self._node.isMovable():
            return

        super(QGraphicsSkeletonNode, self).mouseMoveEvent(event)
        
        dataPos = self.scene().scene2data.map(event.scenePos())
        
        pos = [dataPos.x(), dataPos.y()]
        pos.insert(self.scene().skeletonAxis, self._node.pos[self.scene().skeletonAxis])
        
        if not self.isSelected():
            self._skeletons.selectNode(self._node, True)
        
        self._skeletons.moveNode(self._node, pos)

    def mouseDoubleClickEvent(self, event):
        print "DOUBLE CLICK ON NODE"
        #FIXME: Implement me
        event.accept()

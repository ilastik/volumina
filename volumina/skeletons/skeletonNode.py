from PyQt4.QtCore import QPointF

class SkeletonNode:
    def __init__(self, pos3D, axis, skeletons):
        from volumina.skeletons import Skeletons
        assert isinstance(skeletons, Skeletons)
        
        assert len(pos3D) == 3
        self.pos = pos3D
        self.shape = [6,6,6]
        self.axis = axis
        self._skeletons = skeletons
        self._selected = False
    
    def __str__(self):
        return "SkeletonNode(pos=%r, axis=%r)" % (self.pos, self.axis)

    def __repr__(self):
        return "SkeletonNode(pos=%r, axis=%r)" % (self.pos, self.axis)

    def move(self, pos):
        self.pos = pos
        
    def intersectsBbox(self, point):
        assert len(point) == 3
        for i in range(3):
            if not (self.pos[i] - self.shape/2.0 >= point[i] and self.pos[i] + self.shape/2.0 <= point[i]):
                return False 
        return True

    def shape2D(self, axis):
        shape = list(self.shape)
        del shape[axis]
        return shape
    
    def setNewShape(self, axis, newShape):
        self.shape[axis] = newShape

    def pointF(self, axis=None):
        if axis is None:
            axis = self.axis
        pos2D = list(self.pos)
        del pos2D[axis]
        return QPointF(*pos2D)

    def setSelected(self, selected):
        if self._selected == selected:
            return
        self._selected = selected

    def isSelected(self):
        return self._selected

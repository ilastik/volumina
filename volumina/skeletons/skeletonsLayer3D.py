from PyQt4.QtCore import QObject

from volumina.skeletons.skeletons3D import Skeletons3D
from volumina.skeletons.skeletonsLayer import SkeletonsLayer
from volumina.skeletons.skeletonNode import SkeletonNode

class SkeletonsLayer3D(QObject):
    def __init__(self, editor, skeletons, parent=None):
        super(SkeletonsLayer3D, self).__init__(parent=parent)
        editor.posModel.slicingPositionChanged.connect(self.onSlicingPositionChanged)
        
        #skeletons.nodePositionChanged.connect(self.onNodePositionChanged) 
        #skeletons.nodeSelectionChanged.connect(self.onNodeSelectionChanged) 
        
        skeletons.changed.connect(self.update)
        def onJumpRequested(pos):
            editor.posModel.slicingPos = pos
        skeletons.jumpRequested.connect(onJumpRequested)
        
        self._skeletons = skeletons
        self._layers = []
        
        self._skeletons3D = Skeletons3D(skeletons, editor.view3d)
        
        for i in range(3):
            self._layers.append( SkeletonsLayer(self, i, editor.imageScenes[i]) )
        
    def onNodePositionChanged(self, node):
        pass
    
    def onNodeSelectionChanged(self, node):
        print "XXXXXXXXXXXXXXX selection changed for node=%r to %r" % (node, node.isSelected())
        for l in self._layers:
            l.update()
        pass
    
    def addNode(self, pos, axis):
        n = SkeletonNode(pos, axis, self._skeletons)
        self._skeletons.addNode(n)

    def update(self):
        for l in self._layers:
            l.update()
        self._skeletons3D.update()
        
    def onSlicingPositionChanged(self, newPos, oldPos):
        for i in range(3):
            if newPos[i] != oldPos[i]:
                self._layers[i].setAxisIntersect( newPos[i] )
                
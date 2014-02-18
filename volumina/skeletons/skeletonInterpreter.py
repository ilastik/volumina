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

from PyQt4.QtCore import QObject, QEvent, Qt
import copy

from volumina.skeletons.skeletonsLayer3D import SkeletonsLayer3D

class SkeletonInterpreter(QObject):
       
    def __init__(self, editor, skeletons, parent=None):
        QObject.__init__(self, parent=parent)
        self.baseInterpret = editor.navInterpret
        self.posModel      = editor.posModel
        self.editor = editor
       
        self._vl = SkeletonsLayer3D(self.editor, skeletons)
        
        self._scene2axis = {}
        for i in range(3):
            self._scene2axis[ self.editor.imageScenes[i] ] = i
        
    def start( self ):
        self.baseInterpret.start()

    def stop( self ):
        self.baseInterpret.stop()
        
    def _pos(self):
        pos = self.posModel.cursorPos
        pos = [int(i) for i in pos]
        pos = [self.posModel.time] + pos + [self.posModel.channel]
        return pos

    def eventFilter( self, watched, event ):
        etype = event.type()
        if etype == QEvent.MouseButtonPress or etype == QEvent.MouseButtonDblClick:
            leftButton  = (event.button() == Qt.LeftButton)

            if leftButton and etype == QEvent.MouseButtonPress:
                if len(self.baseInterpret._itemsAt(watched, event.pos())) == 0:
                    axis = self._scene2axis[watched.scene()]
                    scene = watched.scene()
                    dataPos = scene.scene2data.map(event.pos())
                    pos2D = copy.copy(self.posModel.cursorPos)
                    del pos2D[axis]
                    print "add node at data coor=%r, axis=%d, pos2D=%r" % (dataPos, axis, pos2D) 
                    self._vl.addNode(self.posModel.cursorPos, axis)
                    return True
        
        return self.baseInterpret.eventFilter(watched, event)
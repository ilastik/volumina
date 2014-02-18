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

import os

from PyQt4 import uic
from PyQt4.QtGui import QWidget

class SlotMetaInfoDisplayWidget(QWidget):
    """
    Simple display widget for a slot's meta-info (shape, axes, dtype).
    """
    
    def __init__(self, parent):
        super( SlotMetaInfoDisplayWidget, self ).__init__(parent)
        uic.loadUi(os.path.splitext(__file__)[0] + '.ui', self)
    
    def initSlot(self, slot):
        self._slot = slot
        slot.notifyMetaChanged( self._refresh )
        if slot.ready():
            self._refresh()
    
    def _refresh(self, *args):
        if self._slot.ready():
            shape = tuple( self._slot.meta.shape )
            axes = "".join( self._slot.meta.getAxisKeys() )
            dtype = self._slot.meta.dtype.__name__
        else:
            shape = axes = dtype = ""

        self.shapeEdit.setText( str(shape) )
        self.axisOrderEdit.setText( axes )
        self.dtypeEdit.setText( dtype )

if __name__ == "__main__":
    import numpy
    import vigra
    from PyQt4.QtGui import QApplication
    from lazyflow.graph import Graph
    from lazyflow.operators import OpArrayCache

    data = numpy.zeros( (10,20,30,3), dtype=numpy.float32 )
    data = vigra.taggedView(data, 'zyxc')

    op = OpArrayCache(graph=Graph())
    op.Input.setValue( data )

    app = QApplication([])
    w = SlotMetaInfoDisplayWidget(None)
    w.initSlot(op.Output)
    w.show()
    app.exec_()


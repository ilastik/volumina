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


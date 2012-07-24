import unittest as ut
import numpy as np
from PyQt4.QtGui import QApplication
from PyQt4.QtCore import QPointF
from volumina.brushingmodel import BrushingModel

app = QApplication([], False)
def _onBrushStroke( point, labels  ):
    print point.x(), point.y()
    print labels.shape

class BrushingModelTest( ut.TestCase ):
    def _checkBrushSize( self, size, should_diameter ):
        m = BrushingModel()

        def check( point, labels ):
            self.assertEqual(max((np.count_nonzero(labels[row,:]) for row in xrange(labels.shape[0]))), should_diameter)
            self.assertEqual(max((np.count_nonzero(labels[col,:]) for col in xrange(labels.shape[1]))), should_diameter)
        m.setBrushSize( size )
        m.brushStrokeAvailable.connect( check )
        m.beginDrawing( QPointF(size*2,size*2), (size*3,size*3) )
        m.endDrawing( QPointF(size*2, size*2) )


    def testBrushSizes( self ):
        self._checkBrushSize( 0, 1 )
        self._checkBrushSize( 0.7, 1 )
        self._checkBrushSize( 2.1, 2 )
        for i in range(1,20):
            self._checkBrushSize( i, i )

if __name__=='__main__':
    ut.main()

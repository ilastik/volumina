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

import unittest as ut
import numpy as np
from PyQt4.QtGui import QApplication, qApp
from PyQt4.QtCore import QPointF
from volumina.brushingmodel import BrushingModel

def _onBrushStroke( point, labels  ):
    print point.x(), point.y()
    print labels.shape

class BrushingModelTest( ut.TestCase ):

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([], False)

    @classmethod
    def tearDownClass(cls):
        del cls.app
    
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

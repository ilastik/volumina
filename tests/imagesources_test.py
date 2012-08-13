import unittest as ut
import sys
sys.path.append("../.")

import numpy
import os.path

from PyQt4.QtCore import QRect, pyqtSignal
from PyQt4.QtGui import QImage
from PyQt4.QtGui import QColor

import volumina._testing
from volumina.pixelpipeline.imagesources import GrayscaleImageSource, RGBAImageSource, ColortableImageSource
from volumina.pixelpipeline.datasources import ConstantSource, ArraySource
from volumina.layer import GrayscaleLayer, RGBALayer, ColortableLayer



class _ArraySource2d( ArraySource ):
    idChanged = pyqtSignal( object, object )

    def __init__( self, array ):
        super(_ArraySource2d, self).__init__( array )
        self.id = id(self)


#*******************************************************************************
# G r a y s c a l e I m a g e S o u r c e T e s t 
#*******************************************************************************
        
class GrayscaleImageSourceTest( ut.TestCase ):
    def setUp( self ):
        self.raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy'))
        self.ars = _ArraySource2d(self.raw)
        self.ims = GrayscaleImageSource( self.ars, GrayscaleLayer( self.ars ))

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        def check(result, codon):
            self.assertEqual(codon, "unique")
            self.assertTrue(type(result) == QImage)
        imr.notify(check, codon="unique")

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 12 )
            self.assertEqual( rect.y(), 34 )
            self.assertEqual( rect.width(), 22 )
            self.assertEqual( rect.height(), 3  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )


#*******************************************************************************
# C o l o r t a b l e I m a g e S o u r c e T e s t 
#*******************************************************************************
        
class ColortableImageSourceTest( ut.TestCase ):
    def setUp( self ):
        self.seg = numpy.zeros((6,7), dtype=numpy.uint32) 
        self.seg[0:2,:] = 0
        self.seg[2:4,:] = 1
        self.seg[4:6,:] = 2
        self.ars = _ArraySource2d(self.seg)
        self.ctable = [QColor(255,0,0).rgba(), QColor(0,255,0).rgba(), QColor(0,0,255).rgba()]
        self.layer = ColortableLayer(self.ars, self.ctable)
        self.ims = ColortableImageSource( self.ars, self.layer )

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        def check(result, codon):
            self.assertEqual(codon, "unique")
            self.assertTrue(type(result) == QImage)
            img = QImage(7,6, QImage.Format_ARGB32)
            for i in range(7):
                img.setPixel(i, 0, QColor(255,0,0).rgba())
                img.setPixel(i, 1, QColor(255,0,0).rgba())

                img.setPixel(i, 2, QColor(0,255,0).rgba())
                img.setPixel(i, 3, QColor(0,255,0).rgba())

                img.setPixel(i, 4, QColor(0,0,255).rgba())
                img.setPixel(i, 5, QColor(0,0,255).rgba())
            assert img.size() == result.size()
            assert img == result

        imr.notify(check, codon="unique")

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 12 )
            self.assertEqual( rect.y(), 34 )
            self.assertEqual( rect.width(), 22 )
            self.assertEqual( rect.height(), 3  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )

#*******************************************************************************
# R G B A I m a g e S o u r c e T e s t                                        *
#*******************************************************************************

class RGBAImageSourceTest( ut.TestCase ):
    def setUp( self ):
        import numpy as np
        import os.path
        from volumina import _testing
        basedir = os.path.dirname(_testing.__file__)
        self.data = np.load(os.path.join(basedir, 'rgba129x104.npy'))
        self.red = _ArraySource2d(self.data[:,:,0])
        self.green = _ArraySource2d(self.data[:,:,1])
        self.blue = _ArraySource2d(self.data[:,:,2])
        self.alpha = _ArraySource2d(self.data[:,:,3])

        self.ims_rgba = RGBAImageSource( self.red, self.green, self.blue, self.alpha, RGBALayer( self.red, self.green, self.blue, self.alpha) )
        self.ims_rgb = RGBAImageSource( self.red, self.green, self.blue, ConstantSource(), RGBALayer(self.red, self.green, self.blue) )
        self.ims_rg = RGBAImageSource( self.red, self.green, ConstantSource(), ConstantSource(), RGBALayer(self.red, self.green ) )
        self.ims_ba = RGBAImageSource( red = ConstantSource(), green = ConstantSource(), blue = self.blue, alpha = self.alpha, layer = RGBALayer( blue = self.blue, alpha = self.alpha ) )
        self.ims_a = RGBAImageSource( red = ConstantSource(), green = ConstantSource(), blue = ConstantSource(), alpha = self.alpha, layer = RGBALayer( alpha = self.alpha ) )
        self.ims_none = RGBAImageSource( ConstantSource(),ConstantSource(),ConstantSource(),ConstantSource(), RGBALayer())
        
    def testRgba( self ):
        img = self.ims_rgba.request(QRect(0,0,129,104)).wait()
        #img.save('rgba.tif')

    def testRgb( self ):
        img = self.ims_rgb.request(QRect(0,0,129,104)).wait()
        #img.save('rgb.tif')

    def testRg( self ):
        img = self.ims_rg.request(QRect(0,0,129,104)).wait()
        #img.save('rg.tif')

    def testBa( self ):
        img = self.ims_ba.request(QRect(0,0,129,104)).wait()
        #img.save('ba.tif')

    def testA( self ):
        img = self.ims_a.request(QRect(0,0,129,104)).wait()
        #img.save('a.tif')

    def testNone( self ):
        img = self.ims_none.request(QRect(0,0,129,104)).wait()
        #img.save('none.tif')

    def testOpaqueness( self ):
        ims_opaque = RGBAImageSource( self.red, self.green, self.blue, ConstantSource(), RGBALayer(self.red, self.green, self.blue, alpha_missing_value = 255), guarantees_opaqueness = True )
        self.assertTrue( ims_opaque.isOpaque() )
        ims_notopaque = RGBAImageSource( self.red, self.green, self.blue, ConstantSource(), RGBALayer(self.red, self.green, self.blue, alpha_missing_value = 100) )
        self.assertFalse( ims_notopaque.isOpaque() )
        

#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == '__main__':
    ut.main()

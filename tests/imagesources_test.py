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
#Python
from future import standard_library
standard_library.install_aliases()
from builtins import range
import unittest as ut
import os
import sys
sys.path.append("../.")

#SciPy
import numpy

#PyQt
from PyQt5.QtCore import QRect
from PyQt5.QtGui import QImage, QColor
from PyQt5.QtWidgets import QGraphicsItem

import qimage2ndarray

#volumina
import volumina._testing
from volumina.pixelpipeline.imagesources import GrayscaleImageSource, AlphaModulatedImageSource, RGBAImageSource, \
    ColortableImageSource, DummyItemSource
from volumina.pixelpipeline.datasources import ConstantSource, ArraySource
from volumina.layer import GrayscaleLayer, AlphaModulatedLayer, RGBALayer, ColortableLayer

import threading
imagesources_thread_failures = 0
def install_thread_excepthook():
    # This function was copied from: http://bugs.python.org/issue1230540
    # It is necessary because sys.excepthook doesn't work for unhandled exceptions in other threads.
    """
    Workaround for sys.excepthook thread bug
    (https://sourceforge.net/tracker/?func=detail&atid=105470&aid=1230540&group_id=5470).
    Call once from __main__ before creating any threads.
    If using psyco, call psycho.cannotcompile(threading.Thread.run)
    since this replaces a new-style class method.
    """
    run_old = threading.Thread.run
    def run(*args, **kwargs):
        try:
            run_old(*args, **kwargs)
        except (KeyboardInterrupt, SystemExit):
            raise
        except:
            sys.excepthook(*sys.exc_info())
            
            # Remember that this exception occurred.
            global imagesources_thread_failures
            imagesources_thread_failures += 1
            
    threading.Thread.run = run

install_thread_excepthook()

class _ArraySource2d( ArraySource ):
    def request( self, slicing, through=None):
        return super(_ArraySource2d, self).request( slicing )

class ImageSourcesTestBase( ut.TestCase ):
    """
    A common base class for all ImageSource tests.
    Implements a tearDown() method that checks for exceptions in non-main threads.
    """
    def setUp(self):
        global imagesources_thread_failures
        imagesources_thread_failures = 0
        self._my_thread = threading.current_thread()
    
    def tearDown(self):
        # Block for all other (non-daemon) threads to complete so we 
        #  catch any exceptions they caught before we exit.
        for thread in threading.enumerate():
            if thread != threading.current_thread() and not thread.daemon:
                thread.join()
        
        # Check to see if this test caused any exceptions in other threads.
        global imagesources_thread_failures
        if imagesources_thread_failures != 0:
            sys.stderr.write( "\nFAILURE: Uncaught exception in non-main thread during test: {}\n".format( self.id() ) )
        self.assertTrue( imagesources_thread_failures == 0 ) # Check for exceptions in other threads.

#*******************************************************************************
# G r a y s c a l e I m a g e S o u r c e T e s t 
#*******************************************************************************
        
class GrayscaleImageSourceTest( ImageSourcesTestBase ):
    def setUp( self ):
        super( GrayscaleImageSourceTest, self ).setUp()
        self.raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy')).astype( numpy.uint32 )
        self.ars = _ArraySource2d(self.raw)
        self.ims = GrayscaleImageSource( self.ars, GrayscaleLayer( self.ars ))

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        result = imr.wait()
        self.assertTrue(type(result) == QImage)

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )

class GrayscaleImageSourceTest2( ImageSourcesTestBase ):
    def setUp( self ):
        super( GrayscaleImageSourceTest2, self ).setUp()
        self.raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy')).astype( numpy.uint32 )
        self.raw = numpy.ma.masked_array(self.raw, numpy.zeros(self.raw.shape, dtype=bool), shrink=False)

        self.raw[:10, :] = numpy.ma.masked
        self.raw[-10:, :] = numpy.ma.masked
        self.raw[:, :10] = numpy.ma.masked
        self.raw[:, -10:] = numpy.ma.masked

        self.ars = _ArraySource2d(self.raw)
        self.ims = GrayscaleImageSource( self.ars, GrayscaleLayer( self.ars ))

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        result = imr.wait()
        self.assertTrue(type(result) == QImage)

        result_array = qimage2ndarray.byte_view(result)

        assert((result_array[:10, :, -1] == 255).all())
        assert((result_array[-10:, :, -1] == 255).all())
        assert((result_array[:, :10, -1] == 255).all())
        assert((result_array[:, -10:, -1] == 255).all())

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )

#*******************************************************************************
# A l p h a M o d u l a t e d I m a g e S o u r c e T e s t
#*******************************************************************************

class AlphaModulatedImageSourceTest( ImageSourcesTestBase ):
    def setUp( self ):
        super( AlphaModulatedImageSourceTest, self ).setUp()
        self.raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy')).astype( numpy.uint32 )
        self.ars = _ArraySource2d(self.raw)
        self.ims = AlphaModulatedImageSource( self.ars, AlphaModulatedLayer( self.ars, QColor(1,2,3) ))

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        result = imr.wait()
        self.assertTrue(type(result) == QImage)

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )

class AlphaModulatedImageSourceTest2( ImageSourcesTestBase ):
    def setUp( self ):
        super( AlphaModulatedImageSourceTest2, self ).setUp()
        self.raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy')).astype( numpy.uint32 )

        self.raw = numpy.ma.masked_array(self.raw, mask=numpy.zeros(self.raw.shape, dtype=bool), shrink=False)
        self.raw[:1, :] = numpy.ma.masked
        self.raw[-1:, :] = numpy.ma.masked
        self.raw[:, :1] = numpy.ma.masked
        self.raw[:, -1:] = numpy.ma.masked

        self.ars = _ArraySource2d(self.raw)
        self.ims = AlphaModulatedImageSource( self.ars, AlphaModulatedLayer( self.ars, QColor(1,2,3) ))

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        result = imr.wait()
        self.assertTrue(type(result) == QImage)

        result_view = qimage2ndarray.byte_view(result)
        if sys.byteorder == "little":
            self.assertTrue((result_view[:1, :, 3] == 0).all())
            self.assertTrue((result_view[-1:, :, 3] == 0).all())
            self.assertTrue((result_view[:, :1, 3] == 0).all())
            self.assertTrue((result_view[:, -1:, 3] == 0).all())
        else:
            self.assertTrue((result_view[:1, :, 0] == 0).all())
            self.assertTrue((result_view[-1:, :, 0] == 0).all())
            self.assertTrue((result_view[:, :1, 0] == 0).all())
            self.assertTrue((result_view[:, -1:, 0] == 0).all())

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

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
        
class ColortableImageSourceTest( ImageSourcesTestBase ):
    def setUp( self ):
        if 'TRAVIS' in os.environ:
            # Colortable requests require vigra, which is not installed on our Travis-CI build.
            # Skip this test on Travis-CI.
            import nose
            raise nose.SkipTest

        super( ColortableImageSourceTest, self ).setUp()
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
        result = imr.wait()
        
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

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

        # should mark everything dirty
        self.ims.isDirty.connect( checkAllDirty )
        self.ims.setDirty((slice(34,None), slice(12,34)))
        self.ims.isDirty.disconnect( checkAllDirty )

        # dirty subrect
        self.ims.isDirty.connect( checkDirtyRect )
        self.ims.setDirty((slice(34,37), slice(12,34)))
        self.ims.isDirty.disconnect( checkDirtyRect )

class ColortableImageSourceTest2( ImageSourcesTestBase ):
    def setUp( self ):
        if 'TRAVIS' in os.environ:
            # Colortable requests require vigra, which is not installed on our Travis-CI build.
            # Skip this test on Travis-CI.
            import nose
            raise nose.SkipTest

        super( ColortableImageSourceTest2, self ).setUp()
        self.seg = numpy.zeros((6,7), dtype=numpy.uint32)
        self.seg = numpy.ma.masked_array(self.seg, mask=numpy.zeros(self.seg.shape, dtype=bool), shrink=False)
        self.seg[0:2,:] = 0
        self.seg[1,:] = numpy.ma.masked
        self.seg[2:4,:] = 1
        self.seg[3,:] = numpy.ma.masked
        self.seg[4:6,:] = 2
        self.seg[5,:] = numpy.ma.masked
        self.ars = _ArraySource2d(self.seg)
        self.ctable = [QColor(255,0,0).rgba(), QColor(0,255,0).rgba(), QColor(0,0,255).rgba()]
        self.layer = ColortableLayer(self.ars, self.ctable)
        self.ims = ColortableImageSource( self.ars, self.layer )

    def testRequest( self ):
        imr = self.ims.request(QRect(0,0,512,512))
        result = imr.wait()

        self.assertTrue(type(result) == QImage)
        img = QImage(7,6, QImage.Format_ARGB32)
        for i in range(7):
            img.setPixel(i, 0, QColor(255,0,0,255).rgba())
            img.setPixel(i, 1, QColor(0,0,0,0).rgba())

            img.setPixel(i, 2, QColor(0,255,0,255).rgba())
            img.setPixel(i, 3, QColor(0,0,0,0).rgba())

            img.setPixel(i, 4, QColor(0,0,255,255).rgba())
            img.setPixel(i, 5, QColor(0,0,0,0).rgba())

        assert img.size() == result.size()
        assert img == result

    def testSetDirty( self ):
        def checkAllDirty( rect ):
            self.assertTrue( rect.isEmpty() )

        def checkDirtyRect( rect ):
            self.assertEqual( rect.x(), 34 )
            self.assertEqual( rect.y(), 12 )
            self.assertEqual( rect.width(), 3 )
            self.assertEqual( rect.height(), 22  )

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

class RGBAImageSourceTest( ImageSourcesTestBase ):
    def setUp( self ):
        super( RGBAImageSourceTest, self ).setUp()
        basedir = os.path.dirname(volumina._testing.__file__)
        self.data = numpy.load(os.path.join(basedir, 'rgba129x104.npy'))
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
        img = self.ims_rgba.request(QRect(0,0,104,129)).wait()
        #img.save('rgba.tif')

    def testRgb( self ):
        img = self.ims_rgb.request(QRect(0,0,104,129)).wait()
        #img.save('rgb.tif')

    def testRg( self ):
        img = self.ims_rg.request(QRect(0,0,104,129)).wait()
        #img.save('rg.tif')

    def testBa( self ):
        img = self.ims_ba.request(QRect(0,0,104,129)).wait()
        #img.save('ba.tif')

    def testA( self ):
        img = self.ims_a.request(QRect(0,0,104,129)).wait()
        #img.save('a.tif')

    def testNone( self ):
        img = self.ims_none.request(QRect(0,0,104,129)).wait()
        #img.save('none.tif')

    def testOpaqueness( self ):
        ims_opaque = RGBAImageSource( self.red, self.green, self.blue, ConstantSource(), RGBALayer(self.red, self.green, self.blue, alpha_missing_value = 255), guarantees_opaqueness = True )
        self.assertTrue( ims_opaque.isOpaque() )
        ims_notopaque = RGBAImageSource( self.red, self.green, self.blue, ConstantSource(), RGBALayer(self.red, self.green, self.blue, alpha_missing_value = 100) )
        self.assertFalse( ims_notopaque.isOpaque() )
    
class TestGraphicsItems(ut.TestCase):
    
    def test(self):
        raw = numpy.load(os.path.join(volumina._testing.__path__[0], 'lena.npy')).astype( numpy.uint32 )
        ars = _ArraySource2d(raw)
        ims = DummyItemSource(ars)
        req = ims.request( QRect( 0, 0, 256, 256 ) )
        item = req.wait()
        assert isinstance(item, QGraphicsItem)

        DEBUG = False
        if DEBUG:        
            from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene
            app = QApplication([])
            scene = QGraphicsScene()
            scene.addItem(item)
            view = QGraphicsView(scene)
            view.show()
            view.raise_()         
            app.exec_()
        
#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == '__main__':
    ut.main()

import unittest as ut
import os
import time, datetime

from PyQt4.QtGui import QImage, QPainter, QApplication, QPicture

from qimage2ndarray import byte_view
import numpy as np

from volumina.imageScene2D import ImageScene2D, DirtyIndicator
from volumina.positionModel import PositionModel
from volumina.pixelpipeline.datasources import ConstantSource
from volumina.pixelpipeline.imagepump import StackedImageSources
from volumina.tiling import Tiling
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
import volumina.pixelpipeline.imagesourcefactories as imsfac

class DirtyIndicatorTest( ut.TestCase ):
    @classmethod
    def setUpClass(cls):
        cls.app = None
        if QApplication.instance():
            cls.app = QApplication.instance()
        else:
            cls.app = QApplication([], False)

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def testPaintDelay( self ):
        t = Tiling((100, 100))
        assert( len(t.tileRectFs) == 1 )

        delay=datetime.timedelta(milliseconds=300)
        # fudge should prevent hitting the delay time exactly
        # during the while loops below;
        # if your computer is verrry slow and the fudge too small
        # the test will fail...
        fudge=datetime.timedelta(milliseconds=50)
        d = DirtyIndicator( t, delay=delay )

        # make the image a little bit larger to accomodate the tile overlap
        img = QImage(110,110,QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        img_saved = QImage(img)

        painter = QPainter()

        start = datetime.datetime.now()
        d.setTileProgress( 0, 0 ) # resets delay timer

        # 1. do not update the progress during the delay time
        actually_checked = False
        while( datetime.datetime.now() - start < delay - fudge ):
            # nothing should be painted
            self.assertEqual( img, img_saved )
            actually_checked = True
        self.assertTrue(actually_checked)
        time.sleep(fudge.total_seconds()*2)
        # after the delay, the pie chart is painted
        painter.begin(img)
        d.paint( painter, None, None )
        self.assertNotEqual( img, img_saved )
        painter.end()

        # 2. update the progress during delay (this exposed a bug:
        #    the delay was ignored in that case and the pie chart
        #    painted nevertheless)
        img.fill(0)
        start = datetime.datetime.now()
        d.setTileProgress( 0, 0 ) # resets delay timer

        actually_checked = False
        while( datetime.datetime.now() - start < delay - fudge ):
            # the painted during the delay time should have no effect
            painter.begin(img)
            d.setTileProgress( 0, 0.5 )
            d.paint( painter, None, None )
            painter.end()
            self.assertEqual( img, img_saved )
            actually_checked = True
        self.assertTrue(actually_checked)
        time.sleep(fudge.total_seconds()*2)
        # now the pie should be painted
        painter.begin(img)
        d.paint( painter, None, None )
        self.assertNotEqual( img, img_saved )
        painter.end()

class ImageScene2DTest( ut.TestCase ):

    @classmethod
    def setUpClass(cls):
        cls.app = None
        if QApplication.instance():
            cls.app = QApplication.instance()
        else:
            cls.app = QApplication([], False)

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def testStackedImageSourcesProperty( self ):
        s = ImageScene2D(PositionModel(), (0,3,4), preemptive_fetch_number=0)
        self.assertEqual(len(s.stackedImageSources), 0)

        sims = StackedImageSources( LayerStackModel() )
        s.stackedImageSources = sims
        self.assertEqual(id(s.stackedImageSources), id(sims))

class ImageScene2D_RenderTest( ut.TestCase ):

    @classmethod
    def setUpClass(cls):
        cls.app = None
        if QApplication.instance():
            cls.app = QApplication.instance()
        else:
            cls.app = QApplication([], False)

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def setUp( self ):
        self.layerstack = LayerStackModel()
        self.sims = StackedImageSources( self.layerstack )

        self.GRAY = 201
        self.ds = ConstantSource(self.GRAY)
        self.layer = GrayscaleLayer( self.ds )
        self.layer.set_normalize(0, False)
        self.layerstack.append(self.layer)
        self.ims = imsfac.createImageSource( self.layer, [self.ds] )
        self.sims.register(self.layer, self.ims)

        self.scene = ImageScene2D(PositionModel(), (0,3,4), preemptive_fetch_number=0)

        self.scene.stackedImageSources = self.sims
        self.scene.dataShape = (310,290)

    def tearDown( self ):
        if self.scene._tileProvider:
            self.scene._tileProvider.notifyThreadsToStop()
            self.scene._tileProvider.joinThreads()

    def renderScene( self, s, exportFilename=None):
        img = QImage(310,290,QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        s.render(p)
        s.joinRendering()
        s.render(p)
        p.end()
        if exportFilename is not None:
            img.save(exportFilename)
        return byte_view(img)

    def testBasicImageRenderingCapability( self ):
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:,:,3] == 255))

    def testToggleVisibilityOfOneLayer( self ):
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:,:,3] == 255))

        self.layer.visible = False
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == 0)) # all white
        self.assertTrue(np.all(aimg[:,:,3] == 0))

        self.layer.visible = True
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:,:,3] == 255))

if __name__ == '__main__':
    ut.main()

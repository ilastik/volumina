import unittest as ut
import sys, os
sys.path.append("../.")

from PyQt4.QtGui import QImage, QPainter, QApplication
from PyQt4.QtCore import QRect

from qimage2ndarray import byte_view
import numpy as np

from volumina.imageScene2D import ImageScene2D
from volumina.pixelpipeline.datasources import ConstantSource
from volumina.pixelpipeline.imagepump import StackedImageSources
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
import volumina.pixelpipeline.imagesourcefactories as imsfac

class ImageScene2DTest( ut.TestCase ):
    def setUp( self ):
        self.app = QApplication([], False)

    @ut.skipIf(os.getenv('TRAVIS'), 'fails on TRAVIS CI due to unknown reasons')
    def testToggleVisibilityOfOneLayer( self ):
        layerstack = LayerStackModel()
        sims = StackedImageSources( layerstack )

        GRAY = 201
        ds = ConstantSource(GRAY)
        layer = GrayscaleLayer( ds )
        layerstack.append(layer)
        ims = imsfac.createImageSource( layer, [ds] )
        sims.register(layer, ims)
        
        scene = ImageScene2D(self.app) 
        scene.stackedImageSources = sims
        scene.sceneShape = (310,290)

        def renderScene(s):
            img = QImage(310,290,QImage.Format_ARGB32_Premultiplied)
            p = QPainter(img)
            s.render(p)
            p.end()
            return byte_view(img)

        aimg = renderScene(scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == GRAY))
        self.assertTrue(np.all(aimg[:,:,3] == 255))

        layer.visible = False
        aimg = renderScene(scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == 255)) # all white
        self.assertTrue(np.all(aimg[:,:,3] == 255))

        layer.visible = True
        aimg = renderScene(scene)
        self.assertTrue(np.all(aimg[:,:,0:3] == GRAY))
        self.assertTrue(np.all(aimg[:,:,3] == 255))

        scene._renderThread.stop()

    def tearDown( self ):
        self.app.quit()

if __name__ == '__main__':
    ut.main()

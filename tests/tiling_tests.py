import unittest as ut
import numpy as np
from PyQt4.QtCore import QRectF
from PyQt4.QtGui import QTransform, qApp
from qimage2ndarray import byte_view

from volumina.tiling import TileProvider, Tiling
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
from volumina.pixelpipeline.datasources import ConstantSource
from volumina.pixelpipeline.imagesources import GrayscaleImageSource
from volumina.pixelpipeline.imagepump import StackedImageSources



class TileProviderTest( ut.TestCase ):
    def setUp( self ):
        self.GRAY1 = 60
        self.ds1 = ConstantSource( self.GRAY1 )

        self.GRAY2 = 120
        self.ds2 = ConstantSource( self.GRAY2 )

        self.GRAY3 = 190
        self.ds3 = ConstantSource( self.GRAY3 )

        self.layer1 = GrayscaleLayer( self.ds1 )
        self.layer1.visible = False
        self.layer1.opacity = 0.1
        self.ims1 = GrayscaleImageSource( self.ds1, self.layer1 )
        self.layer2 = GrayscaleLayer( self.ds2 )
        self.layer2.visible = True
        self.layer2.opacity = 0.3
        self.ims2 = GrayscaleImageSource( self.ds2, self.layer2 )
        self.layer3 = GrayscaleLayer( self.ds3 ) 
        self.layer3.visible = True
        self.layer3.opacity = 1.0
        self.ims3 = GrayscaleImageSource( self.ds3, self.layer3 )

        lsm = LayerStackModel()
        lsm.append(self.layer1)
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        self.lsm = lsm
        sims = StackedImageSources( lsm )
        sims.register( self.layer1, self.ims1 )
        sims.register( self.layer2, self.ims2 )
        sims.register( self.layer3, self.ims3 )
        self.sims = sims

    def testSetAllLayersInvisible( self ):
        tiling = Tiling((900,400), blockSize=100)
        tp = TileProvider(tiling, self.sims)
        try:
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == self.GRAY3))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            self.layer1.visible = False
            self.layer2.visible = False
            self.layer3.visible = False
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == 255)) # all white
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            self.layer1.visible = False
            self.layer2.visible = True
            self.layer2.opacity = 1.0
            self.layer3.visible = False
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == self.GRAY2))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

        finally:
            tp.notifyThreadsToStop()
        


if __name__=='__main__':
    ut.main()

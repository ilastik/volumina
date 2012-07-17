import unittest as ut
from PyQt4.QtCore import QRectF
from PyQt4.QtGui import QTransform

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

    def test( self ):
        lsm = LayerStackModel()
        lsm.append(self.layer1)
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        sims = StackedImageSources( lsm )
        sims.register( self.layer1, self.ims1 )
        sims.register( self.layer2, self.ims2 )
        sims.register( self.layer3, self.ims3 )
        tiling = Tiling((941,497), QTransform(0,1,1,0,0,0) )

        try:
            tp = TileProvider(tiling, sims)
            tiles = tp.getTiles(QRectF(100,100,200,300))
        finally:
            tp.notifyThreadsToStop()
        


if __name__=='__main__':
    ut.main()

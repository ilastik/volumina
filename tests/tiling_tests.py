import os
import unittest as ut
import numpy as np
from PyQt4.QtCore import QRectF, QPoint, QRect
from PyQt4.QtGui import QTransform, qApp
from qimage2ndarray import byte_view

from volumina.tiling import TileProvider, Tiling
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
from volumina.pixelpipeline.datasources import ConstantSource, ArraySource
from volumina.pixelpipeline.imagesources import GrayscaleImageSource
from volumina.pixelpipeline.imagepump import StackedImageSources, ImagePump
from volumina.pixelpipeline.slicesources import SliceSource
from volumina.slicingtools import SliceProjection


class TilingTest ( ut.TestCase ):
    def testNoneShape( self ):
        t = Tiling((0,0), QTransform())
        self.assertEqual( t.imageRectFs, [] )
        self.assertEqual( t.tileRectFs, [] )
        self.assertEqual( t.imageRects, [] )
        self.assertEqual( t.tileRects, [] )
        self.assertEqual( t.sliceShape, (0,0) )
        self.assertEqual( t.boundingRectF(), QRectF(0,0,0,0) )
        self.assertEqual( t.containsF(QPoint(0,0)), None )
        self.assertEqual( t.intersected( QRect(0,0,1,1) ), [])
        self.assertEqual( len(t), 0 )

    def testLen( self ):
        for i in xrange(5):
            t = Tiling((100*i, 100), QTransform(), blockSize = 50)
            self.assertEqual(len(t), (100*i*2)/50)


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
        tiling = Tiling((900,400), QTransform(), blockSize=100)
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
            tp.joinThreads()


class DirtyPropagationTest( ut.TestCase ):
    
    def setUp( self ):
        dataShape = (1, 900, 400, 10, 1) # t,x,y,z,c
        data = np.indices(dataShape)[3] # Data is labeled according to z-index
        self.ds1 = ArraySource( data )
        self.CONSTANT = 13
        self.ds2 = ConstantSource( self.CONSTANT )

        self.layer1 = GrayscaleLayer( self.ds1 )
        self.layer1.visible = True
        self.layer1.opacity = 1.0

        self.layer2 = GrayscaleLayer( self.ds2 )

        self.lsm = LayerStackModel()
        self.pump = ImagePump( self.lsm, SliceProjection() )

    def testEverythingDirtyPropagation( self ):
        self.lsm.append(self.layer2)        
        tiling = Tiling((900,400), QTransform(), blockSize=100)
        tp = TileProvider(tiling, self.pump.stackedImageSources)
        try:
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == self.CONSTANT))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            NEW_CONSTANT = self.CONSTANT+1
            self.ds2.constant = NEW_CONSTANT
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == NEW_CONSTANT))
                self.assertTrue(np.all(aimg[:,:,3] == 255))
            
        finally:
            tp.notifyThreadsToStop()
            tp.joinThreads()

    def testOutOfViewDirtyPropagation( self ):
        self.lsm.append(self.layer1)
        tiling = Tiling((900,400), QTransform(), blockSize=100)
        tp = TileProvider(tiling, self.pump.stackedImageSources)
        try:
            # Navigate down to the second z-slice
            self.pump.syncedSliceSources.through = [0,1,0]
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()

            # Sanity check: Do we see the right data on the second slice? (should be all 1s)
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == 1))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            # Navigate down to the third z-slice
            self.pump.syncedSliceSources.through = [0,2,0]
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()

            # Sanity check: Do we see the right data on the third slice?(should be all 2s)
            tiles = tp.getTiles(QRectF(100,100,200,200))
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == 2))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            # Navigate back up to the second z-slice
            self.pump.syncedSliceSources.through = [0,1,0]
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                self.assertTrue(np.all(aimg[:,:,0:3] == 1))
                self.assertTrue(np.all(aimg[:,:,3] == 255))

            # Change some of the data in the (out-of-view) third z-slice
            slicing = (slice(None), slice(100,300), slice(100,300), slice(2,3), slice(None))
            slicing = tuple(slicing)
            self.ds1._array[slicing] = 99
            self.ds1.setDirty( slicing )
            
            # Navigate back down to the third z-slice
            self.pump.syncedSliceSources.through = [0,2,0]
            tp.requestRefresh(QRectF(100,100,200,200))
            tp.join()

            # Even though the data was out-of-view when it was changed, it should still have new values.
            # If dirtiness wasn't propagated correctly, the cache's old values will be used.
            # (For example, this fails if you comment out the call to setDirty, above.)
            
            tiles = tp.getTiles(QRectF(101,101,198,198)) # Shrink accessed rect by 1 pixel on each side 
                                                         # (Otherwise, tiling overlap_draw causes getTiles() to return 
                                                         #  surrounding tiles that we haven't actually touched in this test)
            for tile in tiles:
                aimg = byte_view(tile.qimg)
                # Use any() because the tile borders may not be perfectly aligned with the data we changed.
                self.assertTrue(np.any(aimg[:,:,0:3] == 99))
        finally:
            tp.notifyThreadsToStop()
            tp.joinThreads()


if __name__=='__main__':
    ut.main()

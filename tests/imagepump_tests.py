import unittest as ut
from PyQt4.QtCore import QRect

from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
from volumina.pixelpipeline.datasources import ConstantSource
from volumina.pixelpipeline.imagesources import GrayscaleImageSource
from volumina.pixelpipeline.imagepump import StackedImageSources



class StackedImageSourcesTest( ut.TestCase ):
    def setUp( self ):
        self.ds = ConstantSource()

        self.layer1 = GrayscaleLayer( self.ds )
        self.layer1.visible = False
        self.layer1.opacity = 0.1
        self.ims1 = GrayscaleImageSource( self.ds, self.layer1 )
        self.layer2 = GrayscaleLayer( self.ds )
        self.layer2.visible = True
        self.layer2.opacity = 0.3
        self.ims2 = GrayscaleImageSource( self.ds, self.layer2 )
        self.layer3 = GrayscaleLayer( self.ds ) 
        self.layer3.visible = True
        self.layer3.opacity = 1.0
        self.ims3 = GrayscaleImageSource( self.ds, self.layer3 )

    def testRegisterAndDeregister( self ):
        lsm = LayerStackModel()
        sims = StackedImageSources( lsm )
        self.assertEqual( len(lsm), 0 )
        self.assertEqual( len(sims), 0 )

        lsm.append(self.layer1)
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        self.assertEqual( lsm.layerIndex(self.layer1), 2 )
        self.assertEqual( lsm.layerIndex(self.layer2), 1 )
        self.assertEqual( lsm.layerIndex(self.layer3), 0 )
        self.assertEqual( len(lsm), 3 )
        self.assertEqual( len(sims), 0 )

        self.assertFalse(sims.isRegistered(self.layer2))
        sims.register( self.layer2, self.ims2 )
        self.assertTrue(sims.isRegistered(self.layer2))
        self.assertEqual( len(sims), 1 )
        self.assertEqual( sims.getImageSource(0), self.ims2 )

        sims.register( self.layer1, self.ims1 )
        sims.register( self.layer3, self.ims3 )
        sims.deregister( self.layer2 )
        self.assertTrue( sims.isRegistered( self.layer1 ))
        self.assertFalse( sims.isRegistered( self.layer2 ))
        self.assertTrue( sims.isRegistered( self.layer3 ))
        self.assertEqual( len(lsm), 3 )
        self.assertEqual( len(sims), 2 )
        self.assertEqual( sims.getImageSource(0), self.ims3 )    
        self.assertEqual( sims.getImageSource(1), self.ims1 )

        for i,v in enumerate(sims):
            if i == 0:
                self.assertEqual(len(v), 3)
                self.assertEqual(v[0], self.layer3.visible) 
                self.assertEqual(v[1], self.layer3.opacity)
                self.assertEqual(v[2], self.ims3)  
            elif i == 1:
                self.assertEqual(len(v), 3)
                self.assertEqual(v[0], self.layer1.visible) 
                self.assertEqual(v[1], self.layer1.opacity)
                self.assertEqual(v[2], self.ims1)
            else:
                raise Exception("unexpected index")

        sims.deregister( self.layer1 )
        sims.deregister( self.layer3 )
        self.assertEqual( len(lsm), 3 )
        self.assertEqual( len(sims), 0 )

        lsm.clear()

    def testAddingAndRemovingLayers( self ):
        lsm = LayerStackModel()
        sims = StackedImageSources( lsm )
        ims_view = sims.viewImageSources()
        self.assertEqual(len(lsm), 0)
        self.assertEqual(len(sims), 0)
        self.assertEqual(len(ims_view), 0)

        lsm.append(self.layer1)
        lsm.append(self.layer2)
        sims.register(self.layer1, self.ims1)
        sims.register(self.layer2, self.ims2)
        self.assertEqual(sims.isRegistered(self.layer1), True)
        self.assertEqual(sims.isRegistered(self.layer2), True)
        self.assertEqual(sims.isActive(self.layer1), True)
        self.assertEqual(sims.isActive(self.layer2), True)
        self.assertEqual(len(lsm), 2)
        self.assertEqual(len(sims), 2)
        self.assertEqual(len(ims_view), 2)
        self.assertEqual(ims_view[0], self.ims2)
        self.assertEqual(ims_view[1], self.ims1)

        lsm.append(self.layer3)
        self.assertEqual(len(lsm), 3)
        self.assertEqual(len(sims), 2)
        self.assertEqual(len(ims_view), 2)
        self.assertEqual(ims_view[0], self.ims2)
        self.assertEqual(ims_view[1], self.ims1)

        lsm.removeRow(1)
        self.assertEqual(len(lsm), 2)
        self.assertEqual(len(sims), 1)
        self.assertEqual(len(ims_view), 1)
        self.assertEqual(ims_view[0], self.ims1)
        self.assertEqual(sims.isRegistered(self.layer1), True)
        self.assertEqual(sims.isRegistered(self.layer2), True)
        self.assertEqual(sims.isActive(self.layer1), True)
        self.assertEqual(sims.isActive(self.layer2), False)

        lsm.removeRow(0)
        self.assertEqual(len(lsm), 1)
        self.assertEqual(len(sims), 1)
        self.assertEqual(len(ims_view), 1)
        self.assertEqual(ims_view[0], self.ims1)
        self.assertEqual(sims.isRegistered(self.layer1), True)
        self.assertEqual(sims.isRegistered(self.layer2), True)
        self.assertEqual(sims.isActive(self.layer1), True)
        self.assertEqual(sims.isActive(self.layer2), False)

        sims.deregister(self.layer1)
        sims.deregister(self.layer2)
        self.assertEqual(len(lsm), 1)
        self.assertEqual(len(sims), 0)
        self.assertEqual(len(ims_view), 0)
        self.assertEqual(sims.isRegistered(self.layer1), False)
        self.assertEqual(sims.isRegistered(self.layer2), False)
        self.assertEqual(sims.isActive(self.layer1), False)
        self.assertEqual(sims.isActive(self.layer2), False)

    def testFirstFullyOpaque( self ):
        lsm = LayerStackModel()
        sims = StackedImageSources( lsm )
        self.assertEqual(sims.firstFullyOpaque(), None)

        lsm.append(self.layer1)
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        self.assertEqual( lsm.layerIndex(self.layer1), 2 )
        self.assertEqual( lsm.layerIndex(self.layer2), 1 )
        self.assertEqual( lsm.layerIndex(self.layer3), 0 )
        sims.register(self.layer1, self.ims1)
        sims.register(self.layer2, self.ims2)
        sims.register(self.layer3, self.ims3)
        self.assertEqual(sims.firstFullyOpaque(), 0)
        lsm.clear()

        sims = StackedImageSources( lsm )
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        lsm.append(self.layer1)
        self.assertEqual( lsm.layerIndex(self.layer1), 0 )
        self.assertEqual( lsm.layerIndex(self.layer2), 2 )
        self.assertEqual( lsm.layerIndex(self.layer3), 1 )
        sims.register(self.layer1, self.ims1)
        sims.register(self.layer2, self.ims2)
        sims.register(self.layer3, self.ims3)
        self.assertEqual(sims.firstFullyOpaque(), 1)
        lsm.clear()

        sims = StackedImageSources( lsm )
        lsm.append(self.layer2)
        lsm.append(self.layer1)
        self.assertEqual( lsm.layerIndex(self.layer1), 0 )
        self.assertEqual( lsm.layerIndex(self.layer2), 1 )
        sims.register(self.layer1, self.ims1)
        sims.register(self.layer2, self.ims2)
        self.assertEqual(sims.firstFullyOpaque(), None)
        lsm.clear()

        

if __name__=='__main__':
    ut.main()

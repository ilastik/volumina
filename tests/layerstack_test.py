import unittest as ut
from volumina.layer import Layer
from volumina.layerstack import LayerStackModel

class LayerStackModelTest( ut.TestCase ):
    def setUp( self ):
        self.l1 = Layer()
        self.l1.name = 'l1'
        self.l2 = Layer()
        self.l2.name = 'l2'
        self.l3 = Layer()
        self.l3.name = 'l3'

    def testAddingAndRemoving( self ):
        lsm = LayerStackModel()
        self.assertEqual(len(lsm), 0)

        lsm.append(self.l1)
        self.assertEqual(len(lsm), 1)
        self.assertEqual(lsm[0].name, self.l1.name )

        lsm.append(self.l2)
        self.assertEqual(len(lsm), 2)
        self.assertEqual(lsm[0].name, self.l2.name )
        self.assertEqual(lsm[1].name, self.l1.name )

        lsm.insert(1, self.l3)
        self.assertEqual(len(lsm), 3)
        self.assertEqual(lsm[0].name, self.l2.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l1.name )

        lsm.selectRow( 0 )
        lsm.deleteSelected()
        self.assertEqual(len(lsm), 2)
        self.assertEqual(lsm[0].name, self.l3.name )
        self.assertEqual(lsm[1].name, self.l1.name )

        lsm.clear()
        self.assertEqual(len(lsm), 0)

    def testMovingLayers( self ):
        lsm = LayerStackModel()
        lsm.append(self.l1)
        lsm.append(self.l2)
        lsm.append(self.l3)
        lsm.selectRow(1)
        self.assertEqual(len(lsm),3)
        self.assertEqual(lsm[0].name, self.l3.name )
        self.assertEqual(lsm[1].name, self.l2.name )
        self.assertEqual(lsm[2].name, self.l1.name )
        self.assertEqual(lsm.selectedRow(), 1)

        lsm.moveSelectedDown()
        self.assertEqual(lsm.selectedRow(), 2)
        self.assertEqual(len(lsm),3)
        self.assertEqual(lsm[0].name, self.l3.name )
        self.assertEqual(lsm[1].name, self.l1.name )
        self.assertEqual(lsm[2].name, self.l2.name )

        lsm.selectRow(1)
        lsm.moveSelectedUp()
        self.assertEqual(lsm.selectedRow(), 0)
        self.assertEqual(len(lsm),3)
        self.assertEqual(lsm[0].name, self.l1.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l2.name )


        # moving topmost layer up => nothing should happen
        lsm.selectRow(0)
        self.assertEqual(lsm.selectedRow(), 0)
        self.assertEqual(lsm[0].name, self.l1.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l2.name )
        lsm.moveSelectedUp()
        self.assertEqual(lsm.selectedRow(), 0)
        self.assertEqual(lsm[0].name, self.l1.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l2.name )

        # moving bottommost layer down => nothing should happen
        lsm.selectRow(2)
        self.assertEqual(lsm.selectedRow(), 2)
        self.assertEqual(lsm[0].name, self.l1.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l2.name )
        lsm.moveSelectedDown()
        self.assertEqual(lsm.selectedRow(), 2)
        self.assertEqual(lsm[0].name, self.l1.name )
        self.assertEqual(lsm[1].name, self.l3.name )
        self.assertEqual(lsm[2].name, self.l2.name )



if __name__=='__main__':
    ut.main()

import unittest as ut
from volumina.layer import Layer
from volumina.layerstack import LayerStackModel

class LayerStackModelTest( ut.TestCase ):
    def testAddingAndRemoving( self ):
        l1 = Layer()
        l1.name = 'l1'
        l2 = Layer()
        l2.name = 'l2'
        l3 = Layer()
        l3.name = 'l3'

        lsm = LayerStackModel()
        self.assertEqual(len(lsm), 0)

        lsm.append(l1)
        self.assertEqual(len(lsm), 1)
        self.assertEqual(lsm[0].name, l1.name )

        lsm.append(l2)
        self.assertEqual(len(lsm), 2)
        self.assertEqual(lsm[0].name, l2.name )
        self.assertEqual(lsm[1].name, l1.name )

        lsm.insert(1, l3)
        self.assertEqual(len(lsm), 3)
        self.assertEqual(lsm[0].name, l2.name )
        self.assertEqual(lsm[1].name, l3.name )
        self.assertEqual(lsm[2].name, l1.name )

        lsm.selectRow( 0 )
        lsm.deleteSelected()
        self.assertEqual(len(lsm), 2)
        self.assertEqual(lsm[0].name, l3.name )
        self.assertEqual(lsm[1].name, l1.name )

        lsm.clear()
        self.assertEqual(len(lsm), 0)

if __name__=='__main__':
    ut.main()

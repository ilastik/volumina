from vigra import VigraArray
from lazyflow.graph import Graph, Operator, InputSlot, OutputSlot
from numpy import ndarray,squeeze,ndarray
from numpy.random import rand
from unittest import TestCase
from volumina.pixelpipeline.datasourcefactories import createDataSource
from volumina.pixelpipeline.datasources import LazyflowSource,ArraySource

class OpPiper(Operator):
    
    inputSlots = [InputSlot("Input")]
    outputSlots = [OutputSlot("Output")]
    
    def setupOutputs(self):
        
        self.outputs["Output"].meta.assignFrom(self.inputs["Input"].meta)
        self.outputs["Output"].connect(self.inputs["Input"])
        
    def execute(self,slot,roi,result):
        
        result[:] = self.outputs["Output"](roi).wait()
        return result
        

class Test_DatasourceFactories(TestCase):
    
    def setUp(self):
        self.dim = (10,)*5
        self.g = Graph()
        self.op = OpPiper(self.g)
        
    def test_lazyflowSource(self):
        for i in range(2,6):
            array = rand(*self.dim[:i])
            self.op.inputs["Input"].setValue(array)
            source = createDataSource(self.op.outputs["Output"])
            self.assertEqual(type(source), LazyflowSource, 'Resulting datatype is not as expected')
            self.assertEqual(squeeze(ndarray(source._outslot.shape)).shape, array.shape, 'Inputdatashape does not match outputdatashape')
    
    def test_numpyArraySource(self):
        for i in range(2,6):
            array = rand(*self.dim[:i])
            source = createDataSource(array)
            self.assertEqual(type(source), ArraySource, 'Resulting datatype is not as expected')
            self.assertEqual(squeeze(ndarray(source._array.shape)).shape, array.shape, 'Inputdatashape does not match outputdatashape')
    
    def test_vigraArraySource(self):
        for i in range(2,6):
            array = VigraArray(self.dim[:i])
            source = createDataSource(array)
            self.assertEqual(type(source), ArraySource, 'Resulting datatype is not as expected')
            self.assertEqual(squeeze(ndarray(source._array.shape)).shape, array.shape, 'Inputdatashape does not match outputdatashape')
    
    #yet to implement    
#    def test_folderSource(self):
#        pass
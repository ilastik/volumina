from numpy import ndarray,squeeze,ndarray
from numpy.random import rand
from unittest import TestCase
from volumina.pixelpipeline.datasourcefactories import createDataSource
from volumina.pixelpipeline.datasources import LazyflowSource,ArraySource

hasLazyflow = True
try:
    from lazyflow.graph import Graph, Operator, InputSlot, OutputSlot
except:
    hasLazyflow = False

if hasLazyflow:
    class OpPiper(Operator):
        
        inputSlots = [InputSlot("Input")]
        outputSlots = [OutputSlot("Output")]
        
        def setupOutputs(self):
            
            self.outputs["Output"].meta.assignFrom(self.inputs["Input"].meta)
            self.outputs["Output"].connect(self.inputs["Input"])
            
        def execute(self, slot, subindex, roi, result):
            
            result[:] = self.outputs["Output"](roi).wait()
            return result

        def propagateDirty(self, inputSlot, subindex, roi):
            self.Output.setDirty(roi)
        
class Test_DatasourceFactories(TestCase):
    
    def setUp(self):
        self.dim = (10,)*5
        if hasLazyflow:
            self.g = Graph()
            self.op = OpPiper(graph=self.g)
        
    def test_lazyflowSource(self):
        if hasLazyflow:
            import vigra
            def test_source( src, array ):
                self.assertEqual(type(src), LazyflowSource)
                self.assertEqual(squeeze(ndarray(src._op5.output.meta.shape)).shape, array.shape)

            for i in range(2,6):
                array = rand(*self.dim[:i]).view(vigra.VigraArray)
                array.axistags = vigra.defaultAxistags('txyzc'[:i])
                self.op.inputs["Input"].setValue(array)

                source_output = createDataSource(self.op.Output)
                test_source( source_output, array )
                source_input = createDataSource(self.op.Input)
                test_source( source_input, array )

        else:
            pass
        
    def test_numpyArraySource(self):
        for i in range(2,6):
            array = rand(*self.dim[:i])
            source = createDataSource(array)
            self.assertEqual(type(source), ArraySource, 'Resulting datatype is not as expected')
            self.assertEqual(squeeze(ndarray(source._array.shape)).shape, array.shape, 'Inputdatashape does not match outputdatashape')
    
    #yet to implement    
#    def test_folderSource(self):
#        pass

if __name__=="__main__":
    import unittest
    unittest.main()

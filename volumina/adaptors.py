'''Input and output from and to other libraries resp. formats.

Volumine works with 5d array-like objects assuming the coordinate
system (time, x, y, z, channel). This module provides methods to convert other
data types to this expected format.
'''
import os
import os.path as path
import numpy as np
from volumina.slicingtools import sl, slicing2shape
import numpy

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False


###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
    from lazyflow.roi import TinyVector
except ImportError:
    _has_lazyflow = False

if _has_lazyflow and _has_vigra:

        class Op5ifyer(Operator):
            name = "Op5ifyer"
            inputSlots = [InputSlot("input")]
            outputSlots = [OutputSlot("output")]
            
            def setupOutputs(self):
                inputAxistags = self.inputs["input"]._axistags
                inputShape = list(self.inputs["input"]._shape)
                self.resSl = [slice(0,stop,None) for stop in list(self.inputs["input"]._shape)]
                
                defaultTags = vigra.defaultAxistags('txyzc')
                
                for tag in [tag for tag in defaultTags if tag not in inputAxistags]:
                    #inputAxistags.insert(defaultTags.index(tag.key),tag)
                    #inputShape.insert(defaultTags.index(tag.key),1)
                    self.resSl.insert(defaultTags.index(tag.key),0)
                
                outputShape = []
                for tag in defaultTags:
                    if tag in inputAxistags:
                        outputShape += [ inputShape[ inputAxistags.index(tag.key) ] ]
                    else:
                        outputShape += [1]                
                
                self.outputs["output"]._dtype = self.inputs["input"]._dtype
                self.outputs["output"]._shape = tuple(outputShape)
                self.outputs["output"]._axistags = defaultTags
                
            def execute(self,slot,roi,result):
                
                sl = [slice(0,roi.stop[i]-roi.start[i],None) if sl != 0\
                      else slice(0,1) for i,sl in enumerate(self.resSl)]
                
                inputTags = self.input.meta.axistags
                
                # Convert the requested slice into a slice for our input
                outSlice = roi.toSlice()
                inSlice = [None] * len(inputTags)
                for i, s in enumerate(outSlice):
                    tagKey = self.output.meta.axistags[i].key
                    inputAxisIndex = inputTags.index(tagKey)
                    if inputAxisIndex < len(inputTags):
                        inSlice[inputAxisIndex] = s
                
#                roi.start = TinyVector([i for i,k in zip(roi.start,sl) if k != 0])
#                roi.stop = TinyVector([i for i,k in zip(roi.stop,sl) if k != 0])
                
                tmpres = self.inputs["input"][inSlice].wait()
                
                # Re-order the axis the way volumina expects them
                v = tmpres.view(vigra.VigraArray)
                v.axistags = inputTags
                result[sl] = v.withAxes(*list('txyzc'))

class Array5d( object ):
    '''Embed a array with dim = 3 into the volumina coordinate system.'''
    def __init__( self, array, dtype=np.uint8):
        assert(len(array.shape) == 3)
        self.a = array
        self.dtype=dtype
        
    def __getitem__( self, slicing ):
        sl3d = (slicing[1], slicing[2], slicing[3])
        ret = np.zeros(slicing2shape(slicing), dtype=self.dtype)
        ret[0,:,:,:,0] = self.a[tuple(sl3d)]
        return ret
    @property
    def shape( self ):
        return (1,) + self.a.shape + (1,)

    def astype( self, dtype):
        return Array5d( self.a, dtype )

if __name__ == "__main__":
    pass

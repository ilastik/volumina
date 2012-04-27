'''Input and output from and to other libraries resp. formats.

Volumine works with 5d array-like objects assuming the coordinate
system (time, x, y, z, channel). This module provides methods to convert other
data types to this expected format.
'''
import os
import os.path as path
import numpy as np
from volumina.slicingtools import sl, slicing2shape
import vigra,numpy
###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
    from lazyflow.roi import TinyVector
except ImportError:
    _has_lazyflow = False

if _has_lazyflow:

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
                    inputAxistags.insert(defaultTags.index(tag.key),tag)
                    inputShape.insert(defaultTags.index(tag.key),1)
                    self.resSl.insert(defaultTags.index(tag.key),0)
                
                self.outputs["output"]._dtype = self.inputs["input"]._dtype
                self.outputs["output"]._shape = tuple(inputShape)
                self.outputs["output"]._axistags = inputAxistags
                
            def execute(self,slot,roi,result):
                
                sl = [slice(0,roi.stop[i]-roi.start[i],None) if sl != 0\
                      else 0 for i,sl in enumerate(self.resSl)]
                
                roi.start = TinyVector([i for i,k in zip(roi.start,sl) if k != 0])
                roi.stop = TinyVector([i for i,k in zip(roi.stop,sl) if k != 0])
                
                tmpres = self.inputs["input"](start=roi.start,stop=roi.stop).wait()
                result[sl] = tmpres
                return result

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



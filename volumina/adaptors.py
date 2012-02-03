'''Input and output from and to other libraries resp. formats.

Volumine works with 5d array-like objects assuming the coordinate
system (time, x, y, z, channel). This module provides methods to convert other
data types to this expected format.
'''
import os
import os.path as path
import numpy as np
from volumina.slicingtools import sl, slicing2shape

###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
except ImportError:
    _has_lazyflow = False

if _has_lazyflow:
    class Op5ifyer(Operator):
        name = "5Difyer"
        inputSlots = [InputSlot("input")]
        outputSlots = [OutputSlot("output")]
        def setupOutputs(self):
            shape = self.inputs["input"].shape
            assert len(shape) in [2,3,4], shape
            if len(shape) == 2:
                outShape = (1,) + shape + (1,1,)
            elif len(shape) == 3:
                outShape = (1,) + shape + (1,)
            else:
                outShape = (1,) + shape
            
            self.ndim = len(shape)
            self.outputs["output"]._shape = outShape
            self.outputs["output"]._dtype = self.inputs["input"].dtype
            self.outputs["output"]._axistags = self.inputs["input"].axistags

        def execute(self, slot, roi, resultArea):
            key = roi.toSlice()
            assert key[0] == slice(0,1,None)
            if self.ndim == 3:
                assert key[-1] == slice(0,1,None)
                req = self.inputs["input"][key[1:-1]].writeInto(resultArea[0,:,:,:,0])
            elif self.ndim ==2:
                assert key[-1] == slice(0,1,None)
                assert key[-2] == slice(0,1,None)
                req = self.inputs["input"][key[1:-2]].writeInto(resultArea[0,:,:,0,0])
            else:
                req = self.inputs["input"][key[1:]].writeInto(resultArea[0,:,:,:,:]) 
            return req.wait()

        def notifyDirty(self,slot,key):
            self.outputs["Output"].setDirty(key)


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



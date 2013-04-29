'''Input and output from and to other libraries resp. formats.

Volumine works with 5d array-like objects assuming the coordinate
system (time, x, y, z, channel). This module provides methods to convert other
data types to this expected format.
'''
import numpy as np
from volumina.slicingtools import slicing2shape

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

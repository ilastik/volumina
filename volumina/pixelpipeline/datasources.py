import threading
import weakref
from functools import partial
from PyQt4.QtCore import QObject, pyqtSignal
from asyncabcs import RequestABC, SourceABC
import volumina
from volumina.slicingtools import is_pure_slicing, slicing2shape, is_bounded, index2slice, sl
from volumina.config import cfg
import numpy as np

import volumina.adaptors
from volumina.slicingtools import slicing2shape

_has_vigra = True
try:
    import vigra
except ImportError:
    _has_vigra = False
    
#*******************************************************************************
# A r r a y R e q u e s t                                                      *
#*******************************************************************************

class ArrayRequest( object ):
    def __init__( self, array, slicing ):
        self._array = array
        self._slicing = slicing
        self._result = None

    def wait( self ):
        if not self._result:
            self._result = self._array[self._slicing]
        return self._result
    
    def getResult(self):
        return self._result

    def cancel( self ):
        pass

    def submit( self ):
        pass
        
    # callback( result = result, **kwargs )
    def notify( self, callback, **kwargs ):
        t = threading.Thread(target=self._doNotify, args=( callback, kwargs ))
        t.start()

    def _doNotify( self, callback, kwargs ):
        result = self.wait()
        callback(result, **kwargs)
assert issubclass(ArrayRequest, RequestABC)

#*******************************************************************************
# A r r a y S o u r c e                                                        *
#*******************************************************************************

class ArraySource( QObject ):
    isDirty = pyqtSignal( object )

    def __init__( self, array ):
        super(ArraySource, self).__init__()
        self._array = array

    def request( self, slicing ):
        if not is_pure_slicing(slicing):
            raise Exception('ArraySource: slicing is not pure')
        assert(len(slicing) == len(self._array.shape)), \
            "slicing into an array of shape=%r requested, but slicing is %r" \
            % (slicing, self._array.shape)  
        return ArrayRequest(self._array, slicing)

    def setDirty( self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        self.isDirty.emit( slicing )

    def __eq__( self, other ):
        # Use id for efficiency
        return self._array is other._array
    
    def __ne__( self, other ):
        return not ( self == other )

assert issubclass(ArraySource, SourceABC)

#*******************************************************************************
# A r r a y S i n k S o u r c e                                                *
#*******************************************************************************

class ArraySinkSource( ArraySource ):
    def put( self, slicing, subarray, neutral = 0 ):
        '''Make an update of the wrapped arrays content.

        Elements with neutral value in the subarray are not written into the
        wrapped array, but the original values are kept.

        '''
        assert(len(slicing) == len(self._array.shape)), \
            "slicing into an array of shape=%r requested, but the slicing object is %r" % (slicing, self._array.shape)  
        self._array[slicing] = np.where(subarray!=neutral, subarray, self._array[slicing])
        pure = index2slice(slicing)
        self.setDirty(pure)

#*******************************************************************************
# R e l a b e l i n g A r r a y S o u r c e                                    * 
#*******************************************************************************

class RelabelingArraySource( ArraySource ):
    """Applies a relabeling to each request before passing it on
       Currently, it casts everything to uint8, so be careful."""
    isDirty = pyqtSignal( object )
    def __init__( self, array ):
        super(RelabelingArraySource, self).__init__(array)
        self.originalData = array
        self._relabeling = None
    
    def setRelabeling( self, relabeling ):
        """Sets new relabeling vector. It should have a len(relabling) == max(your data)+1
           and give, for each possible data value x, the relabling as relabeling[x]."""   
        assert relabeling.dtype == self._array.dtype
        self._relabeling = relabeling
        self.setDirty(5*(slice(None),))

    def setRelabelingEntry( self, index, value, setDirty=True ):
        """Sets the entry for data value index to value, such that afterwards
           relabeling[index] =  value.
           
           If setDirty is true, the source will signal dirtyness. If you plan to issue many calls to this function
           in a loop, setDirty to true only on the last call."""
        self._relabeling[index] = value
        if setDirty:
            self.setDirty(5*(slice(None),))

    def request( self, slicing ):
        if not is_pure_slicing(slicing):
            raise Exception('ArraySource: slicing is not pure')
        assert(len(slicing) == len(self._array.shape)), \
            "slicing into an array of shape=%r requested, but slicing is %r" \
            % (self._array.shape, slicing)
        a = ArrayRequest(self._array, slicing)
        a = a.wait()
        
        #oldDtype = a.dtype
        if self._relabeling is not None:
            a = self._relabeling[a]
        #assert a.dtype == oldDtype 
        return ArrayRequest(a, 5*(slice(None),))
        
#*******************************************************************************
# L a z y f l o w R e q u e s t                                                *
#*******************************************************************************

class LazyflowRequest( object ):
    ## Lazyflow requests are starting to do work at the time of their
    ## creation whereas Volumina requests are idling as long as no
    ## method like wait() or notify() is called. Therefore we have to
    ## delay the creation of the lazyflow request until one of these
    ## Volumina request methods is actually called
    class _req_on_demand(dict):
        def __init__( self, op, slicing, prio ):
            self.p = (op, slicing, prio)
    
        def __missing__(self, key):
            if self.p[0].output.meta.shape is not None:
                assert(self.p[0].output.ready())
                reqobj = self.p[0].output[self.p[1]].allocate(priority = self.p[2])
            else:
                reqobj = ArrayRequest( np.zeros(slicing2shape(self.p[1]), dtype=np.uint8 ), self.p[1] )

            self[0] = reqobj
            return reqobj

    def __init__(self, op, slicing, prio, objectName="Unnamed LazyflowRequest" ):
        self._req = LazyflowRequest._req_on_demand(op, slicing, prio) 
        self._slicing = slicing
        self._shape = slicing2shape(slicing)
        self._objectName = objectName

    def wait( self ):
        a = self._req[0].wait()
        assert(isinstance(a, np.ndarray))
        assert(a.shape == self._shape), "LazyflowRequest.wait() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
        return a
        
    def getResult(self):
        a = self._req[0].getResult()
        assert(isinstance(a, np.ndarray))
        assert(a.shape == self._shape), "LazyflowRequest.getResult() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
        return a

    def adjustPriority(self,delta):
        self._req[0].adjustPriority(delta)
        
    def cancel( self ):
        self._req[0].cancel()

    def submit( self ):
        self._req[0].submit()

    def notify( self, callback, **kwargs ):
        self._req[0].notify( callback, **kwargs)
assert issubclass(LazyflowRequest, RequestABC)

#*******************************************************************************
# L a z y f l o w S o u r c e                                                  *
#*******************************************************************************

def weakref_setDirtyLF( wref, *args, **kwargs ):
    """
    LazyflowSource uses this function to subscribe to dirty notifications without giving out a shared reference to itself.
    Otherwise, LazyflowSource.__del__ would never be called.
    """
    wref()._setDirtyLF(*args, **kwargs)

class LazyflowSource( QObject ):
    isDirty = pyqtSignal( object )

    @property
    def dataSlot(self):
        return self._orig_outslot

    def __init__( self, outslot, priority = 0 ):
        super(LazyflowSource, self).__init__()

        self._orig_outslot = outslot

        # Attach an Op5ifyer to ensure the data will display correctly
        self._op5 = volumina.adaptors.Op5ifyer( graph=outslot.graph )
        self._op5.input.connect( outslot )

        self._priority = priority
        self._dirtyCallback = partial( weakref_setDirtyLF, weakref.ref(self) )
        self._op5.output.notifyDirty( self._dirtyCallback )
        self._op5.externally_managed = True

    def __del__(self):
        if self._op5 is not None:
            self._op5.cleanUp()
    
    def request( self, slicing ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print "  LazyflowSource '%s' requests %s" % (self.objectName(), volumina.strSlicing(slicing))
            volumina.printLock.release()
        if not is_pure_slicing(slicing):
            raise Exception('LazyflowSource: slicing is not pure')
        return LazyflowRequest( self._op5, slicing, self._priority, objectName=self.objectName() )

    def _setDirtyLF(self, slot, roi):
        self.setDirty(roi.toSlice())

    def setDirty( self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        self.isDirty.emit( slicing )

    def __eq__( self, other ):
        return self._orig_outslot is other._orig_outslot
    
    def __ne__( self, other ):
        return not ( self == other )

assert issubclass(LazyflowSource, SourceABC)

class LazyflowSinkSource( LazyflowSource ):
    def __init__( self, outslot, inslot, priority = 0 ):
        LazyflowSource.__init__(self, outslot)
        self._inputSlot = inslot
        self._priority = priority

    def put( self, slicing, array ):
        assert _has_vigra, "Lazyflow SinkSource requires lazyflow and vigra."

        taggedArray = array.view(vigra.VigraArray)
        taggedArray.axistags = vigra.defaultAxistags('txyzc')

        inputTags = self._inputSlot.meta.axistags
        inputKeys = [tag.key for tag in inputTags]
        transposedArray = taggedArray.withAxes(*inputKeys)

        taggedSlicing = dict(zip('txyzc', slicing))
        transposedSlicing = ()
        for k in inputKeys:
            if k in 'txyzc':
                transposedSlicing += (taggedSlicing[k],)
        self._inputSlot[transposedSlicing] = transposedArray.view(np.ndarray)

    def __eq__( self, other ):
        result = super(LazyflowSinkSource, self).__eq__(other)
        result &= self._inputSlot == other._inputSlot
        return result
    
    def __ne__( self, other ):
        return not ( self == other )
        
#*******************************************************************************
# C o n s t a n t R e q u e s t                                                *
#*******************************************************************************

class ConstantRequest( object ):
    def __init__( self, result ):
        self._result = result

    def wait( self ):
        return self._result
    
    def getResult(self):
        return self._result
    
    def cancel( self ):
        pass

    def submit ( self ):
        pass
        
    def adjustPriority(self, delta):
        pass        
        
    # callback( result = result, **kwargs )
    def notify( self, callback, **kwargs ):
        callback(self._result, **kwargs)
assert issubclass(ConstantRequest, RequestABC)

#*******************************************************************************
# C o n s t a n t S o u r c e                                                  *
#*******************************************************************************

class ConstantSource( QObject ):
    isDirty = pyqtSignal( object )
    idChanged = pyqtSignal( object, object ) # old, new

    @property
    def constant( self ):
        return self._constant

    @constant.setter
    def constant( self, value ):
        self._constant = value
        self.setDirty(sl[:,:,:,:,:])

    def __init__( self, constant = 0, dtype = np.uint8, parent=None ):
        super(ConstantSource, self).__init__(parent=parent)
        self._constant = constant
        self._dtype = dtype

    def id( self ):
        return id(self)

    def request( self, slicing, through=None ):
        assert is_pure_slicing(slicing)
        assert is_bounded(slicing)
        shape = slicing2shape(slicing)
        result = np.zeros( shape, dtype = self._dtype )
        result[:] = self._constant
        return ConstantRequest( result )

    def setDirty( self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        self.isDirty.emit( slicing )

    def __eq__( self, other ):
        return self._constant == other._constant
    
    def __ne__( self, other ):
        return not ( self == other )

assert issubclass(ConstantSource, SourceABC)

#*******************************************************************************
# N o r m a l i z i n g R e q u e s t                                          *
#*******************************************************************************
class NormalizingRequest( object ):
    def __init__( self, rawRequest, normFunc ):
        self._rawRequest = rawRequest
        self._normFunc = normFunc

    def wait( self ):
        rawData = self._rawRequest.wait()
        self._result = self._normFunc(rawData)
        return self._result
    
    # callback( result = result, **kwargs )
    def notify( self, callback, **kwargs ):
        def handleResult(rawResult):
            self._result = self._normFunc(rawResult)
            callback( self._result, **kwargs )
        self._rawRequest.notify( handleResult )

    def getResult(self):
        return self._result

assert issubclass(NormalizingRequest, RequestABC)


#*******************************************************************************
# N o r m a l i z i n g S o u r c e                                            *
#*******************************************************************************
class NormalizingSource( QObject ):
    """
    A datasource that serves as a normalizing decorator for other datasources.
    All data from the original (raw) data source is normalized to the range (0,255) before it is provided to the caller.
    """
    isDirty = pyqtSignal( object )
    
    def __init__( self, rawSource, bounds=(0,255), parent=None ):
        """
        rawSource: The original datasource whose data will be normalized
        
        bounds: The range of the original source's data, given as a tuple of (min,max)
                Alternatively, thee following strings can be provided instead of a bounds tuple:
                    'autoMinMax' - Track the min and max values observed from all requests and normalize to that range
                    'autoPercentiles' - Track the 1 and 99 percentiles and normalize all data to that range
                Note: When an incoming request causes the lower or uppoer bound to change, the entire source is marked dirty.
        """
        super(NormalizingSource, self).__init__(parent)
        self._rawSource = rawSource
        self._rawSource.isDirty.connect( self.isDirty )
        if isinstance(bounds, tuple):
            self._method = 'hardcoded'
            self._bounds = ( float(bounds[0]), float(bounds[1]) )
        else:
            self._method = bounds
            self._bounds = (None, None)
    
    def request( self, slicing ):
        rawRequest = self._rawSource.request(slicing)
        if self._method == 'autoMinMax':
            return NormalizingRequest( rawRequest, self._autoNormalizeMinMax )
        elif self._method == 'autoPercentiles':
            return NormalizingRequest( rawRequest, self._autoNormalizePercentiles )
        elif isinstance(self._bounds, tuple):
            return NormalizingRequest( rawRequest, partial(NormalizingSource._normalizeFromBounds, self._bounds) )
        else:
            assert False, "Unknown normalization setting."

    def setDirty( self, slicing ):
        self._rawSource.setDirty( slicing )

    def __eq__( self, other ):
        equal = True
        equal &= isinstance( other, NormalizingSource )
        equal &= ( self._rawSource == other._rawSource )
        equal &= ( self._method == other._method )
        equal &= ( self._method != 'hardcoded' or self._bounds == other._bounds )
        return equal

    def __ne__( self, other ):
        return not ( self == other )

    @staticmethod
    def _normalizeFromBounds(bounds, array):
        lower, upper = bounds
        if bounds != (0,255):
            # Scale
            array = array.astype(np.float32)
            array = (array - lower)*255. / (upper-lower)
            # Clip
            array[array > 255] = 255
            array[array < 0] = 0
        return array

    def _autoNormalizeFromNewBounds(self, newBounds, array):
        # Cast to float to avoid a 'gotcha' with uint8 subtraction (e.g. 100 - 105 = 251)
        nmin = float(newBounds[0])
        nmax = float(newBounds[1])

        # Adjust running bounds if necessary
        # Note: We would protect self._bounds with a lock here if we really 
        #       wanted perfect bounds, but the performance hit isn't worth it.
        dirty = False
        bounds = list(self._bounds)
        if bounds[0] is not None:
            # Everything becomes dirty when the bounds change, so we avoid changing the
            # bounds unless the new min or max is significantly different from the old value
            tolerance = float(bounds[1] - bounds[0])*0.01
        if bounds[0] is None or (bounds[0] - nmin) > tolerance: 
            bounds[0] = nmin
            dirty = True
        if bounds[1] is None or (nmax - bounds[1]) > tolerance:
            bounds[1] = nmax
            dirty = True
        
        # If the min or max value changed, set the entire source dirty
        if dirty:
            self._bounds = tuple(bounds)
            self.setDirty( sl[:,:,:,:,:] )
        
        return NormalizingSource._normalizeFromBounds(self._bounds, array)

    def _autoNormalizeMinMax(self, array):
        return self._autoNormalizeFromNewBounds( (array.min(), array.max() ), array )

    def _autoNormalizePercentiles(self, array):
        p1, p99 = np.percentile(array, [1,99])
        return self._autoNormalizeFromNewBounds( (p1, p99), array )

assert issubclass(NormalizingSource, SourceABC)


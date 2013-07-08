import threading
import weakref
from functools import partial
from PyQt4.QtCore import QObject, pyqtSignal, QTimer
from asyncabcs import RequestABC, SourceABC
import volumina
from volumina.slicingtools import is_pure_slicing, slicing2shape, \
    is_bounded, make_bounded, index2slice, sl
from volumina.config import cfg
import numpy as np

_has_lazyflow = True
try:
    import lazyflow.operators.opReorderAxes
except:
    _has_lazyflow = False

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
        
    def clean_up(self):
        self._array = None

    def dtype(self):
        return self._array.dtype

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
        if other is None:
            return False
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

    def clearRelabeling( self ):
        self._relabeling[:] = 0
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
    def __init__(self, op, slicing, prio, objectName="Unnamed LazyflowRequest" ):
        self._req = op.Output[slicing]
        self._slicing = slicing
        shape = op.Output.meta.shape
        if shape is not None:
            slicing = make_bounded(slicing, shape)
        self._shape = slicing2shape(slicing)
        self._objectName = objectName
        
    def wait( self ):
        a = self._req.wait()
        assert(isinstance(a, np.ndarray))
        assert(a.shape == self._shape), "LazyflowRequest.wait() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
        return a
        
    def getResult(self):
        a = self._req.result
        assert(isinstance(a, np.ndarray))
        assert(a.shape == self._shape), "LazyflowRequest.getResult() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
        return a

    def cancel( self ):
        self._req.cancel()

    def submit( self ):
        self._req.submit()

    def notify( self, callback, **kwargs ):
        self._req.notify_finished( partial(callback, (), **kwargs) )
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

        assert _has_lazyflow, "Can't instantiate a LazyflowSource: Wasn't able to import lazyflow."

        self._orig_outslot = outslot

        # Attach an OpReorderAxes to ensure the data will display correctly
        self._op5 = lazyflow.operators.opReorderAxes.OpReorderAxes( parent=outslot.getRealOperator().parent )
        self._op5.Input.connect( outslot )

        self._priority = priority
        self._dirtyCallback = partial( weakref_setDirtyLF, weakref.ref(self) )
        self._op5.Output.notifyDirty( self._dirtyCallback )
        self._op5.externally_managed = True

    def clean_up(self):
        self._op5.cleanUp()
        self._op5 = None

    def __del__(self):
        if self._op5 is not None:
            self._op5.cleanUp()
            
    def dtype(self):
        dtype = self._orig_outslot.meta.dtype
        assert dtype is not None, "Your LazyflowSource doesn't have a dtype! Is your lazyflow slot properly configured in setupOutputs()?"
        return dtype
    
    def request( self, slicing ):
        if cfg.getboolean('pixelpipeline', 'verbose'):
            volumina.printLock.acquire()
            print "  LazyflowSource '%s' requests %s" % (self.objectName(), volumina.strSlicing(slicing))
            volumina.printLock.release()
        if not is_pure_slicing(slicing):
            raise Exception('LazyflowSource: slicing is not pure')
        assert self._op5 is not None, "Underlying operator is None.  Are you requesting from a datasource that has been cleaned up already?"
        return LazyflowRequest( self._op5, slicing, self._priority, objectName=self.objectName() )

    def _setDirtyLF(self, slot, roi):
        self.setDirty(roi.toSlice())

    def setDirty( self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception('dirty region: slicing is not pure')
        self.isDirty.emit( slicing )

    def __eq__( self, other ):
        if other is None:
            return False
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
        if other is None:
            return False
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

    def clean_up(self):
        pass

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
        if other is None:
            return False
        return self._constant == other._constant
    
    def __ne__( self, other ):
        return not ( self == other )

    def dtype(self):
        return self._dtype

assert issubclass(ConstantSource, SourceABC)


class MinMaxUpdateRequest( object ):
    def __init__( self, rawRequest, update_func ):
        self._rawRequest = rawRequest
        self._update_func = update_func

    def wait( self ):
        rawData = self._rawRequest.wait()
        self._result = rawData
        self._update_func(rawData)
        return self._result
    
    # callback( result = result, **kwargs )
    def notify( self, callback, **kwargs ):
        def handleResult(rawResult):
            self._result =  rawResult
            self._update_func(rawResult)
            callback( self._result, **kwargs )
        self._rawRequest.notify( handleResult )

    def getResult(self):
        return self._result

assert issubclass(MinMaxUpdateRequest, RequestABC)




class MinMaxSource( QObject ):
    """
    A datasource that serves as a normalizing decorator for other datasources.
    """
    isDirty = pyqtSignal( object )
    boundsChanged = pyqtSignal(object) # When a new min/max is discovered in the result of a request, this signal is fired with the new (dmin, dmax)
    
    def __init__( self, rawSource, parent=None ):
        """
        rawSource: The original datasource whose data will be normalized
        """
        super(MinMaxSource, self).__init__(parent)
        
        self._rawSource = rawSource
        self._rawSource.isDirty.connect( self.isDirty )
        self._bounds = [1e9,-1e9]
        
        self._delayedDirtySignal = QTimer()
        self._delayedDirtySignal.setSingleShot(True)
        self._delayedDirtySignal.setInterval(10)
        self._delayedDirtySignal.timeout.connect( partial(self.setDirty, sl[:,:,:,:,:]) )
            
    def clean_up(self):
        self._rawSource.clean_up()

    @property
    def dataSlot(self):
        if hasattr(self._rawSource, "_orig_outslot"):
            return self._rawSource._orig_outslot
        else:
            return None
            
    def dtype(self):
        return self._rawSource.dtype()
    
    def request( self, slicing ):
        rawRequest = self._rawSource.request(slicing)
        return MinMaxUpdateRequest( rawRequest, self._getMinMax )

    def setDirty( self, slicing ):
        self.isDirty.emit(slicing)

    def __eq__( self, other ):
        equal = True
        if other is None:
            return False
        equal &= isinstance( other, MinMaxSource )
        equal &= ( self._rawSource == other._rawSource )
        return equal

    def __ne__( self, other ):
        return not ( self == other )

    def _getMinMax(self, data):
        dmin = np.min(data)
        dmax = np.max(data)
        dmin = min(self._bounds[0], dmin)
        dmax = max(self._bounds[1], dmax)
        dirty = False
        if (self._bounds[0]-dmin) > 1e-2:
            dirty = True
        if (dmax-self._bounds[1]) > 1e-2:
            dirty = True

        if dirty:
            self._bounds[0] = min(self._bounds[0], dmin)
            self._bounds[1] = max(self._bounds[0], dmax)
            self.boundsChanged.emit(self._bounds)

            # Our min/max have changed, which means we must force the TileProvider to re-request all tiles.
            # If we simply mark everything dirty now, then nothing changes for the tile we just rendered.
            # (It was already dirty.  That's why we are rendering it right now.)
            # And when this data gets back to the TileProvider that requested it, the TileProvider will mark this tile clean again.
            # To ENSURE that the current tile is marked dirty AFTER the TileProvider has stored this data (and marked the tile clean),
            #  we'll use a timer to set everything dirty.
            # This fixes ilastik issue #418

            # Finally, note that before this timer was added, the problem described above occurred at random due to a race condition:
            # Sometimes the 'dirty' signal was processed BEFORE the data (bad) and sometimes it was processed after the data (good),
            # due to the fact that the Qt signals are always delivered in the main thread.
            # Perhaps a better way to fix this would be to store a timestamp in the TileProvider for dirty notifications, which 
            # could be compared with the request timestamp before clearing the dirty state for each tile.

            # Signal everything dirty with a timer, as described above.            
            self._delayedDirtySignal.start()

            # Now, that said, we can still give a slightly more snappy response to the OTHER tiles (not this one)
            # if we immediately tell the TileProvider we are dirty.  This duplicates some requests, but that shouldn't be a big deal.
            self.setDirty( sl[:,:,:,:,:] )
    
    def resetBounds(self):
        self._bounds = [1e9,-1e9]


assert issubclass(MinMaxSource, SourceABC)


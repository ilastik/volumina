###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#		   http://ilastik.org/license/
###############################################################################
import sys
import threading
import weakref
from functools import partial, wraps
from PyQt5.QtCore import QObject, pyqtSignal, QTimer
from asyncabcs import RequestABC, SourceABC, IndeterminateRequestError
import volumina
from volumina.slicingtools import is_pure_slicing, slicing2shape, \
    is_bounded, make_bounded, index2slice, sl
from volumina.config import cfg
import numpy as np

_has_lazyflow = True
try:
    import lazyflow.operators.opReorderAxes
    from lazyflow.roi import sliceToRoi, roiToSlice
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
        if self._result is None:
            self._result = self._array[self._slicing]
        return self._result
    
    def getResult(self):
        return self._result

    def cancel( self ):
        pass

    def submit( self ):
        pass
        
assert issubclass(ArrayRequest, RequestABC)

#*******************************************************************************
# A r r a y S o u r c e                                                        *
#*******************************************************************************

class ArraySource( QObject ):
    isDirty = pyqtSignal( object )
    numberOfChannelsChanged = pyqtSignal(int) # Never emitted
     
    def __init__( self, array ):
        super(ArraySource, self).__init__()
        self._array = array
        
    @property
    def numberOfChannels(self):
        return self._array.shape[-1]

    def clean_up(self):
        self._array = None

    def dtype(self):
        if isinstance(self._array.dtype, type):
            return self._array.dtype
        return self._array.dtype.type

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
        assert relabeling.dtype == self._array.dtype, "relabeling.dtype=%r != self._array.dtype=%r" % (relabeling.dtype, self._array.dtype)
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
        

if _has_lazyflow:
    from lazyflow.graph import Slot
    def translate_lf_exceptions(func):
        """
        Decorator.
        Since volumina doesn't know about lazyflow, this datasource is responsible 
        for translating SlotNotReady errors into the volumina equivalent.
        """
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Slot.SlotNotReadyError as ex:
                # Translate lazyflow not-ready errors into the volumina equivalent.
                raise IndeterminateRequestError, IndeterminateRequestError(ex), sys.exc_info()[2]
        wrapper.__wrapped__ = func # Emulate python 3 behavior of @functools.wraps        
        return wrapper

    #*******************************************************************************
    # L a z y f l o w R e q u e s t                                                *
    #*******************************************************************************
    class LazyflowRequest( object ):
        
        @translate_lf_exceptions
        def __init__(self, op, slicing, prio, objectName="Unnamed LazyflowRequest" ):
            shape = op.Output.meta.shape
            if shape is not None:
                slicing = make_bounded(slicing, shape)
            self._req = op.Output[slicing]
            self._slicing = slicing
            self._shape = slicing2shape(slicing)
            self._objectName = objectName
            
        @translate_lf_exceptions
        def wait( self ):
            a = self._req.wait()
            assert(isinstance(a, np.ndarray))
            assert(a.shape == self._shape), "LazyflowRequest.wait() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
            return a
            
        @translate_lf_exceptions
        def getResult(self):
            a = self._req.result
            assert(isinstance(a, np.ndarray))
            assert(a.shape == self._shape), "LazyflowRequest.getResult() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s" % (self._objectName, self._shape, self._slicing, a.shape)
            return a
    
        def cancel( self ):
            self._req.cancel()
    
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
        numberOfChannelsChanged = pyqtSignal(int)
    
        @property
        def dataSlot(self):
            return self._orig_outslot
    
        def __init__( self, outslot, priority = 0 ):
            super(LazyflowSource, self).__init__()
    
            assert _has_lazyflow, "Can't instantiate a LazyflowSource: Wasn't able to import lazyflow."
    
            self._orig_outslot = outslot
            self._orig_meta = outslot.meta.copy()
    
            # Attach an OpReorderAxes to ensure the data will display correctly
            # (We include the graph parameter, too, since tests sometimes provide an operator with no parent.)
            self._op5 = lazyflow.operators.opReorderAxes.OpReorderAxes( parent=outslot.getRealOperator().parent, graph=outslot.getRealOperator().graph )
            self._op5.Input.connect( outslot )
    
            self._priority = priority
            self._dirtyCallback = partial( weakref_setDirtyLF, weakref.ref(self) )
            self._op5.Output.notifyDirty( self._dirtyCallback )
            self._op5.externally_managed = True
    
            self.additional_owned_ops = [] 
    
            self._shape = self._op5.Output.meta.shape
            self._op5.Output.notifyMetaChanged( self._checkForNumChannelsChanged )
    
        @property
        def numberOfChannels(self):
            return self._shape[-1]
        
        def _checkForNumChannelsChanged(self, *args):
            if self._op5 and self._op5.Output.ready() and self._shape[-1] != self._op5.Output.meta.shape[-1]:
                self._shape = tuple(self._op5.Output.meta.shape)
                self.numberOfChannelsChanged.emit( self._shape[-1] )
    
        def clean_up(self):
            self._op5.cleanUp()
            self._op5 = None
            for op in reversed(self.additional_owned_ops):
                op.cleanUp()
    
        def dtype(self):
            dtype = self._orig_outslot.meta.dtype
            assert dtype is not None, "Your LazyflowSource doesn't have a dtype! Is your lazyflow slot properly configured in setupOutputs()?"
            return dtype
        
        @translate_lf_exceptions
        def request( self, slicing ):
            if cfg.getboolean('pixelpipeline', 'verbose'):
                volumina.printLock.acquire()
                print "  LazyflowSource '%s' requests %s" % (self.objectName(), volumina.strSlicing(slicing))
                volumina.printLock.release()
            if not is_pure_slicing(slicing):
                raise Exception('LazyflowSource: slicing is not pure')
            assert self._op5 is not None, "Underlying operator is None.  Are you requesting from a datasource that has been cleaned up already?"

            start, stop = sliceToRoi(slicing, self._op5.Output.meta.shape)
            clipped_roi = np.maximum(start, (0,0,0,0,0)), np.minimum(stop, self._op5.Output.meta.shape)
            clipped_slicing = roiToSlice(*clipped_roi)
            return LazyflowRequest( self._op5, clipped_slicing, self._priority, objectName=self.objectName() )
    
        def _setDirtyLF(self, slot, roi):
            clipped_roi = np.maximum(roi.start, (0,0,0,0,0)), np.minimum(roi.stop, self._op5.Output.meta.shape)
            self.setDirty( roiToSlice(*clipped_roi) )
    
        def setDirty( self, slicing):
            if not is_pure_slicing(slicing):
                raise Exception('dirty region: slicing is not pure')
            self.isDirty.emit( slicing )
    
        def __eq__( self, other ):
            if other is None:
                return False
            if self._orig_meta != other._orig_meta:
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
        
assert issubclass(ConstantRequest, RequestABC)

#*******************************************************************************
# C o n s t a n t S o u r c e                                                  *
#*******************************************************************************

class ConstantSource( QObject ):
    isDirty = pyqtSignal( object )
    idChanged = pyqtSignal( object, object ) # old, new
    numberOfChannelsChanged = pyqtSignal(int) # Never emitted

    @property
    def constant( self ):
        return self._constant

    @property
    def numberOfChannels(self):
        return 1

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
    
    def getResult(self):
        return self._result

assert issubclass(MinMaxUpdateRequest, RequestABC)


class MinMaxSource( QObject ):
    """
    A datasource that serves as a normalizing decorator for other datasources.
    """
    isDirty = pyqtSignal( object )
    boundsChanged = pyqtSignal(object) # When a new min/max is discovered in the result of a request, this signal is fired with the new (dmin, dmax)
    numberOfChannelsChanged = pyqtSignal(int)
    
    _delayedBoundsChange = pyqtSignal() # Internal use only.  Allows non-main threads to start the delayedDirtySignal timer.
    
    
    def __init__( self, rawSource, parent=None ):
        """
        rawSource: The original datasource whose data will be normalized
        """
        super(MinMaxSource, self).__init__(parent)
        
        self._rawSource = rawSource
        self._rawSource.isDirty.connect( self.isDirty )
        self._rawSource.numberOfChannelsChanged.connect( self.numberOfChannelsChanged )
        self._bounds = [1e9,-1e9]
        
        self._delayedDirtySignal = QTimer()
        self._delayedDirtySignal.setSingleShot(True)
        self._delayedDirtySignal.setInterval(10)
        self._delayedDirtySignal.timeout.connect( partial(self.setDirty, sl[:,:,:,:,:]) )
        self._delayedBoundsChange.connect(self._delayedDirtySignal.start)

    @property
    def numberOfChannels(self):
        return self._rawSource.numberOfChannels

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
            self._bounds[0] = dmin 
            self._bounds[1] = dmax 
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
            self._delayedBoundsChange.emit()

            # Now, that said, we can still give a slightly more snappy response to the OTHER tiles (not this one)
            # if we immediately tell the TileProvider we are dirty.  This duplicates some requests, but that shouldn't be a big deal.
            self.setDirty( sl[:,:,:,:,:] )


assert issubclass(MinMaxSource, SourceABC)


class HaloAdjustedDataSource( QObject ):
    """
    A wrapper for other datasources.
    For any datasource request, expands the requested ROI by a halo
    and forwards the expanded request to the underlying datasouce object.
    """
    isDirty = pyqtSignal( object )
    numberOfChannelsChanged = pyqtSignal(int)
    
    def __init__( self, rawSource, halo_start_delta, halo_stop_delta, parent=None ):
        """
        rawSource: The original datasource that we'll be requesting data from.
        halo_start_delta: For example, to expand by 1 pixel in spatial dimensions only:
                          (0,-1,-1,-1,0)
        halo_stop_delta: For example, to expand by 1 pixel in spatial dimensions only:
                          (0,1,1,1,0)
        """
        super(HaloAdjustedDataSource, self).__init__(parent)
        self._rawSource = rawSource
        self._rawSource.isDirty.connect( self.setDirty )
        self._rawSource.numberOfChannelsChanged.connect( self.numberOfChannelsChanged )
        
        assert all(s <= 0 for s in halo_start_delta), "Halo start should be non-positive"
        assert all(s >= 0 for s in halo_stop_delta), "Halo stop should be non-negative"
        self.halo_start_delta = halo_start_delta
        self.halo_stop_delta = halo_stop_delta

    @property
    def numberOfChannels(self):
        return self._rawSource.numberOfChannels

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
        slicing_with_halo = self._expand_slicing_with_halo(slicing)
        return self._rawSource.request(slicing_with_halo)

    def setDirty( self, slicing ):
        # FIXME: This assumes the halo is symmetric
        slicing_with_halo = self._expand_slicing_with_halo(slicing)
        self.isDirty.emit(slicing_with_halo)

    def __eq__( self, other ):
        equal = True
        if other is None:
            return False
        equal &= isinstance( other, type(self) )
        equal &= ( self._rawSource == other._rawSource )
        return equal

    def __ne__( self, other ):
        return not ( self == other )

    def _expand_slicing_with_halo(self, slicing):
        return tuple( slice(s.start+halo_start, s.stop+halo_stop)
                      for (s, halo_start, halo_stop) in zip( slicing,
                                    self.halo_start_delta,
                                    self.halo_stop_delta ) )
    

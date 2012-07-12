from functools import partial
from PyQt4.QtCore import QObject, pyqtSignal, QRect
from slicesources import SliceSource, SyncedSliceSources
from imagesourcefactories import createImageSource
from volumina.pixelpipeline.imagesources import AlphaModulatedImageSource, ColortableImageSource

class StackedImageSources( QObject ):
    """
    Manages an ordered stack of image sources.
    
    The StackedImageSources manages the 'add' and 'remove' operation to a stack
    of objects derived from 'ImageSource'. The stacking order mirrors the
    LayerStackModel, and each Layer object has a corresponding ImageSource
    object that can be queried to produce images which adhere to the
    specification as defined in the Layer object. 

    Imagesource indices in the stack correspond to row numbers. So the
    topmost imagesource has an index 0, the second-to-the-top an index
    of 1 and so on. This is different from other stacks, where the
    bottommost item has the lowest index.

    Layers from the underlying layerstack have to be registered
    explicitly to become active in the StackedImageSources. If
    registered layers are removed in the underlying layerstack they
    become inactive, but are still registered internally. You have to
    call 'deregister' explicitly to remove them from the internal
    datastructures. The reason for this design is as follows. If
    layers are moved around in the layerstack, they are removed and
    readded internally. We can't distinguish between such a remove and
    a permanent remove.

    """    
    layerDirty = pyqtSignal(int, QRect)
    visibleChanged = pyqtSignal(int, bool)
    opacityChanged = pyqtSignal(int, float)
    syncedIdChanged = pyqtSignal( object, object ) # old id, new id
    sizeChanged  = pyqtSignal()
    orderChanged = pyqtSignal()

    class _ViewBase( object ):
        def __init__( self, sims ):
            self.sims = sims

        def __len__( self ):
            return len(self.sims)

    class VisibleView( _ViewBase ):
        def __iter__( self ):
            return ( layer.visible
                     for layer in self.sims._layerStackModel
                     if self.sims.isActive(layer)  )

        def __getitem__( self, row ):
            return self.sims._getLayer(row).visible

    class OpacityView( _ViewBase ):
        def __iter__( self ):
            return ( layer.opacity
                     for layer in self.sims._layerStackModel
                     if self.sims.isActive(layer) )

        def __getitem__( self, row ):
            return self.sims._getLayer(row).opacity

    class ImageSourceView( _ViewBase ):
        def __iter__( self ):
            return ( self.sims._layerToIms[layer]
                     for layer in self.sims._layerStackModel
                     if self.sims.isActive(layer) )

        def __getitem__( self, row ):
            return self.sims._layerToIms[self.sims._getLayer(row)]

    def __init__( self, layerStackModel ):
        super(StackedImageSources, self).__init__()
        self._layerStackModel = layerStackModel

        # we need to store partial functions to which we connect
        # for later disconnection
        self._curryRegistry = {'I':{}, "O":{}, "V":{}, "Id":{}}

        # Each layer has a single image source, which has been set-up according
        # to the layer's specification.
        # Note, that we don't maintain our own imagesource stack. We just observe
        # the layerStackModel and mirror the stack order there
        self._layerToIms = {} #look up layer -> corresponding image source
        self._imsToLayer = {} #look up image source -> corresponding layer
        self._imsOccluded = {}
        self._firstOpaqueIdx = None

        layerStackModel.orderChanged.connect( self._onOrderChanged )
        layerStackModel.sizeChanged.connect( self._onSizeChanged )

        self.syncedId = (0,0,0)

    def __len__( self ):
        return len([ _ for _ in self])

    def __getitem__(self, row):
        layer = self._getLayer(row)
        ims = self._layerToIms[layer]
        return (layer.visible, layer.opacity, ims)

    def __iter__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in self._layerStackModel
                 if layer in self._layerToIms.keys() )
                
    def __reversed__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in reversed(self._layerStackModel)
                 if self.isActive(layer) )

    def getVisible( self, row ):
        return self._getLayer(row).visible

    def getOpacity( self, row ):
        return self._getLayer(row).opacity

    def getImageSource( self, row ):
        return self._layerToIms[self._getLayer(row)]

    def viewVisible( self ):
        return StackedImageSources.VisibleView( self )

    def viewOpacity( self ):
        return StackedImageSources.OpacityView( self )

    def viewImageSources( self ):
        return StackedImageSources.ImageSourceView( self )

    def register( self, layer, imageSource ):
        if self.isRegistered(layer):
            raise Exception("StackedImageSources.register(): layer %s already registered" % str(layer))
        if layer not in self._layerStackModel:
            raise Exception("StackedImageSources.register(): layer %s is not in LayerStackModel" % str(layer))
        self._layerToIms[layer] = imageSource
        self._imsToLayer[imageSource] = layer

        self._curryRegistry['I'][imageSource] = partial(self._onImageSourceDirty, imageSource)
        self._curryRegistry['O'][layer] = partial(self._onOpacityChanged, layer)
        self._curryRegistry['V'][layer] = partial(self._onVisibleChanged, layer)
        self._curryRegistry['Id'][imageSource] = partial(self._onImageSourceIdChanged, imageSource)

        imageSource.isDirty.connect( self._curryRegistry['I'][imageSource] ) 
        layer.opacityChanged.connect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.connect( self._curryRegistry['V'][layer] )
        imageSource.idChanged.connect( self._curryRegistry['Id'][imageSource] )

        self.syncedId = imageSource.id

        self._updateOcclusionInfo()
        self.sizeChanged.emit()

    def deregister( self, layer ):
        if layer not in self._layerToIms:
            raise Exception("StackedImageSources.deregister(): layer %s is not registered; can't be deregistered" % str(layer))
        ims = self._layerToIms[layer]

        ims.isDirty.disconnect( self._curryRegistry['I'][ims] )
        layer.opacityChanged.disconnect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.disconnect( self._curryRegistry['V'][layer] )
        ims.idChanged.disconnect( self._curryRegistry['Id'][ims] )
        
        del self._curryRegistry['I'][ims]
        del self._curryRegistry['O'][layer]
        del self._curryRegistry['V'][layer]
        del self._curryRegistry['Id'][ims]

        del self._imsToLayer[ims]
        del self._layerToIms[layer]

        self._updateOcclusionInfo()
        self.sizeChanged.emit()

    def isRegistered( self, layer ):
        return layer in self._layerToIms

    def isActive( self, layer ):
        if not self.isRegistered( layer ):
            return False
        elif layer not in self._layerStackModel:
            return False
        else:
            return True

    def firstFullyOpaque(self):
        '''Return index of the first fully opaque imagesource.

        An imagesource is fully opaque when:
        * it is visible
        * its opacity is 1.0
        * the corresponding layer is opaque (i.e. there are
          no transparent 'holes' in the layer)
        
        '''
        return self._firstOpaqueIdx

    def isOccluded( self, ims ):
        return self._imsOccluded[ims]

    def _onImageSourceDirty( self, imageSource, rect ):
        layer = self._imsToLayer[imageSource]
        if layer.visible:
            self.layerDirty.emit(self._layerStackModel.layerIndex(layer), rect)

    def _onImageSourceIdChanged( self, imageSource, oldId, newId ):
        if not(newId == self.syncedId):
            oldId = self.syncedId
            self.syncedId = newId
            self.syncedIdChanged.emit(oldId, self.syncedId) 

    def _onOpacityChanged( self, layer, opacity ):
        self._updateOcclusionInfo()
        if layer.visible:
            self.opacityChanged.emit(self._layerStackModel.layerIndex(layer), opacity)

    def _onVisibleChanged( self, layer, visible ):
        self._updateOcclusionInfo()
        self.visibleChanged.emit(self._layerStackModel.layerIndex(layer), visible)

    def _onOrderChanged( self ):
        self._updateOcclusionInfo()
        self.orderChanged.emit()

    def _onSizeChanged( self ):
        self._updateOcclusionInfo()
        self.sizeChanged.emit()

    def _getLayer( self, ims_row ):
        return [layer for layer in self._layerStackModel
                       if self.isActive(layer)][ims_row]

    def _updateOcclusionInfo(self):
        self._firstOpaqueIdx = None
        self._imsOccluded = {}

        # Search for the first totally opaque and visible layer (if any)
        for i, v in enumerate( self ):
            if (v[0] # visible
            and v[1] == 1.0 # opacity
            and v[2].isOpaque()): # ims guarantees opaqueness
                self._firstOpaqueIdx = i
                break

        for i, v in enumerate( self.viewImageSources() ):
            if self._firstOpaqueIdx != None and i > self._firstOpaqueIdx:
                self._imsOccluded[v] = True
            else:
                self._imsOccluded[v] = False



#*******************************************************************************
# I m a g e P u m p                                                            *
#*******************************************************************************

class ImagePump( object ):
    @property
    def syncedSliceSources( self ):
        return self._syncedSliceSources

    @property
    def stackedImageSources( self ):
        return self._stackedImageSources

    def __init__( self, layerStackModel, sliceProjection ):
        super(ImagePump, self).__init__()
        self._layerStackModel = layerStackModel
        self._projection = sliceProjection
        self._layerToSliceSrcs = {}
    
        ## setup image source stack and slice sources
        self._stackedImageSources = StackedImageSources( layerStackModel )
        self._syncedSliceSources = SyncedSliceSources( len(sliceProjection.along) * [0] )
        for layer in layerStackModel:
            self._addLayer( layer )

        # ## handle layers removed from layerStackModel
        # def onRowsAboutToBeRemoved( parent, start, end):
        #     newSize = len(self._layerStackModel)-(end-start+1)
        #     #self._stackedImageSources.aboutToResize.emit(newSize) FIXME
        #     for i in xrange(start, end + 1):
        #         layer = self._layerStackModel[i]
        #         self._stackedImageSources.deregister(layer)
        #         self._removeLayer( layer )
        # layerStackModel.rowsAboutToBeRemoved.connect(onRowsAboutToBeRemoved)

        # def onRowsRemoved(parent,start,end):
        #     newSize = len(self._layerStackModel)
        #     #self._stackedImageSources.resizeFinished.emit(newSize) FIXME
        # layerStackModel.rowsRemoved.connect(onRowsRemoved)
        
        # def onRowsAboutToBeInserted(parent, start, end):
        #     # This function just forwards the signal to the image sources.
        #     # Layers are actually added in obDataChanged(), below
        #     newSize = len(self._layerStackModel)+(end-start+1)
        #     # self._stackedImageSources.aboutToResize.emit(newSize) #FIXME
        # layerStackModel.rowsAboutToBeInserted.connect(onRowsAboutToBeInserted)

        # def onRowsInserted(parent, start, end):
        #     newSize = len(self._layerStackModel)
        #     #self._stackedImageSources.resizeFinished.emit(newSize) FIXME
        # layerStackModel.rowsInserted.connect(onRowsInserted)

        ## handle new layers in layerStackModel
        def onDataChanged( startIndexItem, endIndexItem):
            start = startIndexItem.row()
            stop = endIndexItem.row() + 1

            for i in xrange(start, stop):
                layer = self._layerStackModel[i]
                # model implementation removes and adds the same layer instance to move selections up/down
                # therefore, check if the layer is already registered before adding as new
                if not self._stackedImageSources.isRegistered(layer): 
                    self._addLayer(layer)
        layerStackModel.dataChanged.connect(onDataChanged)

    def _createSources( self, layer ):
        def sliceSrcOrNone( datasrc ):
            if datasrc:
                return SliceSource( datasrc, self._projection )
            return None

        slicesrcs = map( sliceSrcOrNone, layer.datasources )
        ims = createImageSource( layer, slicesrcs )
        # remove Nones
        slicesrcs = [ src for src in slicesrcs if src != None]
        return slicesrcs, ims

    def _addLayer( self, layer ):
        sliceSources, imageSource = self._createSources(layer)
        for ss in sliceSources:
            self._syncedSliceSources.add(ss)
        self._layerToSliceSrcs[layer] = sliceSources
        self._stackedImageSources.register(layer, imageSource)

    def _removeLayer( self, layer ):
        for ss in self._layerToSliceSrcs[layer]:
            self._syncedSliceSources.remove(ss)
        del self._layerToSliceSrcs[layer] 

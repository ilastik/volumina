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

    """    
    layerDirty    = pyqtSignal(int, QRect)
    stackChanged  = pyqtSignal()
    aboutToResize = pyqtSignal(int)
    resizeFinished = pyqtSignal(int)

    def __init__( self, layerStackModel ):
        super(StackedImageSources, self).__init__()
        self._layerStackModel = layerStackModel
        #we need to store partial functions to which we connect
        #for later disconnection
        self._curryRegistry = {'I':{}, "O":{}, "V":{}}
        #each layer has a single image source, which has been set-up according
        #to the layer's specification
        self._layerToIms = {} #look up layer -> corresponding image source
        self._imsToLayer = {} #look up image source -> corresponding layer
        
        layerStackModel.orderChanged.connect( self.stackChanged )
        self.stackChanged.connect( self._updateLastVisibleLayer)
        self._lastVisibleLayer = 1e10

    def __len__( self ):
        return self._layerStackModel.rowCount()

    def __getitem__(self, i):
        layer = self._layerStackModel[i]
        return (layer.visible, layer.opacity, self._layerToIms[layer])

    def __iter__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in self._layerStackModel
                 if layer in self._layerToIms.keys() )
                
    def __reversed__( self ):
        return ( (layer.visible, layer.opacity, self._layerToIms[layer])
                 for layer in reversed(self._layerStackModel)
                 if layer in self._layerToIms.keys() )

    def getImageSource( self, index ):
        return self._layerToIms[self._layerStackModel[index]]

    def register( self, layer, imageSource ):
        assert not layer in self._layerToIms, "layer %s already registered" % str(layer)
        self._layerToIms[layer] = imageSource
        self._imsToLayer[imageSource] = layer
        
        self._curryRegistry['I'][imageSource] = partial(self._onImageSourceDirty, imageSource)
        self._curryRegistry['O'][layer] = partial(self._onOpacityChanged, layer)
        self._curryRegistry['V'][layer] = partial(self._onVisibleChanged, layer)

        imageSource.isDirty.connect( self._curryRegistry['I'][imageSource] ) 
        layer.opacityChanged.connect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.connect( self._curryRegistry['V'][layer] )
        self.stackChanged.emit()

    def deregister( self, layer ):
        assert layer in self._layerToIms, "layer %s is not registered; can't be deregistered" % str(layer)
        ims = self._layerToIms[layer]
        ims.isDirty.disconnect( self._curryRegistry['I'][ims] )
        layer.opacityChanged.disconnect( self._curryRegistry['O'][layer] )
        layer.visibleChanged.disconnect( self._curryRegistry['V'][layer] )
        self._layerToIms.pop(layer)

    def remove( self, layer ):
        del self._curryRegistry['I'][ims]
        del self._curryRegistry['V'][layer]
        del self._curryRegistry['O'][layer]
        del self._imsToLayer[ims]
        del self._layerToIms[layer]
        self.stackChanged.emit()

    def isRegistered( self, layer ):
        return layer in self._layerToIms

    def _onImageSourceDirty( self, imageSource, rect ):
        layer = self._imsToLayer[imageSource]
        if layer.visible:
            self.layerDirty.emit(self._layerStackModel.layerIndex(layer), rect)

    def _updateLastVisibleLayer(self):
        # By default, assume all layers are visible
        self._lastVisibleLayer = len(self._layerStackModel) - 1

        # Search for the first totally opaque layer (if any)
        for i, layer in enumerate(self._layerStackModel):
          if  layer in self._layerToIms.keys() \
          and layer.visible \
          and layer.opacity == 1.0 \
          and not isinstance(self._layerToIms[layer], (AlphaModulatedImageSource, ColortableImageSource)): 
            self._lastVisibleLayer = i
            break

    def _onOpacityChanged( self, layer, opacity ):
        self._updateLastVisibleLayer()
        if layer.visible:
            self.layerDirty.emit(self._layerStackModel.layerIndex(layer), QRect())

    def _onVisibleChanged( self, layer, visible ):
        self._updateLastVisibleLayer()
        self.layerDirty.emit(self._layerStackModel.layerIndex(layer), QRect())

    def lastVisibleLayer(self):
        return self._lastVisibleLayer



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

        ## handle layers removed from layerStackModel
        def onRowsAboutToBeRemoved( parent, start, end):
            newSize = len(self._layerStackModel)-(end-start+1)
            self._stackedImageSources.aboutToResize.emit(newSize)
            for i in xrange(start, end + 1):
                layer = self._layerStackModel[i]
                self._stackedImageSources.deregister(layer)
                self._removeLayer( layer )
        layerStackModel.rowsAboutToBeRemoved.connect(onRowsAboutToBeRemoved)

        def onRowsRemoved(parent,start,end):
            newSize = len(self._layerStackModel)
            self._stackedImageSources.resizeFinished.emit(newSize)
        layerStackModel.rowsRemoved.connect(onRowsRemoved)
        
        def onRowsAboutToBeInserted(parent, start, end):
            # This function just forwards the signal to the image sources.
            # Layers are actually added in obDataChanged(), below
            newSize = len(self._layerStackModel)+(end-start+1)
            self._stackedImageSources.aboutToResize.emit(newSize)
        layerStackModel.rowsAboutToBeInserted.connect(onRowsAboutToBeInserted)

        def onRowsInserted(parent, start, end):
            newSize = len(self._layerStackModel)
            self._stackedImageSources.resizeFinished.emit(newSize)
        layerStackModel.rowsInserted.connect(onRowsInserted)

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

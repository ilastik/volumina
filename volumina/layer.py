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
import colorsys
import numpy

from PyQt4.QtCore import Qt, QObject, pyqtSignal, QString
from PyQt4.QtGui import QColor, QPen

from volumina.interpreter import ClickInterpreter
from volumina.pixelpipeline.asyncabcs import SourceABC
from volumina.pixelpipeline.datasources import MinMaxSource, HaloAdjustedDataSource

from volumina.utility import decode_to_qstring, encode_from_qstring, SignalingDefaultDict

from functools import partial

#*******************************************************************************
# L a y e r                                                                    *
#*******************************************************************************

class Layer( QObject ):
    '''
    properties:
    datasources -- list of ArraySourceABC; read-only
    visible -- boolean
    opacity -- float; range 0.0 - 1.0
    name -- QString
    numberOfChannels -- int
    layerId -- any object that can uniquely identify this layer within a layerstack (by default, same as name)
    '''

    '''changed is emitted whenever one of the more specialized
    somethingChanged signals is emitted.'''
    changed = pyqtSignal()

    visibleChanged = pyqtSignal(bool) 
    opacityChanged = pyqtSignal(float) 
    nameChanged = pyqtSignal(object)  # sends a python str object, not a QString!
    channelChanged = pyqtSignal(int)
    numberOfChannelsChanged = pyqtSignal(int)

    @property
    def normalize( self ):
        return None

    @property
    def visible( self ):
        return self._visible
    @visible.setter
    def visible( self, value ):
        if value != self._visible and self._allowToggleVisible:
            self._visible = value
            self.visibleChanged.emit( value )
    
    def toggleVisible(self):
        """Convenience function."""
        if self._allowToggleVisible:
            self.visible = not self._visible

    @property
    def opacity( self ):
        return self._opacity
    @opacity.setter
    def opacity( self, value ):
        if value != self._opacity:
            self._opacity = value
            self.opacityChanged.emit( value )
            
    @property
    def name( self ):
        return self._name
    @name.setter
    def name( self, n ):
        if isinstance(n, str):
            n = decode_to_qstring(n, 'utf-8')
        assert isinstance(n, QString)
        pystr = encode_from_qstring(n, 'utf-8')

        if self._name != n:
            self._name = n
            self.nameChanged.emit(pystr)

    @property
    def numberOfChannels( self ):
        return self._numberOfChannels
    @numberOfChannels.setter
    def numberOfChannels( self, n ):
        if self._numberOfChannels == n:
            return
        if self._channel >= n and n > 0:
            self.channel = n - 1
        elif n < 1:
            raise ValueError("Layer.numberOfChannels(): should be greater or equal 1")
        self._numberOfChannels = n
        self.numberOfChannelsChanged.emit(n)

    @property
    def channel( self ):
        return self._channel
    
    @channel.setter
    def channel( self, n ):
        if self._channel == n:
            return
        if n < self.numberOfChannels:
            self._channel = n
        else:
            raise ValueError("Layer.channel.setter: channel value has to be less than number of channels")
        self.channelChanged.emit( self._channel ) 

    @property
    def datasources( self ):
        return self._datasources

    @property
    def layerId( self ):
        # If we have no real id, use the name
        if self._layerId is None:
            return self._name
        else:
            return self._layerId
    
    @layerId.setter
    def layerId( self, lid ):
        self._layerId = lid

    def setActive( self, active ):
        """This function is called whenever the layer is selected (active = True) or deselected (active = False)
           by the user.
           As an example, this can be used to enable a specific event interpreter when the layer is active
           and to disable it when it is not active.
           See ClickableColortableLayer for an example."""
        pass

    def timePerTile( self, timeSec, tileRect ):
        """Update the average time per tile with new data: the tile of size tileRect took timeSec seonds"""
        #compute cumulative moving average
        self._numTiles += 1
        self.averageTimePerTile = (timeSec + (self._numTiles-1)*self.averageTimePerTile) / self._numTiles

    def toolTip(self):
        return self._toolTip

    def setToolTip(self, tip):
        self._toolTip = tip
        
    def isDifferentEnough(self, other_layer):
        """This ugly function is here to support the updateAllLayers function in the layerViewerGui in ilastik"""
        if type(other_layer) != type(self):
            return True
        if other_layer.datasources != self.datasources:
            return True
        if other_layer.numberOfChannels != self.numberOfChannels:
            return True
        return False

    def __init__( self, datasources, direct=False ):
        super(Layer, self).__init__()
        self._name = QString("Unnamed Layer")
        self._visible = True
        self._opacity = 1.0
        self._datasources = datasources
        self._layerId = None
        self._numberOfChannels = 1
        self._allowToggleVisible = True
        self._channel = 0
        self.direct = direct
        self._toolTip = ""
        self._cleaned_up = False

        self._updateNumberOfChannels()
        for datasource in filter(None, self._datasources):
            datasource.numberOfChannelsChanged.connect( self._updateNumberOfChannels )

        if self.direct:
            #in direct mode, we calculate the average time per tile for debug purposes
            #this is useful to identify which of your layers cause slowness
            self.averageTimePerTile = 0.0
            self._numTiles = 0

        self.visibleChanged.connect(self.changed)
        self.opacityChanged.connect(self.changed)
        self.nameChanged.connect(self.changed)
        self.numberOfChannelsChanged.connect(self.changed)
        self.channelChanged.connect(self.changed)

        self.contexts = []

    def _updateNumberOfChannels(self):
        # As there can be many datasources and they can all be None,
        # grab numberOfChannels for those that are defined.
        # That is, if there are any datasources.
        newchannels = []
        for i in xrange(len(self._datasources)):
            if self._datasources[i] is not None:
                newchannels.append(self._datasources[i].numberOfChannels)

        # If the datasources are all None or there aren't any,
        # default to 1 channel as we must have at least 1.
        if not newchannels:
            newchannels = [1]

        # Get the smallest number of channels that works for all.
        newchannels = min(newchannels)

        if newchannels != self.numberOfChannels:
            # Update property (emits signal)
            self.numberOfChannels = newchannels

    def clean_up(self):
        """
        Cleans up resources in this layer's datasources.
        Must not be called more than once.
        """
        assert not self._cleaned_up, "Bug: You're attempting to clean layer {} twice.".format( self.name )
        for src in self.datasources:
            if src is not None:
                src.clean_up()
        self._cleaned_up = True

        
#*******************************************************************************
# C l i c k a b l e L a y e r                                                  *
#*******************************************************************************

class ClickableLayer( Layer ):
    """A layer that, when being activated/selected, switches to an interpreter than can intercept
       right click events"""
    def __init__( self, datasource, editor, clickFunctor, direct=False, right=True ):
        super(ClickableLayer, self).__init__([datasource], direct=direct)
        self._editor = editor
        self._clickInterpreter = ClickInterpreter(editor, self, clickFunctor, right=right)
        self._inactiveInterpreter = self._editor.eventSwitch.interpreter
    
    def setActive(self, active):
        if active:
            self._editor.eventSwitch.interpreter = self._clickInterpreter
        else:
            self._editor.eventSwitch.interpreter = self._inactiveInterpreter

#*******************************************************************************
# N o r m a l i z a b l e L a y e r                                            *
#*******************************************************************************

def dtype_to_range(dsource):
    if dsource is not None:
        dtype = dsource.dtype()
    else:
        dtype = numpy.uint8
    
    if (dtype == numpy.bool_ or dtype == bool):
        # Special hack for bool
        rng = (0,1)
    elif issubclass(dtype, (int, long, numpy.integer)):
        rng = (0, numpy.iinfo(dtype).max)
    elif (dtype == numpy.float32 or dtype == numpy.float64):
        # Is there a way to get the min and max values of the actual dataset(s)?
        # arbitrary range choice
        rng = (-4096,4096)
    else:
        # raise error 
        raise Exception('dtype_to_range: unknown dtype {}'.format(dtype))
    return rng

class NormalizableLayer( Layer ):
    '''
    int -- datasource index
    int -- lower threshold
    int -- upper threshold
    '''
    normalizeChanged = pyqtSignal(int, int, int)

    '''
    int -- datasource index
    int -- minimum
    int -- maximum
    '''
    rangeChanged = pyqtSignal(int, int, int)

    @property
    def range( self ):
        return self._range

    def set_range( self, datasourceIdx, value ):
        '''
        value -- (rmin, rmax)
        '''
        if value is not None:
            self._range[datasourceIdx] = value
        else:
            value = self._range[datasourceIdx] = \
                dtype_to_range(self._datasources[datasourceIdx])
        self.rangeChanged.emit(datasourceIdx, value[0], value[1])
    
    @property
    def normalize( self ):
        return self._normalize

    def set_normalize( self, datasourceIdx, value ):
        '''
        value -- (nmin, nmax)
        value -- None : grabs (min, max) from the MinMaxSource
        '''
        if self._datasources[datasourceIdx] is None:
            return
        
        if value is None:
            value = self._datasources[datasourceIdx]._bounds
            self._autoMinMax[datasourceIdx] = True
        if value is False:
            value = self._range[datasourceIdx]
            self._autoMinMax[datasourceIdx] = False
        else:
            self._autoMinMax[datasourceIdx] = False
        self._normalize[datasourceIdx] = value 
        self.normalizeChanged.emit(datasourceIdx, value[0], value[1])

    def __init__( self, datasources, range=None, normalize=None, direct=False ):
        """
        datasources - a list of raw data sources
        range - Not sure.  I think this parameter should be removed.
        normalize - If normalize is a tuple (dmin, dmax), the data is normalized from (dmin, dmax) to (0,255) before it is displayed.
                    If normalize=None, then (dmin, dmax) is automatically determined before normalization.
                    If normalize=False, then no normalization is applied before displaying the data.
        
        """
        self._normalize = []
        self._range = []
        self._autoMinMax = []
        self._mmSources = []

        wrapped_datasources = [None]*len( datasources )

        for i,datasource in enumerate(datasources):
            if datasource is not None:
                self._autoMinMax.append(normalize is None) # Don't auto-set normalization if the caller provided one.
                mmSource = MinMaxSource(datasource)
                mmSource.boundsChanged.connect(partial(self._bounds_changed, i))
                wrapped_datasources[i] = mmSource
                self._mmSources.append(mmSource)

        super(NormalizableLayer, self).__init__(wrapped_datasources, direct=direct)

        for i, datasource in enumerate(self.datasources):
            if datasource is not None:
                self._normalize.append(normalize)
                self._range.append(range)
                self.set_range(i, range)
                self.set_normalize(i, normalize)
            else:
                self._normalize.append((0,1))
                self._range.append((0,1))
                self._autoMinMax.append(True)

        self.rangeChanged.connect(self.changed)
        self.normalizeChanged.connect(self.changed)

    def _bounds_changed(self, datasourceIdx, range):
        if self._autoMinMax[datasourceIdx]:
            self.set_normalize(datasourceIdx, None)

    def resetBounds(self):
        for mm in self._mmSources:
            mm.resetBounds()


#*******************************************************************************
# G r a y s c a l e L a y e r                                                  *
#*******************************************************************************

class GrayscaleLayer( NormalizableLayer ):
    @property
    def window_leveling( self ):
        return self._window_leveling
    
    @window_leveling.setter
    def window_leveling( self, wl ):
        self._window_leveling = wl

    def __init__( self, datasource, range = None, normalize = None, direct=False, window_leveling=False):
        assert isinstance(datasource, SourceABC)
        super(GrayscaleLayer, self).__init__([datasource], range, normalize, direct=direct)
        self._window_leveling = window_leveling

#*******************************************************************************
# A l p h a M o d u l a t e d L a y e r                                        *
#*******************************************************************************

class AlphaModulatedLayer( NormalizableLayer ):
    tintColorChanged = pyqtSignal()

    @property
    def tintColor(self):
        return self._tintColor
    @tintColor.setter
    def tintColor(self, c):
        if self._tintColor != c:
            self._tintColor = c
            self.tintColorChanged.emit()
    
    def __init__( self, datasource, tintColor = QColor(255,0,0), range = (0,255), normalize = None ):
        assert isinstance(datasource, SourceABC)
        super(AlphaModulatedLayer, self).__init__([datasource], range, normalize)
        self._tintColor = tintColor
        self.tintColorChanged.connect(self.changed)
        
#*******************************************************************************
# C o l o r t a b l e L a y e r                                                *
#*******************************************************************************

def generateRandomColors(M=256, colormodel="hsv", clamp=None, zeroIsTransparent=False):
    """Generate a colortable with M entries.
       colormodel: currently only 'hsv' is supported
       clamp:      A dictionary stating which parameters of the color in the colormodel are clamped to a certain
                   value. For example: clamp = {'v': 1.0} will ensure that the value of any generated
                   HSV color is 1.0. All other parameters (h,s in the example) are selected randomly
                   to lie uniformly in the allowed range. """
    r = numpy.random.random((M, 3))
    if clamp is not None:
        for k,v in clamp.iteritems():
            idx = colormodel.index(k)
            r[:,idx] = v

    colors = []
    if colormodel == "hsv":
        for i in range(M):
            if zeroIsTransparent and i == 0:
                colors.append(QColor(0, 0, 0, 0).rgba())
            else:
                h, s, v = r[i,:] 
                color = numpy.asarray(colorsys.hsv_to_rgb(h, s, v)) * 255
                qColor = QColor(*color)
                colors.append(qColor.rgba())
        return colors
    else:
        raise RuntimeError("unknown color model '%s'" % colormodel)

class ColortableLayer( NormalizableLayer ):
    colorTableChanged = pyqtSignal()

    @property
    def colorTable( self ):
        return self._colorTable

    @colorTable.setter
    def colorTable( self, colorTable ):
        self._colorTable = colorTable
        self.colorTableChanged.emit()

    def randomizeColors(self, zeroIsTransparent=True):
        self.colorTable = generateRandomColors(len(self._colorTable), "hsv", {"v": 1.0}, zeroIsTransparent)
        
    def isDifferentEnough(self, other_layer):
        if type(other_layer) != type(self):
            return True
        if other_layer._colorTable != self._colorTable:
            return True
        if other_layer.datasources != self.datasources:
            return True
        return False
        

    def __init__( self, datasource , colorTable, normalize=False, direct=False ):
        assert isinstance(datasource, SourceABC)
        
        """
        By default, no normalization is performed on ColortableLayers.  
        If the normalize parameter is set to 'auto', 
        your data will be automatically normalized to the length of your colorable.  
        If a tuple (dmin, dmax) is passed, this specifies the range of your data, 
        which is used to normalize the data before the colorable is applied.
        """


        if normalize is 'auto':
            normalize = None
        range = (0,len(colorTable)-1)
        super(ColortableLayer, self).__init__([datasource], range = range, normalize=normalize, direct=direct)
        self.data = datasource
        self._colorTable = colorTable
        
        self.colortableIsRandom = False
        self.zeroIsTransparent  = False
        
class ClickableColortableLayer(ClickableLayer):
    colorTableChanged = pyqtSignal()
    
    def __init__( self, editor, clickFunctor, datasource , colorTable, direct=False, right=True ):
        assert isinstance(datasource, SourceABC)
        super(ClickableColortableLayer, self).__init__(datasource, editor, clickFunctor, direct=direct, right=right)
        self._colorTable = colorTable
        self.data = datasource
        
        self.colortableIsRandom = False
        self.zeroIsTransparent  = False

    @property
    def colorTable( self ):
        return self._colorTable

    @colorTable.setter
    def colorTable( self, colorTable ):
        self._colorTable = colorTable
        self.colorTableChanged.emit()

    def randomizeColors(self):
        self.colorTable = generateRandomColors(len(self._colorTable), "hsv", {"v": 1.0}, True)

#*******************************************************************************
# R G B A L a y e r                                                            *
#*******************************************************************************

class RGBALayer( NormalizableLayer ):
    channelIdx = {'red': 0, 'green': 1, 'blue': 2, 'alpha': 3}
    channelName = {0: 'red', 1: 'green', 2: 'blue', 3: 'alpha'}
    
    @property
    def color_missing_value( self ):
        return self._color_missing_value

    @property
    def alpha_missing_value( self ):
        return self._alpha_missing_value

    def __init__( self, red = None, green = None, blue = None, alpha = None, \
                  color_missing_value = 0, alpha_missing_value = 255,
                  range = (None,)*4,
                  normalizeR=None, normalizeG=None, normalizeB=None, normalizeA=None):
        assert red is None or isinstance(red, SourceABC)
        assert green is None or isinstance(green, SourceABC)
        assert blue is None or isinstance(blue, SourceABC)
        assert alpha is None or isinstance(alpha, SourceABC)
        super(RGBALayer, self).__init__([red,green,blue,alpha])
        self._color_missing_value = color_missing_value
        self._alpha_missing_value = alpha_missing_value

    @classmethod
    def createFromMultichannel(cls, data):
        # disect data
        l = RGBALayer()
        return l

##
## GraphicsItem layers
##
class DummyGraphicsItemLayer( Layer ):
    def __init__(self, datasource):
        super( DummyGraphicsItemLayer, self ).__init__( [datasource] )

class DummyRasterItemLayer( Layer ):
    def __init__(self, datasource):
        super( DummyRasterItemLayer, self ).__init__( [datasource] )

class SegmentationEdgesLayer( Layer ):
    """
    A layer that displays segmentation edge boundaries using vector graphics.
    (See imagesources.SegmentationEdgesItem.)
    """

    DEFAULT_PEN = QPen()
    DEFAULT_PEN.setCosmetic(True)
    DEFAULT_PEN.setCapStyle(Qt.RoundCap)
    DEFAULT_PEN.setColor(Qt.white)
    DEFAULT_PEN.setWidth(3)

    @property
    def pen_table(self):
        """
        Items in the colortable can be added/replaced/deleted, but the
        colortable object itself cannot be overwritten with a different dict object.
        The SegmentationEdgesItem(s) associated witht this layer will react
        immediately to any changes you make to this colortable dict.
        """
        return self._pen_table

    def __init__(self, datasource, default_pen=DEFAULT_PEN):
        """
        datasource: A single-channel label image.
        default_pen: The initial pen style for each edge.
        """
        # 1-pixel offset in the right/down directions
        halo_start_delta = (0,0,0,0,0)
        halo_stop_delta = (0,1,1,1,0)
        
        adjusted_datasource = HaloAdjustedDataSource(datasource, halo_start_delta, halo_stop_delta)
        super( SegmentationEdgesLayer, self ).__init__( [adjusted_datasource] )

        # Changes to this colortable will be detected automatically in the QGraphicsItem
        self._pen_table = SignalingDefaultDict(parent=self, default_factory=lambda:default_pen )

    def handle_edge_clicked(self, id_pair):
        """
        Handles clicks from our associated SegmentationEdgesItem(s).
        (See connection made in SegmentationEdgesItemRequest.) 
        
        id_pair: The edge that was clicked.
        """
        # For now, simple debug functionality: change to a random color.
        # Please verify in the viewer that edges spanning multiple tiles changed color
        # together, even though only one of the tiles was clicked.
        random_color = QColor( *list( numpy.random.randint(0,255,(3,)) ) )
        pen = QPen(self.pen_table[id_pair])
        pen.setColor(random_color)
        self.pen_table[id_pair] = pen

class LabelableSegmentationEdgesLayer( SegmentationEdgesLayer ):
    """
    Shows a set of user-labeled edges.
    """
    
    labelChanged = pyqtSignal( tuple, int ) # id_pair, label_class
    
    def __init__(self, datasource, label_class_pens, initial_labels={}):
        # Class 0 (no label) is the default pen
        super(LabelableSegmentationEdgesLayer, self).__init__( datasource, default_pen=label_class_pens[0] )
        self._label_class_pens = label_class_pens
        self._edge_labels = defaultdict(lambda: 0, initial_labels)
    
    def handle_edge_clicked(self, id_pair):
        """
        Overridden from SegmentationEdgesLayer
        """
        num_classes = len(self._label_class_pens)
        old_class = self._edge_labels[id_pair]
        new_class = (old_label+1) % num_classes

        # Update the display
        self.pen_table[id_pair] = self._label_class_pens[new_class]

        # For now, edge_labels dictionary will still contain 0-labeled edges.
        # We could delete them, but why bother?
        self._edge_labels[id_pair] = new_class
        self.labelChanged.emit(id_pair, new_class)

#     def update_edge_labels(self, new_edge_labels):
        
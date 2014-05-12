# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

#Python
import copy
from functools import partial

#SciPy
import numpy

#PyQt
from PyQt4.QtCore import pyqtSignal, QObject
from PyQt4.QtGui import QApplication, QWidget

#volumina
import volumina.pixelpipeline.imagepump
from eventswitch import EventSwitch
from imageScene2D import ImageScene2D
from imageView2D import ImageView2D
from positionModel import PositionModel
from croppingMarkers import CropExtentsModel
from navigationControler import NavigationControler, NavigationInterpreter
from brushingcontroler import BrushingInterpreter, BrushingControler, \
                              CrosshairControler
from thresholdingcontroler import ThresholdingInterpreter
from brushingmodel import BrushingModel
from slicingtools import SliceProjection

import logging
logger = logging.getLogger(__name__)

useVTK = True
try:
    from view3d.view3d import OverviewScene
except:
    logger.error( "Warning: could not import optional dependency VTK" )
    useVTK = False

#*******************************************************************************
# V o l u m e E d i t o r                                                      *
#*******************************************************************************

class VolumeEditor( QObject ):
    newImageView2DFocus = pyqtSignal()
    shapeChanged = pyqtSignal()

    @property
    def showDebugPatches(self):
        return self._showDebugPatches
    @showDebugPatches.setter
    def showDebugPatches(self, show):
        for s in self.imageScenes:
            s.showTileOutlines = show
        self._showDebugPatches = show

    @property
    def showTileProgress(self):
        return self._showTileProgress
    @showDebugPatches.setter
    def showTileProgress(self, show):
        for s in self.imageScenes:
            s.showTileProgress = show
        self._showTileProgress = show

    @property
    def cacheSize(self):
        return self._cacheSize
    @cacheSize.setter
    def cacheSize(self, cache_size):
        self._cacheSize = cache_size
        for s in self.imageScenes:
            s.setCacheSize(cache_size)

    @property
    def navigationInterpreterType(self):
        return type(self.navInterpret)
    @navigationInterpreterType.setter
    def navigationInterpreterType(self,navInt):
        self.navInterpret = navInt(self.navCtrl)
        self.eventSwitch.interpreter = self.navInterpret

    def setNavigationInterpreter(self, navInterpret):
        self.navInterpret = navInterpret
        self.eventSwitch.interpreter = self.navInterpret

    @property
    def syncAlongAxes( self ):
        '''Axes orthogonal to slices, whose values are synced between layers.

        Returns: a tuple of up to three values, encoding:
                 0 - time
                 1 - space
                 2 - channel

                 for example the meaning of (0,1) is: time and orthogonal space axes
                 are synced for all layers, channel is not. (For the x-y slice, the space
                 axis would be z and so on.)
 
        '''
        return tuple(self._sync_along)

    @property
    def dataShape(self):
        return self.posModel.shape5D
    @dataShape.setter
    def dataShape(self, s):
        self.posModel.shape5D = s
        for i, v in enumerate(self.imageViews):
            v.sliceShape = self.posModel.sliceShape(axis=i)
        self.view3d.dataShape = s[1:4]
      
        self.cropModel.set_volume_shape_3d(s[1:4])
      
        #for 2D images, disable the slice intersection marker
        x = numpy.sum(numpy.asarray(s[1:4]) == 1) 
        self.navCtrl.indicateSliceIntersection = (x != 1)
        
        self.shapeChanged.emit()
        
    def lastImageViewFocus(self, axis):
        self._lastImageViewFocus = axis
        self.newImageView2DFocus.emit()

    def __init__( self, layerStackModel, parent, labelsink=None, crosshair=True, syncAlongAxes=(0,1)):
        super(VolumeEditor, self).__init__(parent=parent)
        self._sync_along = tuple(syncAlongAxes)

        ##
        ## properties
        ##
        self._showDebugPatches   = False
        self._showTileProgress   = True

        ##
        ## base components
        ##
        self.layerStack = layerStackModel
        self.posModel = PositionModel()
        self.brushingModel = BrushingModel()
        self.cropModel = CropExtentsModel( self )

        self.imageScenes = [ImageScene2D(self.posModel, (0,1,4), swapped_default=True),
                            ImageScene2D(self.posModel, (0,2,4)),
                            ImageScene2D(self.posModel, (0,3,4))]
        self.imageViews = [ImageView2D(parent, self.cropModel, self.imageScenes[i]) for i in [0,1,2]]
        self.imageViews[0].focusChanged.connect(lambda arg=0 : self.lastImageViewFocus(arg))
        self.imageViews[1].focusChanged.connect(lambda arg=1 : self.lastImageViewFocus(arg))
        self.imageViews[2].focusChanged.connect(lambda arg=2 : self.lastImageViewFocus(arg))
        self._lastImageViewFocus = 0

        if not crosshair:
            for view in self.imageViews:
                view._crossHairCursor.enabled = False

        self.imagepumps = self._initImagePumps()

        self.view3d = self._initView3d() if useVTK else QWidget()

        names = ['x', 'y', 'z']
        for scene, name, pump in zip(self.imageScenes, names, self.imagepumps):
            scene.setObjectName(name)
            scene.stackedImageSources = pump.stackedImageSources

        self.cacheSize = 50

        ##
        ## interaction
        ##
        # event switch
        self.eventSwitch = EventSwitch(self.imageViews)

        # navigation control
        v3d = self.view3d if useVTK else None
        self.navCtrl      = NavigationControler(self.imageViews, self.imagepumps, self.posModel, view3d=v3d)
        self.navInterpret = NavigationInterpreter(self.navCtrl)

        # brushing control
        if crosshair:
            self.crosshairControler = CrosshairControler(self.brushingModel, self.imageViews)
        self.brushingControler = BrushingControler(self.brushingModel, self.posModel, labelsink)
        self.brushingInterpreter = BrushingInterpreter(self.navCtrl, self.brushingControler)

        for v in self.imageViews:
            self.brushingControler._brushingModel.brushSizeChanged.connect(v._sliceIntersectionMarker._set_diameter)

        # thresholding control
        self.thresInterpreter = ThresholdingInterpreter(self.navCtrl, 
                                                        self.layerStack,
                                                        self.posModel)
        # initial interaction mode
        self.eventSwitch.interpreter = self.navInterpret

        # By default, don't show cropping controls
        self.showCropLines(False)

        ##
        ## connect
        ##
        self.posModel.timeChanged.connect(self.navCtrl.changeTime)
        self.posModel.slicingPositionChanged.connect(self.navCtrl.moveSlicingPosition)
        if crosshair:
            self.posModel.cursorPositionChanged.connect(self.navCtrl.moveCrosshair)
        self.posModel.slicingPositionSettled.connect(self.navCtrl.settleSlicingPosition)

        self.layerStack.layerAdded.connect( self._onLayerAdded )

    def _reset(self):
        for s in self.imageScenes:
            s.reset()

    def scheduleSlicesRedraw(self):
        for s in self.imageScenes:
            s._invalidateRect()

    def setInteractionMode( self, name):
        modes = {'navigation': self.navInterpret, 
                 'brushing': self.brushingInterpreter,
                 'thresholding' : self.thresInterpreter}
        self.eventSwitch.interpreter = modes[name]

    def showCropLines(self, visible):
        for view in self.imageViews:
            view.showCropLines(visible)

    def cleanUp(self):
        QApplication.processEvents()
        for scene in self._imageViews:
            scene.close()
            scene.deleteLater()
        self._imageViews = []
        QApplication.processEvents()

    def closeEvent(self, event):
        event.accept()

    def setLabelSink(self, labelsink):
        self.brushingControler.setDataSink(labelsink)

    ##
    ## private
    ##
    def _initImagePumps( self ):
        alongTXC = SliceProjection( abscissa = 2, ordinate = 3, along = [0,1,4] )
        alongTYC = SliceProjection( abscissa = 1, ordinate = 3, along = [0,2,4] )
        alongTZC = SliceProjection( abscissa = 1, ordinate = 2, along = [0,3,4] )

        imagepumps = []
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump( self.layerStack, alongTXC, self._sync_along ))
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump( self.layerStack, alongTYC, self._sync_along ))
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump( self.layerStack, alongTZC, self._sync_along ))
        return imagepumps

    def _initView3d( self ):
        view3d = OverviewScene()
        def onSliceDragged(num, pos):
            newPos = copy.deepcopy(self.posModel.slicingPos)
            newPos[pos] = num
            self.posModel.slicingPos = newPos
        view3d.changedSlice.connect(onSliceDragged)
        return view3d

    def _onLayerAdded( self, layer, row ):
        self.navCtrl.layerChangeChannel( layer)
        layer.channelChanged.connect( partial(self.navCtrl.layerChangeChannel, layer=layer) )

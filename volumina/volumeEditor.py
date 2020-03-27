from __future__ import absolute_import

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
# 		   http://ilastik.org/license/
###############################################################################
# Python
import copy
from functools import partial

# SciPy
import numpy

# PyQt
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QApplication, QWidget

# volumina
import volumina.pixelpipeline.imagepump
from .eventswitch import EventSwitch
from .imageScene2D import ImageScene2D
from .imageView2D import ImageView2D
from .positionModel import PositionModel
from .croppingMarkers import CropExtentsModel
from .navigationController import NavigationController, NavigationInterpreter
from .brushingcontroller import BrushingInterpreter, BrushingController, CrosshairController
from .thresholdingcontroller import ThresholdingInterpreter
from .brushingmodel import BrushingModel
from .slicingtools import SliceProjection

import logging

logger = logging.getLogger(__name__)


# *******************************************************************************
# V o l u m e E d i t o r                                                      *
# *******************************************************************************


class VolumeEditor(QObject):
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
    def navigationInterpreterType(self, navInt):
        self.navInterpret = navInt(self.navCtrl)
        self.eventSwitch.interpreter = self.navInterpret

    def setNavigationInterpreter(self, navInterpret):
        self.navInterpret = navInterpret
        self.eventSwitch.interpreter = self.navInterpret

    @property
    def syncAlongAxes(self):
        """Axes orthogonal to slices, whose values are synced between layers.

        Returns: a tuple of up to three values, encoding:
                 0 - time
                 1 - space
                 2 - channel

                 for example the meaning of (0,1) is: time and orthogonal space axes
                 are synced for all layers, channel is not. (For the x-y slice, the space
                 axis would be z and so on.)

        """
        return tuple(self._sync_along)

    @property
    def dataShape(self):
        return self.posModel.shape5D

    @dataShape.setter
    def dataShape(self, s):
        self.cropModel.set_volume_shape_3d_cropped([0, 0, 0], s[1:4])
        self.cropModel.set_time_shape_cropped(0, s[0])

        self.posModel.shape5D = s
        # for 2D images, disable the slice intersection marker
        is_2D = (numpy.asarray(s[1:4]) == 1).any()
        if is_2D:
            self.navCtrl.indicateSliceIntersection = False
        else:
            for i in range(3):
                self.parent.volumeEditorWidget.quadview.ensureMinimized(i)

        self.shapeChanged.emit()

        for i, v in enumerate(self.imageViews):
            v.sliceShape = self.posModel.sliceShape(axis=i)
        self.view3d.set_shape(s[1:4])

    def lastImageViewFocus(self, axis):
        self._lastImageViewFocus = axis
        self.newImageView2DFocus.emit()

    def __init__(
        self, layerStackModel, parent, labelsink=None, crosshair=True, is_3d_widget_visible=False, syncAlongAxes=(0, 1)
    ):
        super(VolumeEditor, self).__init__(parent=parent)
        self._sync_along = tuple(syncAlongAxes)

        ##
        ## properties
        ##
        self._showDebugPatches = False
        self._showTileProgress = True

        ##
        ## base components
        ##
        self.layerStack = layerStackModel
        self.posModel = PositionModel(self)
        self.brushingModel = BrushingModel()
        self.cropModel = CropExtentsModel(self)

        self.imageScenes = [
            ImageScene2D(self.posModel, (0, 1, 4), swapped_default=True),
            ImageScene2D(self.posModel, (0, 2, 4)),
            ImageScene2D(self.posModel, (0, 3, 4)),
        ]
        self.imageViews = [ImageView2D(parent, self.cropModel, self.imageScenes[i]) for i in [0, 1, 2]]
        self.imageViews[0].focusChanged.connect(lambda arg=0: self.lastImageViewFocus(arg))
        self.imageViews[1].focusChanged.connect(lambda arg=1: self.lastImageViewFocus(arg))
        self.imageViews[2].focusChanged.connect(lambda arg=2: self.lastImageViewFocus(arg))
        self._lastImageViewFocus = 0

        if not crosshair:
            for view in self.imageViews:
                view._crossHairCursor.enabled = False

        self.imagepumps = self._initImagePumps()

        self.view3d = self._initView3d(is_3d_widget_visible)

        names = ["x", "y", "z"]
        for scene, name, pump in zip(self.imageScenes, names, self.imagepumps):
            scene.setObjectName(name)
            scene.stackedImageSources = pump.stackedImageSources

        self.cacheSize = 50

        ##
        ## interaction
        ##

        # navigation control
        self.navCtrl = NavigationController(self.imageViews, self.imagepumps, self.posModel, view3d=self.view3d)
        self.navInterpret = NavigationInterpreter(self.navCtrl)

        # event switch
        self.eventSwitch = EventSwitch(self.imageViews, self.navInterpret)

        # brushing control
        if crosshair:
            self.crosshairController = CrosshairController(self.brushingModel, self.imageViews)
        self.brushingController = BrushingController(self.brushingModel, self.posModel, labelsink)
        self.brushingInterpreter = BrushingInterpreter(self.navCtrl, self.brushingController)

        for v in self.imageViews:
            self.brushingController._brushingModel.brushSizeChanged.connect(v._sliceIntersectionMarker._set_diameter)

        # thresholding control
        self.thresInterpreter = ThresholdingInterpreter(self.navCtrl, self.layerStack, self.posModel)

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

        self.layerStack.layerAdded.connect(self._onLayerAdded)
        self.parent = parent

    def _reset(self):
        for s in self.imageScenes:
            s.reset()

    def scheduleSlicesRedraw(self):
        for s in self.imageScenes:
            s._invalidateRect()

    def setInteractionMode(self, name):
        modes = {
            "navigation": self.navInterpret,
            "brushing": self.brushingInterpreter,
            "thresholding": self.thresInterpreter,
        }
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
        self.brushingController.setDataSink(labelsink)

    ##
    ## private
    ##
    def _initImagePumps(self):
        alongTXC = SliceProjection(abscissa=2, ordinate=3, along=[0, 1, 4])
        alongTYC = SliceProjection(abscissa=1, ordinate=3, along=[0, 2, 4])
        alongTZC = SliceProjection(abscissa=1, ordinate=2, along=[0, 3, 4])

        imagepumps = []
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump(self.layerStack, alongTXC, self._sync_along))
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump(self.layerStack, alongTYC, self._sync_along))
        imagepumps.append(volumina.pixelpipeline.imagepump.ImagePump(self.layerStack, alongTZC, self._sync_along))

        return imagepumps

    def _initView3d(self, is_3d_widget_visible):
        from .view3d.overview3d import Overview3D

        view3d = Overview3D(is_3d_widget_visible=is_3d_widget_visible)

        def onSliceDragged():
            self.posModel.slicingPos = view3d.get_slice()

        view3d.slice_changed.connect(onSliceDragged)
        return view3d

    def _onLayerAdded(self, layer, row):
        self.navCtrl.layerChangeChannel(layer)
        layer.channelChanged.connect(partial(self.navCtrl.layerChangeChannel, layer=layer))

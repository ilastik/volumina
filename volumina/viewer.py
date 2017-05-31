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
"""High-level API.

"""
from __future__ import print_function
from builtins import range
from volumina.pixelpipeline.datasources import *
from volumina.pixelpipeline.datasourcefactories import *
from volumina.layer import *
from volumina.layerstack import LayerStackModel
from volumina.navigationController import NavigationInterpreter
from volumina.colortables import default16

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMainWindow, QApplication, QAction, qApp
from PyQt5.uic import loadUi

import os
import random

#******************************************************************************
# C l i c k a b l e S e g m e n t a t i o n L a y e r                         * 
#******************************************************************************

class ClickableSegmentationLayer(QObject):

    #whether label (int) is shown (true) or hidden (false)
    clickedValue = pyqtSignal(int, bool, QColor)

    def __init__(self, seg, viewer, name=None, direct=None, parent=None, colortable=None, reuseColors=True):
        """ seg:         segmentation image/volume (5D) 
            reuseColors: if True, colors are assigned based on the number of currently visible objects,
                         if False, a segment with 'label' is assigned colortable[label] as color
        """
        super(ClickableSegmentationLayer, self).__init__(parent)

        assert seg.ndim == 5

        #public attributes 
        self.layer            = None #volumina layer object
        self.relabelingSource = None #RelabelingArraySource
        self._reuseColors     = reuseColors

        self._M = seg.max()
        self._clickedObjects = dict() #maps from object to the label that is used for it
        self._usedLabels = set()
        self._seg = seg

        relabeling = numpy.zeros(self._M+1, dtype=self._seg.dtype)

        #add layer
        if colortable is None:
            colortable = volumina.layer.generateRandomColors(1000, "hsv", {"v": 1.0}, zeroIsTransparent=True)
            colortable[1:17] = default16
        
        layer, source = viewer.addRelabelingColorTableLayer(seg, clickFunctor=self.onClick, name=name,
            relabeling=relabeling, colortable=colortable, direct=direct)
        layer.zeroIsTransparent = True
        layer.colortableIsRandom = True
        self.layer = layer
        self.relabelingSource = source

    def setMaxLabel(self, l):
        self._M = l
        self.relabelingSource.setRelabeling(numpy.zeros(self._M+1, dtype=self._seg.dtype))

    def deselectAll(self):
        self._clickedObjects = dict()
        self._usedLabels = set()
        self.relabelingSource.clearRelabeling() 
        
    def labelColor(self, label):
        """ return the current color for object 'label' """
        color = self.layer.colorTable[label]
        color = QColor.fromRgba(color)
        return color
    
    def labelShown(self, label):
        return label in self._clickedObjects

    def toggleLabel(self, label):
        color = QColor()
        shown = True
        if label in self._clickedObjects:
            self.layer._datasources[0].setRelabelingEntry(label, 0)
            self._usedLabels.remove( self._clickedObjects[label] )
            del self._clickedObjects[label]
            shown = False
        else:
            self._labels = sorted(list(self._usedLabels))
            
            if self._reuseColors:
                #find first free entry
                if self._labels:
                    for l in range(1, self._labels[-1]+2):
                        if l not in self._labels:
                            break
                    assert l not in self._usedLabels
                else:
                    l = 1
            else:
                l = label
                
            color = self.labelColor(l)

            self._usedLabels.add(l) 
            self._clickedObjects[label] = l
            self.layer._datasources[0].setRelabelingEntry(label, l)
        self.clickedValue.emit(label, shown, color)

    def onClick(self, layer, pos5D, pos):
        obj = layer.data.originalData[pos5D]
        self.toggleLabel(obj)

#******************************************************************************
# V i e w e r                                                                 *
#******************************************************************************

class Viewer(QMainWindow):
    """High-level API to view multi-dimensional arrays.

    Properties:
        title -- window title

    """
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        uiDirectory = os.path.split(volumina.__file__)[0]
        if uiDirectory == '':
            uiDirectory = '.'
        loadUi(uiDirectory + '/viewer.ui', self)

        self._dataShape = None
        self._viewerInitialized = False
        self.editor = None
        self.viewingWidget = None
        self.actionQuit.triggered.connect(qApp.quit)
        
        #when connecting in renderScreenshot to a partial(...) function,
        #we need to remember the created function to be able to disconnect
        #to it later
        self._renderScreenshotDisconnect = None

        self.initLayerstackModel()

        self.actionCurrentView = QAction(QIcon(), "Only for selected view", self.menuView)
        f = self.actionCurrentView.font()
        f.setBold(True)
        self.actionCurrentView.setFont(f)

        # Lazy import here to prevent this module from ignoring volumine.NO3D flag.
        from volumina.volumeEditor import VolumeEditor
        self.editor = VolumeEditor(self.layerstack, parent=self)

        #make sure the layer stack widget, which is the right widget
        #managed by the splitter self.splitter shows up correctly
        #TODO: find a proper way of doing this within the designer
        def adjustSplitter():
            s = self.splitter.sizes()
            s = [int(0.66*s[0]), s[0]-int(0.66*s[0])]
            self.splitter.setSizes(s)
        QTimer.singleShot(0, adjustSplitter)
        
    @property
    def title(self):
        return self.windowTitle()
    
    @title.setter
    def title(self, t):
        self.setWindowTitle(t)
        
    def initLayerstackModel(self):
        self.layerstack = LayerStackModel()
        self.layerWidget.init(self.layerstack)
        model = self.layerstack
        self.UpButton.clicked.connect(model.moveSelectedUp)
        model.canMoveSelectedUp.connect(self.UpButton.setEnabled)
        self.DownButton.clicked.connect(model.moveSelectedDown)
        model.canMoveSelectedDown.connect(self.DownButton.setEnabled)
        self.DeleteButton.clicked.connect(model.deleteSelected)
        model.canDeleteSelected.connect(self.DeleteButton.setEnabled)
    
    @property
    def dataShape(self):
        return self._dataShape
    @dataShape.setter
    def dataShape(self, s):
        if s is None:
            return
        assert len(s) == 5
        
        self._dataShape = s
        self.editor.dataShape = s
        if not self._viewerInitialized:
            self._viewerInitialized = True
            self.viewer.init(self.editor)
            #make sure the data shape is correctly set
            #(some signal/slot connections may be set up in the above init)
            self.editor.dataShape = s

            #FIXME: this code is broken
            #if its 2D, maximize the corresponding window
            #if len([i for i in list(self.dataShape)[1:4] if i == 1]) == 1:
            #    viewAxis = [i for i in range(1,4) if self.dataShape[i] == 1][0] - 1
            #    self.viewer.quadview.switchMinMax(viewAxis)    
        
    def addGrayscaleLayer(self, a, name=None, direct=False):
        source,self.dataShape = createDataSource(a,True)
        layer = GrayscaleLayer(source, direct=direct)
        layer.numberOfChannels = self.dataShape[-1]
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
        
    def addAlphaModulatedLayer(self, a, name=None, **kwargs):
        source,self.dataShape = createDataSource(a,True)
        layer = AlphaModulatedLayer(source, **kwargs)
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
    
    def addRGBALayer(self, a, name=None):
        assert a.shape[2] >= 3
        sources = [None, None, None,None]
        for i in range(3):
            sources[i], self.dataShape = createDataSource(a[...,i], True)
        if(a.shape[-1] >= 4):
            sources[3], self.dataShape = createDataSource(a[...,3], True) 
        layer = RGBALayer(sources[0],sources[1],sources[2], sources[3])
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer

    def addRandomColorsLayer(self, a, name=None, direct=False):
        layer = self.addColorTableLayer(a, name, colortable=None, direct=direct)
        layer.colortableIsRandom = True
        layer.zeroIsTransparent = True
        return layer
    
    def addColorTableLayer(self, a, name=None, colortable=None, direct=False, clickFunctor=None):
        if colortable is None:
            colortable = self._randomColors(16384)
        source,self.dataShape = createDataSource(a,True)
        if clickFunctor is None:
            layer = ColortableLayer(source, colortable, direct=direct)
        else:
            layer = ClickableColortableLayer(self.editor, clickFunctor, source, colortable, direct=direct)
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
    
    def addRelabelingColorTableLayer(self, a, name=None, relabeling=None, colortable=None, direct=False, clickFunctor=None, right=True):
        if colortable is None:
            colortable = self._randomColors()
        source = RelabelingArraySource(a)
        if relabeling is None:
            source.setRelabeling(numpy.zeros(numpy.max(a)+1, dtype=a.dtype))
        else:
            source.setRelabeling(relabeling)
        if colortable is None:
            colortable = [QColor(0,0,0,0).rgba(), QColor(255,0,0).rgba()]
        if clickFunctor is None:
            layer = ColortableLayer(source, colortable, direct=direct)
        else:
            layer = ClickableColortableLayer(self.editor, clickFunctor, source, colortable, direct=direct, right=right)
        if name:
            layer.name = name 
        self.layerstack.append(layer)
        return (layer, source)
    
    def addClickableSegmentationLayer(self, a, name=None, direct=False, colortable=None, reuseColors=True):
        return ClickableSegmentationLayer(a, self, name=name, direct=direct, colortable=colortable, reuseColors=reuseColors) 

    def addSegmentationEdgesLayer(self, a, name=None, **kwargs):
        source = createDataSource(a, False)
        layer = SegmentationEdgesLayer(source, **kwargs)
        layer.numberOfChannels = 1
        layer.name = name
        self.layerstack.append(layer)
        return layer
        
    def _randomColors(self, M=256):
        """Generates a pleasing color table with M entries."""

        colors = []
        for i in range(M):
            if i == 0:
                colors.append(QColor(0, 0, 0, 0).rgba())
            else:
                h, s, v = random.random(), random.random(), 1.0
                color = numpy.asarray(colorsys.hsv_to_rgb(h, s, v)) * 255
                qColor = QColor(*color)
                colors.append(qColor.rgba())
        #for the first 16 objects, use some colors that are easily distinguishable
        colors[1:17] = default16 
        return colors

if __name__ == "__main__":
    import sys
    
    app = QApplication(sys.argv)
    viewer = Viewer()
    viewer.show()


#     array1 = (numpy.random.random((1,1000,1000,10,1))) * 255
#     viewer.addGrayscaleLayer(array1)
# 
#     from volumina.layer import DummyGraphicsItemLayer
#     source = createDataSource(array1,False)
#     layer = DummyGraphicsItemLayer(source)
#     layer.name = "DUMMY GRAPHICS"
#     viewer.layerstack.append(layer)

    test = '2d'
    if test == '2d':
        from volumina.utility import SegmentationEdgesItem
        labels_img = numpy.load('/Users/bergs/workspace/ilastik-meta/ilastik/seg-slice-256.npy')
        viewer.addRandomColorsLayer(labels_img, 'labels')
        #g_item = SegmentationEdgesItem(labels_img)
        #viewer.editor.imageScenes[2].addItem(g_item)
         
        source = createDataSource(labels_img, False)
        layer = SegmentationEdgesLayer(source)
        layer.numberOfChannels = 1
        layer.name = "Edges"
        viewer.layerstack.append(layer)

    if test == '3d':
        os.chdir('/magnetic/data/flyem/chris-two-stage-ilps/volumes/subvol')    
        
        import h5py
        print("Loading grayscale...")
        grayscale_file = h5py.File('grayscale-512.h5', 'r')
        grayscale_dset = grayscale_file['grayscale']
        grayscale_zyx = grayscale_dset[...,0]
        
        print("Loading membranes...")
        membranes_file = h5py.File('final-membranes-512.h5', 'r')
        membranes_dset = membranes_file['membranes']
        membranes_zyx = membranes_dset[...,0]
        
        print("Loading watershed...")
        watershed_file = h5py.File('watershed-512.h5', 'r')
        watershed_dset = watershed_file['watershed']
        watershed_zyx = watershed_dset[:]
    
        print("Loading segmentation...")
        segmentation_file = h5py.File('segmentation-512.h5', 'r')
        segmentation_dset = segmentation_file['segmentation']
        segmentation_zyx = segmentation_dset[:]
    
        print("Adding raster layers...")
        viewer.addGrayscaleLayer(grayscale_zyx.transpose(), 'grayscale')
        viewer.addAlphaModulatedLayer(membranes_zyx.transpose(), 'membranes', tintColor=QColor(255,0,0))
        viewer.addRandomColorsLayer(watershed_zyx.transpose(), 'watershed')
        viewer.addRandomColorsLayer(segmentation_zyx.transpose(), 'segmentation')
    
        print("Adding vector layers...")
        watershed_pen = QPen(SegmentationEdgesLayer.DEFAULT_PEN)
        watershed_pen.setColor(Qt.yellow)
        viewer.addSegmentationEdgesLayer(watershed_zyx.transpose(), 'watershed edges', default_pen=watershed_pen)
    
        segmentation_pen = QPen(SegmentationEdgesLayer.DEFAULT_PEN)
        segmentation_pen.setColor(Qt.blue)
        viewer.addSegmentationEdgesLayer(segmentation_zyx.transpose(), 'segmentation edges', default_pen=segmentation_pen)
    
    
    #from PyQt5.QtWidgets import QGraphicsView
    #viewer.editor.imageViews[2].setOptimizationFlag(QGraphicsView.DontAdjustForAntialiasing, True)

#     try:
#         import vigra
#     except:
#         pass
#     else:
#         array1 = vigra.taggedView(array1, 'txyzc')
#     viewer.addGrayscaleLayer(array1)
# 
#     array2 = (numpy.random.random((100,100,100,3))) * 255
#     viewer.addRGBALayer(array2)
# 
#     try:
#         import h5py
#     except:
#         pass
#     else:
#         f = h5py.File('/tmp/blabla.h5', 'w')
#         f['data'] = (numpy.random.random((1,100,100,100,4))) * 255
#         viewer.addGrayscaleLayer(f['data'], name='from_hdf5')    
#     
#     white_array = (numpy.ones((100,100,100,1))) * 255
#     viewer.addGrayscaleLayer(white_array, "white")
#     
#     array3 = (numpy.random.random((100,100,100,3))) * 255
#     red_layer = viewer.addAlphaModulatedLayer(array3[...,0], "array3-red", tintColor=QColor(255,0,0))
#     green_layer = viewer.addAlphaModulatedLayer(array3[...,1], "array3-green", tintColor=QColor(0,255,0))
#     blue_layer = viewer.addAlphaModulatedLayer(array3[...,2], "array3-blue", tintColor=QColor(0,0,255))
# 
#     red_layer.opacity = 1.0
#     green_layer.opacity = 0.66
#     blue_layer.opacity = 0.33
    
    viewer.raise_()
    
#     class MyInterpreter(NavigationInterpreter):
#         
#         def __init__(self, navigationcontroller):
#             NavigationInterpreter.__init__(self,navigationcontroller)
#     
#         def onMouseMove_default( self, imageview, event ):
#             if imageview._ticker.isActive():
#                 #the view is still scrolling
#                 #do nothing until it comes to a complete stop
#                 return
#     
#             imageview.mousePos = mousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
#             imageview.oldX, imageview.oldY = imageview.x, imageview.y
#             x = imageview.x = mousePos.y()
#             y = imageview.y = mousePos.x()
#             self._navCtrl.positionCursor( x, y, self._navCtrl._views.index(imageview))
#     
#     #like this
#     myInt = MyInterpreter
#     viewer.editor.navigationInterpreterType = myInt
#     
#     #or like this
#     tmpInt = viewer.editor.navigationInterpreterType
#     tmpInt.onMouseMove_default = myInt.onMouseMove_default
#     viewer.editor.navigationInterpreterType = tmpInt
    
    app.exec_()

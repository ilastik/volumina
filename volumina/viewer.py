"""High-level API.

"""
from pixelpipeline.imagepump import ImagePump
from volumina.pixelpipeline.datasources import *
from volumina.pixelpipeline.datasourcefactories import *
from volumina.layer import *
from volumina.layerstack import LayerStackModel
from volumina.volumeEditor import VolumeEditor
from volumina.volumeEditorWidget import VolumeEditorWidget
from volumina.widgets.layerwidget import LayerWidget
from volumina.navigationControler import NavigationInterpreter

from PyQt4.QtCore import QRectF, QTimer
from PyQt4.QtGui import QMainWindow, QApplication, QIcon, QAction, qApp, \
    QImage, QPainter, QMessageBox
from PyQt4.uic import loadUi
import volumina.icons_rc

import os
import sys
import numpy
import colorsys
import random

_has_lazyflow = True
try:
    from volumina.adaptors import Op5ifyer
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False
from volumina.adaptors import Array5d

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

        self.editor = VolumeEditor(self.layerstack)

        #make sure the layer stack widget, which is the right widget
        #managed by the splitter self.splitter shows up correctly
        #TODO: find a proper way of doing this within the designer
        def adjustSplitter():
            s = self.splitter.sizes()
            s = [int(0.66*s[0]), s[0]-int(0.66*s[0])]
            self.splitter.setSizes(s)
        QTimer.singleShot(0, adjustSplitter)
        
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
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
        
    def addAlphaModulatedLayer(self, a, name=None):
        source,self.dataShape = createDataSource(a,True)
        layer = AlphaModulatedLayer(source)
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
    
    def addRGBALayer(self, a, name=None):
        assert a.shape[2] >= 3
        sources = [None, None, None,None]
        for i in range(3):
            sources[i], self.dataShape = createDataSource(a[...,i], True)
        if(a.shape[2] >= 4):
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
            colortable = self._randomColors()
        source,self.dataShape = createDataSource(a,True)
        if clickFunctor is None:
            layer = ColortableLayer(source, colortable, direct=direct)
        else:
            layer = ClickableColortableLayer(self.editor, clickFunctor, source, colortable, direct=direct)
        if name:
            layer.name = name
        self.layerstack.append(layer)
        return layer
    
    def addRelabelingColorTableLayer(self, a, name=None, relabeling=None, colortable=None, direct=False, clickFunctor=None):
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
            layer = ClickableColortableLayer(self.editor, clickFunctor, source, colortable, direct=direct)
        if name:
            layer.name = name 
        self.layerstack.append(layer)
        return (layer, source)
    
    def addClickableSegmentationLayer(self, a, name=None, direct=False):
        M = a.max()
        clickedObjects = dict() #maps from object to the label that is used for it
        usedLabels = set()
        def onClick(layer, pos5D, pos):
            obj = layer.data.originalData[pos5D]
            if obj in clickedObjects:
                layer._datasources[0].setRelabelingEntry(obj, 0)
                usedLabels.remove( clickedObjects[obj] )
                del clickedObjects[obj]
            else:
                labels = sorted(list(usedLabels))
                
                #find first free entry
                if labels:
                    for l in range(1, labels[-1]+2):
                        if l not in labels:
                            break
                    assert l not in usedLabels
                else:
                    l = 1
               
                usedLabels.add(l) 
                clickedObjects[obj] = l
                layer._datasources[0].setRelabelingEntry(obj, l)
        
        colortable = volumina.layer.generateRandomColors(1000, "hsv", {"v": 1.0}, zeroIsTransparent=True)
             
        layer, source = self.addRelabelingColorTableLayer(a, clickFunctor=onClick, name=None,
            relabeling=numpy.zeros(M+1, dtype=a.dtype), colortable=colortable, direct=direct)
        if name is not None:
            layer.name = name
        layer.zeroIsTransparent = True
        layer.colortableIsRandom = True
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
        return colors
        
if __name__ == "__main__":
    
    import sys
    from lazyflow.operators import OpImageReader
    from lazyflow.graph import Operator, OutputSlot, InputSlot
    from lazyflow.graph import Graph
    from vigra import VigraArray

    
    app = QApplication(sys.argv)
    viewer = Viewer()
    viewer.show()
    source1 = (numpy.random.random((100,100,1))) * 255
    viewer.addGrayscaleLayer(source1)
    
    class MyInterpreter(NavigationInterpreter):
        
        def __init__(self, navigationcontroler):
            NavigationInterpreter.__init__(self,navigationcontroler)
    
        def onMouseMove_default( self, imageview, event ):
            if imageview._ticker.isActive():
                #the view is still scrolling
                #do nothing until it comes to a complete stop
                return
    
            imageview.mousePos = mousePos = imageview.mapScene2Data(imageview.mapToScene(event.pos()))
            imageview.oldX, imageview.oldY = imageview.x, imageview.y
            x = imageview.x = mousePos.y()
            y = imageview.y = mousePos.x()
            self._navCtrl.positionCursor( x, y, self._navCtrl._views.index(imageview))
    
    #like this
    myInt = MyInterpreter
    viewer.editor.navigationInterpreterType = myInt
    
    #or like this
    tmpInt = viewer.editor.navigationInterpreterType
    tmpInt.onMouseMove_default = myInt.onMouseMove_default
    viewer.editor.navigationInterpreterType = tmpInt
    
    app.exec_()

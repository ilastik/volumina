#!/usr/bin/env python

#Python
from functools import partial
import copy

#SciPy
import numpy

#PyQt
from PyQt4.QtCore import Qt, QRectF, QEvent, QObject, QTimerEvent
from PyQt4.QtGui import QApplication, QWidget, QShortcut, QKeySequence, QHBoxLayout, \
                        QColor, QSizePolicy, QAction, QIcon, QSpinBox

#volumina
from quadsplitter import QuadView
from sliceSelectorHud import ImageView2DHud, QuadStatusBar
from pixelpipeline.datasources import ArraySource
from volumeEditor import VolumeEditor
from volumina.utility import ShortcutManager

class __TimerEventEater( QObject ):
    def eventFilter( self, obj, ev ):
        if isinstance(obj, QSpinBox) and isinstance(ev, QTimerEvent):
            return True
        return False
_timerEater = __TimerEventEater()
        
class VolumeEditorWidget(QWidget):
    def __init__( self, parent=None, editor=None ):
        super(VolumeEditorWidget, self).__init__(parent=parent)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)
        
        self.editor = None
        if editor!=None:
            self.init(editor)

        self.allZoomToFit = QAction(QIcon(":/icons/icons/view-fullscreen.png"), "Zoom to &Fit", self)
        self.allZoomToFit.triggered.connect(self._fitToScreen)

        self.allToggleHUD = QAction(QIcon(), "Show &HUDs", self)
        self.allToggleHUD.setCheckable(True)
        self.allToggleHUD.setChecked(True)
        self.allToggleHUD.toggled.connect(self._toggleHUDs)

        self.allCenter = QAction(QIcon(), "&Center views", self)
        self.allCenter.triggered.connect(self._centerAllImages)

        self.selectedCenter = QAction(QIcon(), "C&enter view", self)
        self.selectedCenter.triggered.connect(self._centerImage)

        self.selectedZoomToFit = QAction(QIcon(":/icons/icons/view-fullscreen.png"), "Zoom to Fit", self)
        self.selectedZoomToFit.triggered.connect(self._fitImage)

        self.selectedZoomToOriginal = QAction(QIcon(), "Reset Zoom", self)
        self.selectedZoomToOriginal.triggered.connect(self._restoreImageToOriginalSize)

        self.rubberBandZoom = QAction(QIcon(), "Rubberband Zoom", self)
        self.rubberBandZoom.triggered.connect(self._rubberBandZoom)

        self.toggleSelectedHUD = QAction(QIcon(), "Show HUD", self)
        self.toggleSelectedHUD.setCheckable(True)
        self.toggleSelectedHUD.setChecked(True)
        self.toggleSelectedHUD.toggled.connect(self._toggleSelectedHud)


    def _setupVolumeExtent( self ):
        '''Setup min/max values of position/coordinate control elements.

        Position/coordinate information is read from the volumeEditor's positionModel.

        '''
        maxChannel = self.editor.posModel.shape5D[-1] - 1
        self.quadview.statusBar.channelLabel.setHidden(maxChannel == 0)
        self.quadview.statusBar.channelSpinBox.setHidden(maxChannel == 0)
        self.quadview.statusBar.channelSpinBox.setRange(0,maxChannel)
        self.quadview.statusBar.channelSpinBox.setSuffix("/{}".format( maxChannel ) )

        maxTime = self.editor.posModel.shape5D[0] - 1
        self.quadview.statusBar.timeLabel.setHidden(maxTime == 0)
        self.quadview.statusBar.timeSpinBox.setHidden(maxTime == 0)
        self.quadview.statusBar.timeSpinBox.setRange(0,maxTime)
        self.quadview.statusBar.timeSpinBox.setSuffix("/{}".format( maxTime ) )
        
        for i in range(3):
            self.editor.imageViews[i].hud.setMaximum(self.editor.posModel.volumeExtent(i)-1)
    
    def init(self, volumina):
        self.editor = volumina
        
        self.hudsShown = [True]*3
        
        def onViewFocused():
            axis = self.editor._lastImageViewFocus;
            self.toggleSelectedHUD.setChecked( self.editor.imageViews[axis]._hud.isVisible() )
        self.editor.newImageView2DFocus.connect(onViewFocused)

        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.setLayout(self.layout)
        
        # setup quadview
        axisLabels = ["X", "Y", "Z"]
        axisColors = [QColor("#dc143c"), QColor("green"), QColor("blue")]
        for i, v in enumerate(self.editor.imageViews):
            v.hud = ImageView2DHud(v)
            #connect interpreter
            v.hud.createImageView2DHud(axisLabels[i], 0, axisColors[i], QColor("white"))
            v.hud.sliceSelector.valueChanged.connect(partial(self.editor.navCtrl.changeSliceAbsolute, axis=i))

        self.quadview = QuadView(self, self.editor.imageViews[2],
                                 self.editor.imageViews[0], self.editor.imageViews[1],
                                 self.editor.view3d)
        self.quadview.installEventFilter(self)
        self.quadViewStatusBar = QuadStatusBar()
        self.quadViewStatusBar.createQuadViewStatusBar(
            QColor("#dc143c"),
            QColor("white"),
            QColor("green"),
            QColor("white"),
            QColor("blue"),
            QColor("white"))
        self.quadview.addStatusBar(self.quadViewStatusBar)
        self.layout.addWidget(self.quadview)

        ## Why do we have to prevent TimerEvents reaching the SpinBoxes?
        #
        # Sometimes clicking a SpinBox once caused the value to increase by
        # two. This is why:
        #
        # When a MouseClicked event is received by the SpinBox it fires a timerevent to control
        # the repeated increase of the value as long as the mouse button is pressed. The timer
        # is killed when it receives a MouseRelease event. If a slot connected to the valueChanged
        # signal of the SpinBox takes to long to process the signal the mouse release
        # and timer events get queued up and sometimes the timer event reaches the widget before
        # the mouse release event. That's why it increases the value by another step. To prevent
        # this we are blocking the timer events at the cost of no autorepeat anymore.
        #
        # See also:
        # http://lists.trolltech.com/qt-interest/2002-04/thread00137-0.html
        # http://www.qtcentre.org/threads/43078-QSpinBox-Timer-Issue
        # http://qt.gitorious.org/qt/qt/blobs/4.8/src/gui/widgets/qabstractspinbox.cpp#line1195
        self.quadview.statusBar.channelSpinBox.installEventFilter( _timerEater )
        self.quadview.statusBar.timeSpinBox.installEventFilter( _timerEater )

        def setChannel(c):
            if c == self.editor.posModel.channel:
                return
            self.editor.posModel.channel = c
        self.quadview.statusBar.channelSpinBox.valueChanged.connect(setChannel)
        def getChannel(newC):
            self.quadview.statusBar.channelSpinBox.setValue(newC)
        self.editor.posModel.channelChanged.connect(getChannel)
        def setTime(t):
            if t == self.editor.posModel.time:
                return
            self.editor.posModel.time = t
        self.quadview.statusBar.timeSpinBox.valueChanged.connect(setTime)
        def getTime(newT):
            self.quadview.statusBar.timeSpinBox.setValue(newT)
        self.editor.posModel.timeChanged.connect(getTime) 

        def toggleSliceIntersection(state):
            self.editor.navCtrl.indicateSliceIntersection = (state == Qt.Checked)
        self.quadview.statusBar.positionCheckBox.stateChanged.connect(toggleSliceIntersection)

        self.editor.posModel.cursorPositionChanged.connect(self._updateInfoLabels)

        def onShapeChanged():
            singletonDims = filter( lambda (i,dim): dim == 1, enumerate(self.editor.posModel.shape5D[1:4]) )
            if len(singletonDims) == 1:
                # Maximize the slicing view for this axis
                axis = singletonDims[0][0]
                self.quadview.ensureMaximized(axis)
                self.hudsShown[axis] = self.editor.imageViews[axis].hudVisible()
                self.editor.imageViews[axis].setHudVisible(False)
                self.quadViewStatusBar.showXYCoordinates()
                
                self.quadview.statusBar.positionCheckBox.setVisible(False)
            else:
                self.quadViewStatusBar.showXYZCoordinates()
                for i in range(3):
                    self.editor.imageViews[i].setHudVisible(self.hudsShown[i])
                self.quadview.statusBar.positionCheckBox.setVisible(True)
        
            self._setupVolumeExtent()

        self.editor.shapeChanged.connect(onShapeChanged)
        
        self.updateGeometry()
        self.update()
        self.quadview.update()

        # shortcuts
        self._initShortcuts()

    def _toggleDebugPatches(self,show):
        self.editor.showDebugPatches = show

    def _fitToScreen(self):
        shape = self.editor.posModel.shape
        for i, v in enumerate(self.editor.imageViews):
            s = list(copy.copy(shape))
            del s[i]
            v.changeViewPort(v.scene().data2scene.mapRect(QRectF(0,0,*s)))  
            
    def _fitImage(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].fitImage()
            
    def _restoreImageToOriginalSize(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].doScaleTo()
                
    def _rubberBandZoom(self):
        if self.editor._lastImageViewFocus is not None:
            if not self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom:
                self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = True
                self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup = self.editor.imageViews[self.editor._lastImageViewFocus].cursor()
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(Qt.CrossCursor)
            else:
                self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = False
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup)
            
    
    def _toggleHUDs(self, checked):
        for v in self.editor.imageViews:
            v.setHudVisible(checked)
            
    def _toggleSelectedHud(self, checked):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].setHudVisible(checked)
            
    def _centerAllImages(self):
        for v in self.editor.imageViews:
            v.centerImage()
            
    def _centerImage(self):
        if self.editor._lastImageViewFocus is not None:
            self.editor.imageViews[self.editor._lastImageViewFocus].centerImage()

    def _shortcutHelper(self, keySequence, group, description, parent, function, context = None, enabled = None, widget=None):
        shortcut = QShortcut(QKeySequence(keySequence), parent, member=function, ambiguousMember=function)
        if context != None:
            shortcut.setContext(context)
        if enabled != None:
            shortcut.setEnabled(True)

        ShortcutManager().register( group, description, shortcut, widget )
        return shortcut, group, description

    def _initShortcuts(self):
        self.shortcuts = []

        # TODO: Fix this dependency on ImageView/HUD internals
        self.shortcuts.append(self._shortcutHelper("x", "Navigation", "Minimize/Maximize x-Window", self, self.quadview.switchXMinMax, Qt.ApplicationShortcut, True, widget=self.editor.imageViews[0].hud.buttons['maximize']))
        self.shortcuts.append(self._shortcutHelper("y", "Navigation", "Minimize/Maximize y-Window", self, self.quadview.switchYMinMax, Qt.ApplicationShortcut, True, widget=self.editor.imageViews[1].hud.buttons['maximize']))
        self.shortcuts.append(self._shortcutHelper("z", "Navigation", "Minimize/Maximize z-Window", self, self.quadview.switchZMinMax, Qt.ApplicationShortcut, True, widget=self.editor.imageViews[2].hud.buttons['maximize']))
        
        
        for i, v in enumerate(self.editor.imageViews):
            self.shortcuts.append(self._shortcutHelper("+", "Navigation", "Zoom in", v,  v.zoomIn, Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("-", "Navigation", "Zoom out", v, v.zoomOut, Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("c", "Navigation", "Center image", v,  v.centerImage, Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("h", "Navigation", "Toggle hud", v,  v.toggleHud, Qt.WidgetShortcut))
            
            # FIXME: The nextChannel/previousChannel functions don't work right now.
            #self.shortcuts.append(self._shortcutHelper("q", "Navigation", "Switch to next channel",     v, self.editor.nextChannel,     Qt.WidgetShortcut))
            #self.shortcuts.append(self._shortcutHelper("a", "Navigation", "Switch to previous channel", v, self.editor.previousChannel, Qt.WidgetShortcut))
            
            def sliceDelta(axis, delta):
                newPos = copy.copy(self.editor.posModel.slicingPos)
                newPos[axis] += delta
                self.editor.posModel.slicingPos = newPos
            
            # TODO: Fix this dependency on ImageView/HUD internals
            self.shortcuts.append(self._shortcutHelper("Ctrl+Up",   "Navigation", "Slice up",   v, partial(sliceDelta, i, 1),  Qt.WidgetShortcut, widget=v.hud.buttons['slice'].upLabel))
            self.shortcuts.append(self._shortcutHelper("Ctrl+Down", "Navigation", "Slice down", v, partial(sliceDelta, i, -1), Qt.WidgetShortcut, widget=v.hud.buttons['slice'].downLabel))
            
#            self.shortcuts.append(self._shortcutHelper("p", "Navigation", "Slice up (alternate shortcut)",   v, partial(sliceDelta, i, 1),  Qt.WidgetShortcut))
#            self.shortcuts.append(self._shortcutHelper("o", "Navigation", "Slice down (alternate shortcut)", v, partial(sliceDelta, i, -1), Qt.WidgetShortcut))
            
            self.shortcuts.append(self._shortcutHelper("Ctrl+Shift+Up",   "Navigation", "10 slices up",   v, partial(sliceDelta, i, 10),  Qt.WidgetShortcut))
            self.shortcuts.append(self._shortcutHelper("Ctrl+Shift+Down", "Navigation", "10 slices down", v, partial(sliceDelta, i, -10), Qt.WidgetShortcut))

    def _updateInfoLabels(self, pos):
        self.quadViewStatusBar.setMouseCoords(*pos)

    def eventFilter(self, watched, event):
        # If the user performs a ctrl+scroll on the splitter itself,
        # scroll all views.
        if event.type() == QEvent.Wheel and (event.modifiers() == Qt.ControlModifier):
            for view in self.editor.imageViews:
                if event.delta() > 0:
                    view.zoomIn()
                else:
                    view.zoomOut()
            return True
        return False
                     
#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************
if __name__ == "__main__":
    
    import sys
    from layerstack import LayerStackModel
    from volumina.layer import GrayscaleLayer
    
    array = numpy.random.rand(1,100,100,100,1)
    array *= 255
    array = array.astype('uint8')
    
    layer = GrayscaleLayer(ArraySource(array))
    app = QApplication(sys.argv)
    layerStackModel = LayerStackModel()
    layerStackModel.insert(0,layer)
    volumeEditor = VolumeEditor(layerStackModel)
    volumeEditor.dataShape = array.shape
    volumeEditorWidget = VolumeEditorWidget(editor=volumeEditor)
    volumeEditorWidget.show()
    app.exec_()   

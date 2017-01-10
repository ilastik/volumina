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
#!/usr/bin/env python
from __future__ import division
import sys
from PyQt5.QtCore import Qt, pyqtSignal, QEvent, QTimer
from PyQt5.QtWidgets import QSizePolicy, QWidget, QVBoxLayout, QSplitter, QApplication

class ImageView2DFloatingWindow(QWidget):
    onCloseClick = pyqtSignal()
    def __init__(self):
        QWidget.__init__(self)
    
    def closeEvent(self, event):
        self.onCloseClick.emit()
        event.ignore()

class ImageView2DDockWidget(QWidget):
    onDockButtonClicked = pyqtSignal()
    onMaxButtonClicked = pyqtSignal()
    onMinButtonClicked = pyqtSignal()

    def __init__(self, graphicsView):
        QWidget.__init__(self)

        self.graphicsView = graphicsView
        self._isDocked = True
        self._isMaximized = False
        
        self.setContentsMargins(0, 0, 0, 0)
        
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(self.layout)
        
        self.windowForGraphicsView = ImageView2DFloatingWindow()
        self.windowForGraphicsView.layout = QVBoxLayout()
        self.windowForGraphicsView.layout.setContentsMargins(0, 0, 0, 0)
        self.windowForGraphicsView.setLayout(self.windowForGraphicsView.layout)
        
        self.windowForGraphicsView.onCloseClick.connect(self.onDockButton)
    
        self.addGraphicsView()
    
    def connectHud(self):
        if hasattr(self.graphicsView, '_hud'):
            self.graphicsView._hud.dockButtonClicked.connect(self.onDockButton)
            self.graphicsView._hud.maximizeButtonClicked.connect(self.onMaxButton)

    def onMaxButton(self):
        if self._isMaximized:
            self.onMinButtonClicked.emit()
            self.minimizeView()
        else:
            self.onMaxButtonClicked.emit()
            self.maximizeView()
        
    def onDockButton(self):
        self.onDockButtonClicked.emit()
        
    def addGraphicsView(self):
        self.layout.addWidget(self.graphicsView)
        
    def removeGraphicsView(self):
        self.layout.removeWidget(self.graphicsView)
        
    def undockView(self):
        self._isDocked = False
        if hasattr(self.graphicsView, '_hud'):
            self.graphicsView._hud.dockButton.setIcon('dock')
            self.graphicsView._hud.maxButton.setEnabled(False)
        
        self.removeGraphicsView()
        self.windowForGraphicsView.layout.addWidget(self.graphicsView)
        self.windowForGraphicsView.showMaximized() #supersize me
        self.windowForGraphicsView.setWindowTitle("ilastik")
        self.windowForGraphicsView.raise_()
    
    def dockView(self):
        self._isDocked = True
        if hasattr(self.graphicsView, '_hud'):
            self.graphicsView._hud.dockButton.setIcon('undock')
            self.graphicsView._hud.maxButton.setEnabled(True)
        
        self.windowForGraphicsView.layout.removeWidget(self.graphicsView)
        self.windowForGraphicsView.hide()
        self.addGraphicsView()
        
    def maximizeView(self):
        self._isMaximized = True
        if hasattr(self.graphicsView, '_hud'):
            self.graphicsView._hud.maxButton.setIcon('minimize')
        
    def minimizeView(self):
        self._isMaximized = False
        if hasattr(self.graphicsView, '_hud'):
            self.graphicsView._hud.maxButton.setIcon('maximize')

class QuadView(QWidget):
    def __init__(self, parent, view1, view2, view3, view4 = None):
        QWidget.__init__(self, parent)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.installEventFilter(self)
        
        self.dockableContainer = []
        
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        self.splitVertical = QSplitter(Qt.Vertical, self)
        self.layout.addWidget(self.splitVertical)
        self.splitHorizontal1 = QSplitter(Qt.Horizontal, self.splitVertical)
        self.splitHorizontal1.setObjectName("splitter1")
        self.splitHorizontal2 = QSplitter(Qt.Horizontal, self.splitVertical)
        self.splitHorizontal2.setObjectName("splitter2")
        self.splitHorizontal1.splitterMoved.connect(self.horizontalSplitterMoved)
        self.splitHorizontal2.splitterMoved.connect(self.horizontalSplitterMoved)
        
        self.imageView2D_1 = view1
        
        self.imageView2D_2 = view2
        
        self.imageView2D_3 = view3
        
        self.dock1_ofSplitHorizontal1 = ImageView2DDockWidget(self.imageView2D_1)
        self.dock1_ofSplitHorizontal1.connectHud()
        self.dockableContainer.append(self.dock1_ofSplitHorizontal1)
        self.dock1_ofSplitHorizontal1.onDockButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal1 : self.on_dock(arg))
        self.dock1_ofSplitHorizontal1.onMaxButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal1 : self.on_max(arg))
        self.dock1_ofSplitHorizontal1.onMinButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal1 : self.on_min(arg))
        self.splitHorizontal1.addWidget(self.dock1_ofSplitHorizontal1)

        self.dock2_ofSplitHorizontal1 = ImageView2DDockWidget(self.imageView2D_2)
        self.dock2_ofSplitHorizontal1.onDockButtonClicked.connect(lambda arg=self.dock2_ofSplitHorizontal1 : self.on_dock(arg))
        self.dock2_ofSplitHorizontal1.onMaxButtonClicked.connect(lambda arg=self.dock2_ofSplitHorizontal1 : self.on_max(arg))
        self.dock2_ofSplitHorizontal1.onMinButtonClicked.connect(lambda arg=self.dock2_ofSplitHorizontal1 : self.on_min(arg))
        self.dock2_ofSplitHorizontal1.connectHud()
        self.dockableContainer.append(self.dock2_ofSplitHorizontal1)
        self.splitHorizontal1.addWidget(self.dock2_ofSplitHorizontal1)

        self.dock1_ofSplitHorizontal2 = ImageView2DDockWidget(self.imageView2D_3)
        self.dock1_ofSplitHorizontal2.onDockButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal2 : self.on_dock(arg))
        self.dock1_ofSplitHorizontal2.onMaxButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal2 : self.on_max(arg))
        self.dock1_ofSplitHorizontal2.onMinButtonClicked.connect(lambda arg=self.dock1_ofSplitHorizontal2 : self.on_min(arg))
        self.dock1_ofSplitHorizontal2.connectHud()
        self.dockableContainer.append(self.dock1_ofSplitHorizontal2)
        self.splitHorizontal2.addWidget(self.dock1_ofSplitHorizontal2)

        self.dock2_ofSplitHorizontal2 = ImageView2DDockWidget(view4)
        self.dockableContainer.append(self.dock2_ofSplitHorizontal2)
        self.splitHorizontal2.addWidget(self.dock2_ofSplitHorizontal2)  
        
        #this is a hack: with 0 ms it does not work...
        QTimer.singleShot(250, self._resizeEqual)
        
    def _resizeEqual(self):
        if not all( [dock.isVisible() for dock in self.dockableContainer] ):
            return
        assert sys.version_info.major == 2, "Alert! This function has not been tested "\
        "under python 3. Please remove this assetion and be wary of any strnage behavior you encounter"
        w, h = self.size().width()-self.splitHorizontal1.handleWidth(), self.size().height()-self.splitVertical.handleWidth()

        self.splitVertical.setSizes([h/2, h/2])

        if self.splitHorizontal1.count() == 2 and self.splitHorizontal2.count() == 2:
            #docks = [self.imageView2D_1, self.imageView2D_2, self.imageView2D_3, self.testView4]
            docks = []        
            for splitter in [self.splitHorizontal1, self.splitHorizontal2]:
                for i in range( splitter.count() ):
                    docks.append( splitter.widget(i).graphicsView )
            
            w1  = [docks[i].minimumSize().width() for i in [0,2] ]
            w2  = [docks[i].minimumSize().width() for i in [1,3] ]
            wLeft  = max(w1)
            wRight = max(w2)
            if wLeft > wRight and wLeft > w//2:
                wRight = w - wLeft
            elif wRight >= wLeft and wRight > w//2:
                wLeft = w - wRight
            else:
                wLeft = w//2
                wRight = w//2
            self.splitHorizontal1.setSizes([wLeft, wRight])
            self.splitHorizontal2.setSizes([wLeft, wRight])
        
    def eventFilter(self, obj, event):
        if(event.type() in [QEvent.WindowActivate, QEvent.Show]):
            self._synchronizeSplitter()
        return False

    def _synchronizeSplitter(self):
        sizes1 = self.splitHorizontal1.sizes()
        sizes2 = self.splitHorizontal2.sizes()
        if len(sizes1) > 0 and sizes1[0] > 0:
            self.splitHorizontal2.setSizes(sizes1)
        elif len(sizes2) > 0 and sizes2[0] > 0:
            self.splitHorizontal1.setSizes(sizes2)
    
    def resizeEvent(self, event):
        QWidget.resizeEvent(self, event)
        self._synchronizeSplitter()
    
    def horizontalSplitterMoved(self, x, y):
        if self.splitHorizontal1.count() != 2 or self.splitHorizontal2.count() != 2:
            return 
        sizes = self.splitHorizontal1.sizes()
        #What. Nr2
        if self.splitHorizontal2.closestLegalPosition(x, y) < self.splitHorizontal2.closestLegalPosition(x, y):
            sizeLeft = self.splitHorizontal1.closestLegalPosition(x, y)
        else:
            sizeLeft = self.splitHorizontal2.closestLegalPosition(x, y)
            
        sizeRight = sizes[0] + sizes[1] - sizeLeft
        sizes = [sizeLeft, sizeRight]
        
        self.splitHorizontal1.setSizes(sizes)
        self.splitHorizontal2.setSizes(sizes) 

    def addStatusBar(self, bar):
        self.statusBar = bar
        self.layout.addLayout(self.statusBar)
        
    def setGrayScaleToQuadStatusBar(self, gray):
        self.quadViewStatusBar.setGrayScale(gray)
        
    def setMouseCoordsToQuadStatusBar(self, x, y, z):
        self.quadViewStatusBar.setMouseCoords(x, y, z) 

    def ensureMaximized(self, axis):
        """
        Maximize the view for the given axis if it isn't already maximized.
        """
        axisDict = { 0 : self.dock2_ofSplitHorizontal1,  # x
                     1 : self.dock1_ofSplitHorizontal2,  # y
                     2 : self.dock1_ofSplitHorizontal1 } # z
        
        if not axisDict[axis]._isMaximized:
            self.switchMinMax(axis)

    def switchMinMax(self,axis):
        """Switch an AxisViewWidget between from minimized to maximized and vice
        versa.

        Keyword arguments:
        axis -- the axis which is represented by the widget (no default)
                either string or integer 
                'x' - 0
                'y' - 1
                'z' - 2
        """
        
        #TODO: get the mapping information from where it is set! if this is not
        #done properly - do it properly

        if type(axis) == str:
            axisDict = { 'x' : self.dock2_ofSplitHorizontal1,  # x
                         'y' : self.dock1_ofSplitHorizontal2,  # y
                         'z' : self.dock1_ofSplitHorizontal1 } # z
        elif type(axis) == int:
            axisDict = { 0 : self.dock2_ofSplitHorizontal1,  # x
                         1 : self.dock1_ofSplitHorizontal2,  # y
                         2 : self.dock1_ofSplitHorizontal1 } # z

        dockWidget = axisDict.pop(axis)
        for dWidget in axisDict.values():
            if dWidget._isMaximized:
                dWidget.graphicsView._hud.maximizeButtonClicked.emit()
        dockWidget.graphicsView._hud.maximizeButtonClicked.emit()
    
    def switchXMinMax(self):
        self.switchMinMax('x')
    
    def switchYMinMax(self):
        self.switchMinMax('y')
        
    def switchZMinMax(self):
        self.switchMinMax('z')

    def on_dock(self, dockWidget):
        if dockWidget._isDocked:
            dockWidget.undockView()
            self.on_min(dockWidget)
            dockWidget.minimizeView()
        else:
            dockWidget.dockView()

    def on_max(self, dockWidget):
        dockWidget.setVisible(True)
        for dock in self.dockableContainer:
            if not dockWidget == dock:
                dock.setVisible(False)

        # Force sizes to be updated now
        QApplication.processEvents()
        
        # On linux, the vertical splitter doesn't seem to refresh unless we do so manually
        # Presumably, this is a QT bug.
        self.splitVertical.refresh()

        # Viewport doesn't update automatically...
        view = dockWidget.graphicsView        
        view.viewport().setGeometry( view.rect() )

    def on_min(self, dockWidget):

        for dock in self.dockableContainer:
            dock.setVisible(True)

        # Force sizes to be updated now
        QApplication.processEvents()
        self._resizeEqual()

        # Viewports don't update automatically...
        for dock in self.dockableContainer:
            view = dock.graphicsView
            if hasattr(view, 'viewport'):
                view.viewport().setGeometry( view.rect() )
   

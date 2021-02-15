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
#!/usr/bin/env python

# Python
from __future__ import division
from __future__ import absolute_import
from builtins import range
from functools import partial
import copy

# SciPy
import numpy

# PyQt
from PyQt5.QtCore import Qt, QRectF, QEvent, QObject, QTimerEvent, QTimer
from PyQt5.QtGui import QKeySequence, QColor, QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QShortcut,
    QHBoxLayout,
    QSizePolicy,
    QAction,
    QSpinBox,
    QMenu,
    QDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QMainWindow,
    QSpacerItem,
    QDialogButtonBox,
    QVBoxLayout,
)

# volumina
from .quadsplitter import QuadView
from .sliceSelectorHud import ImageView2DHud, QuadStatusBar
from .pixelpipeline.datasources import ArraySource
from .volumeEditor import VolumeEditor
from volumina.utility import ShortcutManager
from volumina.utility import preferences


class __TimerEventEater(QObject):
    def eventFilter(self, obj, ev):
        if isinstance(obj, QSpinBox) and isinstance(ev, QTimerEvent):
            return True
        return False


_timerEater = __TimerEventEater()


class VolumeEditorWidget(QWidget):
    def __init__(self, parent=None, editor=None):
        super(VolumeEditorWidget, self).__init__(parent=parent)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        self.editor = None
        if editor != None:
            self.init(editor)

        self._viewMenu = None

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

    def _setupVolumeExtent(self):
        """Setup min/max values of position/coordinate control elements.

        Position/coordinate information is read from the volumeEditor's positionModel.

        """
        maxTime = self.editor.posModel.shape5D[0] - 1
        self.quadview.statusBar.timeLabel.setHidden(maxTime == 0)
        self.quadview.statusBar.timeSpinBox.setHidden(maxTime == 0)
        self.quadview.statusBar.timeSpinBox.setRange(0, maxTime)
        self.quadview.statusBar.timeSpinBox.setSuffix("/{}".format(maxTime))
        self.quadview.statusBar.hideTimeSlider(maxTime == 0)

        cropMidPos = numpy.mean(self.editor.cropModel.get_roi_3d(), axis=0).astype(int)
        for i in range(3):
            self.editor.imageViews[i].hud.setMaximum(self.editor.posModel.volumeExtent(i) - 1)
            self.editor.navCtrl.changeSliceAbsolute(cropMidPos[i], i)
        self.editor.navCtrl.changeTime(self.editor.cropModel._crop_times[0])

    def init(self, volumina):
        self.editor = volumina

        self.hudsShown = [True] * 3

        def onViewFocused():
            axis = self.editor._lastImageViewFocus
            self.toggleSelectedHUD.setChecked(self.editor.imageViews[axis]._hud.isVisible())

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
            # connect interpreter
            v.hud.createImageView2DHud(axisLabels[i], 0, axisColors[i], QColor("white"))
            v.hud.sliceSelector.valueChanged.connect(partial(self.editor.navCtrl.changeSliceAbsolute, axis=i))

        self.quadview = QuadView(
            self, self.editor.imageViews[2], self.editor.imageViews[0], self.editor.imageViews[1], self.editor.view3d
        )
        self.quadview.installEventFilter(self)
        self.quadViewStatusBar = QuadStatusBar()
        self.quadViewStatusBar.createQuadViewStatusBar(
            QColor("#dc143c"), QColor("white"), QColor("green"), QColor("white"), QColor("blue"), QColor("white")
        )
        self.quadview.addStatusBar(self.quadViewStatusBar)
        self.layout.addWidget(self.quadview)

        # Little hack: Can't call setTabOrder on these widgets until the
        #              layout has been added to a widget, so we do this here.
        QWidget.setTabOrder(self.quadViewStatusBar.zSpinBox, self.quadViewStatusBar.timeSpinBox)

        # Here we subscribe to the dirtyChanged() signal from all slicing views,
        #  and show the status bar "busy indicator" if any view is dirty.
        # Caveat: To avoid a flickering indicator for quick updates, we use a
        #         timer that prevents the indicator from showing for a bit.
        def updateDirtyStatus(fromTimer=False):
            # We only care about views that are both VISIBLE and DIRTY.
            dirties = [v.scene().dirty for v in self.editor.imageViews]
            visibilities = [v.isVisible() for v in self.editor.imageViews]
            visible_dirtiness = numpy.logical_and(visibilities, dirties)

            if not any(visible_dirtiness):
                # Not dirty: Hide immediately
                self.quadViewStatusBar.busyIndicator.setVisible(False)
            else:
                if fromTimer:
                    # The timer finished and we're still dirty:
                    # Time to show the busy indicator.
                    self.quadViewStatusBar.busyIndicator.setVisible(True)
                elif not self.quadViewStatusBar.busyIndicator.isVisible() and not self._dirtyTimer.isActive():
                    # We're dirty, but delay for a bit before showing the busy indicator.
                    self._dirtyTimer.start(750)

        self._dirtyTimer = QTimer()
        self._dirtyTimer.setSingleShot(True)
        self._dirtyTimer.timeout.connect(partial(updateDirtyStatus, fromTimer=True))
        for i, view in enumerate(self.editor.imageViews):
            view.scene().dirtyChanged.connect(updateDirtyStatus)

        # If the user changes the position in the quad-view status bar (at the bottom),
        # Update the position of the whole editor.
        def setPositionFromQuadBar(x, y, z):
            self.editor.posModel.slicingPos = (x, y, z)
            self.editor.posModel.cursorPos = (x, y, z)
            self.editor.navCtrl.panSlicingViews((x, y, z), [0, 1, 2])

        self.quadViewStatusBar.positionChanged.connect(setPositionFromQuadBar)

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
        self.quadview.statusBar.timeSpinBox.installEventFilter(_timerEater)

        def setTime(t):
            if t == self.editor.posModel.time:
                return
            self.editor.posModel.time = t

        self.quadview.statusBar.timeSpinBox.delayedValueChanged.connect(setTime)

        def setTimeSpinBox(newT):
            self.quadview.statusBar.timeSpinBox.setValue(newT)

        self.editor.posModel.timeChanged.connect(setTimeSpinBox)

        def toggleSliceIntersection(state):
            self.editor.navCtrl.indicateSliceIntersection = state == Qt.Checked

        self.quadview.statusBar.crosshairsCheckbox.stateChanged.connect(toggleSliceIntersection)
        toggleSliceIntersection(self.quadview.statusBar.crosshairsCheckbox.checkState())

        self.editor.posModel.cursorPositionChanged.connect(self._updateInfoLabels)

        def onShapeChanged():
            # By default, 3D HUD buttons are visible,
            #  but we'll turn them off below if the dataset is 2D.
            for axis in [0, 1, 2]:
                self.editor.imageViews[axis].hud.set3DButtonsVisible(True)

            singletonDims = [i_dim for i_dim in enumerate(self.editor.posModel.shape5D[1:4]) if i_dim[1] == 1]
            if len(singletonDims) == 1:
                # Maximize the slicing view for this axis
                axis = singletonDims[0][0]
                self.quadview.ensureMaximized(axis)
                self.hudsShown[axis] = self.editor.imageViews[axis].hudVisible()
                self.editor.imageViews[axis].hud.set3DButtonsVisible(False)
                self.quadViewStatusBar.showXYCoordinates()
                self.quadview.statusBar.crosshairsCheckbox.setChecked(False)
            else:
                self.quadViewStatusBar.showXYZCoordinates()
                for i in range(3):
                    self.editor.imageViews[i].setHudVisible(self.hudsShown[i])
                self.quadview.statusBar.crosshairsCheckbox.setChecked(False)

            self._updateTileWidth()

            self.quadview.statusBar.crosshairsCheckbox.setVisible(True)

            if self.editor.cropModel.cropZero() or None in self.editor.cropModel.get_roi_3d()[0]:
                self.quadViewStatusBar.updateShape5D(self.editor.posModel.shape5D)
            else:
                crop_roi_3d = self.editor.cropModel.get_roi_3d()
                cropMin = (self.editor.posModel.time,) + tuple(crop_roi_3d[0]) + (0,)
                self.quadViewStatusBar.updateShape5Dcropped(cropMin, self.editor.posModel.shape5D)

            self._setupVolumeExtent()

        self.editor.shapeChanged.connect(onShapeChanged)

        self.updateGeometry()
        self.update()
        self.quadview.update()
        self.editor.view3d.dock_status_changed.connect(
            partial(self.quadview.on_dock, self.quadview.dock2_ofSplitHorizontal2)
        )

        # shortcuts
        self._initShortcuts()

    def _toggleDebugPatches(self, show):
        self.editor.showDebugPatches = show

    def _fitToScreen(self):
        shape = self.editor.posModel.shape
        for i, v in enumerate(self.editor.imageViews):
            s = list(copy.copy(shape))
            del s[i]
            v.changeViewPort(v.scene().data2scene.mapRect(QRectF(0, 0, *s)))

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
                self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup = self.editor.imageViews[
                    self.editor._lastImageViewFocus
                ].cursor()
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(Qt.CrossCursor)
            else:
                self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = False
                self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(
                    self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup
                )

    def _updateTileWidth(self):
        tile_width = self._getTileWidth()
        self.editor.setTileWidth(tile_width)

    def _getTileWidthConfigKeyDefault(self):
        singletons_spacial = [True for dim in self.editor.posModel.shape if dim == 1]
        assert len(singletons_spacial) in range(2)
        if len(singletons_spacial) == 0:
            # 3D data
            key = "tileWidth3D"
            default = 256
        else:
            # 2D data
            key = "tileWidth"
            default = 512
        return key, default

    def _getTileWidth(self):
        key, default = self._getTileWidthConfigKeyDefault()
        tile_width = preferences.get("ImageScene2D", key, default=default)
        return tile_width

    def _setTileWidth(self, value):
        key, _ = self._getTileWidthConfigKeyDefault()
        preferences.set("ImageScene2D", key, value)
        self._updateTileWidth()

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

    def _initShortcuts(self):
        # TODO: Fix this dependency on ImageView/HUD internals
        mgr = ShortcutManager()
        ActionInfo = ShortcutManager.ActionInfo
        mgr.register(
            "x",
            ActionInfo(
                "Navigation",
                "Minimize/Maximize x-Window",
                "Minimize/Maximize x-Window",
                self.quadview.switchXMinMax,
                self.editor.imageViews[0].hud.buttons["maximize"],
                self.editor.imageViews[0].hud.buttons["maximize"],
            ),
        )

        mgr.register(
            "y",
            ActionInfo(
                "Navigation",
                "Minimize/Maximize y-Window",
                "Minimize/Maximize y-Window",
                self.quadview.switchYMinMax,
                self.editor.imageViews[1].hud.buttons["maximize"],
                self.editor.imageViews[1].hud.buttons["maximize"],
            ),
        )

        mgr.register(
            "z",
            ActionInfo(
                "Navigation",
                "Minimize/Maximize z-Window",
                "Minimize/Maximize z-Window",
                self.quadview.switchZMinMax,
                self.editor.imageViews[2].hud.buttons["maximize"],
                self.editor.imageViews[2].hud.buttons["maximize"],
            ),
        )

        for i, v in enumerate(self.editor.imageViews):
            mgr.register("+", ActionInfo("Navigation", "Zoom in", "Zoom in", v.zoomIn, v, None))
            mgr.register("-", ActionInfo("Navigation", "Zoom out", "Zoom out", v.zoomOut, v, None))

            mgr.register("c", ActionInfo("Navigation", "Center image", "Center image", v.centerImage, v, None))

            mgr.register("h", ActionInfo("Navigation", "Toggle hud", "Toggle hud", v.toggleHud, v, None))

            # FIXME: The nextChannel/previousChannel functions don't work right now.
            # self._shortcutHelper("q", "Navigation", "Switch to next channel",     v, self.editor.nextChannel,     Qt.WidgetShortcut))
            # self._shortcutHelper("a", "Navigation", "Switch to previous channel", v, self.editor.previousChannel, Qt.WidgetShortcut))

            def sliceDelta(axis, delta):
                newPos = copy.copy(self.editor.posModel.slicingPos)
                newPos[axis] += delta
                newPos[axis] = max(0, newPos[axis])
                newPos[axis] = min(self.editor.posModel.shape[axis] - 1, newPos[axis])
                self.editor.posModel.slicingPos = newPos

            def jumpToFirstSlice(axis):
                newPos = copy.copy(self.editor.posModel.slicingPos)
                newPos[axis] = 0
                self.editor.posModel.slicingPos = newPos

            def jumpToLastSlice(axis):
                newPos = copy.copy(self.editor.posModel.slicingPos)
                newPos[axis] = self.editor.posModel.shape[axis] - 1
                self.editor.posModel.slicingPos = newPos

            # TODO: Fix this dependency on ImageView/HUD internals
            mgr.register(
                "Ctrl+Up",
                ActionInfo(
                    "Navigation", "Slice up", "Slice up", partial(sliceDelta, i, 1), v, v.hud.buttons["slice"].upLabel
                ),
            )

            mgr.register(
                "Ctrl+Down",
                ActionInfo(
                    "Navigation",
                    "Slice up",
                    "Slice up",
                    partial(sliceDelta, i, -1),
                    v,
                    v.hud.buttons["slice"].downLabel,
                ),
            )

            #            self._shortcutHelper("p", "Navigation", "Slice up (alternate shortcut)",   v, partial(sliceDelta, i, 1),  Qt.WidgetShortcut)
            #            self._shortcutHelper("o", "Navigation", "Slice down (alternate shortcut)", v, partial(sliceDelta, i, -1), Qt.WidgetShortcut)

            mgr.register(
                "Ctrl+Shift+Up",
                ActionInfo("Navigation", "10 slices up", "10 slices up", partial(sliceDelta, i, 10), v, None),
            )

            mgr.register(
                "Ctrl+Shift+Down",
                ActionInfo("Navigation", "10 slices down", "10 slices down", partial(sliceDelta, i, -10), v, None),
            )

            mgr.register(
                "Shift+Up",
                ActionInfo(
                    "Navigation", "Jump to first slice", "Jump to first slice", partial(jumpToFirstSlice, i), v, None
                ),
            )

            mgr.register(
                "Shift+Down",
                ActionInfo(
                    "Navigation", "Jump to last slice", "Jump to last slice", partial(jumpToLastSlice, i), v, None
                ),
            )

    def _updateInfoLabels(self, pos):
        self.quadViewStatusBar.setMouseCoords(*pos)

    def eventFilter(self, watched, event):
        # If the user performs a ctrl+scroll on the splitter itself,
        # scroll all views.
        if event.type() == QEvent.Wheel and (event.modifiers() == Qt.ControlModifier):
            for view in self.editor.imageViews:
                if event.angleDelta().y() > 0:
                    view.zoomIn()
                else:
                    view.zoomOut()
            return True
        return False

    def getViewMenu(self, debug_mode=False):
        """
        Return a QMenu with a set of actions for our editor.
        """
        if self._viewMenu is None:
            self._initViewMenu()
        for action in self._debugActions:
            action.setEnabled(debug_mode)
            action.setVisible(debug_mode)
        return self._viewMenu

    def _initViewMenu(self):
        self._viewMenu = QMenu("View", parent=self)
        self._viewMenu.setObjectName("view_menu")
        self._debugActions = []

        ActionInfo = ShortcutManager.ActionInfo

        # This action is saved as a member so it can be triggered from tests
        self._viewMenu.actionFitToScreen = self._viewMenu.addAction("&Zoom to &fit")
        self._viewMenu.actionFitToScreen.triggered.connect(self._fitToScreen)

        def toggleHud():
            hide = not self.editor.imageViews[0]._hud.isVisible()
            for v in self.editor.imageViews:
                v.setHudVisible(hide)

        # This action is saved as a member so it can be triggered from tests
        self._viewMenu.actionToggleAllHuds = self._viewMenu.addAction("Toggle huds")
        self._viewMenu.actionToggleAllHuds.triggered.connect(toggleHud)

        def resetAllAxes():
            for s in self.editor.imageScenes:
                s.resetAxes()

        self._viewMenu.addAction("Reset all axes").triggered.connect(resetAllAxes)

        def centerAllImages():
            for v in self.editor.imageViews:
                v.centerImage()

        self._viewMenu.addAction("Center images").triggered.connect(centerAllImages)

        def toggleDebugPatches(show):
            self.editor.showDebugPatches = show

        actionShowTiling = self._viewMenu.addAction("Show Tiling")
        actionShowTiling.setCheckable(True)
        actionShowTiling.toggled.connect(toggleDebugPatches)
        ShortcutManager().register(
            "Ctrl+D", ActionInfo("Navigation", "Show tiling", "Show tiling", actionShowTiling.toggle, self, None)
        )
        self._debugActions.append(actionShowTiling)

        def setCacheSize(cache_size):
            dlg = QDialog(self)
            layout = QHBoxLayout()
            layout.addWidget(QLabel("Cached Slices Per View:"))

            spinBox = QSpinBox(parent=dlg)
            spinBox.setRange(0, 1000)
            spinBox.setValue(self.editor.cacheSize)
            layout.addWidget(spinBox)
            okButton = QPushButton("OK", parent=dlg)
            okButton.clicked.connect(dlg.accept)
            layout.addWidget(okButton)
            dlg.setLayout(layout)
            dlg.setModal(True)
            if dlg.exec_() == QDialog.Accepted:
                self.editor.cacheSize = spinBox.value()

        self._viewMenu.addAction("Set layer cache size").triggered.connect(setCacheSize)

        def enablePrefetching(enable):
            # Enable for Z view only
            self.editor.imageScenes[2].setPrefetchingEnabled(enable)

        #             for scene in self.editor.imageScenes:
        #                 scene.setPrefetchingEnabled( enable )
        actionUsePrefetching = self._viewMenu.addAction("Use prefetching")
        actionUsePrefetching.setCheckable(True)
        actionUsePrefetching.toggled.connect(enablePrefetching)

        def blockGuiForRendering():
            for v in self.editor.imageViews:
                v.scene().joinRenderingAllTiles()
                v.repaint()
            QApplication.processEvents()

        actionBlockGui = self._viewMenu.addAction("Block for rendering")
        actionBlockGui.triggered.connect(blockGuiForRendering)
        ShortcutManager().register(
            "Ctrl+B",
            ActionInfo(
                "Navigation", "Block gui for rendering", "Block gui for rendering", actionBlockGui.trigger, self, None
            ),
        )
        self._debugActions.append(actionBlockGui)

        def changeTileWidth():
            """Change tile width (tile block size) and reset image-scene"""
            dlg = QDialog(self)
            dlg.setWindowTitle("Viewer Tile Width")
            dlg.setModal(True)

            saved = self._getTileWidth()
            spinBox = QSpinBox(parent=dlg)
            spinBox.setRange(128, 10 * 1024)
            spinBox.setValue(saved)

            ctrl_layout = QHBoxLayout()
            ctrl_layout.addSpacerItem(QSpacerItem(10, 0, QSizePolicy.Expanding))
            ctrl_layout.addWidget(QLabel("Tile Width:"))
            ctrl_layout.addWidget(spinBox)

            button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=dlg)
            button_box.accepted.connect(dlg.accept)
            button_box.rejected.connect(dlg.reject)

            dlg_layout = QVBoxLayout()
            dlg_layout.addLayout(ctrl_layout)
            dlg_layout.addWidget(
                QLabel("Setting will apply current view immediately,\n" "and all other views upon restart.")
            )
            dlg_layout.addWidget(button_box)

            dlg.setLayout(dlg_layout)

            if dlg.exec_() == QDialog.Accepted:
                if spinBox.value() != saved:
                    self._setTileWidth(spinBox.value())

        self._viewMenu.addAction("Set Tile Width...").triggered.connect(changeTileWidth)

        # ------ Separator ------
        self._viewMenu.addAction("").setSeparator(True)

        # Text only
        actionOnlyForSelectedView = self._viewMenu.addAction("Only for selected view")
        actionOnlyForSelectedView.setIconVisibleInMenu(True)
        font = actionOnlyForSelectedView.font()
        font.setItalic(True)
        font.setBold(True)
        actionOnlyForSelectedView.setFont(font)

        def setCurrentAxisIcon():
            """Update the icon that shows the currently selected axis."""
            actionOnlyForSelectedView.setIcon(
                QIcon(self.editor.imageViews[self.editor._lastImageViewFocus]._hud.axisLabel.pixmap())
            )

        self.editor.newImageView2DFocus.connect(setCurrentAxisIcon)
        setCurrentAxisIcon()

        actionFitImage = self._viewMenu.addAction("Fit image")
        actionFitImage.triggered.connect(self._fitImage)
        ShortcutManager().register(
            "K",
            ActionInfo("Navigation", "Fit image on screen", "Fit image on screen", actionFitImage.trigger, self, None),
        )

        def toggleSelectedHud():
            self.editor.imageViews[self.editor._lastImageViewFocus].toggleHud()

        actionToggleSelectedHud = self._viewMenu.addAction("Toggle hud")
        actionToggleSelectedHud.triggered.connect(toggleSelectedHud)

        def resetAxes():
            self.editor.imageScenes[self.editor._lastImageViewFocus].resetAxes()

        self._viewMenu.addAction("Reset axes").triggered.connect(resetAxes)

        def centerImage():
            self.editor.imageViews[self.editor._lastImageViewFocus].centerImage()

        actionCenterImage = self._viewMenu.addAction("Center image")
        actionCenterImage.triggered.connect(centerImage)
        ShortcutManager().register(
            "C", ActionInfo("Navigation", "Center image", "Center image", actionCenterImage.trigger, self, None)
        )

        def restoreImageToOriginalSize():
            self.editor.imageViews[self.editor._lastImageViewFocus].doScaleTo()

        actionResetZoom = self._viewMenu.addAction("Reset zoom")
        actionResetZoom.triggered.connect(restoreImageToOriginalSize)
        ShortcutManager().register(
            "W", ActionInfo("Navigation", "Reset zoom", "Reset zoom", actionResetZoom.trigger, self, None)
        )

        def updateHudActions():
            dataShape = self.editor.dataShape
            # if the image is 2D, do not show the HUD action (issue #190)
            is2D = numpy.sum(numpy.asarray(dataShape[1:4]) == 1) == 1
            actionToggleSelectedHud.setVisible(not is2D)
            self._viewMenu.actionToggleAllHuds.setVisible(not is2D)

        self.editor.shapeChanged.connect(updateHudActions)

        # FIXME: this needs bug fixing
        # def rubberBandZoom():
        #    if hasattr(self.editor, '_lastImageViewFocus'):
        #        if not self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom:
        #            self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = True
        #            self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup = self.editor.imageViews[self.editor._lastImageViewFocus].cursor()
        #            self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(Qt.CrossCursor)
        #        else:
        #            self.editor.imageViews[self.editor._lastImageViewFocus]._isRubberBandZoom = False
        #            self.editor.imageViews[self.editor._lastImageViewFocus].setCursor(self.editor.imageViews[self.editor._lastImageViewFocus]._cursorBackup)
        # self._viewMenu.addAction( "RubberBand zoom" ).triggered.connect(rubberBandZoom)


# *******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
# *******************************************************************************
if __name__ == "__main__":

    import sys
    from .layerstack import LayerStackModel
    from volumina.layer import GrayscaleLayer

    array = numpy.random.rand(1, 100, 100, 100, 1)
    array *= 255
    array = array.astype("uint8")

    layer = GrayscaleLayer(ArraySource(array))
    app = QApplication(sys.argv)
    layerStackModel = LayerStackModel()
    layerStackModel.insert(0, layer)
    volumeEditor = VolumeEditor(layerStackModel, parent=None)
    volumeEditor.dataShape = array.shape
    volumeEditorWidget = VolumeEditorWidget(editor=volumeEditor)
    volumeEditorWidget.show()
    app.exec_()

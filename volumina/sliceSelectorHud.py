from __future__ import division
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

from past.utils import old_div
from functools import partial

#PyQt
from PyQt5.QtCore import pyqtSignal, Qt, QPointF, QSize
from PyQt5.QtGui import QPen, QPainter, QPixmap, QColor, QFont, QPainterPath, QBrush, QTransform

from PyQt5.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QAbstractSpinBox, QCheckBox, QWidget, \
                            QFrame, QProgressBar, QSizePolicy, QSlider, QPushButton



from volumina.widgets.delayedSpinBox import DelayedSpinBox

TEMPLATE = "QSpinBox {{ color: {0}; font: bold; background-color: {1}; border:0;}}"

def _load_icon(filename, backgroundColor, width, height):
    foreground = QPixmap()
    foreground.load(filename)
    pixmap = QPixmap(foreground.size())
    pixmap.fill(backgroundColor)

    painter = QPainter()
    painter.begin(pixmap)
    painter.drawPixmap(QPointF(0, 0), foreground)
    painter.end()

    pixmap = pixmap.scaled(QSize(width, height),
                           Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    return pixmap

# TODO: replace with QPushButton. in __init__(), read icon and give
# correct background color.
class LabelButtons(QLabel):
    clicked = pyqtSignal()
    def __init__(self, style, parentView, backgroundColor, foregroundColor, width, height):
        QLabel.__init__(self)
        self.setColors(backgroundColor, foregroundColor)
        self.setPixmapSize(width, height)
        self.setIcon(style)
        self._swapped = False
        self._rotation = 0

    def setColors(self, backgroundColor, foregroundColor):
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor

    def setPixmapSize(self, width, height):
        self.pixmapWidth = width
        self.pixmapHeight = height

    # values: (icon path, tooltip)
    icons = {
        'export' : (':icons/icons/export.png', "Export Current Composite View"),
        'undock' : (':icons/icons/undock.png', "Undock"),
        'dock' : (':icons/icons/dock.png', "Dock"),
        'zoom-to-fit' : (':icons/icons/spin-up.png', "Zoom to fit"),
        'reset-zoom' : (':icons/icons/spin-down.png', "Reset zoom"),
        'maximize' : (':icons/icons/maximize.png', "Maximize"),
        'minimize' : (':icons/icons/minimize.png', "Minimize"),
        'spin-up' : (':icons/icons/spin-up.png', "+ 1"),
        'spin-down' : (':icons/icons/spin-down.png', "- 1"),
        'rotate-left' : (':icons/icons/rotate-left.png', "Rotate left"),
        'rotate-right' : (':icons/icons/rotate-right.png', "Rotate right"),
        'swap-axes' : (':icons/icons/swap-axes.png', "Swap axes"),
        'swap-axes-swapped' : (':icons/icons/swap-axes-swapped.png', "Swap axes"),
    }

    def setIcon(self, style):
        self.buttonStyle = style
        iconpath, tooltip = self.icons[style]
        self.setToolTip(tooltip)
        pixmap = _load_icon(iconpath,
                            self.backgroundColor,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)
        self._orig_pixmap = pixmap

        if style == 'swap-axes':
            iconpath, _ = self.icons['swap-axes-swapped']
            self._pixmap_swapped = _load_icon(iconpath,
                                              self.backgroundColor,
                                              self.pixmapWidth,
                                              self.pixmapHeight)

    def mousePressEvent(self, event):
        self.clicked.emit()

    def _resetIcon(self):
        if self._swapped:
            pixmap = self._pixmap_swapped
        else:
            pixmap = self._orig_pixmap
        transform = QTransform().rotate(self._rotation * 90)
        self.setPixmap(pixmap.transformed(transform))

    @property
    def rotation(self):
        return self._rotation

    @rotation.setter
    def rotation(self, value):
        self._rotation = value
        self._resetIcon()

    @property
    def swapped(self):
        return self._swapped

    @swapped.setter
    def swapped(self, value):
        self._swapped = value
        self._resetIcon()

class SpinBoxImageView(QHBoxLayout):
    valueChanged = pyqtSignal(int)
    def __init__(self, parentView, parent, backgroundColor, foregroundColor,
                 value, height, fontSize):
        QHBoxLayout.__init__(self)
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor

        self.labelLayout = QVBoxLayout()
        self.upLabel = LabelButtons('spin-up', parentView,
                                    backgroundColor, foregroundColor,
                                    old_div(height,2), old_div(height,2))
        self.labelLayout.addWidget(self.upLabel)
        self.upLabel.clicked.connect(self.on_upLabel)

        self.downLabel = LabelButtons('spin-down', parentView,
                                      backgroundColor,
                                      foregroundColor, old_div(height,2),
                                      old_div(height,2))
        self.labelLayout.addWidget(self.downLabel)
        self.downLabel.clicked.connect(self.on_downLabel)

        self.addLayout(self.labelLayout)

        self.spinBox = DelayedSpinBox(750)
        self.spinBox.delayedValueChanged.connect(self.spinBoxValueChanged)
        self.addWidget(self.spinBox)
        self.spinBox.setToolTip("Spinbox")
        self.spinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.spinBox.setAlignment(Qt.AlignRight)
        self.spinBox.setMaximum(value)
        self.spinBox.setMaximumHeight(height)
        self.spinBox.setSuffix("/" + str(value))
        font = self.spinBox.font()
        font.setPixelSize(fontSize)
        self.spinBox.setFont(font)
        self.do_draw()

    def do_draw(self):
        r, g, b, a = self.foregroundColor.getRgb()
        rgb = "rgb({0},{1},{2})".format(r, g, b)
        sheet = TEMPLATE.format(rgb,
                                self.backgroundColor.name())
        self.spinBox.setStyleSheet(sheet)

    def spinBoxValueChanged(self, value):
        self.valueChanged.emit(value)

    def setValue(self, value):
        self.spinBox.setValueWithoutSignal(value)

    def setNewValue(self, value):
        self.spinBox.setMaximum(value)
        self.spinBox.setSuffix("/" + str(value))

    def on_upLabel(self):

        imgView = self.parent().parent().parent().parent()
        try:
            roi_3d = imgView._croppingMarkers.crop_extents_model.get_roi_3d()
            maxValue = roi_3d[1][imgView.axis]
        except:
            maxValue = imgView.posModel.parent().dataShape[imgView.axis+1]

        if self.spinBox.value() < maxValue - 1:
            self.spinBox.setValue(self.spinBox.value() + 1)

    def on_downLabel(self):

        imgView = self.parent().parent().parent().parent()
        try:
            roi_3d = imgView._croppingMarkers.crop_extents_model.get_roi_3d()
            minValue = roi_3d[0][imgView.axis]
        except:
            minValue = 0

        if self.spinBox.value() > minValue:
            self.spinBox.setValue(self.spinBox.value() - 1)


def setupFrameStyle( frame ):
    # Use this function to add a consistent frame style to all HUD
    # elements
    frame.setFrameShape( QFrame.Box )
    frame.setFrameShadow( QFrame.Raised )
    frame.setLineWidth( 2 )

class ZoomLevelIndicator(QLabel):
    def __init__(self,parent,backgroundColor,foregroundColor,font,height):
        QLabel.__init__(self,parent)
        p = self.palette()
        p.setColor(self.backgroundRole(),backgroundColor)
        p.setColor(self.foregroundRole(),foregroundColor)
        self.setPalette(p)
        self.setFont(font)
        self.setAutoFillBackground(True)
        self.setFixedHeight(height)
        self.setFrameShape( QFrame.Box )
        self.setFrameShadow( QFrame.Raised )
        #self.setLineWidth( 2 )
        self.setText(" 100 %")
        self.setToolTip("Zoom Level")
    
    def updateLevel(self,level):
        level = int(level*100)
        self.setText(" {} %".format(level))
        
    
class ImageView2DHud(QWidget):
    dockButtonClicked = pyqtSignal()
    zoomToFitButtonClicked = pyqtSignal()
    resetZoomButtonClicked = pyqtSignal()
    maximizeButtonClicked = pyqtSignal()
    rotLeftButtonClicked = pyqtSignal()
    rotRightButtonClicked = pyqtSignal()
    swapAxesButtonClicked = pyqtSignal()
    exportButtonClicked = pyqtSignal()
    def __init__(self, parent ):
        QWidget.__init__(self, parent)

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0,4,0,0)
        self.layout.setSpacing(0)

        self.buttons = {}

    def _add_button(self, name, handler):
        button = LabelButtons(
            name,
            self.parent(),
            self.backgroundColor,
            self.foregroundColor,
            self.labelsWidth,
            self.labelsheight)
        self.buttons[name] = button
        button.clicked.connect(handler)
        setupFrameStyle(button)
        self.layout.addWidget(button)
        self.layout.addSpacing(4)

    def createImageView2DHud(self, axis, value, backgroundColor,
                             foregroundColor):
        self.axis = axis
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor
        self.labelsWidth = 20
        self.labelsheight = 20

        self.layout.addSpacing(4)
        fontsize = 12

        self.axisLabel = self.createAxisLabel()
        self.sliceSelector = SpinBoxImageView(self.parent(),
                                              self,
                                              backgroundColor,
                                              foregroundColor,
                                              value,
                                              self.labelsheight, fontsize)

        self.buttons['slice'] = self.sliceSelector

        # Add left-hand items into a sub-layout so we can draw a frame
        # around them
        leftHudLayout = QHBoxLayout()
        leftHudLayout.setContentsMargins(0,0,0,0)
        leftHudLayout.setSpacing(0)
        leftHudLayout.addWidget( self.axisLabel )
        leftHudLayout.addSpacing(1)
        leftHudLayout.addLayout(self.sliceSelector)

        leftHudFrame = QFrame()
        leftHudFrame.setLayout( leftHudLayout )
        setupFrameStyle( leftHudFrame )
        self.leftHudFrame = leftHudFrame

        self.layout.addWidget( leftHudFrame )

        self.layout.addSpacing(12)

        for name, handler in [('rotate-left', self.on_rotLeftButton),
                              ('swap-axes', self.on_swapAxesButton),
                              ('rotate-right', self.on_rotRightButton)]:
            self._add_button(name, handler)

        self.layout.addStretch()
        
        self.zoomLevelIndicator = ZoomLevelIndicator(self.parent(),
                                backgroundColor,
                                foregroundColor,
                                self.sliceSelector.spinBox.font(),
                                self.buttons["rotate-left"].sizeHint().height())

        self.buttons["zoomlevel"] = self.zoomLevelIndicator
        self.layout.addWidget(self.zoomLevelIndicator)
        self.layout.addSpacing(4)
        
        for name, handler in [('export', self.on_exportButton),
                              ('zoom-to-fit', self.on_zoomToFit),
                              ('reset-zoom', self.on_resetZoom),
                              ('undock', self.on_dockButton),
                              ('maximize', self.on_maxButton)]:
            self._add_button(name, handler)
        
        # some other classes access these members directly.
        self.sliceSelector = self.buttons['slice']
        self.dockButton = self.buttons['undock']
        self.maxButton = self.buttons['maximize']

    def set3DButtonsVisible(self, visible):
        self.leftHudFrame.setVisible( visible )
        self.dockButton.setVisible( visible )
        self.maxButton.setVisible( visible )

    def setMaximum(self, v):
        self.sliceSelector.setNewValue(v)

    def on_dockButton(self):
        self.dockButtonClicked.emit()
    
    def on_zoomToFit(self):
        self.zoomToFitButtonClicked.emit()
    
    def on_exportButton(self):
        self.exportButtonClicked.emit()
    
    def on_resetZoom(self):
        self.resetZoomButtonClicked.emit()
    
    def on_maxButton(self):
        self.maximizeButtonClicked.emit()

    def on_rotLeftButton(self):
        self.rotLeftButtonClicked.emit()

    def on_rotRightButton(self):
        self.rotRightButtonClicked.emit()

    def on_swapAxesButton(self):
        self.swapAxesButtonClicked.emit()

    def createAxisLabel(self):
        axisLabel = QLabel()
        axisLabel.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        pixmap = self.createAxisLabelPixmap()
        axisLabel.setPixmap(pixmap)
        return axisLabel

    def createAxisLabelPixmap(self):
        pixmap = QPixmap(250, 250)
        pixmap.fill(self.backgroundColor)
        painter = QPainter()
        painter.begin(pixmap)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(250-30)
        path = QPainterPath()
        path.addText(QPointF(50, 250-50), font, self.axis)
        brush = QBrush(self.foregroundColor)
        painter.setBrush(brush)
        painter.drawPath(path)
        painter.setFont(font)
        painter.end()
        pixmap = pixmap.scaled(QSize(self.labelsWidth,
                                     self.labelsheight),
                               Qt.KeepAspectRatio,
                               Qt.SmoothTransformation)
        return pixmap

    def setAxes(self, rotation, swapped):
        self.buttons["swap-axes"].rotation = rotation
        self.buttons["swap-axes"].swapped = swapped

def _get_pos_widget(name, backgroundColor, foregroundColor):
    label = QLabel()
    label.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    pixmap = QPixmap(25*10, 25*10)
    pixmap.fill(backgroundColor)
    painter = QPainter()
    painter.begin(pixmap)
    pen = QPen(foregroundColor)
    painter.setPen(pen)
    painter.setRenderHint(QPainter.Antialiasing)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(25*10-30)
    path = QPainterPath()
    path.addText(QPointF(50, 25*10-50), font, name)
    brush = QBrush(foregroundColor)
    painter.setBrush(brush)
    painter.drawPath(path)
    painter.setFont(font)
    painter.end()
    pixmap = pixmap.scaled(QSize(20,20),
                           Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    label.setPixmap(pixmap)

    spinbox = DelayedSpinBox(750)
    spinbox.setAlignment(Qt.AlignCenter)
    spinbox.setToolTip("{0} Spin Box".format(name))
    spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
    spinbox.setMaximumHeight(20)
    font = spinbox.font()
    font.setPixelSize(14)
    spinbox.setFont(font)
    sheet = TEMPLATE.format(foregroundColor.name(),
                            backgroundColor.name())
    spinbox.setStyleSheet(sheet)
    return label, spinbox


class QuadStatusBar(QHBoxLayout):
    positionChanged = pyqtSignal(int, int, int) # x,y,z
    
    def __init__(self, parent=None ):
        QHBoxLayout.__init__(self, parent)
        self.setContentsMargins(0,4,0,0)
        self.setSpacing(0)
        self.timeControlFontSize = 12

    def showXYCoordinates(self):
        self.zLabel.setHidden(True)
        self.zSpinBox.setHidden(True)
        
    def showXYZCoordinates(self):
        self.zLabel.setHidden(False)
        self.zSpinBox.setHidden(False)
    
    def hideTimeSlider(self,flag):
        self.timeSlider.setHidden(flag)
        self.timeEndButton.setHidden(flag)
        self.timeStartButton.setHidden(flag)

    def setToolTipTimeButtonsCrop(self,croppingFlag=False):
        if croppingFlag==True:
            self.timeStartButton.setToolTip("Set the time coordinate to the beginning of the current crop.")
            self.timeEndButton.setToolTip("Set the time coordinate to the end of the current crop.")
            self.timePreviousButton.setToolTip("Set the time coordinate to the previous time frame.")
            self.timeNextButton.setToolTip("Set the time coordinate to the next time frame.")
        else:
            self.timeStartButton.setToolTip("Set the time coordinate to the beginning of the current dataset.")
            self.timeEndButton.setToolTip("Set the time coordinate to the end of the current dataset.")
            self.timePreviousButton.setToolTip("Set the time coordinate to the previous time frame.")
            self.timeNextButton.setToolTip("Set the time coordinate to the next time frame.")

    def setToolTipTimeSliderCrop(self,croppingFlag=False):
        if croppingFlag==True:
            self.timeSlider.setToolTip("Choose the time coordinate of the current crop.")
        else:
            self.timeSlider.setToolTip("Choose the time coordinate of the current dataset.")

    def createQuadViewStatusBar(self,
                                xbackgroundColor, xforegroundColor,
                                ybackgroundColor, yforegroundColor,
                                zbackgroundColor, zforegroundColor):
        self.xLabel, self.xSpinBox = _get_pos_widget('X',
                                                     xbackgroundColor,
                                                     xforegroundColor)
        self.yLabel, self.ySpinBox = _get_pos_widget('Y',
                                                     ybackgroundColor,
                                                     yforegroundColor)
        self.zLabel, self.zSpinBox = _get_pos_widget('Z',
                                                     zbackgroundColor,
                                                     zforegroundColor)
        
        self.xSpinBox.delayedValueChanged.connect( partial(self._handlePositionBoxValueChanged, 'x') )
        self.ySpinBox.delayedValueChanged.connect( partial(self._handlePositionBoxValueChanged, 'y') )
        self.zSpinBox.delayedValueChanged.connect( partial(self._handlePositionBoxValueChanged, 'z') )

        self.addWidget(self.xLabel)
        self.addWidget(self.xSpinBox)
        self.addWidget(self.yLabel)
        self.addWidget(self.ySpinBox)
        self.addWidget(self.zLabel)
        self.addWidget(self.zSpinBox)

        self.addSpacing(10)

        self.busyIndicator = QProgressBar()
        self.busyIndicator.setMaximumWidth(200)
        self.busyIndicator.setMaximum(0)
        self.busyIndicator.setMinimum(0)
        self.busyIndicator.setVisible(False)
        self.busyIndicator.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.addWidget( self.busyIndicator )
        self.setStretchFactor(self.busyIndicator, 1)

        self.addStretch()
        self.addSpacing(10)

        self.positionCheckBox = QCheckBox()
        self.positionCheckBox.setChecked(False)
        self.positionCheckBox.setCheckable(True)
        self.positionCheckBox.setText("Position")
        self.addWidget(self.positionCheckBox)

        self.addSpacing(20)

        self.timeSpinBox = DelayedSpinBox(750)

        self.timeStartButton = QPushButton("|<")
        self.addWidget(self.timeStartButton)
        self.timeStartButton.clicked.connect(self._onTimeStartButtonClicked)

        self.timePreviousButton = QPushButton("<")
        self.addWidget(self.timePreviousButton)
        self.timePreviousButton.clicked.connect(self._onTimePreviousButtonClicked)
        self.timePreviousButton.setFixedWidth(4*self.timeControlFontSize)

        self.timeSlider = QSlider(Qt.Horizontal)
        self.timeSlider.setMinimumWidth(10)
        self.timeSlider.setMaximumWidth(200)
        self.setToolTipTimeSliderCrop()
        self.addWidget(self.timeSlider)
        self.timeSlider.valueChanged.connect(self._onTimeSliderChanged)

        self.timeNextButton = QPushButton(">")
        self.addWidget(self.timeNextButton)
        self.timeNextButton.clicked.connect(self._onTimeNextButtonClicked)
        self.timeNextButton.setFixedWidth(4*self.timeControlFontSize)

        self.timeEndButton = QPushButton(">|")
        self.timeEndButton.setFixedWidth(4*self.timeControlFontSize)

        self.timeStartButton.setFixedWidth(4*self.timeControlFontSize)
        
        self.setToolTipTimeButtonsCrop()
        self.addWidget(self.timeEndButton)
        self.timeEndButton.clicked.connect(self._onTimeEndButtonClicked)

        self.timeLabel = QLabel("       Time:")
        self.addWidget(self.timeLabel)

        timeControlFont = self.timeSpinBox.font()
        if self.timeControlFontSize > timeControlFont.pointSize():
            timeControlFont.setPixelSize(2*self.timeControlFontSize)
            self.timeStartButton.setFont(timeControlFont)
            self.timeEndButton.setFont(timeControlFont)
            self.timeLabel.setFont(timeControlFont)
            self.timeSpinBox.setFont(timeControlFont)

        self.addWidget(self.timeSpinBox)
        self.timeSpinBox.delayedValueChanged.connect(self._onTimeSpinBoxChanged)

    def _onTimeStartButtonClicked(self):
        self.timeSpinBox.setValue(self.parent().parent().parent().editor.cropModel.get_roi_t()[0])

    def _onTimeEndButtonClicked(self):
        self.timeSpinBox.setValue(self.parent().parent().parent().editor.cropModel.get_roi_t()[1])

    def _onTimePreviousButtonClicked(self):
        self.timeSpinBox.setValue(self.timeSpinBox.value()-1)

    def _onTimeNextButtonClicked(self):
        self.timeSpinBox.setValue(self.timeSpinBox.value()+1)

    def _onTimeSpinBoxChanged(self):
        editor = self.parent().parent().parent().editor
        cropModel = editor.cropModel
        minValueT = cropModel.get_roi_t()[0]
        maxValueT = cropModel.get_roi_t()[1]

        if cropModel.get_scroll_time_outside_crop():
            if minValueT > self.timeSpinBox.value() or maxValueT < self.timeSpinBox.value():
                for imgView in editor.imageViews:
                    imgView._croppingMarkers._shading_item.set_paint_full_frame(True)
            else:
                for imgView in editor.imageViews:
                    imgView._croppingMarkers._shading_item.set_paint_full_frame(False)
            self.timeSlider.setValue(self.timeSpinBox.value())
        else:
            for imgView in editor.imageViews:
                imgView._croppingMarkers._shading_item.set_paint_full_frame(False)
            if minValueT > self.timeSpinBox.value():
                self.timeSlider.setValue(minValueT)
            elif maxValueT < self.timeSpinBox.value():
                self.timeSlider.setValue(maxValueT)
            elif minValueT <= self.timeSpinBox.value() and self.timeSpinBox.value() <= maxValueT:
                self.timeSlider.setValue(self.timeSpinBox.value())

    def _onTimeSliderChanged(self):
        cropModel = self.parent().parent().parent().editor.cropModel
        minValueT = cropModel.get_roi_t()[0]
        maxValueT = cropModel.get_roi_t()[1]

        if cropModel.get_scroll_time_outside_crop():
            self.timeSpinBox.setValue(self.timeSlider.value())
        else:
            if minValueT > self.timeSlider.value():
                self.timeSpinBox.setValue(minValueT)
                self.timeSlider.setValue(minValueT)
            elif self.timeSlider.value() > maxValueT:
                self.timeSpinBox.setValue(maxValueT)
                self.timeSlider.setValue(maxValueT)
            elif minValueT <= self.timeSlider.value() and self.timeSlider.value() <= maxValueT:
                self.timeSpinBox.setValue(self.timeSlider.value())

    def _handlePositionBoxValueChanged(self, axis, value):
        new_position = [self.xSpinBox.value(), self.ySpinBox.value(), self.zSpinBox.value()]
        changed_axis = ord(axis) - ord('x')
        new_position[changed_axis] = value
        self.positionChanged.emit(*new_position)

    def updateShape5D(self, shape5D):
        self.timeSpinBox.setMaximum(shape5D[0]-1)
        self.xSpinBox.setMaximum(shape5D[1]-1)
        self.ySpinBox.setMaximum(shape5D[2]-1)
        self.zSpinBox.setMaximum(shape5D[3]-1)

    def updateShape5Dcropped(self, shape5DcropMin, shape5Dmax):
        self.timeSpinBox.setMaximum(shape5Dmax[0]-1)
        self.xSpinBox.setMaximum(shape5Dmax[1]-1)
        self.ySpinBox.setMaximum(shape5Dmax[2]-1)
        self.zSpinBox.setMaximum(shape5Dmax[3]-1)
        self.timeSlider.setMaximum(shape5Dmax[0]-1)

        self.timeSpinBox.setValue(shape5DcropMin[0])
        self.xSpinBox.setValue(shape5DcropMin[1])
        self.ySpinBox.setValue(shape5DcropMin[2])
        self.zSpinBox.setValue(shape5DcropMin[3])
        self.timeSlider.setValue(shape5DcropMin[0])

    def setMouseCoords(self, x, y, z):
        self.xSpinBox.setValueWithoutSignal(x)
        self.ySpinBox.setValueWithoutSignal(y)
        self.zSpinBox.setValueWithoutSignal(z)


if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QDialog, QApplication
    #make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)

    app = QApplication(sys.argv)
    widget = QDialog()
    ex1 = ImageView2DHud(widget)
    ex1.createImageView2DHud("X", 12, QColor("red"), QColor("white"))
    widget.show()
    widget.raise_()
    app.exec_()

from PyQt4.QtCore import pyqtSignal, Qt, QPointF, QSize

from PyQt4.QtGui import QLabel, QPen, QPainter, QPixmap, QColor, QHBoxLayout, QVBoxLayout, \
                        QFont, QPainterPath, QBrush, QPolygonF, QSpinBox, QAbstractSpinBox, \
                        QCheckBox, QWidget, QPalette, QFrame, QIcon, QTransform, QImage
import sys, random
import numpy, qimage2ndarray
import icons


def _load_icon(filename, backgroundColor, width, height):
    foreground = QPixmap()
    foreground.load(filename)

    pixmap = QPixmap(foreground.size())

    h, s, v, a = backgroundColor.getHsv()
    s = 70
    backgroundColor = QColor.fromHsv(h, s, v, a)

    pixmap.fill(backgroundColor)

    painter = QPainter()
    painter.begin(pixmap)
    painter.drawPixmap(QPointF(0, 0), foreground)
    painter.end()

    pixmap = pixmap.scaled(QSize(width, height),
                           Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    return pixmap


# TODO: replace with icon files
def _draw_icon(shapes, backgroundColor, foregroundColor, opacity, width, height):
    pixmap = QPixmap(250, 250)
    pixmap.fill(backgroundColor)
    painter = QPainter()
    painter.begin(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setOpacity(opacity)
    pen = QPen(foregroundColor)
    pen.setWidth(30)
    painter.setPen(pen)
    for shape, args in shapes:
        if shape == "line":
            painter.drawLine(*args)
        elif shape == "rect":
            painter.drawRect(*args)
        elif shape == "polygon":
            points = QPolygonF()
            for point in args:
                points.append(QPointF(*point))
            painter.drawPolygon(points)
    painter.end()
    pixmap = pixmap.scaled(QSize(width, height),
                           Qt.KeepAspectRatio,
                           Qt.SmoothTransformation)
    return pixmap


class LabelButtons(QLabel):
    clicked = pyqtSignal()
    def __init__(self, parentView, backgroundColor, foregroundColor, width, height):
        QLabel.__init__(self)

        parentView.installEventFilter(self)

        self.setColors(backgroundColor, foregroundColor)
        self.setPixmapSize(width, height)

    def setColors(self, backgroundColor, foregroundColor):
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor

    def setPixmapSize(self, width, height):
        self.pixmapWidth = width
        self.pixmapHeight = height

    def setUndockIcon(self, opacity=0.6):
        self.buttonStyle = "undock"
        self.setToolTip("Undock")
        shapes = [("line", (70.0, 170.0, 190.0, 60.0)),
                  ("line", (200.0, 140.0, 200.0, 50.0)),
                  ("line", (110.0, 50.0, 200.0, 50.0))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)

    def setDockIcon(self, opacity=0.6):
        self.buttonStyle = "dock"
        self.setToolTip("Dock")
        shapes = [("line", (70.0, 170.0, 190.0, 60.0)),
                  ("line", (60.0, 90.0, 60.0, 180.0)),
                  ("line", (150.0, 180.0, 60.0, 180.0))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)

    def setMaximizeIcon(self, opacity=0.6):
        self.buttonStyle = "max"
        self.setToolTip("maximize")
        shapes = [("rect", (50.0, 50.0, 150.0, 150.0))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)

    def setMinimizeIcon(self, opacity=0.6):
        shapes = [("rect", (50.0, 50.0, 150.0, 150.0)),
                  ("line", (50.0, 125.0, 200.0, 125.0)),
                  ("line", (125.0, 200.0, 125.0, 50.0))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)

    def setRotLeftIcon(self, opacity=0.6):
        self.buttonStyle = "rotleft"
        self.setToolTip("Rotate left")
        pixmap = _load_icon(':icons/icons/rotate-right.png',
                              self.backgroundColor,
                              self.pixmapWidth,
                              self.pixmapHeight)
        pixmap = pixmap.transformed(QTransform().scale(-1, 1))
        self.setPixmap(pixmap)

    def setRotRightIcon(self, opacity=0.6):
        self.buttonStyle = "rotright"
        self.setToolTip("Rotate right")
        pixmap = _load_icon(':icons/icons/rotate-right.png',
                              self.backgroundColor,
                              self.pixmapWidth,
                              self.pixmapHeight)
        self.setPixmap(pixmap)

    def setSwapAxesIcon(self, opacity=0.6):
        self.buttonStyle = "swapaxes"
        self.setToolTip("Swap axes")
        pixmap = _load_icon(':icons/icons/swap-axes.png',
                              self.backgroundColor,
                              self.pixmapWidth,
                              self.pixmapHeight)
        self.setPixmap(pixmap)

    def setSpinBoxUpIcon(self, opacity=0.6):
        self.buttonStyle = "spinUp"
        self.setToolTip("+ 1")
        shapes = [("polygon", ((125.0, 50.0),
                               (200.0, 180.0),
                               (50.0, 180.0)))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)


    def setSpinBoxDownIcon(self, opacity=0.6):
        self.buttonStyle = "spinDown"
        self.setToolTip("- 1")
        shapes = [("polygon", ((125.0, 200.0),
                               (200.0, 70.0),
                               (50.0, 70.0)))]
        pixmap = _draw_icon(shapes,
                            self.backgroundColor,
                            self.foregroundColor,
                            opacity,
                            self.pixmapWidth,
                            self.pixmapHeight)
        self.setPixmap(pixmap)


    def changeOpacity(self, opacity):
        if self.buttonStyle == "undock":
            self.setUndockIcon(opacity)
        elif self.buttonStyle == "dock":
            self.setDockIcon(opacity)
        elif self.buttonStyle == "min":
            self.setMinimizeIcon(opacity)
        elif self.buttonStyle == "max":
            self.setMaximizeIcon(opacity)
        elif self.buttonStyle == "rotleft":
            self.setRotLeftIcon(opacity)
        elif self.buttonStyle == "rotright":
            self.setRotRightIcon(opacity)
        elif self.buttonStyle == "swapaxes":
            self.setSwapAxesIcon(opacity)
        elif self.buttonStyle == "spinUp":
            self.setSpinBoxUpIcon(opacity)
        elif self.buttonStyle == "spinDown":
            self.setSpinBoxDownIcon(opacity)

    def mouseReleaseEvent(self, event):
        if self.underMouse():
            self.clicked.emit()

    def eventFilter(self, watched, event):
        # Block the parent view from seeing events while we've got the mouse.
        if self.underMouse():
            return True
        return False

class SpinBoxImageView(QHBoxLayout):
    valueChanged = pyqtSignal(int)
    def __init__(self, parentView, backgroundColor, foregroundColor, value, height, fontSize):
        QHBoxLayout.__init__(self)
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor

        self.labelLayout = QVBoxLayout()
        self.upLabel = LabelButtons(parentView, backgroundColor, foregroundColor, height/2, height/2)
        self.labelLayout.addWidget(self.upLabel)
        self.upLabel.setSpinBoxUpIcon()
        self.upLabel.clicked.connect(self.on_upLabel)

        self.downLabel = LabelButtons(parentView, backgroundColor, foregroundColor, height/2, height/2)
        self.labelLayout.addWidget(self.downLabel)
        self.downLabel.setSpinBoxDownIcon()
        self.downLabel.clicked.connect(self.on_downLabel)

        self.addLayout(self.labelLayout)


        self.spinBox = QSpinBox()
        self.spinBox.valueChanged.connect(self.spinBoxValueChanged)
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
        rgb = foregroundColor.getRgb()
        rgba_string = "rgba("+str(rgb[0])+","+str(rgb[1])+","+str(rgb[2])+","+str(0.6*100)+"%)"
        self.spinBox.setStyleSheet("QSpinBox { color: " + rgba_string + "; font: bold; background-color: " + str(backgroundColor.name()) + "; border:0;}")

    def changeOpacity(self, opacity):
        rgb = self.foregroundColor.getRgb()
        rgba_string = "rgba("+str(rgb[0])+","+str(rgb[1])+","+str(rgb[2])+","+str(opacity*100)+"%)"
        self.spinBox.setStyleSheet("QSpinBox { color: " + rgba_string + "; font: bold; background-color: " + str(self.backgroundColor.name()) + "; border:0;}")
        self.upLabel.changeOpacity(opacity)
        self.downLabel.changeOpacity(opacity)

    def spinBoxValueChanged(self, value):
        self.valueChanged.emit(value)

    def setValue(self, value):
        self.spinBox.setValue(value)

    def setNewValue(self, value):
        self.spinBox.setMaximum(value)
        self.spinBox.setSuffix("/" + str(value))

    def on_upLabel(self):
        self.spinBox.setValue(self.spinBox.value() + 1)

    def on_downLabel(self):
        self.spinBox.setValue(self.spinBox.value() - 1)

class ImageView2DHud(QWidget):
    dockButtonClicked = pyqtSignal()
    maximizeButtonClicked = pyqtSignal()
    rotLeftButtonClicked = pyqtSignal()
    rotRightButtonClicked = pyqtSignal()
    swapAxesButtonClicked = pyqtSignal()
    def __init__(self, parent ):
        QWidget.__init__(self, parent)

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)
        self.layout.setContentsMargins(0,4,0,0)
        self.layout.setSpacing(0)

        self.buttons = []

    def createImageView2DHud(self, axis, value, backgroundColor, foregroundColor):
        self.axis = axis
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor
        self.labelsWidth = 20
        self.labelsheight = 20

        self.layout.addSpacing(4)

        self.axisLabel = self.createAxisLabel()
        self.sliceSelector = SpinBoxImageView(self.parent(), backgroundColor, foregroundColor, value, self.labelsheight, 12)

        self.buttons.append(self.sliceSelector)

        # Add left-hand items into a sub-layout so we can draw a frame around them
        leftHudLayout = QHBoxLayout()
        leftHudLayout.setContentsMargins(0,0,0,0)
        leftHudLayout.setSpacing(0)
        leftHudLayout.addWidget( self.axisLabel )
        leftHudLayout.addSpacing(1)
        leftHudLayout.addLayout(self.sliceSelector)

        def setupFrameStyle( frame ):
            # Use this function to add a consistent frame style to all HUD elements
            frame.setFrameShape( QFrame.Box )
            frame.setFrameShadow( QFrame.Raised )
            frame.setLineWidth( 2 )

        leftHudFrame = QFrame()
        leftHudFrame.setLayout( leftHudLayout )
        setupFrameStyle( leftHudFrame )

        self.layout.addWidget( leftHudFrame )

        self.layout.addSpacing(12)

        rotLeftButton = LabelButtons(self.parent(), backgroundColor, foregroundColor, self.labelsWidth, self.labelsheight)
        self.buttons.append(rotLeftButton)
        rotLeftButton.clicked.connect(self.on_rotLeftButton)
        rotLeftButton.setRotLeftIcon()
        setupFrameStyle( rotLeftButton )
        self.layout.addWidget(rotLeftButton)

        self.layout.addSpacing(4)

        swapAxesButton = LabelButtons(self.parent(), backgroundColor, foregroundColor, self.labelsWidth, self.labelsheight)
        self.buttons.append(swapAxesButton)
        swapAxesButton.clicked.connect(self.on_swapAxesButton)
        swapAxesButton.setSwapAxesIcon()
        setupFrameStyle( swapAxesButton )
        self.layout.addWidget(swapAxesButton)

        self.layout.addSpacing(4)

        rotRightButton = LabelButtons(self.parent(), backgroundColor, foregroundColor, self.labelsWidth, self.labelsheight)
        self.buttons.append(rotRightButton)
        rotRightButton.clicked.connect(self.on_rotRightButton)
        rotRightButton.setRotRightIcon()
        setupFrameStyle( rotRightButton )
        self.layout.addWidget(rotRightButton)

        self.layout.addStretch()

        dockButton = LabelButtons(self.parent(), backgroundColor, foregroundColor, self.labelsWidth, self.labelsheight)
        self.buttons.append(dockButton)
        dockButton.clicked.connect(self.on_dockButton)
        dockButton.setUndockIcon()
        setupFrameStyle( dockButton )
        self.layout.addWidget(dockButton)
        self.layout.addSpacing(4)

        maxButton = LabelButtons(self.parent(), backgroundColor, foregroundColor, self.labelsWidth, self.labelsheight)
        self.buttons.append(maxButton)
        maxButton.clicked.connect(self.on_maxButton)
        maxButton.setMaximizeIcon()
        setupFrameStyle(maxButton)
        self.layout.addWidget(maxButton)
        self.layout.addSpacing(4)

    def setMaximum(self, v):
        self.sliceSelector.setNewValue(v)

    def on_dockButton(self):
        self.dockButtonClicked.emit()

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

    def createAxisLabelPixmap(self, opacity=0.6):
        pixmap = QPixmap(250, 250)
        pixmap.fill(self.backgroundColor)
        painter = QPainter()
        painter.begin(pixmap)
        painter.setOpacity(opacity)
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
        pixmap = pixmap.scaled(QSize(self.labelsWidth,self.labelsheight),Qt.KeepAspectRatio, Qt.SmoothTransformation)
        return pixmap

    def changeOpacity(self, opacity):
        self.axisLabel.setPixmap(self.createAxisLabelPixmap(opacity))
        for b in self.buttons:
            b.changeOpacity(opacity)


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
    pixmap = pixmap.scaled(QSize(20,20),Qt.KeepAspectRatio, Qt.SmoothTransformation)
    label.setPixmap(pixmap)

    spinbox = QSpinBox()
    spinbox.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    spinbox.setEnabled(False)
    spinbox.setAlignment(Qt.AlignCenter)
    spinbox.setToolTip("{0} Spin Box".format(name))
    spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
    spinbox.setMaximumHeight(20)
    spinbox.setMaximum(9999)
    font = spinbox.font()
    font.setPixelSize(14)
    spinbox.setFont(font)
    spinbox.setStyleSheet("QSpinBox { color: " + str(foregroundColor.name()) + "; font: bold; background-color: " + str(backgroundColor.name()) + "; border:0;}")
    return label, spinbox


class QuadStatusBar(QHBoxLayout):
    def __init__(self, parent=None ):
        QHBoxLayout.__init__(self, parent)
        self.setContentsMargins(0,4,0,0)
        self.setSpacing(0)

    def createQuadViewStatusBar(self,
                                xbackgroundColor,
                                xforegroundColor,
                                ybackgroundColor,
                                yforegroundColor,
                                zbackgroundColor,
                                zforegroundColor,
                                graybackgroundColor,
                                grayforegroundColor):

        self.xLabel, self.xSpinBox = _get_pos_widget('X', xbackgroundColor, xforegroundColor)
        self.addWidget(self.xLabel)
        self.addWidget(self.xSpinBox)

        self.yLabel, self.ySpinBox = _get_pos_widget('Y', ybackgroundColor, yforegroundColor)
        self.addWidget(self.yLabel)
        self.addWidget(self.ySpinBox)

        self.zLabel, self.zSpinBox = _get_pos_widget('Z', zbackgroundColor, zforegroundColor)
        self.addWidget(self.zLabel)
        self.addWidget(self.zSpinBox)

        self.addSpacing(4)

        self.grayScaleLabel = QLabel()
        self.grayScaleLabel.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.addWidget(self.grayScaleLabel)

        self.addStretch()

        self.positionCheckBox = QCheckBox()
        self.positionCheckBox.setChecked(True)
        self.positionCheckBox.setCheckable(True)
        self.positionCheckBox.setText("Position")
        self.addWidget(self.positionCheckBox)

        self.addSpacing(20)

        self.channelLabel = QLabel("Channel:")
        self.addWidget(self.channelLabel)

        self.channelSpinBox = QSpinBox()
        self.addWidget(self.channelSpinBox)
        self.addSpacing(20)

        self.timeLabel = QLabel("Time:")
        self.addWidget(self.timeLabel)

        self.timeSpinBox = QSpinBox()
        self.addWidget(self.timeSpinBox)

    def setMouseCoords(self, x, y, z):
        self.xSpinBox.setValue(x)
        self.ySpinBox.setValue(y)
        self.zSpinBox.setValue(z)


if __name__ == "__main__":
    from PyQt4.QtGui import QDialog, QApplication
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

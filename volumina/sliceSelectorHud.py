from PyQt4.QtCore import pyqtSignal, Qt, QPointF, QSize

from PyQt4.QtGui import QLabel, QPen, QPainter, QPixmap, QColor, QHBoxLayout, QVBoxLayout, \
                        QFont, QPainterPath, QBrush, QPolygonF, QSpinBox, QAbstractSpinBox, \
                        QCheckBox, QWidget, QPalette, QFrame, QTransform
import sys, random
import numpy, qimage2ndarray
import volumina.icons_rc

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
        parentView.installEventFilter(self)
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
        'undock' : (':icons/icons/undock.png', "Undock"),
        'dock' : (':icons/icons/dock.png', "Dock"),
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

    def mouseReleaseEvent(self, event):
        if self.underMouse():
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

    def eventFilter(self, watched, event):
        # Block the parent view from seeing events while we've got the mouse.
        if self.underMouse():
            return True
        return False

class SpinBoxImageView(QHBoxLayout):
    valueChanged = pyqtSignal(int)
    def __init__(self, parentView, backgroundColor, foregroundColor,
                 value, height, fontSize):
        QHBoxLayout.__init__(self)
        self.backgroundColor = backgroundColor
        self.foregroundColor = foregroundColor

        self.labelLayout = QVBoxLayout()
        self.upLabel = LabelButtons('spin-up', parentView,
                                    backgroundColor, foregroundColor,
                                    height/2, height/2)
        self.labelLayout.addWidget(self.upLabel)
        self.upLabel.clicked.connect(self.on_upLabel)

        self.downLabel = LabelButtons('spin-down', parentView,
                                      backgroundColor,
                                      foregroundColor, height/2,
                                      height/2)
        self.labelLayout.addWidget(self.downLabel)
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
        self.spinBox.setValue(value)

    def setNewValue(self, value):
        self.spinBox.setMaximum(value)
        self.spinBox.setSuffix("/" + str(value))

    def on_upLabel(self):
        self.spinBox.setValue(self.spinBox.value() + 1)

    def on_downLabel(self):
        self.spinBox.setValue(self.spinBox.value() - 1)


def setupFrameStyle( frame ):
    # Use this function to add a consistent frame style to all HUD
    # elements
    frame.setFrameShape( QFrame.Box )
    frame.setFrameShadow( QFrame.Raised )
    frame.setLineWidth( 2 )


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

        self.axisLabel = self.createAxisLabel()
        self.sliceSelector = SpinBoxImageView(self.parent(),
                                              backgroundColor,
                                              foregroundColor,
                                              value,
                                              self.labelsheight, 12)

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

        self.layout.addWidget( leftHudFrame )

        self.layout.addSpacing(12)

        for name, handler in [('rotate-left', self.on_rotLeftButton),
                              ('swap-axes', self.on_swapAxesButton),
                              ('rotate-right', self.on_rotRightButton)]:
            self._add_button(name, handler)

        self.layout.addStretch()

        for name, handler in [('undock', self.on_dockButton),
                              ('maximize', self.on_maxButton)]:
            self._add_button(name, handler)

        # some other classes access these members directly.
        self.sliceSelector = self.buttons['slice']
        self.dockButton = self.buttons['undock']
        self.maxButton = self.buttons['maximize']

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
    sheet = TEMPLATE.format(foregroundColor.name(),
                            backgroundColor.name())
    spinbox.setStyleSheet(sheet)
    return label, spinbox


class QuadStatusBar(QHBoxLayout):
    def __init__(self, parent=None ):
        QHBoxLayout.__init__(self, parent)
        self.setContentsMargins(0,4,0,0)
        self.setSpacing(0)

    def showXYCoordinates(self):
        self.zLabel.setHidden(True)
        self.zSpinBox.setHidden(True)
        
    def showXYZCoordinates(self):
        self.zLabel.setHidden(False)
        self.zSpinBox.setHidden(False)
    
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

        self.addWidget(self.xLabel)
        self.addWidget(self.xSpinBox)
        self.addWidget(self.yLabel)
        self.addWidget(self.ySpinBox)
        self.addWidget(self.zLabel)
        self.addWidget(self.zSpinBox)

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

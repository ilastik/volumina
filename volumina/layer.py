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
from builtins import range
import colorsys
import numpy

from PyQt5.QtCore import Qt, QObject, pyqtSignal, QTimer
from PyQt5.QtGui import QColor, QPen

from volumina.interpreter import ClickInterpreter
from volumina.pixelpipeline.slicesources import PlanarSliceSource
from volumina.pixelpipeline.datasources import MinMaxSource, ConstantSource
from volumina.pixelpipeline.interface import DataSourceABC
from volumina.pixelpipeline import imagesources as imsrc

from volumina.utility import SignalingDict

from functools import partial
from collections import defaultdict

import sys
from numbers import Number
from typing import Tuple


class Layer(QObject):
    """
    properties:
    datasources -- list of ArraySourceABC; read-only
    visible -- boolean
    opacity -- float; range 0.0 - 1.0
    name -- str
    numberOfChannels -- int
    layerId -- any object that can uniquely identify this layer within a layerstack (by default, same as name)
    """

    """changed is emitted whenever one of the more specialized
    somethingChanged signals is emitted."""
    changed = pyqtSignal()

    visibleChanged = pyqtSignal(bool)
    opacityChanged = pyqtSignal(float)
    nameChanged = pyqtSignal(object)
    channelChanged = pyqtSignal(int)
    numberOfChannelsChanged = pyqtSignal(int)

    @property
    def normalize(self):
        return None

    @property
    def visible(self):
        return self._visible

    @visible.setter
    def visible(self, value):
        if value != self._visible and self._allowToggleVisible:
            self._visible = value
            self.visibleChanged.emit(value)

    def toggleVisible(self):
        """Convenience function."""
        if self._allowToggleVisible:
            self.visible = not self._visible

    @property
    def opacity(self):
        return self._opacity

    @opacity.setter
    def opacity(self, value):
        if value != self._opacity:
            self._opacity = value
            self.opacityChanged.emit(value)

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, n):
        assert isinstance(n, str)
        if self._name != n:
            self._name = n
            self.nameChanged.emit(n)

    @property
    def numberOfChannels(self):
        return self._numberOfChannels

    @numberOfChannels.setter
    def numberOfChannels(self, n):
        if self._numberOfChannels == n:
            return
        if self._channel >= n and n > 0:
            self.channel = n - 1
        elif n < 1:
            raise ValueError("Layer.numberOfChannels(): should be greater or equal 1")
        self._numberOfChannels = n
        self.numberOfChannelsChanged.emit(n)

    @property
    def channel(self):
        return self._channel

    @channel.setter
    def channel(self, n):
        if self._channel == n:
            return
        if n < self.numberOfChannels:
            self._channel = n
        else:
            raise ValueError("Layer.channel.setter: channel value has to be less than number of channels")
        self.channelChanged.emit(self._channel)

    @property
    def datasources(self):
        return self._datasources

    @property
    def layerId(self):
        # If we have no real id, use the name
        if self._layerId is None:
            return self._name
        else:
            return self._layerId

    @layerId.setter
    def layerId(self, lid):
        self._layerId = lid

    def setActive(self, active):
        """This function is called whenever the layer is selected (active = True) or deselected (active = False)
        by the user.
        As an example, this can be used to enable a specific event interpreter when the layer is active
        and to disable it when it is not active.
        See ClickableColortableLayer for an example."""
        pass

    def toolTip(self):
        return self._toolTip

    def setToolTip(self, tip):
        self._toolTip = tip

    def createImageSource(self, data_sources):
        raise NotImplementedError

    def isDifferentEnough(self, other_layer):
        """This ugly function is here to support the updateAllLayers function in the layerViewerGui in ilastik"""
        if type(other_layer) != type(self):
            return True
        if other_layer.datasources != self.datasources:
            return True
        if other_layer.numberOfChannels != self.numberOfChannels:
            return True
        return False

    def __init__(self, datasources, direct=False):
        super(Layer, self).__init__()
        self._name = u"Unnamed Layer"
        self._visible = True
        self._opacity = 1.0
        self._datasources = datasources
        self._layerId = None
        self._numberOfChannels = 1
        self._allowToggleVisible = True
        self._channel = 0
        self.direct = direct
        self._toolTip = ""
        self._cleaned_up = False

        self._updateNumberOfChannels()
        for datasource in [_f for _f in self._datasources if _f]:
            datasource.numberOfChannelsChanged.connect(self._updateNumberOfChannels)

        self.visibleChanged.connect(self.changed)
        self.opacityChanged.connect(self.changed)
        self.nameChanged.connect(self.changed)
        self.numberOfChannelsChanged.connect(self.changed)
        self.channelChanged.connect(self.changed)

        self.contexts = []

    def _updateNumberOfChannels(self):
        # As there can be many datasources and they can all be None,
        # grab numberOfChannels for those that are defined.
        # That is, if there are any datasources.
        newchannels = []
        for i in range(len(self._datasources)):
            if self._datasources[i] is not None:
                newchannels.append(self._datasources[i].numberOfChannels)

        # If the datasources are all None or there aren't any,
        # default to 1 channel as we must have at least 1.
        if not newchannels:
            newchannels = [1]

        # Get the smallest number of channels that works for all.
        newchannels = min(newchannels)

        if newchannels != self.numberOfChannels:
            # Update property (emits signal)
            self.numberOfChannels = newchannels

    def clean_up(self):
        """
        Cleans up resources in this layer's datasources.
        Must not be called more than once.
        """
        assert not self._cleaned_up, "Bug: You're attempting to clean layer {} twice.".format(self.name)
        for src in self.datasources:
            if src is not None:
                src.clean_up()
        self._cleaned_up = True


class ClickableLayer(Layer):
    """A layer that, when being activated/selected, switches to an interpreter than can intercept
    right click events"""

    def __init__(self, datasource, editor, clickFunctor, direct=False, right=True):
        super(ClickableLayer, self).__init__([datasource], direct=direct)
        self._editor = editor
        self._clickInterpreter = ClickInterpreter(editor, self, clickFunctor, right=right)
        self._inactiveInterpreter = self._editor.eventSwitch.interpreter

    def setActive(self, active):
        if active:
            self._editor.eventSwitch.interpreter = self._clickInterpreter
        else:
            self._editor.eventSwitch.interpreter = self._inactiveInterpreter


def dtype_to_range(dsource):
    if dsource is not None:
        dtype = dsource.dtype()
    else:
        dtype = numpy.uint8

    if dtype == numpy.bool_ or dtype == bool:
        # Special hack for bool
        rng = (0, 1)
    elif issubclass(dtype, (int, int, numpy.integer)):
        rng = (0, numpy.iinfo(dtype).max)
    elif dtype == numpy.float32 or dtype == numpy.float64:
        # Is there a way to get the min and max values of the actual dataset(s)?
        # arbitrary range choice
        rng = (-4096, 4096)
    else:
        # raise error
        raise Exception("dtype_to_range: unknown dtype {}".format(dtype))
    return rng


class NormalizableLayer(Layer):
    """
    int -- datasource index
    int -- lower threshold
    int -- upper threshold
    """

    normalizeChanged = pyqtSignal()

    @property
    def normalize(self):
        return self._normalize

    def set_normalize(self, datasourceIdx, value):
        """
        value -- (nmin, nmax)
        value -- None : grabs (min, max) from the MinMaxSource
        """
        if self._datasources[datasourceIdx] is None:
            return

        if value is None:
            value = self.get_datasource_default_range(datasourceIdx)
            self._autoMinMax[datasourceIdx] = True
        else:
            self._autoMinMax[datasourceIdx] = False
        self._normalize[datasourceIdx] = value
        self.normalizeChanged.emit()

    def get_datasource_default_range(self, datasourceIdx: int) -> Tuple[Number, Number]:
        return self._datasources[datasourceIdx]._bounds

    def get_datasource_range(self, datasourceIdx: int) -> Tuple[Number, Number]:
        if isinstance(self._normalize[datasourceIdx], tuple):
            return self._normalize[datasourceIdx]
        return self.get_datasource_default_range(datasourceIdx)

    def __init__(self, datasources, normalize=None, direct=False):
        """
        datasources - a list of raw data sources
        normalize - If normalize is a tuple (dmin, dmax), the data is normalized from (dmin, dmax) to (0,255) before it is displayed.
                    If normalize=None, then (dmin, dmax) is automatically determined before normalization.
                    If normalize=False, then no normalization is applied before displaying the data.

        """
        self._normalize = []
        self._autoMinMax = []
        self._mmSources = []

        wrapped_datasources = [None] * len(datasources)

        for i, datasource in enumerate(datasources):
            if datasource is not None:
                self._autoMinMax.append(normalize is None)  # Don't auto-set normalization if the caller provided one.
                mmSource = MinMaxSource(datasource)
                mmSource.boundsChanged.connect(partial(self._bounds_changed, i))
                wrapped_datasources[i] = mmSource
                self._mmSources.append(mmSource)

        super(NormalizableLayer, self).__init__(wrapped_datasources, direct=direct)

        for i, datasource in enumerate(self.datasources):
            if datasource is not None:
                self._normalize.append(normalize)
                self.set_normalize(i, normalize)
            else:
                self._normalize.append((0, 1))
                self._autoMinMax.append(True)

        self.normalizeChanged.connect(self.changed)
        self.channelChanged.connect(self._channel_changed)

    def _channel_changed(self, ch_idx):
        for idx, src in enumerate(self._mmSources):
            src.reset_bounds()
            self._bounds_changed(idx, None)

    def _bounds_changed(self, datasourceIdx, range):
        if self._autoMinMax[datasourceIdx]:
            self.set_normalize(datasourceIdx, None)

    def resetBounds(self):
        for mm in self._mmSources:
            mm.resetBounds()


class GrayscaleLayer(NormalizableLayer):
    @property
    def window_leveling(self):
        return self._window_leveling

    @window_leveling.setter
    def window_leveling(self, wl):
        self._window_leveling = wl

    def isDifferentEnough(self, other_layer):
        if super(GrayscaleLayer, self).isDifferentEnough(other_layer):
            return True
        return self._window_leveling != other_layer._window_leveling

    def __init__(self, datasource, normalize=None, direct=False, window_leveling=False):
        assert isinstance(datasource, DataSourceABC)
        super().__init__([datasource], normalize, direct=direct)
        self._window_leveling = window_leveling

    def createImageSource(self, data_sources):
        if len(data_sources) != 1:
            raise ValueError("Expected 1 data source got %s" % len(data_sources))

        src = imsrc.GrayscaleImageSource(data_sources[0], self)
        src.setObjectName(self.name)
        self.nameChanged.connect(lambda x: src.setObjectName(str(x)))
        return src


class AlphaModulatedLayer(NormalizableLayer):
    tintColorChanged = pyqtSignal()

    @property
    def tintColor(self):
        return self._tintColor

    @tintColor.setter
    def tintColor(self, c):
        if self._tintColor != c:
            self._tintColor = c
            self.tintColorChanged.emit()

    def __init__(self, datasource, tintColor=QColor(255, 0, 0), normalize=None):
        assert isinstance(datasource, DataSourceABC)
        super().__init__([datasource], normalize=normalize)
        self._tintColor = tintColor
        self.tintColorChanged.connect(self.changed)

    def createImageSource(self, data_sources):
        if len(data_sources) != 1:
            raise ValueError("Expected 1 data source got %s" % len(data_sources))

        src = imsrc.AlphaModulatedImageSource(data_sources[0], self)
        src.setObjectName(self.name)

        self.nameChanged.connect(lambda x: src.setObjectName(str(x)))
        self.tintColorChanged.connect(lambda: src.setDirty((slice(None, None), slice(None, None))))
        return src


def generateRandomColors(M=256, colormodel="hsv", clamp=None, zeroIsTransparent=False):
    """Generate a colortable with M entries.
    colormodel: currently only 'hsv' is supported
    clamp:      A dictionary stating which parameters of the color in the colormodel are clamped to a certain
                value. For example: clamp = {'v': 1.0} will ensure that the value of any generated
                HSV color is 1.0. All other parameters (h,s in the example) are selected randomly
                to lie uniformly in the allowed range."""
    r = numpy.random.random((M, 3))
    if clamp is not None:
        for k, v in clamp.items():
            idx = colormodel.index(k)
            r[:, idx] = v

    colors = []
    if colormodel == "hsv":
        for i in range(M):
            if zeroIsTransparent and i == 0:
                colors.append(QColor(0, 0, 0, 0).rgba())
            else:
                h, s, v = r[i, :]
                color = numpy.asarray(colorsys.hsv_to_rgb(h, s, v)) * 255
                qColor = QColor(*color)
                colors.append(qColor.rgba())
        return colors
    else:
        raise RuntimeError("unknown color model '%s'" % colormodel)


class ColortableLayer(NormalizableLayer):
    colorTableChanged = pyqtSignal()

    @property
    def colorTable(self):
        return self._colorTable

    @colorTable.setter
    def colorTable(self, colorTable):
        self._colorTable = colorTable
        self.colorTableChanged.emit()

    def randomizeColors(self):
        self.colorTable = generateRandomColors(len(self._colorTable), "hsv", {"v": 1.0}, self.zeroIsTransparent)

    def isDifferentEnough(self, other_layer):
        if type(other_layer) != type(self):
            return True
        if other_layer._colorTable != self._colorTable:
            return True
        if other_layer.datasources != self.datasources:
            return True
        return False

    def __init__(self, datasource, colorTable, normalize=False, direct=False):
        assert isinstance(datasource, DataSourceABC)

        """
        By default, no normalization is performed on ColortableLayers.
        If the normalize parameter is set to 'auto',
        your data will be automatically normalized to the length of your colorable.
        If a tuple (dmin, dmax) is passed, this specifies the range of your data,
        which is used to normalize the data before the colorable is applied.
        """

        if normalize is "auto":
            normalize = None
        super().__init__([datasource], normalize=normalize, direct=direct)
        self.data = datasource
        self._colorTable = colorTable

        self.colortableIsRandom = False
        self.zeroIsTransparent = QColor.fromRgba(colorTable[0]).alpha() == 0

    def createImageSource(self, data_sources):
        if len(data_sources) != 1:
            raise ValueError("Expected 1 data source got %s" % len(data_sources))

        src = imsrc.ColortableImageSource(data_sources[0], self)
        src.setObjectName(self.name)

        self.nameChanged.connect(lambda x: src.setObjectName(str(x)))
        return src


class ClickableColortableLayer(ClickableLayer):
    colorTableChanged = pyqtSignal()

    def __init__(self, editor, clickFunctor, datasource, colorTable, direct=False, right=True):
        assert isinstance(datasource, DataSourceABC)
        super(ClickableColortableLayer, self).__init__(datasource, editor, clickFunctor, direct=direct, right=right)
        self._colorTable = colorTable
        self.data = datasource

        self.colortableIsRandom = False
        self.zeroIsTransparent = QColor.fromRgba(colorTable[0]).alpha() == 0

    @property
    def colorTable(self):
        return self._colorTable

    @colorTable.setter
    def colorTable(self, colorTable):
        self._colorTable = colorTable
        self.colorTableChanged.emit()

    def randomizeColors(self):
        self.colorTable = generateRandomColors(len(self._colorTable), "hsv", {"v": 1.0}, True)


class RGBALayer(NormalizableLayer):
    channelIdx = {"red": 0, "green": 1, "blue": 2, "alpha": 3}
    channelName = {0: "red", 1: "green", 2: "blue", 3: "alpha"}

    @property
    def color_missing_value(self):
        return self._color_missing_value

    @property
    def alpha_missing_value(self):
        return self._alpha_missing_value

    def __init__(
        self,
        red=None,
        green=None,
        blue=None,
        alpha=None,
        color_missing_value=0,
        alpha_missing_value=255,
        normalizeR=None,
        normalizeG=None,
        normalizeB=None,
        normalizeA=None,
    ):
        assert red is None or isinstance(red, DataSourceABC)
        assert green is None or isinstance(green, DataSourceABC)
        assert blue is None or isinstance(blue, DataSourceABC)
        assert alpha is None or isinstance(alpha, DataSourceABC)
        super(RGBALayer, self).__init__([red, green, blue, alpha])
        self._color_missing_value = color_missing_value
        self._alpha_missing_value = alpha_missing_value

    @classmethod
    def createFromMultichannel(cls, data):
        # disect data
        l = RGBALayer()
        return l

    def createImageSource(self, data_sources):
        if len(data_sources) != 4:
            raise ValueError("Expected 4 data sources got %s" % len(data_sources))

        ds = data_sources.copy()
        for i in range(3):
            if data_sources[i] == None:
                ds[i] = PlanarSliceSource(ConstantSource(self.color_missing_value))
        guarantees_opaqueness = False
        if data_sources[3] == None:
            ds[3] = PlanarSliceSource(ConstantSource(self.alpha_missing_value))
            guarantees_opaqueness = True if self.alpha_missing_value == 255 else False
        src = imsrc.RGBAImageSource(ds[0], ds[1], ds[2], ds[3], self, guarantees_opaqueness=guarantees_opaqueness)
        src.setObjectName(self.name)
        self.nameChanged.connect(lambda x: src.setObjectName(str(x)))
        self.normalizeChanged.connect(lambda: src.setDirty((slice(None, None), slice(None, None))))
        return src


##
## GraphicsItem layers
##
class DummyGraphicsItemLayer(Layer):
    def __init__(self, datasource):
        super(DummyGraphicsItemLayer, self).__init__([datasource])

    def createImageSource(self, data_sources):
        return imsrc.DummyItemSource(data_sources[0])


class DummyRasterItemLayer(Layer):
    def __init__(self, datasource):
        super(DummyRasterItemLayer, self).__init__([datasource])

    def createImageSource(self, data_sources):
        return imsrc.DummyRasterItemSource(data_sources[0])


class SegmentationEdgesLayer(Layer):
    """
    A layer that displays segmentation edge boundaries using vector graphics.
    (See imagesources.SegmentationEdgesItem.)
    """

    hoverIdChanged = pyqtSignal(object)

    DEFAULT_PEN = QPen()
    DEFAULT_PEN.setCosmetic(True)
    DEFAULT_PEN.setCapStyle(Qt.RoundCap)
    DEFAULT_PEN.setColor(Qt.white)
    DEFAULT_PEN.setWidth(2)

    @property
    def pen_table(self):
        """
        Items in the colortable can be added/replaced/deleted, but the
        colortable object itself cannot be overwritten with a different dict object.
        The SegmentationEdgesItem(s) associated witht this layer will react
        immediately to any changes you make to this colortable dict.
        """
        return self._pen_table

    def __init__(self, datasource, default_pen=DEFAULT_PEN, direct=False, *, isClickable=False, isHoverable=False):
        """
        datasource: A single-channel label image.
        default_pen: The initial pen style for each edge.
        """
        super(SegmentationEdgesLayer, self).__init__([datasource], direct=direct)

        # Changes to this colortable will be detected automatically in the QGraphicsItem
        self._pen_table = SignalingDict(self)
        self.default_pen = default_pen
        self._isClickable = isClickable
        self.isHoverable = isHoverable

    def handle_edge_clicked(self, id_pair, event):
        """
        Handles clicks from our associated SegmentationEdgesItem(s).
        (See connection made in SegmentationEdgesItemRequest.)

        id_pair: The edge that was clicked.
        """
        DEBUG_BEHAVIOR = False
        if DEBUG_BEHAVIOR:
            # Simple debug functionality: change to a random color.
            # Please verify in the viewer that edges spanning multiple tiles changed color
            # together, even though only one of the tiles was clicked.
            random_color = QColor(*list(numpy.random.randint(0, 255, (3,))))
            pen = QPen(self.pen_table[id_pair])
            pen.setColor(random_color)
            self.pen_table[id_pair] = pen
            event.accept()

    def handle_edge_swiped(self, id_pair, event):
        pass

    def createImageSource(self, data_sources):
        return imsrc.SegmentationEdgesItemSource(self, data_sources[0], self.isHoverable and self.hoverIdChanged)


class LabelableSegmentationEdgesLayer(SegmentationEdgesLayer):
    """
    Shows a set of user-labeled edges.
    """

    labelsChanged = pyqtSignal(dict)  # { id_pair, label_class }

    def __init__(
        self, datasource, label_class_pens, initial_labels={}, delay_ms=100, *, isClickable=True, isHoverable=True
    ):
        # Class 0 (no label) is the default pen
        super(LabelableSegmentationEdgesLayer, self).__init__(
            datasource, default_pen=label_class_pens[0], isClickable=isClickable, isHoverable=isHoverable
        )
        self._delay_ms = delay_ms
        self._label_class_pens = label_class_pens

        # Initialize the labels and pens
        self.overwrite_edge_labels(initial_labels)

        self._buffered_updates = {}

        # To avoid sending lots of single updates if the user is clicking quickly,
        # we buffer the updates into a dict that is only sent after a brief delay.
        self._timer = QTimer(self)
        self._timer.setInterval(self._delay_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._signal_buffered_updates)

    def overwrite_edge_labels(self, new_edge_labels):
        self._edge_labels = defaultdict(lambda: 0, new_edge_labels)

        # Change the pens accordingly
        pen_table = {}
        for id_pair, label_class in list(self._edge_labels.items()):
            # Omit unlabeled edges; there are usually a lot of them
            # and the default is class 0 anyway.
            if label_class != 0:
                pen_table[id_pair] = self._label_class_pens[label_class]
        self.pen_table.overwrite(pen_table)

    def handle_edge_clicked(self, id_pair, event):
        """
        Overridden from SegmentationEdgesLayer
        """
        old_class = self._edge_labels[id_pair]

        if event.buttons() == Qt.LeftButton:
            new_class = 1
        elif event.buttons() == Qt.RightButton:
            new_class = 2
        else:
            return

        if new_class == old_class:
            new_class = 0

        # For now, edge_labels dictionary will still contain 0-labeled edges.
        # We could delete them, but why bother?
        self._edge_labels[id_pair] = new_class

        # Update the display immediately
        self.pen_table[id_pair] = self._label_class_pens[new_class]

        # Buffer the update for listeners
        self._buffered_updates[id_pair] = new_class

        # Reset the timer
        self._timer.start()

        event.accept()

    def handle_edge_swiped(self, id_pair, event):
        if event.buttons() == Qt.LeftButton:
            new_class = 1
        elif event.buttons() == Qt.RightButton:
            new_class = 2
        elif event.buttons() == (Qt.LeftButton | Qt.RightButton):
            new_class = 0
        else:
            return

        self._edge_labels[id_pair] = new_class

        # Update the display immediately
        self.pen_table[id_pair] = self._label_class_pens[new_class]

        # Notify listeners immediately
        self.labelsChanged.emit({id_pair: new_class})

        event.accept()

    def _signal_buffered_updates(self):
        updates = self._buffered_updates
        self._buffered_updates = {}
        if updates:
            self.labelsChanged.emit(updates)

    def createImageSource(self, data_sources):
        return imsrc.SegmentationEdgesItemSource(self, data_sources[0], self.isHoverable and self.hoverIdChanged)

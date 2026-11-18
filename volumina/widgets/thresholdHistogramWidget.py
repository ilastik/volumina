###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2026, the ilastik developers
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
#          http://ilastik.org/license/
###############################################################################
from enum import Enum
from typing import Any, Tuple

import numpy as np
from numpy.typing import NDArray
from pyqtgraph import ColorMap, HistogramLUTItem, HistogramLUTWidget
from qtpy.QtCore import QTimer, Signal
from qtpy.QtWidgets import QGraphicsScene, QGraphicsView, QVBoxLayout, QWidget
import qtpy.compat


class HistogramColormap(Enum):
    GRAY = ColorMap([0.0, 1.0], [(0, 0, 0), (255, 255, 255)])
    GREEN = ColorMap([0.0, 1.0], [(0, 0, 0), (0, 255, 0)])
    RED = ColorMap([0.0, 1.0], [(0, 0, 0), (255, 0, 0)])
    BLUE = ColorMap([0.0, 1.0], [(0, 0, 0), (0, 0, 255)])


class ThresholdHistogramWidget(QWidget):

    valueChanged = Signal(float, float)

    VALUE_CHANGE_DELAY_MS = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self._eps = np.finfo(np.float64).eps

        w = HistogramLUTWidget(self, orientation="horizontal")
        self._thresholding_widget = w.item
        layout = QVBoxLayout()
        layout.addWidget(w)
        self.setLayout(layout)

        self._last_value: tuple[float | int, float | int] | None = None

        # We don't want to issue an update on any miniscule movement of the sliders
        self._delay_update_timer = QTimer(self)
        self._delay_update_timer.setSingleShot(True)
        self._delay_update_timer.setInterval(self.VALUE_CHANGE_DELAY_MS)

        def _update_limits():
            if not qtpy.compat.isalive(self):
                return
            if self._last_value is not None:
                min, max = self._last_value
                self.valueChanged.emit(min, max)

        def maybe_update(w_thres: HistogramLUTItem):
            self._last_value = w_thres.getLevels()
            self._delay_update_timer.start()  # restarts the 50 ms timer

        self._delay_update_timer.timeout.connect(_update_limits)

        self._thresholding_widget.sigLevelsChanged.connect(maybe_update)

        # Hide away functionality that we don't use (yet)
        self._thresholding_widget.gradient.showTicks(False)
        self._thresholding_widget.vb.setMenuEnabled(False)
        self._thresholding_widget.gradient.showMenu = lambda ev: ev.accept()

    def setValue(self, minimum: float | int, maximum: float | int):
        current_min, current_max = self.getValue()
        if (abs(current_min - minimum) > self._eps) or (abs(current_max - maximum) > self._eps):
            self._thresholding_widget.setLevels(minimum, maximum)

    def getValue(self) -> Tuple[float | int, float | int]:
        return self._thresholding_widget.getLevels()

    def updatePlot(self, bins: NDArray[Any], counts: NDArray[Any]):
        self._thresholding_widget.plot.setData(
            x=bins,
            y=counts,
            stepMode="center",
        )

    def setColormap(self, colormap: HistogramColormap):
        self._thresholding_widget.gradient.setColorMap(colormap.value)
        self._thresholding_widget.gradient.showTicks(False)

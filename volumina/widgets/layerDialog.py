from __future__ import print_function

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
# Python
import os

# PyQt
from qtpy import uic
from qtpy.QtWidgets import QDialog
from qtpy.QtCore import Qt
from functools import partial
from typing import Callable
from pathlib import Path

from volumina.layer import NormalizableLayer
from volumina.widgets.thresholdingWidget import ThresholdingWidget

import logging

logger = logging.getLogger(__name__)


class LayerDialog(QDialog):
    def __init__(self, ui_file_name: str, layer: NormalizableLayer, parent=None):
        super().__init__(parent)
        base_path = Path(__file__).resolve().parent
        ui_path = base_path.joinpath("ui").joinpath(ui_file_name)
        uic.loadUi(ui_path.as_posix(), self)
        self.setLayername(layer.name)
        self.layer = layer

    def initialize_range_widgets(self, datasourceIdx: int, thresholding_widget: ThresholdingWidget, autorange_checkbox):
        def handleRangeChanged(a, b):
            self.layer.set_normalize(datasourceIdx, (a, b))

        normalization_range = self.layer.get_datasource_default_range(datasourceIdx)
        thresholding_widget.setRange(normalization_range[0], normalization_range[1])

        normalization_value = self.layer.get_datasource_range(datasourceIdx)
        thresholding_widget.setValue(int(normalization_value[0]), int(normalization_value[1]))

        thresholding_widget.valueChanged.connect(handleRangeChanged)

        def handleAutoRangeChanged(state):
            self.layer.set_normalize(datasourceIdx, None if state == Qt.Checked else thresholding_widget.getRange())
            thresholding_widget.setEnabled(state == Qt.Unchecked)

        autorange_checkbox.stateChanged.connect(handleAutoRangeChanged)
        autorange_state = Qt.Checked if self.layer._autoMinMax[datasourceIdx] else Qt.Unchecked
        autorange_checkbox.setCheckState(autorange_state)

    def setLayername(self, name: str):
        self._layerLabel.setText(f"<b>{name}</b>")


class GrayscaleLayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="grayLayerDialog.ui", layer=layer, parent=parent)

        self.initialize_range_widgets(
            datasourceIdx=0,
            thresholding_widget=self.grayChannelThresholdingWidget,
            autorange_checkbox=self.grayAutoRange,
        )


class RGBALayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="rgbaLayerDialog.ui", layer=layer, parent=parent)

        for idx, (t_widget, autorange_checkbox, channel) in enumerate(
            [
                (self.redChannelThresholdingWidget, self.redAutoRange, self.redChannel),
                (self.greenChannelThresholdingWidget, self.greenAutoRange, self.greenChannel),
                (self.blueChannelThresholdingWidget, self.blueAutoRange, self.blueChannel),
                (self.alphaChannelThresholdingWidget, self.alphaAutoRange, self.alphaChannel),
            ]
        ):
            if layer.datasources[idx] == None:
                channel.setVisible(False)
                continue
            self.initialize_range_widgets(idx, thresholding_widget=t_widget, autorange_checkbox=autorange_checkbox)

        self.resize(self.minimumSize())


if __name__ == "__main__":
    import optparse
    import sys
    from qtpy.QtWidgets import QApplication

    parser = optparse.OptionParser()
    parser.add_option("--gray", action="store_true")
    parser.add_option("--rgb", action="store_true")
    (options, args) = parser.parse_args()

    app = QApplication([])
    if options.gray:
        l = GrayscaleLayerDialog()
    elif options.rgb:
        l = RGBALayerDialog()
    else:
        print(parser.usage)
        sys.exit()
    l.show()
    app.exec_()

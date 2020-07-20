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
from PyQt5 import uic
from PyQt5.QtWidgets import QDialog
from PyQt5.QtCore import Qt
from functools import partial
from typing import Callable
from pathlib import Path

import logging

logger = logging.getLogger(__name__)


class LayerDialog(QDialog):
    def __init__(self, ui_file_name: str, layer, parent=None):
        super().__init__(parent)
        base_path = Path(__file__).resolve().parent
        ui_path = base_path.joinpath("ui").joinpath(ui_file_name)
        uic.loadUi(ui_path.as_posix(), self)
        self.setLayername(layer.name)
        self.layer = layer

    def update_widget_limits(self, datasourceIdx: int, thresholding_widget, autorange_widget):
        thresholding_widget.setRange(self.layer.range[datasourceIdx][0], self.layer.range[datasourceIdx][1])
        normalize_range = self.layer.get_datasource_range(datasourceIdx)
        thresholding_widget.setValue(normalize_range[0], normalize_range[1])

        autorange_widget.stateChanged.connect(
            self.make_range_checkbox_handler(datasourceIdx=0, thresholding_widget=thresholding_widget)
        )
        autorange_widget.setCheckState(layer._autoMinMax[datasourceIdx] * 2)

    def make_range_checkbox_handler(self, datasourceIdx: int, thresholding_widget) -> Callable[[int], None]:
        def autoRangeHandler(state):
            if state == Qt.Checked:
                self.update_widget_limits(datasourceIdx=datasourceIdx, thresholding_widget=thresholding_widget)
                self.layer.set_normalize(datasourceIdx, None)  # set to auto
                thresholding_widget.setEnabled(False)
            if state == Qt.Unchecked:
                thresholding_widget.setEnabled(True)
                self.layer.set_normalize(datasourceIdx, self.layer.normalize[datasourceIdx])

        return autoRangeHandler

    def setLayername(self, name: str):
        self._layerLabel.setText(f"<b>{name}</b>")


class GrayscaleLayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="grayLayerDialog.ui", layer=layer, parent=parent)

        def dbgPrint(a, b):
            layer.set_normalize(0, (a, b))
            logger.debug("normalization changed to [%d, %d]" % (a, b))

        # import pydevd; pydevd.settrace()
        self.update_widget_limits(
            datasourceIdx=0, thresholding_widget=self.grayChannelThresholdingWidget, autorange_widget=self.grayAutoRange
        )
        self.grayChannelThresholdingWidget.valueChanged.connect(dbgPrint)


class RGBALayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="rgbaLayerDialog.ui", layer=layer, parent=parent)

        def dbgPrint(layerIdx, a, b):
            layer.set_normalize(layerIdx, (a, b))
            logger.debug("normalization changed for channel=%d to [%d, %d]" % (layerIdx, a, b))

        thresholding_widgets = [
            self.redChannelThresholdingWidget,
            self.greenChannelThresholdingWidget,
            self.blueChannelThresholdingWidget,
            self.alphaChannelThresholdingWidget,
        ]
        auto_range_widgets = [self.redAutoRange, self.greenAutoRange, self.blueAutoRange, self.alphaAutoRange]
        channels = [self.redChannel, self.greenChannel, self.blueChannel, self.alphaChannel]

        for idx, t_widget in enumerate(thresholding_widgets):
            channel = channels[idx]
            range_widget = auto_range_widgets[idx]

            if layer.datasources[idx] == None:
                channel.setVisible(False)
                continue

            self.update_widget_limits(idx, thresholding_widget=t_widget, autorange_widget=range_Widget)
            t_widget.valueChanged.connect(partial(dbgPrint, idx))

        self.resize(self.minimumSize())


if __name__ == "__main__":
    import optparse
    import sys
    from PyQt5.QtWidgets import QApplication

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

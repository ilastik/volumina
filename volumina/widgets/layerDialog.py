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
from qtpy import uic
from qtpy.QtWidgets import QDialog
from qtpy.QtCore import Qt
from pathlib import Path
from volumina.layer import NormalizationType
from volumina.widgets.thresholdHistogramWidget import ThresholdHistogramWidget, HistogramColormap

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

    def initialize_range_widgets(
        self,
        datasourceIdx: int,
        thresholding_widget: ThresholdHistogramWidget,
        autorange_checkbox,
        colormap=HistogramColormap.GRAY,
    ):
        thresholding_widget.setColormap(colormap)

        def handleRangeChangedInUi(a, b):
            if not self.layer._autoMinMax[datasourceIdx]:
                self.layer.set_normalize(datasourceIdx, (a, b))

        def handleLayerRangeChanged():
            normalization_range_min, normalization_range_max = self.layer.get_datasource_range(datasourceIdx)
            thresholding_widget.setValue(normalization_range_min, normalization_range_max)

        handleLayerRangeChanged()
        thresholding_widget.valueChanged.connect(handleRangeChangedInUi)
        self.layer.normalizeChanged.connect(handleLayerRangeChanged)

        def handleAutoRangeChanged(state):
            self.layer.set_normalize(
                datasourceIdx,
                NormalizationType.AUTO_NORMALIZE if state == Qt.Checked else thresholding_widget.getValue(),
            )
            thresholding_widget.setEnabled(state == Qt.Unchecked)

        autorange_checkbox.stateChanged.connect(handleAutoRangeChanged)
        autorange_state = Qt.Checked if self.layer._autoMinMax[datasourceIdx] else Qt.Unchecked
        autorange_checkbox.setCheckState(autorange_state)

        def update_hist():
            bins, counts = self.layer.get_datasource_hist(datasourceIdx)
            thresholding_widget.updatePlot(bins, counts)

        self.layer.histogramChanged.connect(update_hist)
        update_hist()

    def setLayername(self, name: str):
        self._layerLabel.setText(f"<b>{name}</b>")


class GrayscaleLayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="grayLayerDialog.ui", layer=layer, parent=parent)

        self.initialize_range_widgets(
            datasourceIdx=0,
            thresholding_widget=self.grayChannelThresholdingWidget,
            autorange_checkbox=self.grayAutoRange,
            colormap=HistogramColormap.GRAY,
        )


class RGBALayerDialog(LayerDialog):
    def __init__(self, layer, parent=None):
        super().__init__(ui_file_name="rgbaLayerDialog.ui", layer=layer, parent=parent)

        for idx, (t_widget, autorange_checkbox, channel, colormap) in enumerate(
            [
                (self.redChannelThresholdingWidget, self.redAutoRange, self.redChannel, HistogramColormap.RED),
                (self.greenChannelThresholdingWidget, self.greenAutoRange, self.greenChannel, HistogramColormap.GREEN),
                (self.blueChannelThresholdingWidget, self.blueAutoRange, self.blueChannel, HistogramColormap.BLUE),
                (self.alphaChannelThresholdingWidget, self.alphaAutoRange, self.alphaChannel, HistogramColormap.GRAY),
            ]
        ):
            if layer.datasources[idx] == None:
                channel.setVisible(False)
                continue
            self.initialize_range_widgets(
                idx, thresholding_widget=t_widget, autorange_checkbox=autorange_checkbox, colormap=colormap
            )


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

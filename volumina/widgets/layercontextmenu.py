from __future__ import absolute_import

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
from builtins import range
from functools import partial

# Qt
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QMenu, QAction, QDialog, QHBoxLayout, QTableWidget, QSizePolicy, QTableWidgetItem
from PyQt5.QtGui import QColor

# volumina
from volumina.layer import ColortableLayer, GrayscaleLayer, RGBALayer, ClickableColortableLayer, SegmentationEdgesLayer
from .layerDialog import GrayscaleLayerDialog, RGBALayerDialog

# ===----------------------------------------------------------------------------------------------------------------===

###
### lazyflow input
###
try:
    import lazyflow

    _has_lazyflow = True
    from .exportHelper import prompt_export_settings_and_export_layer
except ImportError as e:
    _has_lazyflow = False


def _add_actions_grayscalelayer(layer, menu):
    def adjust_thresholds_callback():
        dlg = GrayscaleLayerDialog(layer, menu.parent())
        dlg.show()

    adjThresholdAction = QAction("Adjust thresholds", menu)
    adjThresholdAction.triggered.connect(adjust_thresholds_callback)
    menu.addAction(adjThresholdAction)


def _add_actions_rgbalayer(layer, menu):
    def adjust_thresholds_callback():
        dlg = RGBALayerDialog(layer, menu.parent())
        dlg.show()

    adjThresholdAction = QAction("Adjust thresholds", menu)
    adjThresholdAction.triggered.connect(adjust_thresholds_callback)
    menu.addAction(adjThresholdAction)


class LayerColortableDialog(QDialog):
    def __init__(self, layer, parent=None):
        super(LayerColortableDialog, self).__init__(parent=parent)

        h = QHBoxLayout(self)
        t = QTableWidget(self)
        t.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        t.setRowCount(len(layer._colorTable))
        t.setColumnCount(1)
        t.setVerticalHeaderLabels(["%d" % i for i in range(len(layer._colorTable))])

        for i in range(len(layer._colorTable)):
            item = QTableWidgetItem(" ")
            t.setItem(i, 0, item)
            item.setBackgroundColor(QColor.fromRgba(layer._colorTable[i]))
            item.setFlags(Qt.ItemIsSelectable)

        h.addWidget(t)


def _add_actions_colortablelayer(layer, menu):
    def adjust_colortable_callback():
        dlg = LayerColortableDialog(layer, menu.parent())
        dlg.exec_()

    if layer.colortableIsRandom:
        randomizeColors = QAction("Randomize colors", menu)
        randomizeColors.triggered.connect(layer.randomizeColors)
        menu.addAction(randomizeColors)


def _add_actions(layer, menu):
    if isinstance(layer, GrayscaleLayer):
        _add_actions_grayscalelayer(layer, menu)
    elif isinstance(layer, RGBALayer):
        _add_actions_rgbalayer(layer, menu)
    elif isinstance(layer, (ColortableLayer, ClickableColortableLayer)):
        _add_actions_colortablelayer(layer, menu)


def layercontextmenu(layer, pos, parent=None):
    """Show a context menu to manipulate properties of layer.

    layer -- a volumina layer instance
    pos -- QPoint

    """
    menu = QMenu("Menu", parent)

    # Title
    title = QAction("%s" % layer.name, menu)
    title.setEnabled(False)
    menu.addAction(title)

    # Export
    global _has_lazyflow
    if _has_lazyflow and not isinstance(layer, SegmentationEdgesLayer):  # Edges are stored as sets of paths
        export = QAction("Export...", menu)
        export.setStatusTip("Export Layer...")
        export.triggered.connect(partial(prompt_export_settings_and_export_layer, layer, menu))
        menu.addAction(export)

    menu.addSeparator()
    _add_actions(layer, menu)

    # Layer-custom context menu items
    menu.addSeparator()
    for item in layer.contexts:
        if isinstance(item, QAction):
            menu.addAction(item)
        elif isinstance(item, QMenu):
            menu.addMenu(item)

    menu.exec_(pos)

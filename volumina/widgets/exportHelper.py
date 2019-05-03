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
#          http://ilastik.org/license/
###############################################################################
# Python
import os
from functools import partial
import typing

# Qt
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QMessageBox

# volumina
from .dataExportOptionsDlg import DataExportOptionsDlg
from .multiStepProgressDialog import MultiStepProgressDialog

import logging

from volumina.utility import log_exception, PreferencesManager
from volumina.layer import Layer

import lazyflow
from lazyflow.request import Request
from lazyflow.utility import PathComponents
from lazyflow.operators import OpMultiArrayStacker
from lazyflow.operators.ioOperators import OpFormattedDataExport


logger = logging.getLogger(__name__)


def _get_export_slots(layer: Layer) -> typing.List[lazyflow.slot.Slot]:
    """Returns export slots for layer

    Args:
        layer (Layer): Volumina Layer, its datasources will be checked for "dataSlot" member.

    Returns:
        List of slots that can be exported from layer

    Raises:
        RuntimeError: will be raised if the is no dataSource that has the "dataSlot" attribute, aka
          that is a lazyflow dataSource (slot)
    """
    sourceTags = [
        hasattr(l, "dataSlot") and l.dataSlot is not None for l in layer.datasources
    ]
    if not any(sourceTags):
        raise RuntimeError(
            "can not export from a non-lazyflow data source (layer=%r, datasource=%r)"
            % (type(layer), type(layer.datasources[0]))
        )
    return [
        slot.dataSlot
        for (slot, isSlot) in zip(layer.datasources, sourceTags)
        if isSlot is True
    ]


def _get_stacked_data_sources(layer: Layer) -> OpMultiArrayStacker:
    """Get operator with stacked output from all slots of layer

    Args:
        layer (Layer): layer containing datasources that can be exported
          (datasource.dataSlot -> Slot)

    Returns:
        OpMultiArrayStacker: Operator configured with all stackable input slots
        from layer.
    """
    dataSlots = _get_export_slots(layer)

    opStackChannels = lazyflow.operators.OpMultiArrayStacker(
        dataSlots[0].getRealOperator().parent
    )
    for slot in dataSlots:
        assert isinstance(slot, lazyflow.graph.Slot), "slot is of type %r" % (
            type(slot)
        )
        assert isinstance(
            slot.getRealOperator(), lazyflow.graph.Operator
        ), "slot's operator is of type %r" % (type(slot.getRealOperator()))
    opStackChannels.AxisFlag.setValue("c")
    opStackChannels.Images.resize(len(dataSlots))
    for i, islot in enumerate(opStackChannels.Images):
        islot.connect(dataSlots[i])

    return opStackChannels


def get_export_operator(layer: Layer) -> OpFormattedDataExport:
    """Get export operator configured with stacked output from layer

    Args:
        layer (Layer): layer containing datasources that can be exported
          (datasource.dataSlot -> Slot)

    Returns:
        OpFormattedDataExport: Operator configured with all stackable input slots
        from layer.
    """
    opStackChannels = _get_stacked_data_sources(layer)
    # Create an operator to do the work

    opExport = OpFormattedDataExport(parent=opStackChannels.parent)
    opExport.Input.connect(opStackChannels.Output)
    opExport.TransactionSlot.setValue(True)

    return opExport


def get_settings_and_export_layer(layer: Layer, parent_widget=None) -> None:
    """
    Prompt the user for layer export settings, and perform the layer export.
    """
    opExport = get_export_operator(layer)

    export_dir = PreferencesManager().get(
        "layer", "export-dir", default=os.path.expanduser("~")
    )
    opExport.OutputFilenameFormat.setValue(os.path.join(export_dir, layer.name))

    # Use this dialog to populate the operator's slot settings
    settingsDlg = DataExportOptionsDlg(parent_widget, opExport)

    # If user didn't cancel, run the export now.
    if settingsDlg.exec_() == DataExportOptionsDlg.Accepted:
        export_dir = PathComponents(opExport.ExportPath.value).externalDirectory
        PreferencesManager().set("layer", "export-dir", export_dir)

        helper = ExportHelper(parent_widget)
        helper.run(opExport)

    # Clean up our temporary operators
    opExport.cleanUp()
    opStackChannels.cleanUp()


class ExportHelper(QObject):
    """
    Executes a layer export in the background, shows a progress dialog, and displays errors (if any).
    """

    # This signal is used to ensure that request
    #  callbacks are executed in the gui thread
    _forwardingSignal = pyqtSignal(object)

    def _handleForwardedCall(self, fn):
        # Execute the callback
        fn()

    def __init__(self, parent):
        super(ExportHelper, self).__init__(parent)
        self._forwardingSignal.connect(self._handleForwardedCall)

    def run(self, opExport):
        """
        Start the export and return immediately (after showing the progress dialog).

        :param opExport: The export object to execute.
                         It must have a 'run_export()' method and a 'progressSignal' member.
        """
        progressDlg = MultiStepProgressDialog(parent=self.parent())
        progressDlg.setNumberOfSteps(1)

        def _forwardProgressToGui(progress):
            self._forwardingSignal.emit(partial(progressDlg.setStepProgress, progress))

        opExport.progressSignal.subscribe(_forwardProgressToGui)

        def _onFinishExport(*args):  # Also called on cancel
            self._forwardingSignal.emit(progressDlg.finishStep)

        def _onFail(exc, exc_info):
            log_exception(logger, "Failed to export layer.", exc_info=exc_info)
            msg = "Failed to export layer due to the following error:\n{}".format(exc)
            self._forwardingSignal.emit(
                partial(QMessageBox.critical, self.parent(), "Export Failed", msg)
            )
            self._forwardingSignal.emit(progressDlg.setFailed)

        # Use a request to execute in the background
        req = Request(opExport.run_export)
        req.notify_cancelled(_onFinishExport)
        req.notify_finished(_onFinishExport)
        req.notify_failed(_onFail)

        # Allow cancel.
        progressDlg.rejected.connect(req.cancel)

        # Start the export
        req.submit()

        # Execute the progress dialog
        # (We can block the thread here because the QDialog spins up its own event loop.)
        progressDlg.exec_()

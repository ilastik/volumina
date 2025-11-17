from unittest import mock

import numpy as np
import pytest
import vigra

pytest.importorskip("lazyflow")

from lazyflow.graph import Graph, Operator, InputSlot
from lazyflow.operators.ioOperators import OpFormattedDataExport
from volumina.widgets.multiformatSlotExportFileOptionsWidget import MultiformatSlotExportFileOptionsWidget


class OpMock(Operator):
    OutputFilenameFormat = InputSlot(value="~/something.h5")
    OutputInternalPath = InputSlot(value="volume/data")
    OutputFormat = InputSlot(value="hdf5")
    FormatSelectionErrorMsg = InputSlot(value=True)  # Normally an output slot

    def setupOutputs(self):
        pass

    def execute(self, *args):
        pass

    def propagateDirty(self, *args):
        pass


@pytest.fixture
def data():
    data = np.zeros((10, 11, 3), dtype=np.uint8)
    data = vigra.taggedView(data, "yxc")
    return data


def test_handles_unknown_format(qtbot, data):
    op = OpFormattedDataExport(graph=Graph())
    op.Input.setValue(data)
    op.OutputFormat.setValue("unknown format from the future :D")
    op.TransactionSlot.setValue(True)

    warn_mock = mock.Mock()
    with mock.patch("qtpy.QtWidgets.QMessageBox.warning", warn_mock):
        w = MultiformatSlotExportFileOptionsWidget(None)
        w.initExportOp(op)
        qtbot.addWidget(w)
        w.show()
        qtbot.waitExposed(w)

    warn_mock.assert_called_once()
    assert op.OutputFormat.value == "compressed hdf5"

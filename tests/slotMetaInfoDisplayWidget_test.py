import pytest

import numpy
import re


vigra = pytest.importorskip("vigra")
_ = pytest.importorskip("lazyflow")


from lazyflow.graph import Graph
from lazyflow.operators.operators import OpArrayPiper
from lazyflow.operators.opReorderAxes import OpReorderAxes
from volumina.widgets.slotMetaInfoDisplayWidget import SlotMetaInfoDisplayWidget, OutputSlotMetaInfoDisplayWidget


def test_SlotMetaInfoDisplayWidget_shows_correct_info(qtbot):
    shape = {"x": 10, "y": 20, "z": 30, "c": 3}
    swapped_shape = {"c": 3, "y": 20, "x": 10, "z": 30}
    dtype = numpy.float32
    graph = Graph()

    def create_array(shape: dict):
        arr = numpy.random.rand(*shape.values()).astype(dtype)
        return vigra.taggedView(arr, "".join(shape.keys()))

    data = create_array(shape)

    op = OpArrayPiper(graph=graph)
    op.Input.setValue(data)

    op_reorder = OpReorderAxes(graph=graph, AxisOrder="".join(swapped_shape.keys()), Input=op.Output)

    def init_widget(widget, slot):
        widget.initSlot(slot)
        qtbot.addWidget(widget)
        widget.show()
        return widget

    w = init_widget(SlotMetaInfoDisplayWidget(None), op.Output)
    out_widget = init_widget(OutputSlotMetaInfoDisplayWidget(None), op_reorder.Output)

    qtbot.waitForWindowShown(w)

    def verify_widget(w, shape):
        displayed_shape = tuple(int(s) for s in re.findall(r"[0-9]+", w.shapeDisplay.text()))
        assert displayed_shape == tuple(shape.values())
        assert w.axisOrderDisplay.text() == "".join(shape.keys())
        assert w.dtypeDisplay.text() == dtype.__name__

    verify_widget(w, shape)
    verify_widget(out_widget, swapped_shape)

    new_shape = {"y": 1, "c": 40, "z": 10, "x": 30}
    new_swapped_shape = {"c": 40, "x": 30, "y": 1, "z": 10}
    new_data = create_array(new_shape)

    op.Input.setValue(new_data)
    op_reorder.AxisOrder.setValue("".join(new_swapped_shape.keys()))

    verify_widget(w, new_shape)
    verify_widget(out_widget, new_swapped_shape)

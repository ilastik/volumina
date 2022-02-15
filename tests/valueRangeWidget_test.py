import numpy
import pytest
from volumina.widgets.valueRangeWidget import ValueRangeWidget


@pytest.mark.parametrize("dtype", [numpy.float32, numpy.float64, float])
def test_floating_range(qtbot, dtype):
    """repro of https://github.com/ilastik/ilastik/issues/2542"""
    vrwidget = ValueRangeWidget()
    qtbot.addWidget(vrwidget)
    vrwidget.show()
    qtbot.waitForWindowShown(vrwidget)
    vrwidget.setDType(dtype)
    minmax = vrwidget.getValues()
    minmax_expected = numpy.finfo(dtype).min, numpy.finfo(dtype).max
    numpy.testing.assert_array_almost_equal(minmax, minmax_expected)


@pytest.mark.parametrize("dtype", [numpy.int8, numpy.uint8, numpy.int16, numpy.uint16, numpy.int32, numpy.uint32, int])
def test_integer_range(qtbot, dtype):
    vrwidget = ValueRangeWidget()
    qtbot.addWidget(vrwidget)
    vrwidget.show()
    qtbot.waitForWindowShown(vrwidget)
    vrwidget.setDType(dtype)
    minmax = vrwidget.getValues()
    minmax_expected = numpy.iinfo(dtype).min, numpy.iinfo(dtype).max
    numpy.testing.assert_array_equal(minmax, minmax_expected)

import numpy
import pytest
from volumina.widgets.valueRangeWidget import ValueRangeWidget


@pytest.fixture
def vrwidget(qtbot):
    vrwidget = ValueRangeWidget()
    qtbot.addWidget(vrwidget)
    vrwidget.show()
    return vrwidget


@pytest.mark.parametrize("dtype", [numpy.float32, numpy.float64, float])
def test_floating_range(vrwidget, qtbot, dtype):
    """repro of https://github.com/ilastik/ilastik/issues/2542"""
    with qtbot.waitExposed(vrwidget):
        vrwidget.setDType(dtype)

    minmax = vrwidget.getValues()
    minmax_expected = numpy.finfo(dtype).min, numpy.finfo(dtype).max
    numpy.testing.assert_array_almost_equal(minmax, minmax_expected)


@pytest.mark.parametrize("dtype", [numpy.int8, numpy.uint8, numpy.int16, numpy.uint16, numpy.int32, numpy.uint32, int])
def test_integer_range(vrwidget, qtbot, dtype):
    with qtbot.waitExposed(vrwidget):
        vrwidget.setDType(dtype)

    minmax = vrwidget.getValues()
    minmax_expected = numpy.iinfo(dtype).min, numpy.iinfo(dtype).max
    numpy.testing.assert_array_equal(minmax, minmax_expected)


def test_setBlank(vrwidget, qtbot):
    with qtbot.waitExposed(vrwidget):
        vrwidget.setBlank()

    assert vrwidget._blank == True
    assert vrwidget.minBox.specialValueText() == "--"
    assert vrwidget.maxBox.specialValueText() == "--"


def test_onChangedMinBox(vrwidget, qtbot):
    """Test behavior of max box being incremented if user adds the same value into min"""
    with qtbot.waitExposed(vrwidget):
        vrwidget.setDType(int)
        vrwidget.setLimits(0, 10)
        vrwidget.maxBox.setValue(5)
        vrwidget.minBox.setValue(5)
    assert int(vrwidget.minBox.value()) == 5
    assert int(vrwidget.maxBox.value()) == 6


def test_onChangedMaxBox(vrwidget, qtbot):
    """Test behavior of min box being decremented if user adds the same value into max"""
    with qtbot.waitExposed(vrwidget):
        vrwidget.setDType(int)
        vrwidget.setLimits(0, 10)
        vrwidget.minBox.setValue(5)
        vrwidget.maxBox.setValue(5)
    assert int(vrwidget.maxBox.value()) == 5
    assert int(vrwidget.minBox.value()) == 4


def test_setValues(vrwidget, qtbot):
    with qtbot.waitExposed(vrwidget):
        vrwidget.setDType(int)
        vrwidget.setValues(2, 8)
    assert int(vrwidget.minBox.value()) == 2
    assert int(vrwidget.maxBox.value()) == 8

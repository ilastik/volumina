from time import perf_counter

import pytest

from volumina.widgets.thresholdHistogramWidget import ThresholdHistogramWidget


@pytest.fixture
def threshold_widget(qtbot) -> ThresholdHistogramWidget:
    t_widget = ThresholdHistogramWidget()
    qtbot.addWidget(t_widget)
    return t_widget


def test_init(threshold_widget: ThresholdHistogramWidget):
    assert threshold_widget.getValue() == (0.0, 1.0)


@pytest.mark.parametrize("value", [(0.0, 42.0), (0.5, 1.0), (-3, -1), (5.0, 13)])
def test_setValue_roundtrip(threshold_widget: ThresholdHistogramWidget, value: tuple[int | float, int | float]):
    threshold_widget.setValue(*value)

    assert threshold_widget.getValue() == value


def test_update_delay(qtbot, threshold_widget: ThresholdHistogramWidget):
    t0 = perf_counter()

    with qtbot.waitSignal(threshold_widget.valueChanged, timeout=500) as update_trigger:
        threshold_widget.setValue(5, 10)

    duration = (perf_counter() - t0) * 1000  # ms

    # slightly lower - I've observed qt being a bit faster
    lower_accept_limit = threshold_widget.VALUE_CHANGE_DELAY_MS * 0.95
    # have seen larger delays on CI - so let's be permissive here
    upper_accept_limit = threshold_widget.VALUE_CHANGE_DELAY_MS * 2.5

    assert update_trigger.signal_triggered
    assert upper_accept_limit > duration >= lower_accept_limit

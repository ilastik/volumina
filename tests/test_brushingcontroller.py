from unittest import mock
from volumina.brushingcontroller import DrawLabelCommand
import numpy


class TestDrawLabelCommand:
    def test_redo_command(self):
        sink = mock.Mock()
        old_data = numpy.array([1, 1, 0, 0, 0])
        labels = numpy.array([0, 2, 2, 0, 0], dtype="uint8")
        slicing = slice(0, 5)

        cmd = DrawLabelCommand(sink=sink, slicing=slicing, old_data=old_data, labels=labels)
        cmd.redo()

        expected_put_arr = numpy.array([1, 2, 2, 0, 0])

        sink.put.assert_called_once()
        assert sink.put.call_args[0][0] == slicing
        actual_put_arr = sink.put.call_args[0][1]
        numpy.testing.assert_array_equal(actual_put_arr, expected_put_arr)
        assert actual_put_arr.dtype == labels.dtype

    def test_undo_command_no_eraser_value_should_overwrite_with_old_data(self):
        sink = mock.Mock()
        sink.eraser_value = None

        old_data = numpy.array([1, 1, 0, 0, 0])
        labels = numpy.array([0, 2, 2, 0, 0], dtype="uint8")
        slicing = slice(0, 5)

        cmd = DrawLabelCommand(sink=sink, slicing=slicing, old_data=old_data, labels=labels)
        cmd.undo()

        sink.put.assert_called_once()
        assert sink.put.call_args[0][0] == slicing
        actual_put_arr = sink.put.call_args[0][1]
        numpy.testing.assert_array_equal(actual_put_arr, old_data)
        assert actual_put_arr.dtype == labels.dtype

    def test_undo_command_with_eraser_value_overlays_old_data_with_eraser(self):
        sink = mock.Mock()
        sink.eraser_value = 100

        old_data = numpy.array([1, 1, 0, 0, 0])
        labels = numpy.array([0, 2, 2, 0, 0], dtype="uint8")
        slicing = slice(0, 5)

        cmd = DrawLabelCommand(sink=sink, slicing=slicing, old_data=old_data, labels=labels)
        cmd.undo()

        expected_put_arr = numpy.array([1, 1, 100, 0, 0])

        sink.put.assert_called_once()
        assert sink.put.call_args[0][0] == slicing
        actual_put_arr = sink.put.call_args[0][1]
        numpy.testing.assert_array_equal(actual_put_arr, sink.put.call_args[0][1], expected_put_arr)
        assert actual_put_arr.dtype == labels.dtype

from unittest import mock

import pytest

from PyQt5.QtCore import QObject, pyqtSignal
from volumina.utility import abc


class TestQAbc:
    class IObject(abc.QABC):
        @abc.abstractmethod
        def foo(self):
            ...

    class ISignal(abc.QABC):
        signal = abc.abstractsignal()

    def test_type_error_on_undefined_abstract_method(self):

        with pytest.raises(TypeError):
            self.IObject()

    def test_not_implemented_signal_raises_type_error(self):
        with pytest.raises(TypeError):
            self.ISignal()

    def test_implemented_signal_doesnt_raise_type_error(self):
        class MySignal(self.ISignal):
            signal = pyqtSignal(int)

        MySignal()

    def test_qobject_signal(self):
        class MyObject(QObject, self.IObject, self.ISignal):
            signal = pyqtSignal(int)

            def foo(self):
                self.signal.emit(42)

        reciever = mock.Mock()
        o = MyObject()
        o.signal.connect(reciever)
        o.foo()

        reciever.assert_called_once_with(42)

from unittest import mock

import pytest

from qtpy.QtCore import QObject, Signal
from volumina.utility import qabc


class TestQAbc:
    class IObject(qabc.QABC):
        @qabc.abstractmethod
        def foo(self): ...

    class ISignal(qabc.QABC):
        signal = qabc.abstractsignal()

    def test_type_error_on_undefined_abstract_method(self):

        with pytest.raises(TypeError):
            self.IObject()

    def test_not_implemented_signal_raises_type_error(self):
        with pytest.raises(TypeError):
            self.ISignal()

    def test_implemented_signal_doesnt_raise_type_error(self):
        class MySignal(self.ISignal):
            signal = Signal(int)

        MySignal()

    def test_abstract_signal_accepts_args_and_kwargs(self):
        class MyABC(qabc.QABC):
            signal = qabc.abstractsignal(int, param1=str)

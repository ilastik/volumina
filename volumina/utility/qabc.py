"""
Wraps stdlib abc module to provide convenience classes for defining QObject interfaces
"""

from abc import ABCMeta, abstractmethod, _abc_init

from qtpy.QtCore import QObject

__all__ = ["QABC", "QABCMeta", "abstractmethod", "abstractsignal"]


class abstractsignal:
    """
    Should be used in place of Signal
    NOTE: This class doesn't implement any typechecks as abc decorators also don't provide this capability
    """

    __isabstractmethod__ = True

    def __init__(self, *args, **kwargs):
        pass


class QABCMeta(ABCMeta, type(QObject)):
    """
    from: https://stackoverflow.com/a/78794968

    tested with PyQt5, PySide6
    """

    def __new__(mcls, name, bases, ns, **kw):
        cls = super().__new__(mcls, name, bases, ns, **kw)
        _abc_init(cls)
        return cls

    def __call__(cls, *args, **kw):
        if cls.__abstractmethods__:
            raise TypeError(
                f"Can't instantiate abstract class {cls.__name__} without an implementation for abstract methods {set(cls.__abstractmethods__)}"
            )
        return super().__call__(*args, **kw)


class QABC(metaclass=QABCMeta):
    pass

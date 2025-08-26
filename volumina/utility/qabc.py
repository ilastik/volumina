"""
Wraps stdlib abc module to provide convenience classes for defining QObject interfaces
"""

from abc import ABCMeta, abstractmethod

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


class QABCMeta(type(QObject), ABCMeta):
    pass


class QABC(metaclass=QABCMeta):
    pass

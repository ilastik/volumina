###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
# 		   http://ilastik.org/license/
###############################################################################
from PyQt5.QtCore import pyqtSignal
from future.utils import with_metaclass
from volumina.utility.abc import ABCMeta, ABC, abstractmethod, abstractproperty


def _has_attribute(cls, attr):
    return True if any(attr in B.__dict__ for B in cls.__mro__) else False


def _has_attributes(cls, attrs):
    return True if all(_has_attribute(cls, a) for a in attrs) else False


# *******************************************************************************
# R e q u e s t A B C                                                          *
# *******************************************************************************


class RequestABC(with_metaclass(ABCMeta, object)):
    @abstractmethod
    def wait(self):
        """waits until completion and returns result"""

    @classmethod
    def __subclasshook__(cls, C):
        if cls is RequestABC:
            return True if _has_attributes(C, ["wait"]) else False
        return NotImplemented


# *******************************************************************************
# S o u r c e A B C                                                            *
# *******************************************************************************


class SourceABC(with_metaclass(ABCMeta, object)):
    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)

    @abstractproperty
    def numberOfChannels(self):
        raise NotImplementedError

    @abstractmethod
    def request(self, slicing):
        pass

    @abstractmethod
    def setDirty(self, slicing):
        pass

    @classmethod
    def __subclasshook__(cls, C):
        if cls is SourceABC:
            return True if _has_attributes(C, ["request", "setDirty"]) else False
        return NotImplemented

    @abstractmethod
    def __eq__(self, other):
        raise NotImplementedError

    @abstractmethod
    def __ne__(self, other):
        raise NotImplementedError

    @abstractmethod
    def clean_up(self):
        pass

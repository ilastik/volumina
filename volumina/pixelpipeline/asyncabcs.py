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
from volumina.utility.abc import ABCMeta, ABC, QABC, abstractmethod, abstractproperty, abstractsignal


# *******************************************************************************
# R e q u e s t A B C                                                          *
# *******************************************************************************


class RequestABC(ABC):
    @abstractmethod
    def wait(self):
        """waits until completion and returns result"""


class ImageSourceABC(QABC):
    isDirty = abstractsignal(object)

    @abstractmethod
    def request(self, slicing, along_through=None):
        pass

    @abstractmethod
    def setDirty(self, slicing):
        pass


class ISlice2DSource(QABC):
    isDirty = abstractsignal(object)

    @abstractmethod
    def request(self, slicing, along_through=None):
        pass

    @abstractmethod
    def setDirty(self, slicing):
        pass

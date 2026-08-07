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
from __future__ import annotations
from abc import ABC, abstractmethod

import numpy.typing as npt

from volumina.utility.qabc import QABC, abstractsignal


__all__ = ["DataSourceABC", "RequestABC", "ImageSourceABC", "PlanarSliceSourceABC", "IndeterminateRequestError"]


Slice5D = tuple[slice, slice, slice, slice, slice]


class RequestABC(ABC):
    @abstractmethod
    def wait(self):
        """waits until completion and returns result"""


class DataRequestABC(RequestABC):
    _slicing: Slice5D  # should be set in init

    @property
    def slicing(self) -> Slice5D:
        """5D slicing that was used to construct the request"""
        return self._slicing


class ImageSourceABC(QABC):
    """
    Allows to retrieve renderable object (QImage or QGraphicsItem)
    for given 2D slice
    """

    isDirty = abstractsignal(object)

    @abstractmethod
    def request(self, slicing, along_through=None):
        pass

    @abstractmethod
    def setDirty(self, slicing):
        pass

    @property
    @abstractmethod
    def priority(self) -> int: ...


class PlanarSliceSourceABC(QABC):
    """
    Provides a way to retrieve 2D slices of ND array
    """

    isDirty = abstractsignal(object)

    @abstractmethod
    def request(self, slicing, along_through=None):
        pass

    @abstractmethod
    def setDirty(self, slicing):
        pass


class IndeterminateRequestError(Exception):
    """
    Raised if a request cannot be created or cannot be executed
    because its underlying datasource is in an indeterminate state.
    In such cases, the requester should simply ignore the error.
    The datasource has the responsibility of sending a dirty notification
    when the source is ready again.
    """

    pass


class DataSourceABC(QABC):
    isDirty = abstractsignal(object)
    numberOfChannelsChanged = abstractsignal(int)

    @property
    @abstractmethod
    def numberOfChannels(self) -> int: ...

    @abstractmethod
    def request(self, slicing: Slice5D) -> DataRequestABC: ...

    @abstractmethod
    def dtype(self) -> npt.DTypeLike: ...

    @abstractmethod
    def __eq__(self, other: DataSourceABC): ...

    @abstractmethod
    def __ne__(self, other: DataSourceABC): ...

    @abstractmethod
    def clean_up(self) -> None: ...

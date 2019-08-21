from __future__ import annotations

import numpy as np

from volumina.utility.abc import QABC, ABC, abstractsignal, abstractproperty, abstractmethod


__all__ = ["IDataSource", "IDataRequest", "IndeterminateRequestError"]


class IndeterminateRequestError(Exception):
    """
    Raised if a request cannot be created or cannot be executed
    because its underlying datasource is in an indeterminate state.
    In such cases, the requester should simply ignore the error.
    The datasource has the responsibility of sending a dirty notification
    when the source is ready again.
    """

    pass


class IDataRequest(ABC):
    @abstractmethod
    def wait(self) -> np.ndarray:
        """waits until completion and returns result"""


class IDataSource(QABC):
    isDirty = abstractsignal(object)
    numberOfChannelsChanged = abstractsignal(int)

    @abstractproperty
    def numberOfChannels(self) -> int:
        ...

    @abstractmethod
    def request(self, slicing) -> IDataRequest:
        ...

    @abstractmethod
    def __eq__(self, other: IDataSource):
        ...

    @abstractmethod
    def __ne__(self, other: IDataSource):
        ...

    @abstractmethod
    def clean_up(self) -> None:
        ...

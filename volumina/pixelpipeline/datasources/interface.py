from __future__ import annotations

from volumina.pixelpipeline.asyncabcs import RequestABC as IRequest
from volumina.utility.abc import QABC, abstractsignal, abstractproperty, abstractmethod


__all__ = ["IDataSource", "IRequest", "IndeterminateRequestError"]


class IndeterminateRequestError(Exception):
    """
    Raised if a request cannot be created or cannot be executed
    because its underlying datasource is in an indeterminate state.
    In such cases, the requester should simply ignore the error.
    The datasource has the responsibility of sending a dirty notification
    when the source is ready again.
    """

    pass


class IDataSource(QABC):
    isDirty = abstractsignal(object)
    numberOfChannelsChanged = abstractsignal(int)

    @abstractproperty
    def numberOfChannels(self) -> int:
        ...

    @abstractmethod
    def request(self, slicing) -> IRequest:
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

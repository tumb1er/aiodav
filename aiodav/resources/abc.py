# coding: utf-8
import typing
from abc import ABC, abstractmethod, abstractproperty
from collections import OrderedDict


class AbstractResource(ABC):
    """ Abstract WebDAV Resource."""

    def __init__(self, prefix: str, path: str='/'):
        """
        :param prefix: WebDAV root prefix in aiodav mounts
        :param path: relative path for concrete WebDAV resource
        """
        self._prefix = prefix
        self._path = path

    @property
    def prefix(self):
        return self._prefix

    @property
    def path(self):
        return self._path

    @abstractproperty
    def name(self) -> str:
        raise NotImplementedError()  # pragma: no cover

    @abstractproperty
    def size(self) -> int:
        raise NotImplementedError()  # pragma: no cover 

    @abstractproperty
    def parent(self) -> 'AbstractResource':
        raise NotImplementedError()  # pragma: no cover 

    @abstractproperty
    def is_collection(self):
        raise NotImplementedError()  # pragma: no cover 

    @abstractproperty
    def collection(self)-> typing.List['AbstractResource']:
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    def propfind(self, *props) -> OrderedDict:
        raise NotImplementedError()  # pragma: no cover

    @abstractmethod
    def with_relative(self, relative) -> 'AbstractResource':
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def populate_props(self):
        """
        :raises: aiodav.resources.errors.ResourceDoesNotExist
        """
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def populate_collection(self):
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def get_content(self, write: typing.Callable[[bytes], typing.Any],
                          *, offset: int=None, limit: int=None):
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def make_collection(self, collection: str) -> 'AbstractResource':
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def move(self, destination: str) -> bool:
        raise NotImplementedError()  # pragma: no cover 

    def __truediv__(self, other: str) -> 'AbstractResource':
        return self.with_relative(other)

    @abstractmethod
    async def put_content(self, read_some: typing.Awaitable[bytes]) -> bool:
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def delete(self):
        raise NotImplementedError()  # pragma: no cover 

    @abstractmethod
    async def copy(self, destination: str) -> 'AbstractResource':
        raise NotImplementedError()  # pragma: no cover 

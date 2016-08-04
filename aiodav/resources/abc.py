# coding: utf-8
from abc import ABC, abstractmethod, abstractproperty
from collections import OrderedDict
import typing

import collections


class AbstractResource(ABC):
    """ Abstract WebDAV Resource."""

    @abstractmethod
    def propfind(self, *props) -> OrderedDict:
        raise NotImplementedError()

    def __init__(self, prefix: str, path: str='/'):
        """
        :param prefix: WebDAV root prefix in aiodav mounts
        :param path: relative path for concrete WebDAV resource
        :param kw: other init kwargs
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
        raise NotImplementedError()

    @abstractproperty
    def size(self) -> int:
        raise NotImplementedError()

    @abstractproperty
    def parent(self) -> 'AbstractResource':
        raise NotImplementedError()

    @abstractproperty
    def is_collection(self):
        raise NotImplementedError()

    @abstractproperty
    def collection(self)-> typing.List['AbstractResource']:
        raise NotImplementedError()

    @abstractmethod
    def with_relative(self, relative) -> 'AbstractResource':
        raise NotImplementedError()

    @abstractmethod
    async def populate_props(self):
        raise NotImplementedError()

    @abstractmethod
    async def populate_collection(self):
        raise NotImplementedError()

    def __truediv__(self, other: str) -> 'AbstractResource':
        return self.with_relative(other)

# coding: utf-8
import os
import typing
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import stat

from aiodav.resources import AbstractResource


class FileSystemResource(AbstractResource):

    def __init__(self, prefix, path: str = '/',
                 root_dir=os.path.expanduser('~')):
        assert '..' not in path, 'relative navigation is restricted'
        path = path.lstrip('/')
        super().__init__(prefix, path)
        self._root_dir = Path(root_dir)
        self._stat = None
        self._collection = None
        self._parent = None

    @property
    def name(self) -> str:
        return self.absolute.name

    @property
    def size(self) -> int:
        return self._stat.st_size

    @property
    def parent(self) -> 'FileSystemResource':
        if self._parent:
            return self._parent
        if self.absolute == self._root_dir:
            self._parent = None
        else:
            path = str(self.absolute.parent.relative_to(self._root_dir))
            self._parent = self.__class__(self.prefix, path,
                                          root_dir=self._root_dir)
        return self._parent

    @property
    def absolute(self) -> Path:
        return self._root_dir.joinpath(self._path)

    @property
    def is_collection(self):
        return stat.S_ISDIR(self._stat.st_mode)

    @property
    def collection(self) -> typing.Iterable['FileSystemResource']:
        return self._collection

    def with_relative(self, relative):
        path = Path(self._path) / relative
        new = self.__class__(self.prefix, str(path), root_dir=self._root_dir)
        return new

    async def populate_props(self):
        self._stat = os.stat(str(self.absolute))

    async def populate_collection(self):
        self._collection = []
        collections = []
        files = []
        for child in self.absolute.iterdir():
            relative = self.with_relative(child.relative_to(self.absolute))
            if child.is_dir():
                collections.append(relative)
            else:
                files.append(relative)
        self._collection.extend(sorted(collections, key=lambda r: r.name))
        self._collection.extend(sorted(files, key=lambda r: r.name))

    def propfind(self, *props) -> OrderedDict:
        ctime = datetime.fromtimestamp(self._stat.st_ctime).strftime('%Y-%m-%dT%H:%M:%SZ')
        mtime = datetime.fromtimestamp(self._stat.st_mtime).strftime('%Y-%m-%dT%H:%M:%SZ')
        return OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', mtime),
            ('getcontentlength', self._stat.st_size),
            ('getetag', ''),
            ('creationdate', ctime),
            ('displayname', self.prefix),
        ])

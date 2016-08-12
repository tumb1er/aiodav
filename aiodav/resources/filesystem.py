# coding: utf-8
import asyncio
import os
import shutil
import typing
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
import stat

from aiodav.resources import AbstractResource, errors


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
        try:
            self._stat = os.stat(str(self.absolute))
        except FileNotFoundError:
            raise errors.ResourceDoesNotExist()

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
        fmt = '%Y-%m-%dT%H:%M:%SZ'
        ctime = datetime.fromtimestamp(self._stat.st_ctime).strftime(fmt)
        mtime = datetime.fromtimestamp(self._stat.st_mtime).strftime(fmt)
        all_props = OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', mtime),
            ('getcontentlength', self._stat.st_size),
            ('getetag', ''),
            ('creationdate', ctime),
            ('displayname', self.name),
        ])
        if not props:
            return all_props

        return OrderedDict(p for p in all_props.items() if p[0] in props)

    async def get_content(self, write: typing.Callable[[bytes], typing.Any],
                          *, offset: int=None, limit: int=None):
        with self.absolute.open('rb') as f:
            if offset:
                f.seek(offset)
            block_size = 1024**2
            if not limit:
                limit = None
            while True:
                if limit is not None:
                    buffer = f.read(min(block_size, limit))
                else:
                    buffer = f.read(block_size)
                write(buffer)
                if limit is not None:
                    limit -= len(buffer)
                if len(buffer) < block_size:
                    break

    async def make_collection(self, collection: str) -> 'AbstractResource':
        new_path = self.absolute / collection
        new_path.mkdir(exist_ok=True)

        path = str(new_path.relative_to(self._root_dir))
        return self.__class__(self.prefix, path, root_dir=self._root_dir)

    async def move(self, destination: str) -> bool:
        new_resource = self.__class__(self.prefix, destination,
                                      root_dir=self._root_dir)
        created = not new_resource.absolute.exists()
        self.absolute.rename(new_resource.absolute)
        self._path = new_resource.path
        return created

    async def put_content(self, read_some: typing.Awaitable[bytes]) -> bool:
        created = not self.absolute.exists()
        mode = 'wb' if created else 'r+b'
        with self.absolute.open(mode) as f:
            while read_some:
                buffer = await read_some()
                f.write(buffer)
                if not buffer:
                    return

    async def delete(self):
        self.absolute.unlink()

    async def copy(self, destination: str) -> 'AbstractResource':
        new_resource = self.__class__(self.prefix, destination,
                                      root_dir=self._root_dir)

        if not self.is_collection:
            shutil.copy(str(self.absolute), str(new_resource.absolute))
            await new_resource.populate_props()
        else:
            shutil.copytree(str(self.absolute), str(new_resource.absolute))
            await new_resource.populate_props()
            await new_resource.populate_collection()
        return new_resource



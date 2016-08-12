# coding: utf-8
import os
import typing
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime
from io import BytesIO

from aiodav.resources import AbstractResource


class DummyResource(AbstractResource):
    _root = None

    def __init__(self, prefix: str, path: str = '/', is_collection=True,
                 parent=None, ctime=None, mtime=None):
        super().__init__(prefix, path)
        if path == '/':
            if self._root:
                raise ValueError("Second _root")
            self.__class__._root = self
        self._is_directory = is_collection
        if not is_collection:
            self.content = BytesIO()
        else:
            self.resources = {}
        self._parent = parent
        self._ctime = ctime or datetime.now()
        self._mtime = mtime or datetime.now()

    async def write_content(self, write: typing.Callable[[bytes], typing.Any],
                            *, offset: int=None, limit: int=None):
        self.content.seek(offset)
        buffer = self.content.read(limit)
        await write(buffer)

    def with_relative(self, relative) -> 'AbstractResource':
        res = self
        for part in relative.split('/'):
            res = res.resources[part]
        return res

    @property
    def size(self) -> int:
        if self.is_collection:
            return 0
        return len(self.content.getbuffer())

    async def put_content(self, read_some: typing.Awaitable[bytes]) -> bool:
        while read_some:
            buffer = await read_some()
            self.content.write(buffer)
            if not buffer:
                return

    def propfind(self, *props) -> OrderedDict:
        fmt = '%Y-%m-%dT%H:%M:%SZ'
        ctime = self._ctime.strftime(fmt)
        mtime = self._mtime.strftime(fmt)
        all_props = OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', mtime),
            ('getcontentlength', self.size),
            ('getetag', ''),
            ('creationdate', ctime),
            ('displayname', self.name),
        ])
        if not props:
            return all_props
        return OrderedDict(p for p in all_props.items() if p[0] in props)

    async def populate_props(self):
        return

    async def populate_collection(self):
        return

    @property
    def parent(self) -> 'AbstractResource':
        return self._parent

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    async def move(self, destination: str) -> bool:
        dest_resource = self._root.with_relative(destination)
        self._parent = dest_resource
        return True

    def make_collection(self, collection: str) -> 'AbstractResource':
        dirname = os.path.dirname(collection)
        parent = self._root.with_relative(dirname)
        collection = DummyResource(prefix=self.prefix, path=collection,
                                   parent=parent)
        return collection

    @property
    def is_collection(self):
        return self._is_directory

    async def delete(self):
        del self._parent.resources[self.name]

    async def copy(self, destination: str) -> 'AbstractResource':
        new = self._clone()
        await new.move(destination)
        return new

    @property
    def collection(self) -> typing.List['AbstractResource']:
        result = []
        for k in sorted(self.resources.keys()):
            result.append(self.resources[k])
        return result

    def _clone(self):
        new = DummyResource(prefix=self.prefix, path=self.path,
                            is_collection=self.is_collection,
                            parent=self._parent)
        if new.is_collection:
            new.resources = deepcopy(self.resources)
        else:
            new.content = BytesIO(self.content.getvalue())
        return new

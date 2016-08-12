# coding: utf-8
import os
import typing
from collections import OrderedDict
from datetime import datetime
from io import BytesIO

from aiodav.resources import AbstractResource, errors


class DummyResource(AbstractResource):
    _root = None

    def __init__(self, prefix: str, path: str = '/', is_collection=True,
                 parent=None, ctime=None, mtime=None, exists=None):
        super().__init__(prefix, path)
        if path == '/':
            self._exists = True
            if self._root:
                raise ValueError("Second _root")
            self.__class__._root = self
        else:
            self._exists = exists
        self._is_directory = is_collection
        if self._exists:
            if not is_collection:
                self._content = BytesIO()
            else:
                self._resources = {}
        self._parent = parent

        self._ctime = ctime or datetime.now()
        self._mtime = mtime or datetime.now()

    def _touch_file(self):
        if not self.parent:
            raise errors.ResourceDoesNotExist("Parent resource does not exist")
        if not self.parent.is_collection:
            raise errors.InvalidResourceType("Collection expected")
        # noinspection PyProtectedMember
        self._parent._resources[self.name] = self
        self._exists = True
        self._content = BytesIO()
        self._is_directory = False

    async def get_content(self, write: typing.Callable[[bytes], typing.Any],
                          *, offset: int=0, limit: int=None):
        if self._is_directory:
            raise errors.InvalidResourceType("file resource expected")
        self._content.seek(offset)
        buffer = self._content.read(limit)
        await write(buffer)

    def with_relative(self, relative) -> 'AbstractResource':
        if relative == '/':
            return self
        res = self
        parts = relative.strip('/').split('/')
        for part in parts[:-1]:
            try:
                res = res._resources[part]
            except KeyError:
                raise errors.ResourceDoesNotExist(
                    "one of parent resources does not exist")
        part = parts[-1]
        try:
            if not res.is_collection:
                raise errors.InvalidResourceType("collection expected")
            res = res._resources[part]
        except KeyError:
            res = DummyResource(self.prefix, os.path.join(res.path, part),
                                parent=res, exists=False)
        return res

    @property
    def size(self) -> int:
        if self.is_collection:
            return 0
        return len(self._content.getvalue())

    async def put_content(self, read_some: typing.Awaitable[bytes]) -> bool:
        if self._exists:
            if self.is_collection:
                raise errors.InvalidResourceType("file resource expected")
        else:
            self._touch_file()

        self._content.seek(0)
        self._content.truncate()
        while read_some:
            buffer = await read_some()
            self._content.write(buffer)
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
        if not self._exists:
            raise errors.ResourceDoesNotExist()
        return

    async def populate_collection(self):
        if not self._exists:
            raise errors.ResourceDoesNotExist()
        return

    @property
    def parent(self) -> 'AbstractResource':
        return self._parent

    @property
    def name(self) -> str:
        return os.path.basename(self.path)

    # noinspection PyProtectedMember
    async def move(self, destination: str) -> bool:
        del self._parent._resources[self.name]
        dest_resource = self._root.with_relative(destination)
        if not dest_resource._exists:
            self._path = dest_resource.path
            dest_resource = dest_resource._parent
        self._parent = dest_resource
        self._path = os.path.join(self._parent.path, self.name)
        dest_resource._resources[self.name] = self
        return True

    async def make_collection(self, collection: str) -> 'AbstractResource':
        collection = collection.strip('/')
        parent = os.path.dirname(collection)
        name = os.path.basename(collection)
        if not parent:
            parent = self
        else:
            parent = self._root.with_relative(parent)

        if not parent.is_collection:
            raise errors.InvalidResourceType("collection expected")
        # noinspection PyProtectedMember
        if name in parent._resources:
            raise errors.ResourceAlreadyExists("collection already exists")
        collection = DummyResource(prefix=self.prefix,
                                   path=os.path.join(parent.path, collection),
                                   parent=parent, is_collection=True,
                                   exists=True)
        # noinspection PyProtectedMember
        parent._resources[name] = collection
        return collection

    @property
    def is_collection(self):
        return self._is_directory

    async def delete(self):
        if not self._exists:
            raise errors.ResourceDoesNotExist()
        # noinspection PyProtectedMember
        del self._parent._resources[self.name]

    # noinspection PyProtectedMember
    async def copy(self, destination: str) -> 'AbstractResource':
        if not self.is_collection:
            return self._copy_file(destination)

        dest = self._root / destination.strip('/')
        if not dest.is_collection:
            raise errors.InvalidResourceType("collection expected")
        if not dest._exists:
            name = dest.name
            dest = dest._parent
        else:
            name = self.name
        new_dir = self._clone()
        new_dir._parent = dest
        dest._resources[name] = new_dir
        new_dir._path = os.path.join(dest.path, name)
        for res in self.collection:
            await res.copy(new_dir.path)
        return new_dir

    # noinspection PyProtectedMember
    def _copy_file(self, destination: str) -> 'AbstractResource':
        dest = self._root / destination.strip('/')
        if dest._exists:
            if not dest.is_collection:
                raise errors.ResourceAlreadyExists(
                    "destination file already exists")
            parent = dest
            name = self.name
        else:
            parent = dest._parent
            name = dest.name

        new_file = self._clone()
        new_file._parent = parent
        new_file._path = os.path.join(parent.path, name)
        parent._resources[name] = new_file
        return new_file

    @property
    def collection(self) -> typing.List['AbstractResource']:
        result = []
        for k in sorted(self._resources.keys()):
            result.append(self._resources[k])
        return result

    def _clone(self):
        new = DummyResource(prefix=self.prefix, path=self.path,
                            is_collection=self.is_collection,
                            parent=self._parent, exists=self._exists)
        if new.is_collection:
            new._resources = {}
        else:
            new._content = BytesIO(self._content.getvalue())
        return new

    def __repr__(self):
        return "Dummy<%s>" % self.path  # pragma: no cover

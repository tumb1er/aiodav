# coding: utf-8
from io import BytesIO
from unittest import TestCase
from collections import OrderedDict
import asyncio

from aiohttp_tests import async_test
from aiodav.resources.dummy import DummyResource
from aiodav.resources import errors


def format_time(t):
    return t.replace(microsecond=0).isoformat() + 'Z'


@async_test
class DummyBackendTestCase(TestCase):
    Resource = DummyResource

    @classmethod
    def setUpClass(cls):
        cls.root = cls.Resource('prefix')

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.root._resources.clear()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    async def testEmptyList(self):
        await self.root.populate_collection()
        result = self.root.collection
        self.assertListEqual(result, [])

    async def testMissingResource(self):
        res = self.root / 'unexistent'
        with self.assertRaises(errors.ResourceDoesNotExist):
            await res.populate_props()
        with self.assertRaises(errors.ResourceDoesNotExist):
            await res.populate_collection()

    async def testAddFileResource(self):
        file_resource = self.root / 'filename.txt'
        self.assertIsInstance(file_resource, self.Resource)
        self.assertEqual(file_resource.name, 'filename.txt')
        self.assertEqual(file_resource.path, '/filename.txt')
        self.assertEqual(file_resource.prefix, self.root.prefix)
        self.assertListEqual(self.root.collection, [])

        with self.assertRaises(errors.ResourceDoesNotExist):
            await file_resource.populate_props()

        await self.fill_file(file_resource)
        self.assertListEqual(self.root.collection, [file_resource])

        self.assertIs(file_resource.parent, self.root)
        self.assertIn(file_resource.name, self.root._resources)
        self.assertIs(file_resource, self.root._resources[file_resource.name])
        self.assertFalse(file_resource.is_collection)

        await file_resource.populate_props()

        content = await self.read_file(file_resource)

        self.assertEqual(content, b'CONTENT')

    @staticmethod
    async def read_file(resource):
        content = BytesIO()

        async def write(data):
            content.write(data)

        await resource.get_content(write)
        content = content.getvalue()
        return content

    async def testAddFileWriteAlreadyExists(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)

        new_resource = self.root / 'filename.txt'

        await self.fill_file(new_resource, content=b'NEW_CONTENT')

        content = await self.read_file(file_resource)
        self.assertEqual(content, b'NEW_CONTENT')

    @staticmethod
    async def fill_file(file_resource, content=None):
        content = content or b'CONTENT'

        def chunks():
            yield content
            yield b''

        c = iter(chunks())

        async def read_any():
            return next(c)

        await file_resource.put_content(read_any)

    def testRootRelativeToRoot(self):
        self.assertIs(self.root.with_relative('/'), self.root)

    async def testAddCollection(self):
        resource = await self.root.make_collection('dir')
        self.assertIsInstance(resource, self.Resource)
        self.assertEqual(resource.name, 'dir')
        self.assertEqual(resource.path, '/dir')
        self.assertEqual(resource.prefix, self.root.prefix)
        self.assertIs(resource.parent, self.root)
        self.assertTrue(resource.is_collection)
        self.assertListEqual(self.root.collection, [resource])

    async def testPropfind(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        props = file_resource.propfind()
        self.assertDictEqual(props, OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', format_time(file_resource._mtime)),
            ('getcontentlength', len(b'CONTENT')),
            ('getetag', ''),
            ('creationdate', format_time(file_resource._ctime)),
            ('displayname', 'filename.txt'),
        ]))

    async def testPropfindList(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        props = file_resource.propfind('getcontenttype', 'getlastmodified')

        self.assertDictEqual(props, OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', format_time(file_resource._mtime))
        ]))

    async def testPutContentOnCollection(self):
        resource = await self.root.make_collection('dir')

        with self.assertRaises(errors.InvalidResourceType):
            await self.fill_file(resource)

    async def testMakeCollectionTwice(self):
        await self.root.make_collection('dir')

        with self.assertRaises(errors.ResourceAlreadyExists):
            await self.root.make_collection('dir')

    async def testMakeCollectionInFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)

        with self.assertRaises(errors.InvalidResourceType):
            await self.root.make_collection('filename.txt/dir')

    async def testMakeFileInFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)

        with self.assertRaises(errors.InvalidResourceType):
            file_resource / 'new_file.txt'

    async def testWriteFileInFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        new = self.Resource(prefix=self.root.prefix,
                            path='/filename.txt/new.txt',
                            parent=file_resource,
                            is_collection=False)

        with self.assertRaises(errors.InvalidResourceType):
            await self.fill_file(new)

    async def testWriteOnUnexistentPath(self):
        new = self.Resource(prefix=self.root.prefix,
                            path='/filename.txt/new.txt',
                            is_collection=False)

        with self.assertRaises(errors.ResourceDoesNotExist):
            await self.fill_file(new)

    async def testReadCollectionContent(self):
        resource = await self.root.make_collection('dir')
        with self.assertRaises(errors.InvalidResourceType):
            await self.read_file(resource)

    async def testDeleteUnexistent(self):
        with self.assertRaises(errors.ResourceDoesNotExist):
            new = self.Resource(prefix=self.root.prefix,
                                path='/dir',
                                is_collection=True)
            await new.delete()

    async def testDeleteResource(self):
        res = await self.root.make_collection('dir')
        await res.delete()
        self.assertListEqual(self.root.collection, [])

    async def testMove(self):
        dir1 = await self.root.make_collection('dir')
        dir2 = await self.root.make_collection('dir2')
        await dir2.move('/dir')
        self.assertIs(dir2.parent, dir1)
        self.assertListEqual(self.root.collection, [dir1])
        self.assertListEqual(dir1.collection, [dir2])

    async def testMoveToUnexistent(self):
        dir1 = await self.root.make_collection('dir')
        dir2 = await self.root.make_collection('dir2')
        await dir2.move('/dir/new_dir')
        self.assertIs(dir2.parent, dir1)
        self.assertEqual(dir2.path, '/dir/new_dir')
        self.assertListEqual(self.root.collection, [dir1])
        self.assertListEqual(dir1.collection, [dir2])

    async def testCopyFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        new_file = await file_resource.copy('/copy.txt')
        self.assertEqual(new_file.path, '/copy.txt')
        self.assertIs(new_file.parent, self.root)
        content = await self.read_file(new_file)
        self.assertEqual(content, b'CONTENT')
        self.assertListEqual(self.root.collection, [new_file, file_resource])

    async def testCopyFileAlreadyExists(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        with self.assertRaises(errors.ResourceAlreadyExists):
            await file_resource.copy('/filename.txt')

    async def testCopyFileToCollection(self):
        dir = await self.root.make_collection('dir')
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        new_file = await file_resource.copy('/dir/copy.txt')
        self.assertEqual(new_file.path, '/dir/copy.txt')
        self.assertIs(new_file.parent, dir)
        content = await self.read_file(new_file)
        self.assertEqual(content, b'CONTENT')
        self.assertListEqual(self.root.collection, [dir, file_resource])
        self.assertListEqual(dir.collection, [new_file])

    async def testCopyDir(self):
        dir = await self.root.make_collection('dir')
        f1 = dir / 'filename.txt'
        await self.fill_file(f1)
        d1 = await dir.make_collection('dir2')

        new_dir = await dir.copy('/dircopy')

        self.assertEqual(new_dir.path, '/dircopy')
        self.assertIs(new_dir.parent, self.root)
        self.assertListEqual(self.root.collection, [dir, new_dir])
        self.assertListEqual(dir.collection, [d1, f1])
        self.assertEqual(d1.path, '/dir/dir2')
        self.assertEqual(f1.path, '/dir/filename.txt')

        new_names = [r.name for r in new_dir.collection]
        self.assertListEqual(new_names, [d1.name, f1.name])

    async def testCopyDirToFile(self):
        dir = await self.root.make_collection('dir')
        f1 = dir / 'filename.txt'
        await self.fill_file(f1)
        with self.assertRaises(errors.InvalidResourceType):
            await dir.copy(f1.path)

    async def testCopyFileToUnexistentDest(self):
        f1 = self.root / 'filename.txt'
        await self.fill_file(f1)
        with self.assertRaises(errors.ResourceDoesNotExist):
            await f1.copy('/dir/f2.txt')


    def testCollectionSize(self):
        props = self.root.propfind('getcontentlength')
        self.assertEqual(props['getcontentlength'], 0)

    async def testNestedRelative(self):
        d1 = await self.root.make_collection('dir1')
        d2 = await d1.make_collection('dir2')
        d3 = await d2.make_collection('dir3')

        self.assertEqual(d3.path, '/dir1/dir2/dir3')
        self.assertIs(self.root / 'dir1' / 'dir2' / 'dir3', d3)
        self.assertIs(self.root / 'dir1/dir2/dir3', d3)

    def testSecondRootDeny(self):
        with self.assertRaises(ValueError):
            self.Resource('prefix')

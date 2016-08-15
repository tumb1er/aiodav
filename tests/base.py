# coding: utf-8
import asyncio
from collections import OrderedDict
from io import BytesIO

from aiohttp_tests import async_test

from aiodav.resources import errors
from tests.helpers import format_time


# noinspection PyPep8Naming,PyAttributeOutsideInit
@async_test
class BackendTestsMixin(object):

    @classmethod
    def setUpClass(cls):
        cls.root = cls.create_resource('prefix')

    @classmethod
    def create_resource(cls, *args, **kwargs):
        return cls.Resource(*args, **kwargs)

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

    def tearDown(self):
        self.loop.close()

    @staticmethod
    async def populate(*resources):
        for res in resources:
            await res.populate_props()
            if res.is_collection:
                await res.populate_collection()
                for r in res.collection:
                    await r.populate_props()

    async def testEqMethod(self):
        d1 = await self.root.make_collection('dir1')
        d2 = await self.root.make_collection('dir2')
        f1 = self.root / 'f1.txt'
        f2 = self.root / 'f2.txt'
        await self.fill_file(f1)
        await self.fill_file(f2)

        self.assertFalse(d1 == d2)
        self.assertFalse(f1 == f2)

        f3 = self.root / 'f1.txt'
        await self.populate(f1, f3)
        self.assertTrue(f3 == f1)

        d3 = self.root / 'dir1'
        await self.populate(d1, d3)
        self.assertTrue(d3 == d1)

        await d1.delete()

        d4 = self.root / 'dir1'
        await self.fill_file(d4)

        await self.populate(d4)
        self.assertFalse(d4 == d1)

        self.assertFalse(d1 == 3)
        self.assertFalse(f1 == 3)

    def testRootParent(self):
        self.assertIsNone(self.root.parent)

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
        await self.root.populate_collection()
        self.assertListEqual(self.root.collection, [])

        with self.assertRaises(errors.ResourceDoesNotExist):
            await file_resource.populate_props()

        await self.fill_file(file_resource)
        await self.populate(self.root, file_resource, file_resource.parent)
        self.assertListEqual(self.root.collection, [file_resource])
        self.assertResourcesEqual(file_resource.parent, self.root)
        resources = {r.name: r for r in self.root.collection}
        self.assertIn(file_resource.name, resources)
        self.assertResourcesEqual(file_resource, resources[file_resource.name])
        self.assertFalse(file_resource.is_collection)

        content = await self.read_file(file_resource)

        self.assertEqual(content, b'CONTENT')

    def assertResourcesEqual(self, first, second):
        self.assertIs(first, second)

    @staticmethod
    async def read_file(resource, offset=0, limit=None):
        content = BytesIO()

        async def write(data):
            content.write(data)

        await resource.get_content(write, offset=offset, limit=limit)
        content.seek(0)
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

    async def testRootRelativeToRoot(self):
        root = self.root.with_relative('/')
        await self.populate(root, self.root)
        self.assertResourcesEqual(root, self.root)

    async def testAddCollection(self):
        resource = await self.root.make_collection('dir')
        self.assertIsInstance(resource, self.Resource)
        self.assertEqual(resource.name, 'dir')
        self.assertEqual(resource.path, '/dir')
        self.assertEqual(resource.prefix, self.root.prefix)
        await self.populate(self.root, resource, resource.parent)
        self.assertResourcesEqual(resource.parent, self.root)
        self.assertTrue(resource.is_collection)
        self.assertListEqual(self.root.collection, [resource])

    async def testMakeFileInFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)

        with self.assertRaises(errors.InvalidResourceType):
            res = file_resource / 'new_file.txt'
            await self.fill_file(res)

    async def testPropfind(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        await file_resource.populate_props()
        props = file_resource.propfind()
        self.assertDictEqual(props, OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', format_time(file_resource.mtime)),
            ('getcontentlength', len(b'CONTENT')),
            ('getetag', ''),
            ('creationdate', format_time(file_resource.ctime)),
            ('displayname', 'filename.txt'),
        ]))

    async def testPropfindList(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        await file_resource.populate_props()
        props = file_resource.propfind('getcontenttype', 'getlastmodified')

        self.assertDictEqual(props, OrderedDict([
            ('getcontenttype', ''),
            ('getlastmodified', format_time(file_resource.mtime))
        ]))

    async def testReadLarge(self):
        file_resource = self.root / 'filename.txt'
        expected = b'A' * 2 * 1024**2
        await self.fill_file(file_resource, content=expected)
        content = await self.read_file(file_resource)
        self.assertEqual(content, expected)

    async def testReadOffset(self):
        file_resource = self.root / 'filename.txt'
        expected = b''.join([
            b'A' * 100,
            b'CONTENT',
            b'B' * 100
        ])
        await self.fill_file(file_resource, content=expected)
        content = await self.read_file(file_resource, offset=100)
        self.assertEqual(content, expected[100:])

    async def testReadOffsetLimit(self):
        file_resource = self.root / 'filename.txt'
        expected = b''.join([
            b'A' * 100,
            b'CONTENT',
            b'B' * 100
        ])
        await self.fill_file(file_resource, content=expected)
        content = await self.read_file(file_resource, offset=100, limit=7)
        self.assertEqual(content, expected[100:107])

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

    async def testWriteFileInFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)

        new = self.create_resource(prefix=self.root.prefix,
                                   path='/filename.txt/new.txt')

        with self.assertRaises(errors.InvalidResourceType):
            await self.fill_file(new)

    async def testWriteOnUnexistentPath(self):
        new = self.create_resource(prefix=self.root.prefix,
                                   path='/filename.txt/new.txt')

        with self.assertRaises(errors.ResourceDoesNotExist):
            await self.fill_file(new)

    async def testReadCollectionContent(self):
        resource = await self.root.make_collection('dir')
        with self.assertRaises(errors.InvalidResourceType):
            await self.read_file(resource)

    async def testDeleteUnexistent(self):
        with self.assertRaises(errors.ResourceDoesNotExist):
            new = self.create_resource(prefix=self.root.prefix,
                                       path='/dir')
            await new.delete()

    async def testDeleteResource(self):
        res = await self.root.make_collection('dir')
        await res.delete()
        await self.populate(self.root)
        self.assertListEqual(self.root.collection, [])

    async def testDeleteFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        await file_resource.delete()
        await self.populate(self.root)
        self.assertListEqual(self.root.collection, [])

    async def testMove(self):
        dir1 = await self.root.make_collection('dir')
        dir2 = await self.root.make_collection('dir2')
        await dir2.move('/dir')
        await self.populate(self.root, dir1, dir2, dir2.parent)
        self.assertResourcesEqual(dir2.parent, dir1)
        self.assertListEqual(self.root.collection, [dir1])
        self.assertListEqual(dir1.collection, [dir2])

    async def testMoveToUnexistent(self):
        dir1 = await self.root.make_collection('dir')
        dir2 = await self.root.make_collection('dir2')
        await dir2.move('/dir/new_dir')
        await self.populate(self.root, dir1, dir2, dir2.parent)
        self.assertResourcesEqual(dir2.parent, dir1)
        self.assertEqual(dir2.path, '/dir/new_dir')
        self.assertListEqual(self.root.collection, [dir1])
        self.assertListEqual(dir1.collection, [dir2])

    async def testCopyFile(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        await file_resource.populate_props()
        new_file = await file_resource.copy('/copy.txt')
        self.assertEqual(new_file.path, '/copy.txt')
        await self.populate(new_file.parent, self.root, new_file, file_resource)
        self.assertResourcesEqual(new_file.parent, self.root)
        content = await self.read_file(new_file)
        self.assertEqual(content, b'CONTENT')
        self.assertListEqual(self.root.collection, [new_file, file_resource])

    async def testCopyFileAlreadyExists(self):
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        with self.assertRaises(errors.ResourceAlreadyExists):
            await file_resource.copy('/filename.txt')

    async def testCopyFileToCollection(self):
        directory = await self.root.make_collection('dir')
        file_resource = self.root / 'filename.txt'
        await self.fill_file(file_resource)
        new_file = await file_resource.copy('/dir/copy.txt')
        self.assertEqual(new_file.path, '/dir/copy.txt')
        await self.populate(new_file, new_file.parent, directory, self.root,
                            file_resource)
        self.assertResourcesEqual(new_file.parent, directory)
        content = await self.read_file(new_file)
        self.assertEqual(content, b'CONTENT')
        self.assertListEqual(self.root.collection, [directory, file_resource])
        self.assertListEqual(directory.collection, [new_file])

    async def testCopyDir(self):
        directory = await self.root.make_collection('dir')
        f1 = directory / 'filename.txt'
        await self.fill_file(f1)
        d1 = await directory.make_collection('dir2')

        new_dir = await directory.copy('/dircopy')

        self.assertEqual(new_dir.path, '/dircopy')
        await self.populate(self.root, directory, new_dir,
                            new_dir.parent, d1, f1)

        self.assertResourcesEqual(new_dir.parent, self.root)
        self.assertListEqual(self.root.collection, [directory, new_dir])
        self.assertListEqual(directory.collection, [d1, f1])
        self.assertEqual(d1.path, '/dir/dir2')
        self.assertEqual(f1.path, '/dir/filename.txt')

        new_names = [r.name for r in new_dir.collection]
        self.assertListEqual(new_names, [d1.name, f1.name])

    async def testCopyDirToFile(self):
        directory = await self.root.make_collection('dir')
        f1 = directory / 'filename.txt'
        await self.fill_file(f1)
        with self.assertRaises(errors.InvalidResourceType):
            await directory.copy(f1.path)

    async def testCopyFileToUnexistentDest(self):
        f1 = self.root / 'filename.txt'
        await self.fill_file(f1)
        with self.assertRaises(errors.ResourceDoesNotExist):
            await f1.copy('/dir/f2.txt')

    async def testCollectionSize(self):
        await self.root.populate_props()
        props = self.root.propfind('getcontentlength')
        self.assertEqual(props['getcontentlength'], 0)

    async def testNestedRelative(self):
        d1 = await self.root.make_collection('dir1')
        d2 = await d1.make_collection('dir2')
        d3 = await d2.make_collection('dir3')

        self.assertEqual(d3.path, '/dir1/dir2/dir3')
        relative = self.root / 'dir1' / 'dir2' / 'dir3'
        await self.populate(relative, d3)
        self.assertResourcesEqual(relative, d3)
        relative = self.root / 'dir1/dir2/dir3'
        await self.populate(relative)
        self.assertResourcesEqual(relative, d3)

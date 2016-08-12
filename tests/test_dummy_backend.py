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
        self.assertEqual(file_resource.prefix, self.root.prefix)
        self.assertIs(file_resource.parent, self.root)

        await self.fill_file(file_resource)

        self.assertFalse(file_resource.is_collection)

        await file_resource.populate_props()

        content = BytesIO()

        async def write(data):
            content.write(data)

        await file_resource.get_content(write)
        self.assertEqual(content.getvalue(), b'CONTENT')

    async def fill_file(self, file_resource):
        def chunks():
            yield b'CONTENT'
            yield b''

        c = iter(chunks())

        async def read_any():
            return next(c)

        await file_resource.put_content(read_any)

    async def testAddCollection(self):
        resource = await self.root.make_collection('dir')
        self.assertIsInstance(resource, self.Resource)
        self.assertEqual(resource.name, 'dir')
        self.assertEqual(resource.path, '/dir')
        self.assertEqual(resource.prefix, self.root.prefix)
        self.assertIs(resource.parent, self.root)
        self.assertTrue(resource.is_collection)

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


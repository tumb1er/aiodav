# coding: utf-8
from lxml import etree as et

from aiodav.views import DAV_METHODS
from aiohttp_tests import BaseTestCase, web, async_test

from aiodav.contrib import setup
from aiodav.resources.dummy import DummyResource
from tests.helpers import fill_file, format_time, read_file


__all__ = ['WebDAVTestCase']


@async_test
class WebDAVTestCase(BaseTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = DummyResource('prefix')

    @classmethod
    def tearDownClass(cls):
        DummyResource._root = None

    def init_app(self, loop):
        app = web.Application(loop=loop)
        setup(app, mounts={'prefix': self.root}, hack_debugtoolbar=False)
        return app

    def tearDown(self):
        super().tearDown()
        self.root._resources.clear()

    def testRootView(self):
        response = self.client.get('/')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'text/html; charset=utf-8')
        self.assertIn('<a href="prefix/">prefix', response.text)

    async def testRootListHTML(self):
        d = await self.root.make_collection('dir')
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/',
                                         headers={'Accept': 'text/html'})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'text/html; charset=utf-8')
        self.assertIn('<a href="/%s%s">%s' % (d.prefix, d.path, d.name),
                      response.text)
        self.assertIn('<a href="/%s%s">%s' % (f.prefix, f.path, f.name),
                      response.text)

    async def testDirListHTML(self):
        d = await self.root.make_collection('dir')
        f = d / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/dir/',
                                         headers={'Accept': 'text/html'})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'text/html; charset=utf-8')
        self.assertIn('<a href="/%s%s">%s' % (f.prefix, f.path, f.name),
                      response.text)

    async def testGetFileHTML(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/filename.txt',
                                         headers={'Accept': 'text/html'})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Type'],
                         'text/html; charset=utf-8')
        self.assertIn('<a href="/%s%s?dl=1">%s' % (f.prefix, f.path, f.name),
                      response.text)

    async def testDownloadFileHTML(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/filename.txt?dl=1',
                                         headers={'Accept': 'text/html'})
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Length'], '7')
        self.assertEqual(response.text, 'CONTENT')

    async def testDownloadFileDAV(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/filename.txt')
        self.assertEqual(response.status, 200)
        self.assertEqual(response.headers['Content-Length'], '7')
        self.assertEqual(response.text, 'CONTENT')

    async def testDownloadDirHTML(self):
        await self.root.make_collection('dir')
        response = await self.client.get('/prefix/dir/?dl=1',
                                         headers={'Accept': 'text/html'})
        self.assertEqual(response.status, 400)

    async def testDownloadDirDAV(self):
        await self.root.make_collection('dir')
        response = await self.client.get('/prefix/dir/')
        self.assertEqual(response.status, 400)

    async def testDownloadFileRange(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/filename.txt',
                                         headers={'Range': 'bytes=3-5'})
        self.assertEqual(response.status, 206)
        data = 'CONTENT'[3: 6]
        self.assertEqual(response.headers['Content-Length'], str(len(data)))
        self.assertEqual(response.text, data)

    async def testDownloadFileRangeTillEOF(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.get('/prefix/filename.txt',
                                         headers={'Range': 'bytes=3-'})
        self.assertEqual(response.status, 206)
        data = 'CONTENT'[3:]
        self.assertEqual(response.headers['Content-Length'], str(len(data)))
        self.assertEqual(response.text, data)

    async def testHeadExistentFile(self):
        f = self.root / 'filename.txt'
        await fill_file(f)

        response = await self.client.request('HEAD', '/prefix/filename.txt')
        self.assertEqual(response.status, 200)
        self.assertFalse(response.text)

    async def testHeadExistentDir(self):
        await self.root.make_collection('dir')

        response = await self.client.request('HEAD', '/prefix/dir')
        self.assertEqual(response.status, 200)
        self.assertFalse(response.text)

    def testHeadUnexistent(self):
        response = self.client.request('HEAD', '/prefix/not_exists')
        self.assertEqual(response.status, 404)
        self.assertFalse(response.text)

    def testOptions(self):
        response = self.client.request('OPTIONS', '/prefix/')
        self.assertEqual(response.headers['DAV'], '1, 2')
        self.assertEqual(response.headers['Allow'], ', '.join(DAV_METHODS))

    def testPostNotAllowed(self):
        response = self.client.request('POST', '/prefix/')
        self.assertEqual(response.status, 405)
        methods = ','.join(sorted(
            DAV_METHODS | {'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'}))
        self.assertEqual(response.headers['Allow'], methods)

    def testUnknownMethodNotAllowed(self):
        response = self.client.request('UNKNOWN', '/prefix/')
        self.assertEqual(response.status, 405)
        methods = ','.join(sorted(
            DAV_METHODS | {'GET', 'HEAD', 'OPTIONS', 'PUT', 'DELETE'}))
        self.assertEqual(response.headers['Allow'], methods)

    def testPropfindCollection(self):
        response = self.client.request('PROPFIND', '/prefix/')
        propstat = self.assertMultiStatusResponse(response, '/prefix/')
        self.assertPropstat(propstat, self.root)

    def testPropfindNotFound(self):
        url = '/prefix/not_found'
        response = self.client.request('PROPFIND', url)
        propstat = self.assertMultiStatusResponse(response, url)
        self.assertPropstat(propstat)

    def testPropfindNotFoundGVFS(self):
        url = '/prefix/not_found'
        response = self.client.request('PROPFIND', url,
                                       headers={'User-Agent': 'gvfs/1.20.3'})
        self.assertEqual(response.status, 404)

    async def testPropfindFile(self):
        f = self.root / 'filename.txt'
        await fill_file(f)
        await f.populate_props()
        url = '/prefix/filename.txt'
        response = await self.client.request('PROPFIND', url)
        propstat = self.assertMultiStatusResponse(response, url)
        self.assertPropstat(propstat, f)

    async def testMakeCollection(self):
        response = await self.client.request('MKCOL', '/prefix/dir')
        self.assertEqual(response.status, 201)
        d = self.root / 'dir'
        await d.populate_props()
        self.assertTrue(d.is_collection)
        self.assertListEqual(self.root.collection, [d])

    def testMakeCollectionInUnexistentPath(self):
        response = self.client.request('MKCOL', '/prefix/not_exists/dir')
        self.assertEqual(response.status, 404)

    async def testMakeCollectionInFile(self):
        f = self.root / 'f.txt'
        await fill_file(f)
        response = await self.client.request('MKCOL', '/prefix/f.txt/dir')
        self.assertEqual(response.status, 400)

    async def testMoveToNewDestination(self):
        d = await self.root.make_collection('dir')
        f = self.root / 'f.txt'
        await fill_file(f)

        headers = {'Destination': '/prefix/dir/f.txt'}
        response = await self.client.request('MOVE', '/prefix/f.txt',
                                             headers=headers)
        self.assertEqual(response.status, 201)
        await d.populate_collection()
        f = self.root / 'dir/f.txt'
        await f.populate_props()
        self.assertListEqual(d.collection, [f])

    async def testMoveToRoot(self):
        f = self.root / 'f.txt'
        await fill_file(f)

        headers = {'Destination': '/prefix/f2.txt'}
        response = await self.client.request('MOVE', '/prefix/f.txt',
                                             headers=headers)
        self.assertEqual(response.status, 201)
        f = self.root / 'f2.txt'
        await self.root.populate_collection()
        await f.populate_props()
        self.assertListEqual(self.root.collection, [f])

    async def testMoveOverwrite(self):
        f1 = self.root / 'f1.txt'
        await fill_file(f1)
        f2 = self.root / 'f2.txt'
        await fill_file(f2, content=b'NEW_CONTENT')

        headers = {'Destination': '/prefix/f2.txt'}
        response = await self.client.request('MOVE', '/prefix/f1.txt',
                                             headers=headers)
        self.assertEqual(response.status, 204)
        await self.root.populate_collection()
        f2 = self.root / 'f2.txt'
        await f2.populate_props()
        self.assertListEqual(self.root.collection, [f2])

        content = await read_file(f2)
        self.assertEqual(content, b'CONTENT')

    async def testPropfindWithDepth(self):
        d = await self.root.make_collection('dir')
        f = self.root / 'f.txt'
        await fill_file(f)
        response = await self.client.request('PROPFIND', '/prefix/',
                                             headers={'Depth': '1'})
        propstat = self.assertMultiStatusResponse(response, '/prefix/',
                                                  child_count=2)
        self.assertPropstat(propstat, self.root)
        responses = propstat.getparent().getparent()
        hrefs = responses.xpath('D:response/D:href', namespaces={'D': 'DAV:'})
        urls = {h.text for h in hrefs}
        self.assertSetEqual(urls, {'/prefix/', '/prefix/dir', '/prefix/f.txt'})
        propstats = responses.xpath('D:response/D:propstat',
                                    namespaces={'D': 'DAV:'})
        self.assertPropstat(propstats[0], self.root)
        self.assertPropstat(propstats[1], d)
        self.assertPropstat(propstats[2], f)

    async def testCopyFile(self):
        f1 = self.root / 'f1.txt'
        await fill_file(f1)
        headers = {'Destination': '/prefix/f2.txt'}
        response = await self.client.request('COPY', '/prefix/f1.txt',
                                             headers=headers)
        self.assertEqual(response.status, 201)
        f2 = self.root / 'f2.txt'
        await f1.populate_props()
        await f2.populate_props()
        await self.root.populate_collection()
        self.assertListEqual(self.root.collection, [f1, f2])
        content = await read_file(f2)
        self.assertEqual(content, b'CONTENT')

    async def testCopyFileToExisting(self):
        f1 = self.root / 'f1.txt'
        await fill_file(f1)
        f2 = self.root / 'f2.txt'
        await fill_file(f2, content=b'OLD_CONTENT')
        headers = {'Destination': '/prefix/f2.txt'}
        response = await self.client.request('COPY', '/prefix/f1.txt',
                                             headers=headers)
        self.assertEqual(response.status, 204)
        f2 = self.root / 'f2.txt'
        await f1.populate_props()
        await f2.populate_props()
        await self.root.populate_collection()
        self.assertListEqual(self.root.collection, [f1, f2])
        content = await read_file(f2)
        self.assertEqual(content, b'CONTENT')

    async def testDeleteNotExistent(self):
        response = await self.client.delete('/prefix/f1.txt')
        self.assertEqual(response.status, 404)

    async def testPutContent(self):
        response = await self.client.put('/prefix/f1.txt', body=b'CONTENT')
        self.assertEqual(response.status, 201)
        f1 = self.root / 'f1.txt'
        await f1.populate_props()
        await self.root.populate_collection()
        self.assertListEqual(self.root.collection, [f1])
        content = await read_file(f1)
        self.assertEqual(content, b'CONTENT')

    async def testPutToCollection(self):
        await self.root.make_collection('/dir')
        response = await self.client.put('/prefix/dir', body=b'CONTENT')
        self.assertEqual(response.status, 405)

    async def testPutEmptyFile(self):
        response = await self.client.put('/prefix/f1.txt', body=b'')
        self.assertEqual(response.status, 201)
        f1 = self.root / 'f1.txt'
        await f1.populate_props()
        self.assertEqual(f1.size, 0)

    async def testPutExisting(self):
        f1 = self.root / 'f1.txt'
        await fill_file(f1)
        response = await self.client.put('/prefix/f1.txt', body=b'NEW_CONTENT')
        self.assertEqual(response.status, 200)
        f1 = self.root / 'f1.txt'
        await f1.populate_props()
        content = await read_file(f1)
        self.assertEqual(content, b'NEW_CONTENT')

    async def testDelete(self):
        f1 = self.root / 'f1.txt'
        await fill_file(f1)
        response = await self.client.delete('/prefix/f1.txt')
        self.assertEqual(response.status, 200)
        await self.root.populate_collection()
        self.assertListEqual(self.root.collection, [])

    def assertMultiStatusResponse(self, response, url, child_count=0):
        self.assertEqual(response.status, 207)
        self.assertEqual(response.reason, 'Multi Status')
        doc = et.fromstring(response.body)
        self.assertElementName(doc, 'multistatus')
        responses = doc.getchildren()
        self.assertEqual(len(responses), child_count + 1)
        resp = responses[0]
        self.assertElementName(resp, "response")
        elems = resp.getchildren()
        self.assertEqual(len(elems), 2)
        href = elems[0]
        self.assertElementName(href, 'href')
        self.assertEqual(href.text, url)
        propstat = elems[1]
        self.assertElementName(propstat, 'propstat')
        return propstat

    def assertPropstat(self, propstat, resource=None):
        elems = propstat.getchildren()
        self.assertEqual(len(elems), 2)
        prop = elems[0]
        self.assertElementName(prop, 'prop')
        status = elems[1]
        self.assertElementName(status, 'status')
        if resource:
            self.assertEqual(status.text, 'HTTP/1.1 200 OK')
        else:
            self.assertEqual(status.text, 'HTTP/1.1 404 Not Found')
            return

        for tag in 'getcontenttype', 'getetag':
            tag = self.get_child(prop, tag)
            self.assertIsNone(tag.text)

        name = self.get_child(prop, 'displayname')
        self.assertEqual(name.text or '', resource.name)
        modified = self.get_child(prop, 'getlastmodified')
        self.assertEqual(modified.text, format_time(resource.mtime))
        created = self.get_child(prop, 'creationdate')
        self.assertEqual(created.text, format_time(resource.ctime))
        length = self.get_child(prop, 'getcontentlength')
        self.assertEqual(length.text, str(resource.size))
        rt = self.get_child(prop, 'resourcetype')
        elems = rt.getchildren()
        if resource.is_collection:
            self.assertEqual(len(elems), 1)
            self.assertElementName(elems[0], 'collection')
        else:
            self.assertEqual(len(elems), 0)

    def testPropfindList(self):
        body = b'''<?xml version="1.0" encoding="utf-8" ?>
 <D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:resourcetype/>
        <D:getcontentlength/>
    </D:prop>
 </D:propfind>
'''
        response = self.client.request('PROPFIND', '/prefix/', body=body)
        propstat = self.assertMultiStatusResponse(response, '/prefix/')
        elems = propstat.getchildren()
        self.assertEqual(len(elems), 2)
        prop = elems[0]
        self.assertElementName(prop, 'prop')
        status = elems[1]
        self.assertElementName(status, 'status')
        elems = prop.getchildren()
        self.assertEqual(len(elems), 2)

        rt = self.get_child(prop, 'resourcetype')
        elems = rt.getchildren()
        self.assertEqual(len(elems), 1)
        self.assertElementName(elems[0], 'collection')
        length = self.get_child(prop, 'getcontentlength')
        self.assertEqual(length.text, str(self.root.size))

    @staticmethod
    def get_child(element, name):
        return element.xpath('D:%s' % name, namespaces={'D': 'DAV:'})[0]

    def assertElementName(self, element, name):
        self.assertEqual(element.tag, '{DAV:}%s' % name)
        self.assertDictEqual(element.nsmap, {'D': 'DAV:'})

# coding: utf-8
import asyncio
import os
import typing
from urllib.parse import urlparse, unquote

from aiohttp.streams import EmptyStreamReader
from lxml import etree as et

import aiohttp_jinja2
from aiohttp import web
from aiohttp.web import hdrs
from aiohttp.web_urldispatcher import ResourceRoute
from io import BytesIO

from aiodav import resources, conf
from aiodav.resources import errors

DAV_METHODS = {"COPY", "MOVE", "MKCOL", "PROPFIND"}


@aiohttp_jinja2.template('root.jinja2')
async def root_view(request):
    aiodav_conf = request.app[conf.APP_KEY]
    mounts = aiodav_conf['mounts']
    prefixes = sorted(mounts.keys())
    return {'resources': prefixes}


class ResourceView(web.View):
    """
    Обрабатывает запросы к WebDAV-ресурсу.
    :type resource: resources.AbstractResource
    :type prefix: str
    :type kw: dict
    """

    resource = None
    prefix = None
    kw = None

    @asyncio.coroutine
    def __iter__(self):
        if self.request.method not in hdrs.METH_ALL | DAV_METHODS:
            self._raise_allowed_methods()
        method = getattr(self, self.request.method.lower(), None)
        if method is None:
            self._raise_allowed_methods()
        resp = yield from method()
        return resp

    def _raise_allowed_methods(self):
        allowed_methods = {
            m for m in hdrs.METH_ALL | DAV_METHODS if hasattr(self, m.lower())}
        raise web.HTTPMethodNotAllowed(self.request.method,
                                       sorted(allowed_methods))

    @classmethod
    def with_resource(cls, resource: resources.AbstractResource,
                      prefix: str, **kwargs) -> 'ResourceView':
        attrs = {
            'prefix': prefix,
            'resource': resource,
            'kw': kwargs,
            '__module__': cls.__module__
        }
        klass = type('ResourceView', (ResourceView,), attrs)
        return klass

    @property
    def relative(self):
        return self.request.match_info['relative'].lstrip('/') or '/'

    @property
    def depth(self):
        return int(self.request.headers.get('Depth', 0))

    @property
    def destination(self):
        destination = self.request.headers.get('Destination')
        path = unquote(urlparse(destination).path.lstrip('/'))
        parts = path.split('/')
        if parts[0] == self.prefix:
            parts = parts[1:]
        return '/'.join(parts)

    @property
    def range(self) -> typing.Tuple[int, int]:
        byte_range = self.request.headers.get('Range')
        if byte_range and byte_range.startswith('bytes=') and '-' in byte_range:
            start, end = byte_range[6:].split('-')
            start = int(start)
            if end:
                end = int(end)
            else:
                end = 0
        else:
            start = end = 0
        return start, end

    async def mkcol(self):
        try:
            current, resource = await self._instantiate_parent()
        except errors.ResourceDoesNotExist:
            raise web.HTTPNotFound(text="Parent does not exist")
        if not resource.is_collection:
            raise web.HTTPBadRequest(text="Collection expected")
        await resource.make_collection(current)
        return web.HTTPCreated()

    async def _instantiate_parent(self):
        parent, collection = os.path.split(self.relative.rstrip('/'))
        resource = await self._instantiate_resource(parent)
        return collection, resource

    async def move(self):
        resource = await self._instantiate_resource(self.relative)
        try:
            created = await resource.move(self.destination)
        except errors.InvalidResourceType:
            # destination exists and is not a collection
            old = await self._instantiate_resource(self.destination)
            await old.delete()
            await resource.move(self.destination)
            created = False
        if created:
            return web.HTTPCreated()
        else:
            return web.HTTPNoContent()

    async def copy(self):
        resource = await self._instantiate_resource(self.relative)
        try:
            await resource.copy(self.destination)
            created = True
        except errors.ResourceAlreadyExists:
            old = await self._instantiate_resource(self.destination)
            await old.delete()
            await resource.copy(self.destination)
            created = False

        return web.HTTPCreated() if created else web.HTTPNoContent()

    async def head(self):
        try:
            await self._instantiate_resource(self.relative)
            return web.HTTPOk()
        except errors.ResourceDoesNotExist:
            return web.HTTPNotFound()

    async def delete(self):
        try:
            resource = await self._instantiate_resource(self.relative)
            await resource.delete()
            return web.HTTPOk()
        except errors.ResourceDoesNotExist:
            return web.HTTPNotFound()

    async def get(self):
        accept = self.request.headers.get('Accept', '')
        resource = await self._instantiate_resource(self.relative)
        if 'text/html' in accept and not self.request.GET.get('dl'):
            context = {'resource': resource, 'relative': self.relative}
            return aiohttp_jinja2.render_template(
                'resource.jinja2', self.request, context)
        if resource.is_collection:
            raise web.HTTPBadRequest(text="Can't download collection")
        start, end = self.range
        return await self.stream_resource(resource, start=start, end=end)

    async def put(self):
        editable_resource = self.resource / self.relative
        try:
            await editable_resource.populate_props()
            is_collection = editable_resource.is_collection
        except errors.ResourceDoesNotExist:
            is_collection = False
        if is_collection:
            raise web.HTTPMethodNotAllowed(
                'PUT', ', '.join(DAV_METHODS), text="Can't PUT to collection")
        if isinstance(self.request.content, EmptyStreamReader):
            reader = None
        else:
            reader = self.request.content.readany
        created = await editable_resource.put_content(reader)
        if created:
            return web.HTTPCreated()
        return web.HTTPOk()

    async def stream_resource(self, resource, start=0, end=0):
        response = web.StreamResponse()
        if end:
            length = min(resource.size, end + 1)
        else:
            length = resource.size
        if start:
            response.set_status(206)
            length -= start
            response.headers['Content-Range'] = 'bytes %s-%s/%s' % (
                start, start + length-1, start + length)
        response.content_length = length
        await response.prepare(self.request)
        # noinspection PyTypeChecker
        await resource.get_content(response.write, offset=start,
                                   limit=length)
        await response.write_eof()
        response.set_tcp_nodelay(True)
        return response

    @staticmethod
    async def options():
        response = web.Response(text="", content_type='text/xml')
        response.headers['Allow'] = ', '.join(DAV_METHODS)
        response.headers['DAV'] = '1, 2'
        return response

    async def propfind(self):
        body = await self.request.read()
        props = self.parse_propfind(body) if body else []
        try:
            resource = await self._instantiate_resource(self.relative)
        except errors.ResourceDoesNotExist:
            if 'gvfs' in self.request.headers.get('User-Agent', ''):
                raise web.HTTPNotFound()
            http_resp = web.HTTPNotFound()
            empty_propstat = et.Element('{DAV:}propstat', nsmap={'D': 'DAV:'})
            prop = et.SubElement(empty_propstat, '{DAV:}prop',
                                 nsmap={'D': 'DAV:'})
            prop.text = ''
            resp = DavXMLResponse(self.request.path, empty_propstat,
                                  status=http_resp.status_code,
                                  reason=http_resp.reason)
            return MultiStatusResponse(resp)
        # noinspection PyArgumentList
        propstat = self.propstat_xml(resource, *props)
        response = DavXMLResponse(self.request.path, propstat)

        collection = []
        if resource.is_collection and self.depth == 1:
            # noinspection PyTypeChecker
            for res in resource.collection:
                await res.populate_props()
                propstat = self.propstat_xml(res)
                href = os.path.join(self.request.path, res.path.lstrip('/'))
                resp = DavXMLResponse(href, propstat)
                collection.append(resp)
        return MultiStatusResponse(response, *collection)

    async def _instantiate_resource(self, relative):
        if relative == '':
            return self.resource
        resource = self.resource / relative
        await resource.populate_props()
        if resource.is_collection:
            await resource.populate_collection()
        return resource

    @staticmethod
    def propstat_xml(
            resource: resources.AbstractResource, *props) -> et.Element:
        ps = et.Element('{DAV:}propstat', nsmap={'D': 'DAV:'})
        prop = et.SubElement(ps, '{DAV:}prop', nsmap={'D': 'DAV:'})
        for k, v in resource.propfind(*props).items():
            el = et.SubElement(prop, '{DAV:}%s' % k, nsmap={'D': 'DAV:'})
            el.text = str(v)

        rt = et.SubElement(prop, '{DAV:}resourcetype', nsmap={'D': 'DAV:'})
        if resource.is_collection:
            col = et.SubElement(rt, '{DAV:}collection', nsmap={'D': 'DAV:'})
            col.text = ''
        return ps

    @staticmethod
    def parse_propfind(text) -> typing.List[str]:
        xml = et.fromstring(text)
        props = []
        prop_elems = xml.xpath('D:prop/*', namespaces={'D': 'DAV:'})
        for elem in prop_elems:
            props.append(elem.tag.replace('{DAV:}', ''))
        return props


class DavResourceRoute(ResourceRoute):
    METHODS = set(DAV_METHODS) | {hdrs.METH_ANY}


class DavXMLResponse:
    def __init__(self, href, propstat, *, status=200, reason="OK"):
        s = et.Element('{DAV:}status', nsmap={'D': 'DAV:'})
        s.text = 'HTTP/1.1 %s %s' % (status, reason)
        propstat.append(s)
        self.propstat = propstat
        self.href = href


class MultiStatusResponse(web.Response):
    def __init__(self, *responses: typing.Iterable[DavXMLResponse]):
        ms = self.construct_multistatus_xml(responses)
        body = self.dump_xml(ms)
        super().__init__(status=207, reason="Multi Status", body=body)
        del self.headers['Content-Length']

    @staticmethod
    def dump_xml(xml):
        f = BytesIO()
        f.write(b'<?xml version="1.0" encoding="utf-8" ?>\n')
        et.ElementTree(xml).write(f, pretty_print=True)
        body = f.getvalue()
        return body

    @staticmethod
    def construct_multistatus_xml(
            responses: typing.Iterable[DavXMLResponse]) -> et.Element:
        ms = et.Element('{DAV:}multistatus', nsmap={'D': 'DAV:'})
        for xml_response in responses:
            response = et.SubElement(ms, '{DAV:}response', nsmap={'D': 'DAV:'})
            href = et.SubElement(response, '{DAV:}href', nsmap={'D': 'DAV:'})
            href.text = xml_response.href
            response.append(xml_response.propstat)
        return ms

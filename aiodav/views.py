# coding: utf-8
import asyncio
import os
import typing
from lxml import etree as ET

import aiohttp_jinja2
from aiohttp import web
from aiohttp.web import hdrs
from aiohttp.web_urldispatcher import ResourceRoute
from io import BytesIO

from aiodav import resources, conf

DAV_METHODS = ["OPTIONS", "GET", "HEAD", "POST", "PUT", "DELETE", "TRACE",
               "COPY", "MOVE", "MKCOL", "PROPFIND"]


@aiohttp_jinja2.template('root.jinja2')
async def root_view(request):
    aiodav_conf = request.app[conf.APP_KEY]
    mounts = aiodav_conf['mounts']
    resources = sorted(mounts.keys())
    return {'resources': resources}


class ResourceView(web.View):
    """
    Обрабатывает запросы к WebDAV-ресурсу.
    :type resource: resources.AbstractResource
    :type prefix: str
    :type kw: dict
    """
    @asyncio.coroutine
    def __iter__(self):
        if self.request.method not in DAV_METHODS:
            self._raise_allowed_methods()
        method = getattr(self, self.request.method.lower(), None)
        if method is None:
            self._raise_allowed_methods()
        resp = yield from method()
        return resp


    resource = None
    prefix = None
    kw = None

    @classmethod
    def with_resource(cls, resource: resources.AbstractResource,
                      prefix: str, **kwargs) -> 'ResourceView':
        klass = type('ResourceView', (ResourceView,), {'prefix': prefix,
                                                       'resource': resource,
                                                       'kw': kwargs,
                                                       '__module__': cls.__module__})
        return klass

    @property
    def relative(self):
        return self.request.match_info['relative'].lstrip('/')

    @aiohttp_jinja2.template('resource.jinja2')
    async def get(self):
        resource = await self._instantiate_resource(self.relative)
        return {'resource': resource, 'relative': self.relative}

    async def options(self):
        response = web.Response(text="", content_type='text/xml')
        response.headers['Allow'] = ', '.join(DAV_METHODS)
        response.headers['DAV'] = '1, 2'
        return response

    async def propfind(self):
        resource = await self._instantiate_resource(self.relative)
        propstat = self.propstat_xml(resource)
        response = DavXMLResponse(self.request.path, propstat=propstat)
        collection = []
        # if resource.is_collection:
        #     for res in resource.collection:
        #         await res.populate_props()
        #         propstat = self.propstat_xml(res)
        #         resp = DavXMLResponse(os.path.join(self.request.path, res.path.lstrip('/')), propstat=propstat)
        #         collection.append(resp)
        return MultiStatusResponse(response, *collection)

    async def _instantiate_resource(self, relative):
        resource = self.resource / relative
        await resource.populate_props()
        if resource.is_collection:
            await resource.populate_collection()
        return resource

    def propstat_xml(self, resource: resources.AbstractResource) -> ET.Element:
        ps = ET.Element('{DAV:}propstat', nsmap={'D': 'DAV:'})
        prop = ET.SubElement(ps, '{DAV:}prop', nsmap={'D': 'DAV:'})
        for k, v in resource.propfind().items():
            el = ET.SubElement(prop, '{DAV:}%s' % k, nsmap={'D': 'DAV:'})
            el.text = str(v)

        rt = ET.SubElement(prop, '{DAV:}resourcetype', nsmap={'D': 'DAV:'})
        if resource.is_collection:
            col = ET.SubElement(rt, '{DAV:}collection', nsmap={'D': 'DAV:'})
            col.text = ''
        return ps


class DavResourceRoute(ResourceRoute):
    METHODS = set(DAV_METHODS) | {hdrs.METH_ANY}


class DavXMLResponse:
    def __init__(self, href, *, status=200, reason="OK", propstat=None):
        self.status = ET.Element('{DAV:}status', nsmap={'D': 'DAV:'})
        self.status.text = 'HTTP/1.1 %s %s' % (status, reason)
        self.propstat = propstat
        if self.propstat:
            self.propstat.append(self.status)
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
        ET.ElementTree(xml).write(f, pretty_print=False)
        body = f.getvalue()
        return body

    @staticmethod
    def construct_multistatus_xml(
            responses: typing.Iterable[DavXMLResponse]) -> ET.Element:
        ms = ET.Element('{DAV:}multistatus', nsmap={'D': 'DAV:'})
        for xml_response in responses:
            response = ET.SubElement(ms, '{DAV:}response', nsmap={'D': 'DAV:'})
            href = ET.SubElement(response, '{DAV:}href', nsmap={'D': 'DAV:'})
            href.text = xml_response.href
            if xml_response.propstat is not None:
                response.append(xml_response.propstat)
            else:
                response.append(xml_response.status)
        return ms
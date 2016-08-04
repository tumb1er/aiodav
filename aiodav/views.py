# coding: utf-8

import aiohttp_jinja2
from aiohttp import web

from aiodav import resources, conf


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

    @aiohttp_jinja2.template('resource.jinja2')
    async def get(self):
        relative = self.request.match_info['relative']
        resource = self.resource / relative
        await resource.populate_props()
        if resource.is_collection:
            await resource.populate_collection()
        return {'resource': resource, 'relative': relative}

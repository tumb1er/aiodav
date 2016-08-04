# coding: utf-8
from typing import Dict

import aiohttp_jinja2
import jinja2
from aiohttp import web

from aiodav import views, resources, conf

from aiodav.contrib.debugtoolbar import setup_aiodav_panels


def setup(app: web.Application, *, prefix:str ='/', hack_debugtoolbar: bool=True,
          mounts: Dict[str, resources.AbstractResource]=None):
    mounts = mounts or {'webdav': resources.FileSystemResource('webdav')}
    # setup jinja2 for aiodav templates
    loader = jinja2.PackageLoader('aiodav')
    aiohttp_jinja2.setup(app, loader=loader, extensions=['jinja2.ext.with_'])

    if hack_debugtoolbar:
        setup_aiodav_panels(app)

    app.router.add_route('GET', prefix, views.root_view)

    for prefix, resource in mounts.items():
        resource_view = views.ResourceView.with_resource(resource, prefix)
        path = '/%s{relative:.*}' % prefix.strip('/')
        dav_resource = app.router.add_resource(path)
        route = views.DavResourceRoute('*', resource_view, dav_resource)
        dav_resource.register_route(route)

    app[conf.APP_KEY] = {
        'mounts': mounts
    }





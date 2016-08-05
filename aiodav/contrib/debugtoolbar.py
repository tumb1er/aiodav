# coding: utf-8

import asyncio
from pathlib import Path

import aiohttp_debugtoolbar
import aiohttp_jinja2

from aiohttp_debugtoolbar.panels.base import DebugPanel


class RequestResponseBodyPanel(DebugPanel):
    name = 'RequestResponse'
    has_content = True
    template = 'request_body.jinja2'
    title = 'Request / Response'
    nav_title = title

    @asyncio.coroutine
    def process_response(self, response):
        self.data = data = {}
        text = yield from self.request.text()
        data['request_body'] = text
        try:
            data['response_body'] = response.text
        except AttributeError:
            data['response_body'] = repr(response)


def setup_aiodav_panels(app):
    # Add RequestBody panel to debugtoolbar
    aiohttp_debugtoolbar.main.default_panel_names.append(RequestResponseBodyPanel)
    env = (app.get(aiohttp_debugtoolbar.main.TEMPLATE_KEY) or
           app.get(aiohttp_jinja2.APP_KEY))
    """:type env: jinja2.Environment"""
    loader = env.loader
    """:type loader: jinja2.loaders.FileSystemLoader"""
    templates = Path(__file__).parent.parent / 'templates'
    loader.searchpath.append(str(templates))
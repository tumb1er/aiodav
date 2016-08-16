# coding: utf-8

import aiohttp_debugtoolbar
from aiohttp import web

from aiodav import resources
from aiodav.contrib import setup

app = web.Application()

aiohttp_debugtoolbar.setup(app)

setup(app, mounts={'TEST': resources.FileSystemResource('TEST')})


if __name__ == '__main__':
    web.run_app(app)

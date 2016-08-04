# coding: utf-8

import aiohttp_debugtoolbar
from aiohttp import web

from aiodav.contrib import setup

app = web.Application()

aiohttp_debugtoolbar.setup(app)

setup(app)


if __name__ == '__main__':
    web.run_app(app)

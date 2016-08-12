AioDAV
======

`AioDAV` is a WebDAV proxy and server.

[![Build Status](https://travis-ci.org/tumb1er/aiodav.svg?branch=travis)](https://travis-ci.org/tumb1er/aiodav)
[![codecov](https://codecov.io/gh/tumb1er/aiodav/branch/master/graph/badge.svg)](https://codecov.io/gh/tumb1er/aiodav)


Main features
-------------

* Provides WebDAV-access to a storage
* Provides browser interface to the same storage
* Now only supports local filesystem as a storage
* May be used as an application for aiohttp-based project

Supported storages
------------------
* local filesystem
* **TBD:** webdav shares (serves as a proxy for it)
* **TBD:** mail.ru cloud

Requirements
------------
* Python3.5+
* [aiohttp](https://aiohttp.readthedocs.org)
* [aiohttp_jinja2](https://aiohttp_jinja2.readthedocs.org)

Production Status
-----------------

**Pre-alpha** version.

Futher reading
--------------
* http://www.ietf.org/rfc/rfc4918.txt
* https://habrahabr.ru/post/268123/

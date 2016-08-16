# coding: utf-8
from io import BytesIO


def format_time(t):
    return t.replace(microsecond=0).isoformat() + 'Z'


async def fill_file(file_resource, content=None):
    content = content or b'CONTENT'

    def chunks():
        yield content
        yield b''

    c = iter(chunks())

    async def read_any():
        return next(c)

    return await file_resource.put_content(read_any)


async def read_file(resource, offset=0, limit=None):
    content = BytesIO()

    async def write(data):
        content.write(data)

    await resource.get_content(write, offset=offset, limit=limit)
    content.seek(0)
    content = content.getvalue()
    return content


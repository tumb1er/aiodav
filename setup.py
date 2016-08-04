from setuptools import setup

setup(
    name='aiodav',
    version='0.0.1',
    packages=['aiodav'],
    url='https://github.com/tumb1er/aiodav/',
    license='Beer License',
    author='Sergey Tikhonov',
    author_email='zimbler@gmail.com',
    description='asyncio WebDAV proxy and server',
    install_requires=[
        'aiohttp', 'aiohttp_jinja2'
    ]
)


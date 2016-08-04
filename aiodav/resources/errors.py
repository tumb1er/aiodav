# coding: utf-8


class ResourceError(Exception):
    """ Base aiodav resource exception."""


class ResourceDoesNotExist(ResourceError):
    """ Resource does not exist."""

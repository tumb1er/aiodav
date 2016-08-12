# coding: utf-8


class ResourceError(Exception):
    """ Base aiodav resource exception."""


class ResourceDoesNotExist(ResourceError):
    """ Resource does not exist."""


class ResourceAlreadyExists(ResourceError):
    """ Resource already exists."""


class InvalidResourceType(ResourceError):
    """ Incorrect resource type."""

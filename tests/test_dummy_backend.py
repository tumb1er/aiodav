# coding: utf-8
from unittest import TestCase

from aiodav.resources.dummy import DummyResource
from tests.base import BackendTestsMixin


__all__ = ['DummyBackendTestCase']


class DummyBackendTestCase(BackendTestsMixin, TestCase):
    Resource = DummyResource

    @classmethod
    def tearDownClass(cls):
        cls.Resource._root = None

    def testSecondRootDeny(self):
        with self.assertRaises(ValueError):
            self.create_resource('prefix')

    def tearDown(self):
        super().tearDown()
        self.root._resources.clear()

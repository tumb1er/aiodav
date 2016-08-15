# coding: utf-8
import os
import tempfile
from unittest import TestCase

import shutil

from aiodav.resources import FileSystemResource
from tests.base import BackendTestsMixin


__all__ = ['FileSystemBackendTestCase']


class FileSystemBackendTestCase(BackendTestsMixin, TestCase):

    Resource = FileSystemResource

    @classmethod
    def setUpClass(cls):
        cls.root_dir = tempfile.mkdtemp()
        cls.root = cls.Resource('prefix', root_dir=cls.root_dir)

    @classmethod
    def create_resource(cls, *args, **kwargs):
        kwargs.setdefault('root_dir', cls.root_dir)
        return super().create_resource(*args, **kwargs)

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(cls.root_dir)

    def setUp(self):
        super().setUp()
        self.addTypeEqualityFunc(self.Resource, self.assertResourcesEqual)

    def tearDown(self):
        super().tearDown()
        for d in os.listdir(self.root_dir):
            path = os.path.join(self.root_dir, d)
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.unlink(path)

    def assertResourcesEqual(self, first, second, msg=None):
        self.assertIsInstance(first, self.Resource, msg=None)
        self.assertIsInstance(second, self.Resource, msg=None)
        self.assertIs(first.is_collection, second.is_collection, msg=None)
        self.assertEqual(first.path, second.path, msg=None)

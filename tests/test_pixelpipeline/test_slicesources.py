import unittest as ut
from unittest import mock

import numpy as np

from volumina.pixelpipeline.slicesources import PlanarSliceSource, projectionAlongTZC
from volumina.pixelpipeline.datasources import ArraySource


class PlanarSliceSourceTest(ut.TestCase):
    def setUp(self):
        self.raw = np.random.randint(0, 100, (10, 3, 3, 128, 3))
        self.a = ArraySource(self.raw)
        self.ss = PlanarSliceSource(self.a, projectionAlongTZC)

    def testRequest(self):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        sl = self.ss.request((slice(None), slice(None))).wait()
        self.assertTrue(np.all(sl == self.raw[1, :, :, 127, 2]))

        sl_bounded = self.ss.request((slice(0, 3), slice(1, None))).wait()
        self.assertTrue(np.all(sl_bounded == self.raw[1, 0:3, 1:, 127, 2]))

    def testDirtynessPropagation(self):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        check_mock = mock.Mock()
        self.ss.isDirty.connect(check_mock)
        self.a.setDirty(np.s_[1:2, :, 1:2, 127:128, 2:3])
        self.ss.isDirty.disconnect(check_mock)
        check_mock.assert_called_once_with(np.s_[:, 1:2])

###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2014, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the Lesser GNU General Public License
# as published by the Free Software Foundation; either version 2.1
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# See the files LICENSE.lgpl2 and LICENSE.lgpl3 for full text of the
# GNU Lesser General Public License version 2.1 and 3 respectively.
# This information is also available on the ilastik web site at:
#          http://ilastik.org/license/
###############################################################################
import unittest

import numpy as np
from qtpy.QtCore import QRect

import volumina.slicingtools as st


class SlTest(unittest.TestCase):
    def runTest(self):
        self.assertEqual(st.sl[1, :34, :], (1, slice(34), slice(None)))


class toolsTest(unittest.TestCase):
    def testIntersection(self):
        i = st.intersection(st.sl[5:8, 3:7, 2:9], st.sl[0:50, 0:50, 4:5])
        self.assertEqual(i, st.sl[5:8, 3:7, 4:5])
        ni = st.intersection(st.sl[5:8, 3:7, 2:9], st.sl[0:50, 0:50, 9:10])
        self.assertEqual(ni, None)

    def testIndex2slice(self):
        pure = st.index2slice(st.sl[3:4, 5, :, 10])
        self.assertEqual(pure, st.sl[3:4, 5:6, :, 10:11])


class SliceProjectionTest(unittest.TestCase):
    def testArgumentCheck(self):
        st.SliceProjection(1, 2, [0, 3, 4])
        st.SliceProjection(2, 1, [3, 0, 4])
        self.assertRaises(ValueError, st.SliceProjection, 2, 1, [3, 0, 7])
        self.assertRaises(ValueError, st.SliceProjection, 2, 1, [3, 1, 4])
        self.assertRaises(ValueError, st.SliceProjection, 2, 5, [3, 1, 4])

    def testDomain(self):
        sp = st.SliceProjection(2, 1, [3, 0, 4])
        unbounded = sp.domain([3, 23, 1])
        self.assertEqual(unbounded, (slice(23, 24), slice(None), slice(None), slice(3, 4), slice(1, 2)))

        bounded = sp.domain([3, 23, 1], slice(5, 9), slice(12, None))
        self.assertEqual(bounded, (slice(23, 24), slice(12, None), slice(5, 9), slice(3, 4), slice(1, 2)))

    def testSliceDomain(self):
        sp = st.SliceProjection(2, 1, [3, 0, 4])
        slicing = sp.domain([3, 7, 1], slice(1, 3), slice(0, None))
        raw = np.random.randint(0, 100, (10, 3, 3, 128, 3))
        domainArray = raw[slicing]
        sl = sp(domainArray)
        self.assertTrue(np.all(sl == raw[7, :, 1:3, 3, 1].swapaxes(0, 1)))


class SlicingToolsTest(unittest.TestCase):
    slicing = (slice(5, 7), slice(10, 18))
    qrect = QRect(5, 10, 2, 8)

    def test_slicing2rect(self):
        qrect = st.slicing2rect(self.slicing)
        assert qrect == self.qrect

    def test_rect2slicing(self):
        slicing = st.rect2slicing(self.qrect)
        assert slicing == self.slicing

    def test_slicing_rect_inversion(self):
        """Ensures that slicing2rect and rect2slicing are inverse
        operations.

        """
        a = self.slicing
        b = st.slicing2rect(a)
        c = st.rect2slicing(b)

        assert a == c

        a = self.qrect
        b = st.rect2slicing(a)
        c = st.slicing2rect(b)

        assert a == c


if __name__ == "__main__":
    unittest.main()

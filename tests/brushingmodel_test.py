from __future__ import print_function

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
# 		   http://ilastik.org/license/
###############################################################################
from builtins import range
import unittest as ut
import numpy as np
import pytest
from PyQt5.QtCore import QPointF
from volumina.brushingmodel import BrushingModel


def _onBrushStroke(point, labels):
    print(point.x(), point.y())
    print(labels.shape)


@pytest.mark.usefixtures("qapp")
class BrushingModelTest(ut.TestCase):

    def _checkBrushSize(self, size, should_diameter):
        m = BrushingModel()

        def check(point, labels):
            self.assertEqual(max((np.count_nonzero(labels[row, :]) for row in range(labels.shape[0]))), should_diameter)
            self.assertEqual(max((np.count_nonzero(labels[col, :]) for col in range(labels.shape[1]))), should_diameter)

        m.setBrushSize(size)
        m.brushStrokeAvailable.connect(check)
        m.beginDrawing(QPointF(size * 2, size * 2), (size * 3, size * 3))
        m.endDrawing(QPointF(size * 2, size * 2))

    def testBrushSizes(self):
        self._checkBrushSize(0, 1)
        self._checkBrushSize(0.7, 1)
        self._checkBrushSize(2.1, 2)
        for i in range(1, 20):
            self._checkBrushSize(i, i)


if __name__ == "__main__":
    ut.main()

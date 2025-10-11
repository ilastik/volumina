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
from typing import List
from qtpy.QtCore import QPointF, QRectF

import numpy

# *******************************************************************************
# P a t c h A c c e s s o r                                                    *
# *******************************************************************************


class PatchAccessor:
    """
    Cut a given 2D shape into patches of given rectangular size

    .. note:: If the last block size is less than a third of given block size,
    then this block will be merged with the previous one
    """

    def __init__(self, size_x: int, size_y: int, blockSize=128):
        """
        (size_x, size_y) -- 2D shape
        blockSize        -- maximum width/height of patches

        Constructs a PatchAccessor that will divide the given shape
        into patches of block size.
        """

        self._blockSize = blockSize
        self.size_x = size_x
        self.size_y = size_y

        self._cX = int(numpy.ceil(1.0 * size_x / self._blockSize))

        # last blocks can be very small -> merge them with the secondlast one
        self._cXend = size_x % self._blockSize
        if self._cXend < self._blockSize // 3 and self._cXend != 0 and self._cX > 1:
            self._cX -= 1
        else:
            self._cXend = 0

        self._cY = int(numpy.ceil(1.0 * size_y / self._blockSize))

        # last blocks can be very small -> merge them with the secondlast one
        self._cYend = size_y % self._blockSize
        if self._cYend < self._blockSize // 3 and self._cYend != 0 and self._cY > 1:
            self._cY -= 1
        else:
            self._cYend = 0

        self.patchCount = self._cX * self._cY

    def __len__(self):
        return self.patchCount

    def getPatchBounds(self, blockNum: int, overlap: int = 0) -> List[int]:
        rest = blockNum % (self._cX * self._cY)
        y = int(numpy.floor(rest / self._cX))
        x = rest % self._cX

        startx = max(0, x * self._blockSize - overlap)
        endx = min(self.size_x, (x + 1) * self._blockSize + overlap)
        if x + 1 >= self._cX:
            endx = self.size_x

        starty = max(0, y * self._blockSize - overlap)
        endy = min(self.size_y, (y + 1) * self._blockSize + overlap)
        if y + 1 >= self._cY:
            endy = self.size_y

        return [startx, endx, starty, endy]

    def patchRectF(self, blockNum: int, overlap: int = 0) -> QRectF:
        startx, endx, starty, endy = self.getPatchBounds(blockNum, overlap)
        return QRectF(QPointF(startx, starty), QPointF(endx, endy))

    def getPatchesForRect(self, startx: float, starty: float, endx: float, endy: float) -> List[int]:
        """
        Looks up patches for specified block
        x in [startx, endx)
        y in [starty, endy)
        :returns: list of patch ids
        """
        sx = int(numpy.floor(startx / self._blockSize))
        ex = int(numpy.ceil(endx / self._blockSize))
        sy = int(numpy.floor(starty / self._blockSize))
        ey = int(numpy.ceil(endy / self._blockSize))

        # Clip to rect bounds
        ex = min(ex, self._cX)
        ey = min(ey, self._cY)

        sx = max(min(sx, ex - 1), 0)
        sy = max(min(sy, ey - 1), 0)

        nums = []
        for y in range(sy, ey):
            nums += list(range(y * self._cX + sx, y * self._cX + ex))

        return nums

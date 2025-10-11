###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2024, the ilastik developers
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
import logging

from qtpy.QtCore import QRect, QRectF
from qtpy.QtGui import QTransform

# volumina
from volumina.patchAccessor import PatchAccessor

logger = logging.getLogger(__name__)


class Tiling(object):
    """
    Describes the geometry of a tiling, for easy access
    to patch rects, overall shape, tile size, and data2scene transform.
    """

    def __init__(
        self,
        sliceShape,
        data2scene=QTransform(),
        blockSize: int = 512,
        overlap=0,
        overlap_draw=1e-3,
        name="Unnamed Tiling",
    ):
        """
        Args:
            sliceShape -- (width, height)
            data2scene -- QTransform from data to image coordinates (default:
                          identity transform)
            blockSize  -- base tile size: blockSize x blockSize (default 256)
            overlap    -- overlap between tiles positive number prevents rendering
                          artifacts between tiles for certain zoom levels (default 1)
        """
        self.blockSize = blockSize
        self.overlap = overlap
        self._patchAccessor = PatchAccessor(sliceShape[0], sliceShape[1], blockSize=self.blockSize)
        self._overlap_draw = overlap_draw
        self._overlap = overlap

        numPatches = self._patchAccessor.patchCount

        self.imageRectFs = [None] * numPatches
        self.dataRectFs = [None] * numPatches
        self.tileRectFs = [None] * numPatches
        self.imageRects = [None] * numPatches
        self.dataRects = [None] * numPatches
        self.tileRects = [None] * numPatches
        self.sliceShape = sliceShape
        self.name = name
        self.data2scene = data2scene

    @property
    def data2scene(self):
        return self._data2scene

    @data2scene.setter
    def data2scene(self, data2scene):
        self._data2scene = data2scene
        self.scene2data, isInvertible = data2scene.inverted()
        assert isInvertible

        for patchNr in range(self._patchAccessor.patchCount):
            # the patch accessor uses the data coordinate system.
            # because the patch is drawn on the screen, its holds coordinates
            # corresponding to Qt's QGraphicsScene's system, which need to be
            # converted to scene coordinates

            # the image rectangle includes an overlap margin
            imageRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, self.overlap))

            # the patch rectangle has per default no overlap
            patchRectF = data2scene.mapRect(self._patchAccessor.patchRectF(patchNr, 0))

            # add a little overlap when the overlap_draw setting is
            # activated
            if self._overlap_draw != 0:
                patchRectF = QRectF(
                    patchRectF.x() - self._overlap_draw,
                    patchRectF.y() - self._overlap_draw,
                    patchRectF.width() + 2 * self._overlap_draw,
                    patchRectF.height() + 2 * self._overlap_draw,
                )

            patchRect = QRect(
                round(patchRectF.x()), round(patchRectF.y()), round(patchRectF.width()), round(patchRectF.height())
            )

            # the image rectangles of neighboring patches can overlap
            # slightly, to account for inaccuracies in sub-pixel
            # rendering of many ImagePatch objects
            imageRect = QRect(
                round(imageRectF.x()), round(imageRectF.y()), round(imageRectF.width()), round(imageRectF.height())
            )

            self.imageRectFs[patchNr] = imageRectF
            self.dataRectFs[patchNr] = imageRectF
            self.tileRectFs[patchNr] = patchRectF
            self.imageRects[patchNr] = imageRect
            self.tileRects[patchNr] = patchRect

    def boundingRectF(self):
        if self.tileRectFs:
            p = self.tileRectFs[-1]
            br = QRectF(0, 0, p.x() + p.width(), p.y() + p.height())
        else:
            br = QRectF(0, 0, 0, 0)
        return br

    def containsF(self, point):
        for i, p in enumerate(self.tileRectFs):
            if p.contains(point):
                return i

    def intersected(self, sceneRect):
        if not sceneRect.isValid():
            return list(range(len(self.tileRects)))

        # Patch accessor uses data coordinates
        rect = self.data2scene.inverted()[0].mapRect(sceneRect)
        patchNumbers = self._patchAccessor.getPatchesForRect(
            rect.topLeft().x(), rect.topLeft().y(), rect.bottomRight().x(), rect.bottomRight().y()
        )
        return patchNumbers

    def __len__(self):
        return len(self.imageRectFs)

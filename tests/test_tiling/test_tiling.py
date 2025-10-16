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
# time to wait (in seconds) for rendering to finish
import pytest

import unittest as ut

import numpy as np

from qtpy.QtCore import QRectF, QPoint, QRect
from qtpy.QtGui import QTransform
from qimage2ndarray import byte_view

from volumina.tiling import TileProvider, Tiling
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer
from volumina.pixelpipeline.datasources import ConstantSource, ArraySource
from volumina.pixelpipeline.slicesources import PlanarSliceSource
from volumina.pixelpipeline.imagesources import GrayscaleImageSource
from volumina.pixelpipeline.imagepump import StackedImageSources, ImagePump
from volumina.slicingtools import SliceProjection


@pytest.fixture(autouse=True)
def patch_threadpool():
    """
    Clean up the Render pool after every test

    avoids test hangs starting with python 3.10
    """
    import volumina.tiling.tileprovider

    if not volumina.tiling.tileprovider.USE_LAZYFLOW_THREADPOOL:
        from volumina.utility.prioritizedThreadPool import PrioritizedThreadPoolExecutor

        volumina.tiling.tileprovider.renderer_pool = PrioritizedThreadPoolExecutor(2)
        yield
        volumina.tiling.tileprovider.renderer_pool.shutdown()
        volumina.tiling.tileprovider.renderer_pool = None
    else:
        yield


class TilingTest(ut.TestCase):
    def testNoneShape(self):
        t = Tiling((0, 0))
        self.assertEqual(t.imageRectFs, [])
        self.assertEqual(t.tileRectFs, [])
        self.assertEqual(t.imageRects, [])
        self.assertEqual(t.tileRects, [])
        self.assertEqual(t.sliceShape, (0, 0))
        self.assertEqual(t.boundingRectF(), QRectF(0, 0, 0, 0))
        self.assertEqual(t.containsF(QPoint(0, 0)), None)
        self.assertEqual(t.intersected(QRect(0, 0, 1, 1)), [])
        self.assertEqual(len(t), 0)

    def testLen(self):
        for i in range(5):
            t = Tiling((100 * i, 100), blockSize=50)
            self.assertEqual(len(t), (100 * i * 2) // 50)

    def testData2SceneSetterErrors(self):
        t = Tiling((0, 0))
        trans = QTransform()
        t.data2scene = trans
        self.assertEqual(trans, t.data2scene)

        # try using transformation that is not invertible
        trans = QTransform(1, 1, 1, 1, 1, 1)
        with self.assertRaises(AssertionError):
            t.data2scene = trans


@pytest.mark.parametrize(
    "shape, trafo_scale, imageRect_shape, expected_tiles",
    [
        ((1024, 2048), (1.0, 1.0), (512, 512), 8),
        ((512, 1024), (2.0, 2.0), (1024, 1024), 2),
        ((256, 512), (4.0, 4.0), (1024, 2048), 1),
        ((128, 256), (8.0, 8.0), (1024, 2048), 1),
    ],
)
def test_Data2Scene(shape, trafo_scale, imageRect_shape, expected_tiles):
    t = Tiling(shape, data2scene=QTransform().scale(*trafo_scale), blockSize=512)

    assert len(t.imageRectFs) == expected_tiles
    assert len(t.dataRectFs) == expected_tiles
    assert len(t.tileRectFs) == expected_tiles
    assert len(t.imageRects) == expected_tiles
    assert len(t.dataRects) == expected_tiles
    assert len(t.tileRects) == expected_tiles
    for ir in t.imageRects:
        assert (ir.size().width(), ir.size().height()) == imageRect_shape


@pytest.mark.usefixtures("qapp")
class TileProviderTest(ut.TestCase):
    def setUp(self):
        self.GRAY1 = 60
        self.ds1 = ConstantSource(self.GRAY1)

        self.GRAY2 = 120
        self.ds2 = ConstantSource(self.GRAY2)

        self.GRAY3 = 190
        self.ds3 = ConstantSource(self.GRAY3)

        self.layer1 = GrayscaleLayer(self.ds1, normalize=False)
        self.layer1.visible = False
        self.layer1.opacity = 0.1
        self.ims1 = GrayscaleImageSource(PlanarSliceSource(self.ds1), self.layer1)
        self.layer2 = GrayscaleLayer(self.ds2, normalize=False)
        self.layer2.visible = True
        self.layer2.opacity = 0.3
        self.ims2 = GrayscaleImageSource(PlanarSliceSource(self.ds2), self.layer2)
        self.layer3 = GrayscaleLayer(self.ds3, normalize=False)
        self.layer3.visible = True
        self.layer3.opacity = 1.0
        self.ims3 = GrayscaleImageSource(PlanarSliceSource(self.ds3), self.layer3)

        lsm = LayerStackModel()
        lsm.append(self.layer1)
        lsm.append(self.layer2)
        lsm.append(self.layer3)
        self.lsm = lsm
        sims = StackedImageSources(lsm)
        sims.register(self.layer1, self.ims1)
        sims.register(self.layer2, self.ims2)
        sims.register(self.layer3, self.ims3)
        self.sims = sims

    def testSetAllLayersInvisible(self):
        tiling = Tiling((900, 400), blockSize=100)
        tp = TileProvider(tiling, self.sims)

        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == self.GRAY3))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

        self.layer1.visible = False
        self.layer2.visible = False
        self.layer3.visible = False
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            # If all tiles are invisible, then no tile is even rendered at all.
            assert tile.qimg is None

        self.layer1.visible = False
        self.layer2.visible = True
        self.layer2.opacity = 1.0
        self.layer3.visible = False
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == self.GRAY2))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))


@pytest.mark.usefixtures("qapp")
class DirtyPropagationTest(ut.TestCase):
    def setUp(self):
        dataShape = (1, 900, 400, 10, 1)  # t,x,y,z,c
        data = np.indices(dataShape)[3].astype(np.uint8)  # Data is labeled according to z-index
        self.ds1 = ArraySource(data)
        self.CONSTANT = 13
        self.ds2 = ConstantSource(self.CONSTANT)

        self.layer1 = GrayscaleLayer(self.ds1, normalize=False)
        self.layer1.visible = True
        self.layer1.opacity = 1.0

        self.layer2 = GrayscaleLayer(self.ds2, normalize=False)

        self.lsm = LayerStackModel()
        self.pump = ImagePump(self.lsm, SliceProjection(), sync_along=(0, 1, 2))

    def testEverythingDirtyPropagation(self):
        self.lsm.append(self.layer2)
        tiling = Tiling((900, 400), blockSize=100)
        tp = TileProvider(tiling, self.pump.stackedImageSources)

        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == self.CONSTANT))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

        NEW_CONSTANT = self.CONSTANT + 1
        self.ds2.constant = NEW_CONSTANT
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == NEW_CONSTANT))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

    def testOutOfViewDirtyPropagation(self):
        self.lsm.append(self.layer1)
        tiling = Tiling((900, 400), blockSize=100)
        tp = TileProvider(tiling, self.pump.stackedImageSources)

        # Navigate down to the second z-slice
        self.pump.syncedSliceSources.through = [0, 1, 0]
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()

        # Sanity check: Do we see the right data on the second
        # slice? (should be all 1s)
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == 1))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

        # Navigate down to the third z-slice
        self.pump.syncedSliceSources.through = [0, 2, 0]
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()

        # Sanity check: Do we see the right data on the third
        # slice?(should be all 2s)
        tiles = tp.getTiles(QRectF(100, 100, 200, 200), QRectF())
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == 2))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

        # Navigate back up to the second z-slice
        self.pump.syncedSliceSources.through = [0, 1, 0]
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()
        for tile in tiles:
            aimg = byte_view(tile.qimg)
            self.assertTrue(np.all(aimg[:, :, 0:3] == 1))
            self.assertTrue(np.all(aimg[:, :, 3] == 255))

        # Change some of the data in the (out-of-view) third z-slice
        slicing = (slice(None), slice(100, 300), slice(100, 300), slice(2, 3), slice(None))
        slicing = tuple(slicing)
        self.ds1._array[slicing] = 99
        self.ds1.setDirty(slicing)

        # Navigate back down to the third z-slice
        self.pump.syncedSliceSources.through = [0, 2, 0]
        tp.requestRefresh(QRectF(100, 100, 200, 200))
        tp.waitForTiles()

        # Even though the data was out-of-view when it was
        # changed, it should still have new values. If dirtiness
        # wasn't propagated correctly, the cache's old values will
        # be used. (For example, this fails if you comment out the
        # call to setDirty, above.)

        # Shrink accessed rect by 1 pixel on each side (Otherwise,
        # tiling overlap_draw causes getTiles() to return
        # surrounding tiles that we haven't actually touched in
        # this test)
        tiles = tp.getTiles(QRectF(101, 101, 198, 198), QRectF())

        for tile in tiles:
            aimg = byte_view(tile.qimg)
            # Use any() because the tile borders may not be
            # perfectly aligned with the data we changed.
            self.assertTrue(np.any(aimg[:, :, 0:3] == 99))


if __name__ == "__main__":
    ut.main()

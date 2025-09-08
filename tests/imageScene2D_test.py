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
import unittest as ut
import datetime
import time

import pytest

from qtpy.QtGui import QImage, QPainter
from qtpy.QtWidgets import QStyleOptionGraphicsItem

from qimage2ndarray import byte_view
import numpy as np

from volumina.imageScene2D import ImageScene2D, DirtyIndicator
from volumina.positionModel import PositionModel
from volumina.pixelpipeline.datasources import ConstantSource
from volumina.pixelpipeline.slicesources import PlanarSliceSource
from volumina.pixelpipeline.imagepump import StackedImageSources
from volumina.tiling import Tiling
from volumina.layerstack import LayerStackModel
from volumina.layer import GrayscaleLayer


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


@pytest.mark.usefixtures("qapp")
class DirtyIndicatorTest(ut.TestCase):
    def testPaintDelay(self):
        t = Tiling((100, 100))
        assert len(t.tileRectFs) == 1

        delay = datetime.timedelta(milliseconds=300)
        # fudge should prevent hitting the delay time exactly
        # during the while loops below;
        # if your computer is verrry slow and the fudge too small
        # the test will fail...
        fudge = datetime.timedelta(milliseconds=50)
        d = DirtyIndicator(t, delay=delay)

        # make the image a little bit larger to accomodate the tile overlap
        img = QImage(110, 110, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        img_saved = QImage(img)

        painter = QPainter()
        style = QStyleOptionGraphicsItem()
        style.exposedRect = t.tileRectFs[0]

        start = datetime.datetime.now()
        d.setTileProgress(0, 0)  # resets delay timer

        # 1. do not update the progress during the delay time
        actually_checked = False
        while datetime.datetime.now() - start < delay - fudge:
            # nothing should be painted
            self.assertEqual(img, img_saved)
            actually_checked = True
        self.assertTrue(actually_checked)
        time.sleep(fudge.total_seconds() * 2)
        # after the delay, the pie chart is painted
        painter.begin(img)
        d.paint(painter, style, None)
        self.assertNotEqual(img, img_saved)
        painter.end()

        # 2. update the progress during delay (this exposed a bug:
        #    the delay was ignored in that case and the pie chart
        #    painted nevertheless)
        d = DirtyIndicator(t, delay=delay)
        img.fill(0)
        start = datetime.datetime.now()
        d.setTileProgress(0, 0)  # resets delay timer

        actually_checked = False
        self.assertEqual(img, img_saved)  # precondition
        while datetime.datetime.now() - start < delay - fudge:
            # the painted during the delay time should have no effect
            painter.begin(img)
            d.setTileProgress(0, 0.5)
            d.paint(painter, style, None)
            painter.end()
            self.assertEqual(img, img_saved)
            actually_checked = True
        self.assertTrue(actually_checked)
        time.sleep(fudge.total_seconds() * 2)
        # now the pie should be painted
        painter.begin(img)
        d.paint(painter, style, None)
        self.assertNotEqual(img, img_saved)
        painter.end()


@pytest.mark.usefixtures("qapp")
class ImageScene2DTest(ut.TestCase):

    def testStackedImageSourcesProperty(self):
        s = ImageScene2D(PositionModel(), (0, 3, 4), preemptive_fetch_number=0)
        self.assertEqual(len(s.stackedImageSources), 0)

        sims = StackedImageSources(LayerStackModel())
        s.stackedImageSources = sims
        self.assertEqual(id(s.stackedImageSources), id(sims))


@pytest.mark.usefixtures("qapp")
class ImageScene2D_RenderTest(ut.TestCase):

    def setUp(self):
        self.layerstack = LayerStackModel()
        self.sims = StackedImageSources(self.layerstack)

        self.GRAY = 201
        self.ds = ConstantSource(self.GRAY)
        self.layer = GrayscaleLayer(self.ds)
        self.layer.set_normalize(0, False)
        self.layerstack.append(self.layer)
        self.ims = self.layer.createImageSource([PlanarSliceSource(self.ds)])
        self.sims.register(self.layer, self.ims)

        self.scene = ImageScene2D(PositionModel(), (0, 3, 4), preemptive_fetch_number=0)

        self.scene.stackedImageSources = self.sims
        self.scene.dataShape = (310, 290)

    def renderScene(self, s, exportFilename=None):
        img = QImage(310, 290, QImage.Format_ARGB32_Premultiplied)
        img.fill(0)
        p = QPainter(img)
        s.render(p)
        s.joinRenderingAllTiles(viewport_only=False)
        s.render(p)
        p.end()
        if exportFilename is not None:
            img.save(exportFilename)
        return byte_view(img)

    def testBasicImageRenderingCapability(self):
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:, :, 0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:, :, 3] == 255))

    def testToggleVisibilityOfOneLayer(self):
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:, :, 0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:, :, 3] == 255))

        self.layer.visible = False
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:, :, 0:3] == 0))  # all white
        self.assertTrue(np.all(aimg[:, :, 3] == 0))

        self.layer.visible = True
        aimg = self.renderScene(self.scene)
        self.assertTrue(np.all(aimg[:, :, 0:3] == self.GRAY))
        self.assertTrue(np.all(aimg[:, :, 3] == 255))


if __name__ == "__main__":
    ut.main()

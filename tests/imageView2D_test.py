###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2026, the ilastik developers
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
from typing import Tuple

import numpy
import pytest
import qimage2ndarray
from numpy import typing as npt
from qtpy.QtWidgets import QOpenGLWidget
from qtpy.QtCore import QPointF, QRectF
from qtpy.QtGui import QImage, QOpenGLFramebufferObject, QOpenGLFramebufferObjectFormat, QOpenGLPaintDevice, QPainter

from volumina.croppingMarkers import CropExtentsModel
from volumina.imageScene2D import ImageScene2D
from volumina.imageView2D import ImageView2D
from volumina.layer import GrayscaleLayer
from volumina.layerstack import LayerStackModel
from volumina.pixelpipeline.datasources import ArraySource
from volumina.pixelpipeline.imagepump import StackedImageSources
from volumina.pixelpipeline.slicesources import PlanarSliceSource
from volumina.positionModel import PositionModel

UInt8Array = npt.NDArray[numpy.uint8]


@pytest.fixture
def random_image(shape: Tuple[int, int] = (120, 240)) -> UInt8Array:
    data = numpy.random.default_rng(42).integers(0, 255, shape, dtype="uint8")
    # make it a bit easier to debug by adding some gradients
    data[:, 0:20] = numpy.arange(120).reshape((120, 1))
    data[:, -20:] = numpy.arange(120).reshape((120, 1))
    data[0:10, 20:-20] = numpy.arange(200)
    data[-10:, 20:-20] = numpy.arange(200)
    return data


@pytest.fixture
def image_view_empty(qtbot) -> ImageView2D:
    """Create an image view with"""
    scene = ImageScene2D(PositionModel(), (0, 3, 4), preemptive_fetch_number=0)
    cm = CropExtentsModel(None)
    image_view = ImageView2D(None, cm, scene)
    qtbot.addWidget(image_view)
    image_view._sliceIntersectionMarker.setVisible(False)
    image_view._crossHairCursor.setVisible(False)
    image_view.showCropLines(False)
    return image_view


def set_image(image_view: ImageView2D, image: npt.NDArray):
    layerstack = LayerStackModel()
    sims = StackedImageSources(layerstack)
    image_5d = image.reshape((1, *image.shape, 1, 1))
    ds = ArraySource(image_5d)
    layer = GrayscaleLayer(ds)
    layer.set_normalize(0, (0, 255))
    layerstack.append(layer)
    ims = layer.createImageSource([PlanarSliceSource(ds)])
    sims.register(layer, ims)

    scene = image_view.scene()
    scene.stackedImageSources = sims
    scene.dataShape = image.shape

    image_view.name = "ImageView2D: random_image"
    image_view.sliceShape = image.shape[::1]
    image_view.slices = 1


@pytest.fixture
def image_view(image_view_empty: ImageView2D, random_image: UInt8Array) -> ImageView2D:
    """
    ImageView2D with random image, size of the viewport such that it shows the whole image at zoom==1
    """
    set_image(image_view=image_view_empty, image=random_image)
    image_view_width: int = random_image.shape[0]
    image_view_height: int = random_image.shape[1]
    image_view_empty.setGeometry(0, 0, image_view_width, image_view_height)
    # 0px border makes results reproducible on all platforms, without only MacOSX passes
    image_view_empty.setStyleSheet("border: 0px")
    return image_view_empty


def grab_imageview(image_view: ImageView2D) -> npt.NDArray:
    image_view.scene().joinRenderingAllTiles()
    viewport = image_view.viewport()
    viewport.repaint()

    assert isinstance(viewport, QOpenGLWidget)
    viewport.makeCurrent()
    buffer_format = QOpenGLFramebufferObjectFormat()
    buffer_format.setAttachment(QOpenGLFramebufferObject.CombinedDepthStencil)
    frame_buffer = QOpenGLFramebufferObject(image_view.width(), image_view.height(), buffer_format)
    frame_buffer.bind()
    paint_device = QOpenGLPaintDevice(image_view.width(), image_view.height())
    painter = QPainter(paint_device)
    image_view.render(painter)
    painter.end()

    img = QImage(frame_buffer.toImage())
    img_np_rgb = qimage2ndarray.rgb_view(img)
    return img_np_rgb


class TestImageRendering:
    def test_random_image_render(self, qtbot, image_view: ImageView2D, random_image: UInt8Array):
        """
        test if image is rendered correctly in a viewport larger than the image at zoom=1
        """
        image_view_width: int = 280
        image_view_height: int = 380
        image_view.setGeometry(0, 0, image_view_width, image_view_height)
        image_view.show()
        image_view.centerImage()
        image_view.doScaleTo(zoom=1.0)
        qtbot.waitExposed(image_view)

        rendered = grab_imageview(image_view)

        image_width, image_height = random_image.shape
        padding_width = (image_view_width - image_width) // 2
        padding_height = (image_view_height - image_height) // 2
        numpy.testing.assert_array_equal(
            rendered[
                padding_height : (image_height + padding_height), padding_width : (image_width + padding_width), 0
            ],
            random_image.squeeze().T,
        )

    @pytest.mark.parametrize(
        "zoom_center, image_slicing, zoom",
        [
            ((0.0, 0.0), (slice(0, 60), slice(0, 120)), 2),
            ((3 / 4 * 120, 3 / 4 * 240), (slice(60, 120), slice(120, 240)), 2),
            ((3 / 4 * 120, 0.0), (slice(60, 120), slice(0, 120)), 2),
            ((0.0, 3 / 4 * 240), (slice(0, 60), slice(120, 240)), 2),
            ((0.0, 0.0), (slice(0, 12), slice(0, 24)), 10),
            ((15 / 16 * 120, 15 / 16 * 240), (slice(105, 120), slice(210, 240)), 8),
            ((11 / 12 * 120, 0.0), (slice(100, 120), slice(0, 40)), 6),
            ((0.0, 5 / 6 * 240), (slice(0, 40), slice(160, 240)), 3),
            ((24.0, 128.0), (slice(19, 29), slice(118, 138)), 12),
        ],
        ids=[
            "upper_left_2x",
            "lower_right_2x",
            "upper_right_2x",
            "lower_left_2x",
            "upper_left_10x",
            "lower_right_8x",
            "upper_right_6x",
            "lower_left_4x",
            "somewhere_in_the_middle_12x",
        ],
    )
    def test_random_image_render_scaling(
        self,
        qtbot,
        image_view: ImageView2D,
        random_image: UInt8Array,
        zoom_center: Tuple[float, float],
        image_slicing: Tuple[slice, slice],
        zoom: int,
    ):
        """
        Test if image with zoom=2 is rendered correctly
        """
        image_view.show()
        image_view.centerOn(QPointF(*zoom_center))
        image_view.doScaleTo(zoom=float(zoom))
        qtbot.waitExposed(image_view)
        rendered = grab_imageview(image_view)

        assert zoom > 0, "The simple striding method for accessing zoomed in values only works if zoom is >1"

        numpy.testing.assert_array_equal(rendered[::zoom, ::zoom, 0], random_image[image_slicing].T)

    def test_random_image_render_panning(self, qtbot, image_view: ImageView2D, random_image: UInt8Array):
        """
        Test if image with zoom=2 is rendered correctly
        """
        vp_width = 10
        vp_height = 20
        pan_x = 100.0
        pan_y = 110.0
        image_view.setGeometry(0, 0, vp_width, vp_height)
        image_view.show()
        qtbot.waitExposed(image_view)
        image_view._deltaPan = QPointF(-pan_x, -pan_y)
        image_view._panning()

        rendered = grab_imageview(image_view)

        numpy.testing.assert_array_equal(rendered[:, :, 0], random_image[int(pan_x): int(pan_x + vp_width), int(pan_y ): int(pan_y + vp_height)].T)



class TestImageViewHelperFunctions:

    @pytest.fixture(autouse=True)
    def setup(self, image_view: ImageView2D):
        self.image_view = image_view

    def test_initial_scale(self):
        init_trafo = self.image_view.transform()
        assert init_trafo.m11() == init_trafo.m22() == 1.0

    def test_doScale(self):
        self.image_view.doScale(2.0)
        trafo = self.image_view.transform()
        assert trafo.m11() == trafo.m22() == 2.0

    def test_doScaleTo(self):
        # change scaling to != 1
        self.image_view.doScale(42.0)
        trafo_1 = self.image_view.transform()
        assert trafo_1.m11() == trafo_1.m22() == 42.0

        self.image_view.doScaleTo(0.5)
        trafo_2 = self.image_view.transform()
        assert trafo_2.m11() == trafo_2.m22() == 0.5

    def test_zoomIn(self):
        self.image_view.zoomIn()
        trafo_1 = self.image_view.transform()
        assert trafo_1.m11() == trafo_1.m22() == 1.1

    def test_zoomOut(self):
        self.image_view.zoomOut()
        trafo_1 = self.image_view.transform()
        assert trafo_1.m11() == trafo_1.m22() == 0.9

    @pytest.mark.parametrize("zoom", (1.0, 2.0, 0.5, 10.0))
    def test_viewPortRect(self, qtbot, zoom):
        """
        ImageView2D.viewPortRect relies on self.viewport().geometry()
        which is only properly set once the window is shown.
        """
        vp_width = 20
        vp_height = 40
        center_x = 42.0
        center_y = 112.0
        self.image_view.setGeometry(0, 0, vp_width, vp_height)
        self.image_view.centerOn(QPointF(center_x, center_y))
        self.image_view.doScaleTo(zoom)
        self.image_view.show()
        qtbot.waitExposed(self.image_view)
        vp_rect = self.image_view.viewportRect()
        assert vp_rect == QRectF(center_x - vp_width / zoom / 2, center_y - vp_height / zoom / 2, 20.0 / zoom, 40.0 / zoom)




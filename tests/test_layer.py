import random
from itertools import count
from unittest import mock

import numpy as np
import pytest
from qtpy.QtGui import QColor, QPen

from volumina import layer
from volumina.pixelpipeline import imagesources as imsrc
from volumina.pixelpipeline.interface import DataSourceABC, PlanarSliceSourceABC

_counter = count()


@pytest.fixture(scope="function")
def src():
    src = mock.Mock(spec=DataSourceABC)
    src.numberOfChannels = 1
    src.dtype = lambda: np.uint8
    return src


@pytest.fixture(scope="function")
def planar_src():
    return mock.Mock(spec=PlanarSliceSourceABC)


@pytest.fixture(scope="function")
def priority():
    # arbitrary limits
    return random.randint(-1000, 1000)


@pytest.fixture(scope="function")
def layer_obj(request, src: DataSourceABC, priority: int):
    layer_cls = request.param

    if issubclass(layer_cls, layer.ColortableLayer):
        l = layer_cls(src, colorTable=[QColor(0, 0, 0, 0).rgba(), QColor(255, 0, 0).rgba()], priority=priority)
    elif issubclass(layer_cls, layer.LabelableSegmentationEdgesLayer):
        l = layer_cls(src, label_class_pens=[QPen()], priority=priority)
    elif issubclass(layer_cls, (layer.Layer)):
        l = layer_cls(src, priority=priority)
    else:
        raise NotImplementedError()

    l.name = "name%d" % next(_counter)
    return l


@pytest.mark.parametrize(
    "layer_obj,expected_source_cls",
    [
        (layer.AlphaModulatedLayer, imsrc.AlphaModulatedImageSource),
        (layer.GrayscaleLayer, imsrc.GrayscaleImageSource),
        (layer.ColortableLayer, imsrc.ColortableImageSource),
        (layer.DummyGraphicsItemLayer, imsrc.DummyItemSource),
        (layer.DummyRasterItemLayer, imsrc.DummyRasterItemSource),
        (layer.SegmentationEdgesLayer, imsrc.SegmentationEdgesItemSource),
        (layer.LabelableSegmentationEdgesLayer, imsrc.SegmentationEdgesItemSource),
    ],
    indirect=["layer_obj"],
)
def test_create_image_source_returns_correct_type_and_prio(
    planar_src: PlanarSliceSourceABC, layer_obj: layer.Layer, expected_source_cls: type, priority: int
):
    new_src = layer_obj.createImageSource([planar_src])

    assert isinstance(new_src, expected_source_cls)
    assert new_src.priority == layer_obj.priority == priority


@pytest.mark.parametrize(
    "layer_obj", [layer.AlphaModulatedLayer, layer.GrayscaleLayer, layer.ColortableLayer], indirect=["layer_obj"]
)
def test_reacts_on_name_change(planar_src: PlanarSliceSourceABC, layer_obj: layer.Layer):
    new_src = layer_obj.createImageSource([planar_src])
    assert new_src.objectName() == layer_obj.name

    layer_obj.name = "newName"
    assert new_src.objectName() == "newName"


def test_create_rgba_sourse(src: DataSourceABC, planar_src: PlanarSliceSourceABC):
    layer_obj = layer.RGBALayer(src, src, src, src)
    new_src = layer_obj.createImageSource([planar_src, planar_src, planar_src, planar_src])
    assert isinstance(new_src, imsrc.RGBAImageSource)

    assert new_src.objectName() == layer_obj.name

    layer_obj.name = "newName"
    assert new_src.objectName() == "newName"

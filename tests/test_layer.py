from unittest import mock

import pytest
import numpy as np
from PyQt5.QtGui import QColor, QPen
from itertools import count

from volumina import layer
from volumina.pixelpipeline.asyncabcs import SourceABC
from volumina.pixelpipeline import imagesources as imsrc


_counter = count()

@pytest.fixture(scope='function')
def src():
    src = mock.Mock(spec=SourceABC)
    src.numberOfChannels = 1
    src.dtype = lambda: np.uint8
    return src


@pytest.fixture(scope='function')
def layer_obj(request, src):
    layer_cls = request.param
    if issubclass(layer_cls, layer.ColortableLayer):
        l = layer_cls(src, colorTable=[QColor(0, 0, 0, 0).rgba(), QColor(255, 0, 0).rgba()])
    elif issubclass(layer_cls, layer.LabelableSegmentationEdgesLayer):
        l = layer_cls(src, label_class_pens=[QPen()])
    else:
        l = layer_cls(src)

    l.name = 'name%d' % next(_counter)
    return l


@pytest.mark.parametrize("layer_obj,expected_source_cls", [
    (layer.AlphaModulatedLayer, imsrc.AlphaModulatedImageSource),
    (layer.GrayscaleLayer, imsrc.GrayscaleImageSource),
    (layer.ColortableLayer, imsrc.ColortableImageSource),
    (layer.DummyGraphicsItemLayer, imsrc.DummyItemSource),
    (layer.DummyRasterItemLayer, imsrc.DummyRasterItemSource),
    (layer.SegmentationEdgesLayer, imsrc.SegmentationEdgesItemSource),
    (layer.LabelableSegmentationEdgesLayer, imsrc.SegmentationEdgesItemSource),
], indirect=["layer_obj"])
def test_create_image_source_returns_correct_type(src, layer_obj, expected_source_cls):
    new_src = layer_obj.createImageSource([src])

    assert isinstance(new_src, expected_source_cls)


@pytest.mark.parametrize("layer_obj", [
    layer.AlphaModulatedLayer,
    layer.GrayscaleLayer,
    layer.ColortableLayer,
], indirect=["layer_obj"])
def test_reacts_on_name_change(src, layer_obj):
    new_src = layer_obj.createImageSource([src])
    assert new_src.objectName() == layer_obj.name

    layer_obj.name = 'newName'
    assert new_src.objectName() == 'newName'


def test_create_rgba_sourse(src):
    layer_obj = layer.RGBALayer(src, src, src, src)
    new_src = layer_obj.createImageSource([src, src, src, src])
    assert isinstance(new_src, imsrc.RGBAImageSource)

    assert new_src.objectName() == layer_obj.name

    layer_obj.name = 'newName'
    assert new_src.objectName() == 'newName'

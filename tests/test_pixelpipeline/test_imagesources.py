import contextlib
import logging

from unittest import mock

import pytest

from PyQt5.QtCore import QRect
from volumina.pixelpipeline import imagesources as imsrc
from volumina.pixelpipeline.interface import ImageSourceABC, PlanarSliceSourceABC


class PipelineCfg:
    def __init__(self, verbose):
        self.verbose_pixelpipeline = verbose


@pytest.fixture
def verbose_pipeline():
    patcher = mock.patch("volumina.config.CONFIG", new_callable=lambda: PipelineCfg(verbose=True))
    patcher.start()
    yield
    patcher.stop()


@pytest.fixture
def nonverbose_pipeline():
    patcher = mock.patch("volumina.config.CONFIG", new_callable=lambda: PipelineCfg(verbose=False))
    patcher.start()
    yield
    patcher.stop()


@pytest.fixture(scope="function")
def img_source(request):
    cls = request.param
    src = mock.MagicMock(spec=PlanarSliceSourceABC)
    layer = mock.MagicMock()

    if issubclass(cls, (imsrc.GrayscaleImageSource, imsrc.AlphaModulatedImageSource)):
        src = cls(src, layer)
    elif issubclass(cls, imsrc.ColortableImageSource):
        layer.normalize = [None]
        src = cls(src, layer)
    elif issubclass(cls, imsrc.RGBAImageSource):
        src = cls(src, src, src, src, layer)

    src.setObjectName("test")
    return src


@pytest.mark.parametrize(
    "img_source",
    [imsrc.GrayscaleImageSource, imsrc.AlphaModulatedImageSource, imsrc.ColortableImageSource, imsrc.RGBAImageSource],
    indirect=True,
)
def test_pixelpipeline_verbose_log(img_source, verbose_pipeline, caplog):
    x, y, w, h = 10, 11, 21, 22

    rect = QRect(x, y, w, h)
    img_source.request(rect)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.args == (type(img_source).__qualname__, "test", x, y, w, h)


@pytest.mark.parametrize(
    "img_source",
    [imsrc.GrayscaleImageSource, imsrc.AlphaModulatedImageSource, imsrc.ColortableImageSource, imsrc.RGBAImageSource],
    indirect=True,
)
def test_pixelpipeline_nonverbose_log(img_source, nonverbose_pipeline, caplog):
    x, y, w, h = 10, 11, 21, 22

    rect = QRect(x, y, w, h)
    img_source.request(rect)

    assert len(caplog.records) == 0

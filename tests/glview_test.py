from unittest.mock import patch, PropertyMock
import importlib

import volumina.view3d.glview as glview


def test_import_gl_enabled():
    with patch("volumina.config._Config.show_3d_widget", new=PropertyMock(return_value=True)):
        importlib.reload(glview)
        assert glview.GLView == glview.GLViewReal


def test_import_gl_disabled():
    with patch("volumina.config._Config.show_3d_widget", new=PropertyMock(return_value=False)):
        importlib.reload(glview)
        assert glview.GLView == glview.GLViewMock

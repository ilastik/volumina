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
import pytest
from qtpy.QtCore import QRectF, Qt
from qtpy.QtGui import QColor, QTransform
from qtpy.QtWidgets import QGraphicsScene, QGraphicsView

from volumina.crossHairCursor import CrossHairCursor


class MockImageScene(QGraphicsScene):
    def __init__(self):
        super().__init__()
        self.data2scene = QTransform()


def test_bounding_rect(qtbot):
    cursor = CrossHairCursor()
    scene = MockImageScene()
    scene.addItem(cursor)
    view = QGraphicsView()
    view.setScene(scene)
    qtbot.addWidget(view)

    cursor.dataShape = (42, 60)

    rect = cursor.boundingRect()

    assert isinstance(rect, QRectF)
    assert rect.width() == 42
    assert rect.height() == 60


def test_data_shape():
    cursor = CrossHairCursor()

    cursor.dataShape = (42, 1024)

    assert cursor.dataShape == (42, 1024)
    assert cursor._width == 42
    assert cursor._height == 1024


@pytest.mark.parametrize("position", [(0, 0), (1, 1), (4, 2), (1000, 50000), (-10, 20)])
def test_show_xy_position(position: tuple[int, int]):
    cursor = CrossHairCursor()

    cursor.showXYPosition(*position)
    assert cursor.x == position[0]
    assert cursor.y == position[1]


@pytest.mark.parametrize("brush_size", [1, 4, 13, 42, 100])
def test_set_brush_size(brush_size: int):
    cursor = CrossHairCursor()

    cursor.setBrushSize(brush_size)

    assert cursor.brushSize == brush_size


@pytest.mark.parametrize("color", [Qt.green, Qt.red, QColor.fromRgba(0xEEAACCDD)])
def test_set_color(color: QColor):
    cursor = CrossHairCursor()

    cursor.setColor(color)

    assert cursor.penSolid.color() == color
    assert cursor.penDotted.color() == color


@pytest.mark.parametrize("enabled", [True, False])
def test_enabled(enabled: bool):
    cursor = CrossHairCursor()

    cursor.enabled = enabled

    assert cursor.enabled is enabled


@pytest.mark.parametrize("state_before", [True, False])
def test_hidden_context_restores_state(state_before: bool):
    cursor = CrossHairCursor()

    cursor.setVisible(state_before)

    with cursor.hidden():
        assert not cursor.isVisible()

    assert cursor.isVisible() == state_before

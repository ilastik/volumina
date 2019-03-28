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
"""Colortables.

Colortables map from raw pixel values to colors and are stored as a
list of QRgb values. The list indices are interpreted as the raw
values.

Example:
colortable = [QColor(Qt.Red).rgba(), QColor(Qt.Black).rgba()]

This table is applicable to raw with two different values 0 and 1. 0s
will be displayed red and 1s black.

"""
from __future__ import division

from builtins import range
from past.utils import old_div
import warnings
import itertools
import numpy as np
from PyQt5.QtGui import QColor


def matplotlib_to_qt4_colortable(cmap_name, N, asLong=True):
    """
    get a colortable of desired N in Qt4 format as required from the colortable Layer
    cmap_name can be any matplotlib colortable
    """
    try:
        import matplotlib.cm as cm
    except:
        raise RuntimeError("this function requires matplotlib")

    cmap = cm.get_cmap(cmap_name, N)
    cmap = cmap(np.arange(N))[:, :-1]
    colortable = []
    for el in cmap:
        r, g, b = el * 255
        color = QColor(r, g, b)
        if asLong:
            color = color.rgba()
        colortable.append(color)
    return colortable


def jet(N=256):
    ###This makes a jet colormap with 256 spaces
    return matplotlib_to_qt4_colortable("jet", N=N)


def jetTransparent(N=256):
    ###This makes a jet colormap with 256 spaces
    colortable = matplotlib_to_qt4_colortable("jet", N=N, asLong=False)
    # colortable[0] = QColor(0,0,0,0)
    for i, color in enumerate(colortable):
        color = colortable[i]
        color.setAlpha(i)
        colortable[i] = color.rgba()
    return colortable


# A jet colortable for the first half, only increasing in opacity for the second
def partlyJetTransparent(N=256, ratio=old_div(2.0, 3)):
    colortable = matplotlib_to_qt4_colortable("jet", N=int(ratio * N), asLong=False)
    # colortable[0] = QColor(0,0,0,0)
    maxCol = colortable[-1]
    for i in range(int(ratio * N), 2 * N):
        colortable.append(maxCol)
    for i, color in enumerate(colortable):
        color = colortable[i]
        color.setAlpha(min(int(old_div(i, ratio)), 255))
        colortable[i] = color.rgba()
    return colortable


# taken from https://sashat.me/2017/01/11/list-of-20-simple-distinct-colors/
default16_new = [
    QColor(0, 0, 0, 0).rgba(),  # transparent
    QColor(255, 225, 25).rgba(),  # yellow
    QColor(0, 130, 200).rgba(),  # blue
    QColor(230, 25, 75).rgba(),  # red
    QColor(70, 240, 240).rgba(),  # cyan
    QColor(60, 180, 75).rgba(),  # green
    QColor(250, 190, 190).rgba(),  # pink
    QColor(170, 110, 40).rgba(),  # brown
    QColor(145, 30, 180).rgba(),  # purple
    QColor(0, 128, 128).rgba(),  # teal
    QColor(245, 130, 48).rgba(),  # orange
    QColor(240, 50, 230).rgba(),  # magenta
    QColor(210, 245, 60).rgba(),  # lime
    QColor(255, 215, 180).rgba(),  # coral
    QColor(230, 190, 255).rgba(),  # lavender
    QColor(128, 128, 128).rgba(),  # gray
]


default16 = [
    QColor(0, 0, 255).rgba(),
    QColor(255, 255, 0).rgba(),
    QColor(255, 0, 0).rgba(),
    QColor(0, 255, 0).rgba(),
    QColor(0, 255, 255).rgba(),
    QColor(255, 0, 255).rgba(),
    QColor(255, 105, 180).rgba(),  # hot pink
    QColor(102, 205, 170).rgba(),  # dark aquamarine
    QColor(165, 42, 42).rgba(),  # brown
    QColor(0, 0, 128).rgba(),  # navy
    QColor(255, 165, 0).rgba(),  # orange
    QColor(173, 255, 47).rgba(),  # green-yellow
    QColor(128, 0, 128).rgba(),  # purple
    QColor(192, 192, 192).rgba(),  # silver
    QColor(240, 230, 140).rgba(),  # khaki
    QColor(69, 69, 69).rgba(),
]  # dark grey

random256 = [
    QColor(201, 200, 200).rgba(),
    QColor(0, 0, 255).rgba(),
    QColor(255, 0, 0).rgba(),
    QColor(0, 255, 0).rgba(),
    QColor(20, 20, 192).rgba(),
    QColor(255, 0, 182).rgba(),
    QColor(0, 121, 0).rgba(),
    QColor(255, 211, 0).rgba(),
    QColor(0, 159, 255).rgba(),
    QColor(154, 77, 66).rgba(),
    QColor(0, 255, 190).rgba(),
    QColor(120, 63, 193).rgba(),
    QColor(31, 150, 152).rgba(),
    QColor(255, 172, 253).rgba(),
    QColor(177, 204, 113).rgba(),
    QColor(241, 8, 92).rgba(),
    QColor(254, 143, 66).rgba(),
    QColor(221, 0, 255).rgba(),
    QColor(32, 121, 1).rgba(),
    QColor(114, 0, 85).rgba(),
    QColor(118, 108, 149).rgba(),
    QColor(2, 173, 36).rgba(),
    QColor(200, 255, 0).rgba(),
    QColor(136, 108, 0).rgba(),
    QColor(255, 183, 159).rgba(),
    QColor(133, 133, 103).rgba(),
    QColor(161, 3, 0).rgba(),
    QColor(20, 249, 255).rgba(),
    QColor(0, 71, 158).rgba(),
    QColor(220, 94, 147).rgba(),
    QColor(147, 212, 255).rgba(),
    QColor(0, 76, 255).rgba(),
    QColor(0, 66, 80).rgba(),
    QColor(57, 167, 106).rgba(),
    QColor(238, 112, 254).rgba(),
    QColor(0, 0, 100).rgba(),
    QColor(171, 245, 204).rgba(),
    QColor(161, 146, 255).rgba(),
    QColor(164, 255, 115).rgba(),
    QColor(255, 206, 113).rgba(),
    QColor(124, 0, 21).rgba(),
    QColor(212, 173, 197).rgba(),
    QColor(251, 118, 111).rgba(),
    QColor(171, 188, 0).rgba(),
    QColor(117, 0, 215).rgba(),
    QColor(166, 0, 154).rgba(),
    QColor(0, 115, 254).rgba(),
    QColor(165, 93, 174).rgba(),
    QColor(98, 132, 2).rgba(),
    QColor(0, 121, 168).rgba(),
    QColor(0, 255, 131).rgba(),
    QColor(86, 53, 0).rgba(),
    QColor(159, 0, 63).rgba(),
    QColor(145, 45, 66).rgba(),
    QColor(255, 242, 187).rgba(),
    QColor(0, 93, 67).rgba(),
    QColor(252, 255, 124).rgba(),
    QColor(159, 191, 186).rgba(),
    QColor(167, 84, 19).rgba(),
    QColor(74, 211, 108).rgba(),
    QColor(0, 16, 243).rgba(),
    QColor(145, 78, 109).rgba(),
    QColor(207, 149, 0).rgba(),
    QColor(195, 187, 255).rgba(),
    QColor(253, 68, 64).rgba(),
    QColor(66, 78, 32).rgba(),
    QColor(192, 1, 0).rgba(),
    QColor(181, 131, 84).rgba(),
    QColor(132, 233, 147).rgba(),
    QColor(96, 217, 0).rgba(),
    QColor(255, 111, 211).rgba(),
    QColor(229, 75, 63).rgba(),
    QColor(254, 100, 0).rgba(),
    QColor(228, 3, 127).rgba(),
    QColor(17, 199, 174).rgba(),
    QColor(210, 129, 139).rgba(),
    QColor(91, 118, 124).rgba(),
    QColor(32, 59, 106).rgba(),
    QColor(180, 84, 255).rgba(),
    QColor(226, 8, 210).rgba(),
    QColor(0, 1, 184).rgba(),
    QColor(93, 132, 68).rgba(),
    QColor(50, 184, 163).rgba(),
    QColor(97, 123, 201).rgba(),
    QColor(98, 0, 122).rgba(),
    QColor(126, 190, 58).rgba(),
    QColor(0, 60, 183).rgba(),
    QColor(255, 253, 0).rgba(),
    QColor(7, 197, 226).rgba(),
    QColor(180, 167, 57).rgba(),
    QColor(148, 186, 138).rgba(),
    QColor(204, 187, 160).rgba(),
    QColor(55, 0, 224).rgba(),
    QColor(0, 92, 1).rgba(),
    QColor(150, 122, 129).rgba(),
    QColor(39, 136, 38).rgba(),
    QColor(206, 130, 180).rgba(),
    QColor(150, 164, 196).rgba(),
    QColor(180, 32, 128).rgba(),
    QColor(110, 86, 180).rgba(),
    QColor(147, 0, 185).rgba(),
    QColor(199, 48, 61).rgba(),
    QColor(115, 102, 255).rgba(),
    QColor(15, 187, 253).rgba(),
    QColor(172, 164, 100).rgba(),
    QColor(182, 117, 250).rgba(),
    QColor(216, 220, 254).rgba(),
    QColor(87, 141, 113).rgba(),
    QColor(216, 85, 34).rgba(),
    QColor(0, 196, 103).rgba(),
    QColor(243, 165, 105).rgba(),
    QColor(216, 145, 182).rgba(),
    QColor(1, 24, 219).rgba(),
    QColor(52, 66, 54).rgba(),
    QColor(255, 154, 0).rgba(),
    QColor(87, 95, 1).rgba(),
    QColor(198, 241, 79).rgba(),
    QColor(255, 95, 133).rgba(),
    QColor(123, 172, 240).rgba(),
    QColor(120, 100, 49).rgba(),
    QColor(162, 133, 204).rgba(),
    QColor(105, 255, 220).rgba(),
    QColor(198, 82, 100).rgba(),
    QColor(121, 26, 64).rgba(),
    QColor(0, 238, 70).rgba(),
    QColor(231, 207, 69).rgba(),
    QColor(217, 128, 233).rgba(),
    QColor(255, 211, 87).rgba(),
    QColor(209, 255, 141).rgba(),
    QColor(108, 58, 3).rgba(),
    QColor(87, 163, 193).rgba(),
    QColor(211, 153, 116).rgba(),
    QColor(203, 111, 79).rgba(),
    QColor(62, 131, 0).rgba(),
    QColor(0, 117, 223).rgba(),
    QColor(112, 176, 88).rgba(),
    QColor(209, 24, 0).rgba(),
    QColor(0, 30, 107).rgba(),
    QColor(105, 200, 197).rgba(),
    QColor(255, 203, 255).rgba(),
    QColor(233, 194, 137).rgba(),
    QColor(191, 129, 46).rgba(),
    QColor(69, 42, 145).rgba(),
    QColor(171, 76, 194).rgba(),
    QColor(14, 117, 61).rgba(),
    QColor(0, 184, 25).rgba(),
    QColor(118, 73, 127).rgba(),
    QColor(255, 169, 200).rgba(),
    QColor(94, 55, 217).rgba(),
    QColor(238, 230, 138).rgba(),
    QColor(159, 54, 33).rgba(),
    QColor(80, 0, 148).rgba(),
    QColor(189, 144, 128).rgba(),
    QColor(0, 109, 126).rgba(),
    QColor(88, 223, 96).rgba(),
    QColor(71, 80, 103).rgba(),
    QColor(1, 93, 159).rgba(),
    QColor(99, 48, 60).rgba(),
    QColor(2, 206, 148).rgba(),
    QColor(139, 83, 37).rgba(),
    QColor(171, 0, 255).rgba(),
    QColor(141, 42, 135).rgba(),
    QColor(85, 83, 148).rgba(),
    QColor(150, 255, 0).rgba(),
    QColor(0, 152, 123).rgba(),
    QColor(255, 138, 203).rgba(),
    QColor(222, 69, 200).rgba(),
    QColor(107, 109, 230).rgba(),
    QColor(30, 0, 150).rgba(),
    QColor(173, 76, 138).rgba(),
    QColor(255, 134, 161).rgba(),
    QColor(0, 160, 155).rgba(),
    QColor(138, 205, 0).rgba(),
    QColor(111, 202, 157).rgba(),
    QColor(225, 75, 253).rgba(),
    QColor(255, 176, 77).rgba(),
    QColor(229, 232, 57).rgba(),
    QColor(114, 16, 255).rgba(),
    QColor(111, 82, 101).rgba(),
    QColor(134, 137, 48).rgba(),
    QColor(99, 38, 80).rgba(),
    QColor(105, 38, 32).rgba(),
    QColor(200, 110, 0).rgba(),
    QColor(209, 164, 255).rgba(),
    QColor(198, 210, 86).rgba(),
    QColor(79, 103, 77).rgba(),
    QColor(174, 165, 166).rgba(),
    QColor(170, 45, 101).rgba(),
    QColor(199, 81, 175).rgba(),
    QColor(255, 89, 172).rgba(),
    QColor(146, 102, 78).rgba(),
    QColor(102, 134, 184).rgba(),
    QColor(111, 152, 255).rgba(),
    QColor(92, 255, 159).rgba(),
    QColor(172, 137, 178).rgba(),
    QColor(210, 34, 98).rgba(),
    QColor(199, 207, 147).rgba(),
    QColor(255, 185, 30).rgba(),
    QColor(250, 148, 141).rgba(),
    QColor(49, 63, 145).rgba(),
    QColor(254, 81, 97).rgba(),
    QColor(254, 141, 100).rgba(),
    QColor(134, 129, 224).rgba(),
    QColor(201, 162, 84).rgba(),
    QColor(199, 232, 240).rgba(),
    QColor(68, 152, 0).rgba(),
    QColor(147, 172, 58).rgba(),
    QColor(22, 150, 28).rgba(),
    QColor(8, 84, 121).rgba(),
    QColor(116, 45, 0).rgba(),
    QColor(104, 60, 255).rgba(),
    QColor(64, 41, 147).rgba(),
    QColor(164, 113, 215).rgba(),
    QColor(207, 0, 155).rgba(),
    QColor(118, 1, 35).rgba(),
    QColor(83, 0, 88).rgba(),
    QColor(0, 82, 232).rgba(),
    QColor(43, 92, 87).rgba(),
    QColor(160, 217, 146).rgba(),
    QColor(176, 26, 229).rgba(),
    QColor(29, 3, 155).rgba(),
    QColor(122, 58, 159).rgba(),
    QColor(100, 120, 240).rgba(),
    QColor(160, 100, 105).rgba(),
    QColor(106, 157, 160).rgba(),
    QColor(153, 219, 113).rgba(),
    QColor(192, 56, 207).rgba(),
    QColor(125, 255, 89).rgba(),
    QColor(149, 0, 34).rgba(),
    QColor(213, 162, 223).rgba(),
    QColor(22, 131, 204).rgba(),
    QColor(166, 249, 69).rgba(),
    QColor(109, 105, 97).rgba(),
    QColor(86, 188, 78).rgba(),
    QColor(255, 109, 81).rgba(),
    QColor(255, 3, 248).rgba(),
    QColor(255, 0, 73).rgba(),
    QColor(202, 0, 35).rgba(),
    QColor(67, 109, 18).rgba(),
    QColor(234, 170, 173).rgba(),
    QColor(191, 165, 0).rgba(),
    QColor(38, 145, 51).rgba(),
    QColor(85, 185, 2).rgba(),
    QColor(121, 182, 158).rgba(),
    QColor(254, 236, 212).rgba(),
    QColor(139, 165, 89).rgba(),
    QColor(141, 254, 193).rgba(),
    QColor(0, 134, 43).rgba(),
    QColor(174, 17, 40).rgba(),
    QColor(255, 221, 246).rgba(),
    QColor(17, 26, 146).rgba(),
    QColor(154, 66, 84).rgba(),
    QColor(149, 157, 238).rgba(),
    QColor(126, 130, 72).rgba(),
    QColor(58, 6, 184).rgba(),
    QColor(240, 4, 7).rgba(),
]


def create_default_8bit():
    """Create a colortable suitable for 8bit data.

    Repeatedly applies the default16 colortable to the whole 8bit range.
    
    """
    return [color for color in itertools.islice(itertools.cycle(default16), 0, 2 ** 8)]


def create_default_16bit():
    """Create a colortable suitable for 16bit data.

    Repeatedly applies the default16 colortable to the whole 16bit range.
    
    """
    return [color for color in itertools.islice(itertools.cycle(default16), 0, 2 ** 16)]


def create_random_8bit():
    """Create a colortable suitable for 8bit data.
    
    Creates a pseudo-random colortable in the 8bit range"""
    return random256


def create_random_16bit():
    """Create a colortable suitable for 16bit data.
    
    Repeatedly applies a pseudo-random colortable to the whole 16bit range"""
    return [color for color in itertools.islice(itertools.cycle(random256), 0, 2 ** 16)]


if __name__ == "__main__":
    from volumina.api import *
    from PyQt5.QtWidgets import QApplication
    import numpy
    from volumina.pixelpipeline.datasourcefactories import *

    app = QApplication(sys.argv)
    v = Viewer()
    v.show()
    a = np.zeros((256, 256))
    for i in range(256):
        a[i] = i

    source, sh = createDataSource(a, True)

    layer = ColortableLayer(source, jet(256))
    # layer = GrayscaleLayer(source)

    v.layerstack.append(layer)
    v.dataShape = sh

    v.show()
    app.exec_()

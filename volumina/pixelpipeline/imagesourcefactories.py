# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

import copy
from volumina.multimethods import multimethod
from volumina.layer import GrayscaleLayer, RGBALayer, ColortableLayer, \
                               AlphaModulatedLayer, ClickableColortableLayer
from imagesources import GrayscaleImageSource, ColortableImageSource, \
                         RGBAImageSource, AlphaModulatedImageSource
from datasources import ConstantSource

@multimethod(AlphaModulatedLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    src = AlphaModulatedImageSource( datasources2d[0], layer )
    src.setObjectName(layer.name)
    layer.nameChanged.connect(lambda x: src.setObjectName(str(x)))
    layer.tintColorChanged.connect(lambda: src.setDirty((slice(None,None), slice(None,None))))
    return src

@multimethod(GrayscaleLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    src = GrayscaleImageSource( datasources2d[0], layer )
    src.setObjectName(layer.name)
    layer.nameChanged.connect(lambda x: src.setObjectName(str(x)))
    return src

@multimethod(ColortableLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    src = ColortableImageSource( datasources2d[0], layer )
    src.setObjectName(layer.name)
    layer.nameChanged.connect(lambda x: src.setObjectName(str(x)))
    return src

@multimethod(ClickableColortableLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    src = ColortableImageSource( datasources2d[0], layer )
    src.setObjectName(layer.name)
    layer.nameChanged.connect(lambda x: src.setObjectName(str(x)))
    return src

@multimethod(RGBALayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 4
    ds = copy.copy(datasources2d)
    for i in xrange(3):
        if datasources2d[i] == None:
            ds[i] = ConstantSource(layer.color_missing_value)
    guarantees_opaqueness = False
    if datasources2d[3] == None:
        ds[3] = ConstantSource(layer.alpha_missing_value)
        guarantees_opaqueness = True if layer.alpha_missing_value == 255 else False
    src = RGBAImageSource( ds[0], ds[1], ds[2], ds[3], layer, guarantees_opaqueness = guarantees_opaqueness )
    src.setObjectName(layer.name)
    layer.nameChanged.connect(lambda x: src.setObjectName(str(x)))
    layer.normalizeChanged.connect(lambda: src.setDirty((slice(None,None), slice(None,None))))
    return src

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
#		   http://ilastik.org/license/
###############################################################################
import copy
from volumina.multimethods import multimethod
from volumina.layer import GrayscaleLayer, RGBALayer, ColortableLayer, \
                               AlphaModulatedLayer, ClickableColortableLayer, \
                               DummyGraphicsItemLayer, DummyRasterItemLayer, \
                               SegmentationEdgesLayer, LabelableSegmentationEdgesLayer
from .imagesources import GrayscaleImageSource, ColortableImageSource, \
                         RGBAImageSource, AlphaModulatedImageSource, \
                         DummyItemSource, DummyRasterItemSource, \
                         SegmentationEdgesItemSource
                         
from .datasources import ConstantSource

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
    for i in range(3):
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

@multimethod(DummyGraphicsItemLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    return DummyItemSource(datasources2d[0])

@multimethod(DummyRasterItemLayer, list)
def createImageSource( layer, datasources2d ):
    return DummyRasterItemSource()

@multimethod(SegmentationEdgesLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    return SegmentationEdgesItemSource(layer, datasources2d[0])

@multimethod(LabelableSegmentationEdgesLayer, list)
def createImageSource( layer, datasources2d ):
    assert len(datasources2d) == 1
    return SegmentationEdgesItemSource(layer, datasources2d[0])

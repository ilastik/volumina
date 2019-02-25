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
# check for optional dependencies
import pytest

has_dependencies = True
try:
    import vigra
    from lazyflow.graph import Operator, OutputSlot, Graph
except ImportError:
    has_dependencies = False
    import os.path
    import warnings
    warnings.warn("Modules vigra and/or lazyflow not found. "
          "Will not import %s" % os.path.basename(__file__)) 

if has_dependencies:
    import unittest as ut
    import os
    import time
    
    from PyQt5.QtCore import Qt
    from PyQt5.QtGui import QImage, QPainter
    from PyQt5.QtWidgets import QApplication
    
    from qimage2ndarray import byte_view
    import numpy

    from volumina.imageScene2D import ImageScene2D
    from volumina.positionModel import PositionModel
    from volumina.pixelpipeline.datasources import LazyflowSource
    from volumina.pixelpipeline.slicesources import projectionAlongTZC, SliceSource
    from volumina.pixelpipeline.imagepump import StackedImageSources
    from volumina.layerstack import LayerStackModel
    from volumina.layer import GrayscaleLayer
    import volumina.pixelpipeline.imagesourcefactories as imsfac
    import volumina.tiling

    class OpLazy(Operator):
        Output = OutputSlot()

        def __init__( self, g ):
            super(OpLazy, self).__init__(graph=g)
            self.shape = (1,30,30,30,1)
            self.dtype = numpy.uint8 
            self.a = numpy.ones(self.shape, dtype=self.dtype)
            self.delay = 0

        def setConstant(self, c):
            self.a[:] = c
            self.Output.setDirty(slice(None))

        def setDelay(self, d):
            self.delay = d

        def setupOutputs(self):
            self.Output.meta.shape = self.shape 
            self.Output.meta.dtype = self.dtype
            self.Output.meta.axistags = vigra.AxisTags([vigra.AxisInfo("t"), vigra.AxisInfo("x"), vigra.AxisInfo("y"), vigra.AxisInfo("z"), vigra.AxisInfo("c")])

        def execute(self, slot, subindex, roi, result):
            key = roi.toSlice()
            result[:] = self.a[key]
            time.sleep(self.delay)
            return result

    @pytest.mark.usefixtures('qtapp')
    class ImageScene2D_LazyTest( ut.TestCase ):
        def setUp( self ):
            self.layerstack = LayerStackModel()
            self.sims = StackedImageSources( self.layerstack )

            self.g = Graph()
            self.op = OpLazy(self.g)
            self.ds = LazyflowSource( self.op.Output )

            self.ss = SliceSource( self.ds, projectionAlongTZC )

            self.layer = GrayscaleLayer(self.ds, normalize = False)
            self.layerstack.append(self.layer)
            self.ims = imsfac.createImageSource( self.layer, [self.ss] )
            self.sims.register(self.layer, self.ims)

            self.scene = ImageScene2D(PositionModel(), (0,0,0), preemptive_fetch_number=0)
            self.scene.setCacheSize(1)

            self.scene.stackedImageSources = self.sims
            self.scene.dataShape = (30,30)

        def renderScene( self, s, exportFilename=None, joinRendering=True):
            img = QImage(30,30,QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.white)
            p = QPainter(img)

            s.render(p) #trigger a rendering of the whole scene
            if joinRendering:
                # wait for all the data to arrive
                s.joinRenderingAllTiles( viewport_only=False ) # There is no viewport!
                # finally, render everything
                s.render(p)
            p.end()

            if exportFilename is not None:
                img.save(exportFilename)
            return byte_view(img)

        def testLazy( self ):
            for i in range(3):
                self.op.setConstant(i)
                aimg = self.renderScene(self.scene, "/tmp/a_%03d.png" % i)
                assert numpy.all(aimg[:,:,0] == i), "!= %d, [0,0,0]=%d" % (i, aimg[0,0,0])

                self.op.setConstant(42)
                self.op.setDelay(1)
                aimg = self.renderScene(self.scene, joinRendering=False, exportFilename="/tmp/x_%03d.png" % i)
                #this should be "i", not 255 (the default background for the imagescene)
                assert numpy.all(aimg[:,:,0] == i), "!= %d, [0,0,0]=%d" % (i, aimg[0,0,0])
                
                # Now give the scene time to update before we change it again...
                self.scene.joinRenderingAllTiles( viewport_only=False )

if __name__ == '__main__':
    import unittest as ut
    ut.main()

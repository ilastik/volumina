import unittest as ut
has_vigra = True
try:
    import vigra
except ImportError:
    has_vigra = False

import os
import time

from PyQt4.QtCore import Qt
from PyQt4.QtGui import QImage, QPainter, QApplication

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

has_lazyflow = True
try:
    from lazyflow.graph import Operator, OutputSlot, Graph
except ImportError:
    has_lazyflow = False

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

@ut.skipUnless(has_vigra, "module vigra not found")
@ut.skipUnless(has_lazyflow, "module lazyflow not found")
class ImageScene2D_LazyTest( ut.TestCase ):

    @classmethod
    def setUpClass(cls):
        cls.app = None
        if QApplication.instance():
            cls.app = QApplication.instance()
        else:
            cls.app = QApplication([], False)

    @classmethod
    def tearDownClass(cls):
        del cls.app

    def setUp( self ):
        self.layerstack = LayerStackModel()
        self.sims = StackedImageSources( self.layerstack )

        self.g = Graph()
        self.op = OpLazy(self.g)
        self.ds = LazyflowSource( self.op.Output )
        
        self.ss = SliceSource( self.ds, projectionAlongTZC )
        
        self.layer = GrayscaleLayer(self.ds)
        self.layerstack.append(self.layer)
        self.ims = imsfac.createImageSource( self.layer, [self.ss] )
        self.sims.register(self.layer, self.ims)

        self.scene = ImageScene2D(PositionModel(), (0,0,0), preemptive_fetch_number=0)
        self.scene.setCacheSize(1)

        self.scene.stackedImageSources = self.sims
        self.scene.dataShape = (30,30)

    def tearDown( self ):
        if self.scene._tileProvider:
            self.scene._tileProvider.notifyThreadsToStop()
            self.scene._tileProvider.joinThreads()

    def renderScene( self, s, exportFilename=None, joinRendering=True):
        img = QImage(30,30,QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.white)
        p = QPainter(img)
        
        s.render(p) #trigger a rendering of the whole scene
        if joinRendering:
            #wait for all the data to arrive
            s.joinRendering()
            #finally, render everything
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

if __name__ == '__main__':
    ut.main()

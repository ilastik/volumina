from __future__ import division
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
###
### lazyflow input
###
from past.utils import old_div
_has_lazyflow = True
try:
    from lazyflow.graph import  Operator, InputSlot, OutputSlot
    from lazyflow.operators import OpArrayPiper  
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False

import numpy as np
import time

class OpDelay(OpArrayPiper):
    def __init__( self, g, delay_factor = 0.000001 ):
        super(OpDelay, self).__init__(graph=g)
        self._delay_factor = delay_factor

    def execute(self, slot, subindex, roi, result):
        key = roi.toSlice()
        req = self.inputs["Input"][key].writeInto(result)
        req.wait()
        t = self._delay_factor*result.nbytes
        #print "Delay: " + str(t) + " secs."
        time.sleep(t)    
        return result

class OpDataProvider5D(Operator):
    name = "Data Provider 5D"
    category = "Input"
    
    inputSlots = [InputSlot("Changedata")]
    outputSlots = [OutputSlot("Data5D")]
    
    def __init__(self, g, fn):
        Operator.__init__(self,g)
        self._data = np.load(fn)
        oslot = self.outputs["Data5D"]
        oslot.meta.shape = self._data.shape
        oslot.meta.dtype = self._data.dtype
    
    def execute(self, slot, subindex, roi, result):
        key = roi.toSlice()
        result[:] = self._data[key]
        result[:] = old_div(result, 10)
        return result
    
    def setInSlot(self, slot, subindex, roi, value):
        key = roi.toSlice()
        self._data[key] = value
        self.outputs["Output"].setDirty(key)

'''
if __name__ == "__main__":
    import sys
    fn = sys.argv[1]
    
    g = Graph()
    
    op1 = OpDataProvider5D(graph=g, fn=fn)
    op2 = OpDelay(graph=g, 0.0000000)
    
    op2.inputs["Input"].connect(op1.outputs["Data5D"])
    
    #result = op2.outputs["Output"][0,:,:,1,0].allocate().wait()
    #print "obtained data with shape " + str(result.shape)
    
    #######
    from scipy.misc import imshow
    from PyQt5.QtCore import QTimer
    from PyQt5.QtWidgets import QApplication, QLabel, QPixmap, QImage
    from qimage2ndarray import gray2qimage
    #make the program quit on Ctrl+C
    import signal
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    
    qapp = QApplication([])
    label = QLabel()
    label.fullScreen = True
    
    data_source = LazyflowDataSource( op2, "Output" )
    slicer = SpatialSliceSource5D(data_source)
    
    def show():
        img = gray2qimage(slicer.slice)
        img = img.convertToFormat(QImage.Format_ARGB32_Premultiplied)
        pixmap = QPixmap()
        pixmap.convertFromImage(img)
        label.setPixmap(pixmap)
    
    slicer.changed.connect(show)
    
    slicer.request()
    
    def changeChannel():
        print "changeChannel"
        if slicer.channel == 0:
            slicer.channel = 1
        else:
            slicer.channel = 0
        slicer.request()
    
    import time
    def sliceUp():
        z = int(time.time() % 10)
        print "sliceUp " + str(z)
        slicer.through = z
        slicer.request()
    
    timer = QTimer()
    timer.timeout.connect(changeChannel)
    #timer.start(400)
    
    timer2 = QTimer()
    timer2.timeout.connect(sliceUp)
    timer2.start(3000)
    
    
    label.show()
    qapp.exec_()
    
    g.finalize()
'''

from PyQt4.QtCore import QThread, pyqtSignal, Qt, QMutex, QRect
from PyQt4.QtGui import QPainter, QImage
import numpy

import volumina

import threading
from collections import deque

#*******************************************************************************
# I m a g e S c e n e R e n d e r T h r e a d                                  *
#*******************************************************************************

class ImageSceneRenderThread(QThread):
    """
    A signal is emitted on completion of a request `patchAvailable`
    """
    
    patchAvailable = pyqtSignal(QRect) #bounding box of rendered patches
    
    def __init__(self, stackedImageSources, parent=None):
        #assert hasattr(stackedImageSources, '__iter__')
        QThread.__init__(self, parent)
        self._imagePatches = None

        self._tiling = None

        self._queue = deque() #thread-safe deque
        
        self._dataPending = threading.Event()
        self._dataPending.clear()
        self._stopped = False

        self._stackedIms = stackedImageSources

    def stop(self):
        self._stopped = True
        self._dataPending.set()
        self.wait()
        assert not self.isRunning()
        
    def start(self, tiling):
        self._queue = deque()
        self._tiling = tiling
        self._stopped = False

        self._numLayers = len(self._stackedIms)

        shape = (self._numLayers, len(self._tiling))
        self._imageLayersCurrent = numpy.ndarray(shape, dtype = object)
        self._imageLayersNext    = numpy.ndarray(shape, dtype = object)
        self._compositeCurrent    = numpy.ndarray((len(self._tiling),), dtype = object)
        self._compositeNext       = numpy.ndarray((len(self._tiling),), dtype = object)

        QThread.start(self)

    def _runImpl(self):

        processed = set()
        self._dataPending.wait()
        if self._numLayers == 0:
            return
        bbox = QRect()
        toUpdate = numpy.zeros((len(self._tiling),), dtype=numpy.uint8)
        while len(self._queue) > 0:
            self._dataPending.clear()

            layerNr, patchNr, image = self._queue.popleft()
            if (layerNr, patchNr) in processed:
                continue
            processed.add((layerNr, patchNr))

            rect = self._tiling._imageRect[patchNr]
            bbox = bbox.united(rect)
            
            self._imageLayersNext[layerNr,patchNr] = image
            toUpdate[patchNr] = 1


        for patchNr in toUpdate.nonzero()[0]: 
            self._compositeNext[patchNr] = QImage(self._tiling._imageRect[patchNr].size(), QImage.Format_ARGB32_Premultiplied)
            self._compositeNext[patchNr].fill(Qt.black)
            p = QPainter(self._compositeNext[patchNr])
            for i, v in enumerate(reversed(self._stackedIms)):
                visible, layerOpacity, layerImageSource = v
                if not visible:
                    continue
                layerNr = len(self._stackedIms) - i - 1
                patch = self._imageLayersNext[layerNr, patchNr]
                p.setOpacity(layerOpacity)
                if patch is not None:
                    p.drawImage(0,0, patch)
            p.end()

        w = numpy.equal(self._compositeNext, None)
        self._compositeCurrent = numpy.where(numpy.equal(self._compositeNext, None), self._compositeCurrent, self._compositeNext)
        self._compositeNext[:] = None

        self.patchAvailable.emit(bbox)
    
    def run(self):
        while not self._stopped:
            self._runImpl()

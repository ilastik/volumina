import numpy
from functools import partial
from PyQt4.QtCore import QObject, pyqtSignal, QTimer

#*******************************************************************************
# P o s i t i o n M o d e l                                                    *
#*******************************************************************************

class PositionModel(QObject):
    """
    Currently viewed position within a 5D data volume
    (time, x,y,z, channels).
    
    By writing into the public properties of the PositionModel,
    the user can manipulate the volume viewer by writing code
    in the same way as would be possible by manipulating the
    viewer with a mouse.
    """
    
    timeChanged            = pyqtSignal(int)
    channelChanged         = pyqtSignal(int)
    cursorPositionChanged  = pyqtSignal(object, object)
    slicingPositionChanged = pyqtSignal(object, object)
    slicingPositionSettled = pyqtSignal(bool)
   
    #When the user does not scroll through the stack for more than 300 ms,
    #we call the position 'settled', and slicingPositionSettled will be
    #emitted as true.
    #This is needed to let the progress indicator pies be shown after a short
    #delay only, so that they do not appear when the data arrives fast
    #(viewing raw data only)
    scrollDelay = 300 #in ms.
    
    @property
    def shape5D(self):
        return self._shape5D
    @shape5D.setter
    def shape5D(self, s):
        assert len(s) == 5, str(s) + " not dim 5"
        self._shape5D = s

        #call property setters to trigger updates etc. 
        self.cursorPos   = self._cursorPos
        self.slicingPos  = self._slicingPos
        self.time        = self._time
        self.channel     = self._channel

    @property
    def slicingPos5D(self):
        return [self._time,
                self._slicingPos[0],
                self._slicingPos[1],
                self._slicingPos[2],
                self._channel]

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        
        #init property fields
        self._cursorPos  = [0,0,0]
        self._slicingPos = [0,0,0]
        self._time       = 0
        self._channel    = 0
        self._shape5D    = [0,0,0,0,0]
        
        """
        Index of the currently active view in [0,1,2].
        A view is active when the mouse cursor hovered over it last.
        """
        self.activeView = 0

        self._scrollTimer = QTimer()
        self._scrollTimer.setInterval(self.scrollDelay)
        self._scrollTimer.setSingleShot(True)
        self._scrollTimer.timeout.connect(self._onScrollTimer)
        
        self._slicingSettled = True
        
    def sliceShape(self, axis):
        """
        returns the 2D shape of slices perpendicular to axis
        """
        shape = self._shape5D[1:4]
        if shape is None:
            return None

        if len(shape) == 2:
            return shape
        else:
            shape = list(shape)
            del shape[axis]
            return numpy.asarray(shape)
    
    def volumeExtent(self, axis):
        """
        returns the 1D extent of the volume along axis
        """
        return self._shape5D[axis+1]
    
    @property
    def shape( self ):
        """
        the spatial shape
        """
        if self._shape5D is None:
            return None
        return self._shape5D[1:4]
        
    @property    
    def time( self ):
        """
        the currently shown index of the time dimension
        """
        return self._time
    @time.setter
    def time( self, value ):
        if value < 0 or value >= self._shape5D[0] or value == self._time:
            return
        self._time = value
        self.timeChanged.emit(value)

    @property
    def channel( self ):
        """
        the currently shown index of the channel dimension
        """
        return self._channel
    @channel.setter
    def channel(self, value):
        if value < 0 or value >= self._shape5D[4] or value == self._channel:
            return
        self._channel = value    
        self.channelChanged.emit(value)
    
    @property
    def cursorPos(self):
        """
        Returns the spatial position (x,y,z) that is defined by
        the slice number of the slice under the cursor and the position
        on the cursor on that slice.
        Notice the difference to `slicingPos`.
        """
        return self._cursorPos
    @cursorPos.setter
    def cursorPos(self, coordinates):
        if coordinates == self._cursorPos:
            return
        oldPos = self._cursorPos
        self._cursorPos = coordinates
        self.cursorPositionChanged.emit(self.cursorPos, oldPos)
    
    @property
    def slicingPos(self):
        """
        Returns the spatial position (x,y,z) that the volume viewer is currently
        configured to show.
        Notice the difference to `cursorPos`. Here, we mean the position as defined
        by the three slice views.
        """
        return self._slicingPos
    @slicingPos.setter
    def slicingPos(self, pos):
        if pos == self._slicingPos:
            return
        oldPos = self._slicingPos
        
        self._slicingPos = list(pos)
        
        if self._slicingSettled:
            self._slicingSettled = False
            self.slicingPositionSettled.emit(False)
        self._scrollTimer.start()
        
        self.slicingPositionChanged.emit(self.slicingPos, oldPos)
        
    def _onScrollTimer(self):
        self._slicingSettled = True
        self.slicingPositionSettled.emit(True)

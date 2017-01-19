from __future__ import absolute_import
from PyQt5.QtCore import Qt, QEvent, QObject, QPoint
import numpy as np
from .navigationController import NavigationInterpreter, posView2D
from volumina.layer import GrayscaleLayer


#*******************************************************************************
# T h r e s h o l d i n g  I n t e r p r e t e r                               *
#*******************************************************************************

class ThresholdingInterpreter( QObject ):
    # states
    FINAL             = 0
    DEFAULT_MODE      = 1 # normal navigation functionality
    THRESHOLDING_MODE = 2 # while pressing left mouse button allow thresholding
    NO_VALID_LAYER    = 3 # not a grayscale layer 
    
    @property
    def state( self ):
        return self._current_state

    def __init__( self, navigationController, layerStack, posModel ):
        QObject.__init__( self )
        self._navCtrl = navigationController
        self._navIntr = NavigationInterpreter( navigationController )
        self._layerStack = layerStack
        self._active_layer = None
        self._active_channel_idx = -1
        self._current_state = self.FINAL
        self._current_position = QPoint(0,0)
        # Setting default values, scaled on actual data later on 
        self._steps_mean = 10 
        self._steps_delta = self._steps_mean*2
        self._steps_scaling = 0.07
        self._range_max = 4096.0 # hardcoded, in the case drange is not set in the data file or in the dataSelectionDialogue
        self._range_min = -4096.0
        self._range = np.abs(self._range_max-self._range_min)
        self._channel_range = dict()
        self._posModel = posModel

    def start( self ):
        if self._current_state == self.FINAL:
            self._navIntr.start()
            self._current_state = self.DEFAULT_MODE
            self._init_layer()
        else:
            pass 
    
    def stop( self ):
        self._current_state = self.FINAL
        if self.valid_layer():
            self._active_layer.channelChanged.disconnect(self.channel_changed)
        self._navIntr.stop()            
        
    def eventFilter( self, watched, event ):
        etype = event.type()
        if self._current_state == self.DEFAULT_MODE:
            if etype == QEvent.MouseButtonPress \
                    and event.button() == Qt.LeftButton \
                    and event.modifiers() == Qt.NoModifier \
                    and self._navIntr.mousePositionValid(watched, event): 
                # TODO maybe remove, if we can find out which view is active
                self.set_active_layer()
                if self.valid_layer():
                    self._current_state = self.THRESHOLDING_MODE
                    self._current_position = watched.mapToGlobal( event.pos() )
                    return True
                else:
                    self._current_state = self.NO_VALID_LAYER
                return self._navIntr.eventFilter( watched, event )
            elif etype == QEvent.MouseButtonPress \
                    and event.button() == Qt.RightButton \
                    and event.modifiers() == Qt.NoModifier \
                    and self._navIntr.mousePositionValid(watched, event):
                self.set_active_layer()
                if self.valid_layer():
                    self.onRightClick_resetThreshold(watched, event)
                else:
                    pass # do nothing
                return True
            else:
                return self._navIntr.eventFilter( watched, event )
        elif self._current_state == self.NO_VALID_LAYER:
            self.set_active_layer()
            if self.valid_layer():
                self._current_state = self.DEFAULT_MODE
            return self._navIntr.eventFilter( watched, event )
        elif self._current_state == self.THRESHOLDING_MODE:
            if self._active_layer == None: # No active layer set, should not go here
                return self._navIntr.eventFilter( watched, event )
            if etype == QEvent.MouseButtonRelease and event.button() == Qt.LeftButton:
                self._current_state = self.DEFAULT_MODE
                self._active_layer = None
                self.onExit_threshold( watched, event )
                return True
            elif etype == QEvent.MouseMove and event.buttons() == Qt.LeftButton:
                self.onMouseMove_thresholding(watched, event)
                return True
            else:
                return self._navIntr.eventFilter( watched, event )
        else:
            # let the navigation interpreter handle common events
            return self._navIntr.eventFilter( watched, event )
    
    def onRightClick_resetThreshold(self, imageview, event):
        range = self.get_min_max_of_current_view(imageview)
        self._active_layer.set_normalize(0, (range[0],range[1]))
        self._channel_range[self._active_channel_idx] = (range[0],range[1])

    def set_active_layer(self):
        """
        determines the layer postion in the stack and the currently displayed
        channel. Needs to be called constantly, because the user can change the 
        position of the input layer within the stack
        """
        for idx, layer in enumerate(self._layerStack):
            if isinstance(layer, GrayscaleLayer):
                if layer.window_leveling:
                    self._active_layer = layer
                    self._active_channel_idx= layer._channel
                    return
        self._active_layer = None

    def _init_layer(self):
        self.set_active_layer()
        if self.valid_layer():
            self._active_layer.channelChanged.connect(self.channel_changed)
            if self.get_drange() != None:
                self._range_min, self._range_max = self.get_drange()
        
    def onExit_threshold( self, watched, event ):
        pass

    def get_drange(self):
        """ 
        returns tuple of drange (min, max) as set in hdf5 file or None 
        if nothing is specified
        """
        return self._active_layer._datasources[0]._rawSource._op5.Output.meta.drange

    def valid_layer(self):
        if isinstance(self._active_layer, GrayscaleLayer):
            return self._active_layer.window_leveling
        else:
            return False

    def channel_changed(self):
        self.set_active_layer()
        if self._active_channel_idx in self._channel_range:
            self._active_layer.set_normalize(0, self._channel_range[self._active_channel_idx])
        else:
            self._active_layer.set_normalize(0,(self._range_min, 
                                                self._range_max))

    def get_min_max_of_current_view(self, imageview):
        """
        Function returns min and max value of the current view 
        based on the raw data.
        Ugly hack, but all we got for now
        """
        shape2D = posView2D( list(self._posModel.shape5D[1:4]), 
                             axis=self._posModel.activeView )
        data_x, data_y = 0, 0
        data_x2, data_y2 = shape2D[0], shape2D[1]
        
        if self._posModel.activeView == 0:
            x_pos = self._posModel.slicingPos5D[1]
            slicing = [slice(0, 1), 
                       slice(x_pos, x_pos+1), 
                       slice(data_x, data_x2), 
                       slice(data_y, data_y2), 
                       slice(self._active_channel_idx, self._active_channel_idx+1)]
        if self._posModel.activeView == 1:
            y_pos = self._posModel.slicingPos5D[2]
            slicing = [slice(0, 1), 
                       slice(data_x, data_x2), 
                       slice(y_pos, y_pos+1), 
                       slice(data_y, data_y2), 
                       slice(self._active_channel_idx, self._active_channel_idx+1)]
        if self._posModel.activeView == 2:
            z_pos = self._posModel.slicingPos5D[3]
            slicing = [slice(0, 1), 
                       slice(data_x, data_x2), 
                       slice(data_y, data_y2), 
                       slice(z_pos, z_pos+1), 
                       slice(self._active_channel_idx, self._active_channel_idx+1)]
        request = self._active_layer._datasources[0].request(slicing)
        result = request.wait()
        return result.min(), result.max()

    def onMouseMove_thresholding(self, imageview, event):
        if self._active_channel_idx not in self._channel_range:
            range = self.get_min_max_of_current_view(imageview)
            range_lower = range[0]
            range_upper = range[1]
        else:
            range = self._channel_range[self._active_channel_idx]
            range_lower = range[0]
            range_upper = range[1]
        # don't know what version is more efficient
        # range_delta = np.sqrt((range_upper - range_lower)**2) 
        range_delta = np.abs(range_upper - range_lower)
        range_mean = range_lower + range_delta/2.0

        self._steps_mean = range_delta * self._steps_scaling
        self._steps_delta = self._steps_mean * 2
        pos = imageview.mapToGlobal( event.pos() )
        dx =  pos.x() - self._current_position.x()
        dy =  self._current_position.y() - pos.y()

        if dx > 0.0:
            # move mean to right
            range_mean += self._steps_mean
        elif dx < 0.0:
            # move mean to left
            range_mean -= self._steps_mean
        
        if dy > 0.0:
            # increase delta
            range_delta += self._steps_delta
        elif dy < 0.0:
            # decrease delta
            range_delta -= self._steps_delta

        # check the bounds, ugly use min max values actually present
        if range_mean < self._range_min:
            range_mean = self._range_min
        elif range_mean > self._range_max:
            range_mean = self._range_max
        
        if range_delta < 1:
            range_delta = 1
        elif range_delta > self._range: 
            range_delta = self._range

        a = range_mean - range_delta/2.0
        b = range_mean + range_delta/2.0

        if a < self._range_min:
            a = self._range_min
        elif a > self._range_max:
            a = self._range_max
        
        if b < self._range_min:
            b = self._range_min
        elif b > self._range_max:
            b = self._range_max

        assert a <= b 

        # TODO test if in allowed range (i.e. max and min of data)
        self._active_layer.set_normalize(0, (a,b))
        self._channel_range[self._active_channel_idx] = (a,b)
        self._current_position = pos

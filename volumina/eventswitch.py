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
from PyQt5.QtCore import QObject, Qt, QEvent
from PyQt5.QtGui import QMouseEvent

from abc import ABCMeta, abstractmethod

from pixelpipeline.asyncabcs import _has_attributes

class InterpreterABC:
    __metaclass__ = ABCMeta
    
    @abstractmethod
    def start( self ):
        '''Start the interpretation of an event stream.'''

    @abstractmethod    
    def stop( self ):
        '''Stop the interpretation of the event stream.'''

    @abstractmethod    
    def eventFilter( self, watched, event ):
        '''Necessary to act as a Qt event filter. '''

    @classmethod
    def __subclasshook__(cls, C):
        if cls is InterpreterABC:
            if _has_attributes(C, ['start', 'stop', 'eventFilter']):
                return True
            return False
        return NotImplemented

class EventSwitch( QObject ):
    @property
    def interpreter( self ):
        return self._interpreter

    @interpreter.setter
    def interpreter( self, interpreter ):
        assert(isinstance(interpreter, InterpreterABC))
        # stop old interpreter before switching to it to
        # avoid inconsistencies when eventloop and eventswitch
        # are running in different threads
        if self._interpreter:
            self._interpreter.stop()

        self._interpreter = interpreter

        # start the new interpreter after switching to it
        # to avoid inconcistencies
        self._interpreter.start()

    def __init__( self, imageviews, interpreter=None):
        super(EventSwitch, self).__init__()
        self._imageViews = imageviews
        self._interpreter = None
        if interpreter:
            self.interpreter = interpreter

        # We can't directly install the interpreter as an event filter on each of the views,
        # because repeatedly installing/uninstalling the interpreter changes its priority
        # in the view's list of event filters.
        # Instead, we install ourselves as an event filter, and forward events to the currently selected interpreter.
        self._viewports = []
        for view in self._imageViews:
            #http://stackoverflow.com/questions/2445997/qgraphicsview-and-eventfilter
            view.installEventFilter( self )
            view.viewport().installEventFilter( self )
            self._viewports.append( view.viewport() )
    
    def eventFilter(self, watched, event):
        # Forward filtered events to the interpreter.
        if watched in self._viewports:
            #watched is a viewport. Forward the event to its parent,
            #which will be the QGraphicsView itself
            return self._interpreter.eventFilter(watched.parent(), event)
        else:
            # prevent double delivery of unhandled mouse events that
            # bubble up from the underlying viewport
            if not isinstance(event, QMouseEvent):
                return self._interpreter.eventFilter(watched, event)
            else:
                return False


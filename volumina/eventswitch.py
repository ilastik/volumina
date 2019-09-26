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

from PyQt5.QtCore import QObject, QEvent

from volumina.utility.qabc import QABC, abstractmethod


class InterpreterABC(QABC):
    @abstractmethod
    def start(self) -> None:
        """Start the interpretation of an event stream."""

    @abstractmethod
    def stop(self) -> None:
        """Stop the interpretation of the event stream."""

    @abstractmethod
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Necessary to act as a Qt event filter. """


class EventSwitch(QObject):
    @property
    def interpreter(self):
        return self._interpreter

    @interpreter.setter
    def interpreter(self, interpreter):
        assert isinstance(interpreter, InterpreterABC)
        # stop old interpreter before switching to it to
        # avoid inconsistencies when eventloop and eventswitch
        # are running in different threads
        if self._interpreter:
            self._interpreter.stop()

        self._interpreter = interpreter

        # start the new interpreter after switching to it
        # to avoid inconcistencies
        self._interpreter.start()

    def __init__(self, imageviews, interpreter=None):
        super(EventSwitch, self).__init__()
        self._imageViews = imageviews
        self._interpreter = None
        if interpreter:
            self.interpreter = interpreter

        # We can't directly install the interpreter as an event filter on each of the views,
        # because repeatedly installing/uninstalling the interpreter changes its priority
        # in the view's list of event filters.
        # Instead, we install ourselves as an event filter, and forward events to the currently selected interpreter.
        for imageview in imageviews:
            # QAbstractScrollArea (QGraphicsView superclass) installs itself as a focus proxy into a viewport.
            # Since we want to receive key events in the event filter, uninstall the focus proxy from the viewport.
            # See https://stackoverflow.com/a/2501489.
            viewport = imageview.viewport()
            viewport.setFocusProxy(None)
            viewport.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        return self._interpreter.eventFilter(watched.parent(), event)

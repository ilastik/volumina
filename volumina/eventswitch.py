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

from typing import Iterable

from PyQt5.QtCore import QEvent, QObject
from PyQt5.QtWidgets import QGraphicsView
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
    def interpreter(self) -> InterpreterABC:
        return self._interpreter

    @interpreter.setter
    def interpreter(self, interpreter: InterpreterABC) -> None:
        self._interpreter.stop()
        self._interpreter = interpreter
        interpreter.setParent(self)
        self._interpreter.start()

    def __init__(self, views: Iterable[QGraphicsView], interpreter: InterpreterABC, parent=None):
        super().__init__(parent=parent)
        self._interpreter = interpreter
        interpreter.setParent(self)

        # We can't directly install the interpreter as an event filter on each of the views,
        # because repeatedly installing/uninstalling the interpreter changes its priority
        # in the view's list of event filters.
        # Instead, we install ourselves as an event filter, and forward events to the currently selected interpreter.
        for view in views:
            # QAbstractScrollArea (QGraphicsView superclass) installs itself as a focus proxy into a viewport.
            # Since we want to receive key events in the event filter, uninstall the focus proxy from the viewport.
            # See https://stackoverflow.com/a/2501489.
            viewport = view.viewport()
            viewport.setFocusProxy(None)
            viewport.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        return self._interpreter.eventFilter(watched.parent(), event)

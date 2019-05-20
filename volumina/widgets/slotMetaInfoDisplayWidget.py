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
import os

import sip
from PyQt5 import uic
from PyQt5.QtWidgets import QWidget

class SlotMetaDisplayData:
    def __init__(self, shape=None, axes='', dtype=None):
        self.shape = str(tuple(shape)) if shape is not None else ''
        self.axes = ''.join(axes)
        self.dtype = dtype.__name__ if dtype is not None else ''

class SlotMetaInfoDisplayWidget(QWidget):
    """
    Simple display widget for a slot's meta-info (shape, axes, dtype).
    """

    def __init__(self, parent):
        super().__init__(parent)
        uic.loadUi(os.path.splitext(__file__)[0] + ".ui", self)
        self._slot = None

    def initSlot(self, slot):
        if self._slot is not slot:
            if self._slot:
                self._slot.unregisterMetaChanged(self.update_labels)
            self._slot = slot
            slot.notifyMetaChanged(self.update_labels)
        self.update_labels()

    @property
    def _labels(self) -> SlotMetaDisplayData:
        return SlotMetaDisplayData(shape=self._slot.meta.getOriginalShape(),
                                   axes=self._slot.meta.getOriginalAxisKeys(),
                                   dtype=self._slot.meta.dtype)

    def update_labels(self, *args):
        labels = self._labels if self._slot.ready() else SlotMetaDisplayData()
        if not sip.isdeleted(self.shapeDisplay):
            self.shapeDisplay.setText(labels.shape)
            self.axisOrderDisplay.setText(labels.axes)
            self.dtypeDisplay.setText(labels.dtype)

class OutputSlotMetaInfoDisplayWidget(SlotMetaInfoDisplayWidget):
    @property
    def _labels(self):
        return SlotMetaDisplayData(shape=self._slot.meta.shape,
                                   axes=self._slot.meta.getAxisKeys(),
                                   dtype=self._slot.meta.dtype)

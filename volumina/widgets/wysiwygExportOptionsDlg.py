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
import os

from PyQt4 import uic
from PyQt4.QtCore import Qt, QEvent
from PyQt4.QtGui import QDialog, QDialogButtonBox

class WysiwygExportOptionsDlg(QDialog):
    
    def __init__(self, view):
        """
        Constructor.
        
        :param parent: The parent widget
        """
        super( WysiwygExportOptionsDlg, self ).__init__(view.parent())
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        # references
        self.parent = view.parent()
        self.view = view
        self.scene = view.scene()
        
        # properties
        self.along = self.scene._along
        self.inputAxes = ['t','x','y','z','c']
        self.shape = self.scene._posModel.shape5D

        # Init child widgets
        self._initMetaInfoWidgets()
        self._initSubregionWidget()
        self._initFileOptionsWidget()

        # See self.eventFilter()
        self.installEventFilter(self)

    def eventFilter(self, watched, event):
        # Ignore 'enter' keypress events, since the user may just be entering settings.
        # The user must manually click the 'OK' button to close the dialog.
        if watched == self and \
           event.type() == QEvent.KeyPress and \
           ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return):
            return True
        return False

    def _initMetaInfoWidgets(self):
        self._sliceAxes = [i for i,a in enumerate(self.inputAxes) if not i in self.along]
        self._sliceCoords = ''.join([a for i,a in enumerate(self.inputAxes) 
                                     if not i in self.along]).upper()
    
    def _initSubregionWidget(self):
        self.roi_start = (None,) * len(self.shape)
        self.roi_stop = (None,) * len(self.shape)
        self.roiWidget.initWithExtents(self.inputAxes, self.shape, 
                                       self.roi_start, self.roi_stop)
        
        def _handleRoiChange(newstart, newstop):
            self.roi_start = newstart
            self.roi_stop = newstop

        self.roiWidget.roiChanged.connect(_handleRoiChange)

    def _initFileOptionsWidget(self):
        pass
    
    def getRoi(self):
        start = tuple([s if not s is None else 0 for s in self.roi_start])
        stop = tuple([s if not s is None else self.shape[i] 
                      for i,s in enumerate(self.roi_stop)])
        return start, stop
    
    def getIterAxes(self):
        start, stop = self.getRoi()
        axes = [i for i in self.along if stop[i]-start[i] > 1]
        return axes, [self.inputAxes[i] for i in axes]
        
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
import vigra

from PyQt4 import uic
from PyQt4.QtCore import Qt, QEvent
from PyQt4.QtGui import QDialog, QFileDialog

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
        self.sliceAxes = [i for i in range(len(self.inputAxes)) if not i in self.along]
        self.sliceCoords = ''.join([a for i,a in enumerate(self.inputAxes) 
                                    if not i in self.along]).upper()

        # Init child widgets
        self._initFileOptionsWidget()
        self._initSubregionWidget()
        self._initMetaInfoWidgets()

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
        self._updateExportDesc()
        self._updateFilePattern()
    
    def _updateFilePattern(self):
        # if iterator axes change, update file pattern accordingly
        _, co, _ = self.getIterAxes()
        iters = "".join(["_%s={%s}" % (c, c.lower()) for c in co])
        txt = "export" + iters
        self.filePattern = txt
        self.filePatternEdit.setText(txt + "." + self.fileExt)
        self.filePatternInvalidLabel.setVisible(False)
        return txt
        
    def _validateFilePattern(self, txt):
        # check if placeholders for iterator axes are there (e.g. {t})
        _, co, _ = self.getIterAxes()
        valid = len([1 for c in co if not ("{%s}" % c.lower()) in txt]) < 1
        if valid:
            self.filePatternInvalidLabel.setVisible(False)
        else:
            plc = ", ".join([("{%s}" % c.lower()) for c in co])
            txt = "File pattern invalid! Pattern has to contain placeholder(s) %s." % plc
            self.filePatternInvalidLabel.setText('<font color="red">'+txt+'</font>')
            self.filePatternInvalidLabel.setVisible(True)
        return valid
    
    def _updateExportDesc(self):
        # if iterator axes or slice shape changes, update export description accordingly
        ax, co, it = self.getIterAxes()
        w = self.roi_stop[self.sliceAxes[0]] - self.roi_start[self.sliceAxes[0]]
        h = self.roi_stop[self.sliceAxes[1]] - self.roi_start[self.sliceAxes[1]]
        
        # describe stacking
        slice_str = "images"
        if len(ax) == 1:
            iter_desc = " (stacked along %s-direction)" % co[0]
            iter_num = "%d " % it[0]
        elif len(ax) == 2:
            iter_desc= (" (%d along %s-direction times "
                        "%d along %s-direction)" % (it[0], co[0], it[1], co[1]))
            iter_num = "%d " % it[0]*it[1]
        else:
            iter_desc = ""
            iter_num = "1 "
            slice_str = "image"
        
        # write full description to label in widget
        desc = iter_num + self.sliceCoords + "-" + slice_str + iter_desc + " of size %d x %d" % (w,h)
        self.exportDesc.setText(desc)
    
    def _initSubregionWidget(self):
        # initialize roi which spans everything
        start = [None,] * len(self.shape)
        stop = [None,] * len(self.shape)
        
        # fill in start and stop values from current viewport rectangle
        rect = self.view.viewportRect()
        start[self.sliceAxes[0]] = rect.left()
        stop[self.sliceAxes[0]] = rect.right()
        start[self.sliceAxes[1]] = rect.top()
        stop[self.sliceAxes[1]] = rect.bottom()
        
        # set class attributes
        self.roi_start = tuple(start)
        self.roi_stop = tuple(stop)
        
        # initialize widget
        self.roiWidget.initWithExtents(self.inputAxes, self.shape, 
                                       self.roi_start, self.roi_stop)
        
        # if user changes roi in widget, save new values to class        
        def _handleRoiChange(newstart, newstop):
            self.roi_start = newstart
            self.roi_stop = newstop
            self._updateExportDesc()
            self._updateFilePattern()

        self.roiWidget.roiChanged.connect(_handleRoiChange)

    def _initFileOptionsWidget(self):
        # List all supported formats
        exts = vigra.impex.listExtensions().split()
        
        # insert them into file format combo box
        for ext in exts:
            self.fileFormatCombo.addItem(ext+' sequence')        
        
        # connect handles
        self.fileFormatCombo.currentIndexChanged.connect(self._handleFormatChange)
        self.filePatternEdit.textEdited.connect(self._handlePatternChange)
        self.selectDirectoryButton.clicked.connect(self._browseForFilepath)
            
        # set default file format to png
        self.fileFormatCombo.setCurrentIndex(exts.index('png'))
        
    def _updateFileExtensionInPattern(self, ext):
        fname = str(self.filePatternEdit.text()).split(".")
        if len(fname) > 1:
            txt = ".".join(fname[:-1]+[ext,])
        else:
            txt = ".".join(fname+[ext,])
        self.filePatternEdit.setText(txt)
            
    def _handleFormatChange(self):
        self.fileExt = str(self.fileFormatCombo.currentText()).split(" ")[0]
        self._updateFileExtensionInPattern(self.fileExt)
        print self.fileExt
        
    def _handlePatternChange(self):
        txt = str(self.filePatternEdit.text()).split(".")
        
        # in case extension was altered/removed
        if len(txt) < 2:
            self._updateFileExtensionInPattern(self.fileExt)
            txt = str(self.filePatternEdit.text()).split(".")
        
        # validate file name pattern
        txt = ".".join(txt[:-1])
        if self._validateFilePattern(txt):
            self.filePattern = txt
        print self.filePattern
        
    def _browseForFilepath(self):
        starting_dir = os.path.expanduser("~")
        export_dir = QFileDialog.getExistingDirectory(self, "Export Directory", starting_dir)
        
        if not export_dir.isNull():
            self.directoryEdit.setText(export_dir)
        
    def getRoi(self):
        self.roi_start = tuple([s if not s is None else 0 for s in self.roi_start])
        self.roi_stop = tuple([s if not s is None else self.shape[i] 
                      for i,s in enumerate(self.roi_stop)])
        return self.roi_start, self.roi_stop
    
    def getIterAxes(self):
        start, stop = self.getRoi()
        axes = [i for i in self.along if stop[i]-start[i] > 1]
        return axes, [self.inputAxes[i].upper() for i in axes], [stop[i]-start[i] for i in axes]
    
    def getExportInfo(self):
        return str(self.directoryEdit.text()), self.filePattern, self.fileExt
        
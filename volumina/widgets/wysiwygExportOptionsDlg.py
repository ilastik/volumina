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
from itertools import product
from operator import mul, itemgetter
import os

from PyQt4 import uic
from PyQt4.QtCore import Qt, QEvent, QString, QRectF
from PyQt4.QtGui import QDialog, QDialogButtonBox, QFileDialog, QImageWriter, QImage, QPainter, qRgb, QColorDialog, \
    QApplication

from volumina.widgets.multiStepProgressDialog import MultiStepProgressDialog

class WysiwygExportOptionsDlg(QDialog):
    
    def __init__(self, view):
        """
        Constructor.
        
        :param view: The parent widget -> ImageView2D
        """
        super( WysiwygExportOptionsDlg, self ).__init__(view)
        uic.loadUi( os.path.splitext(__file__)[0] + '.ui', self )

        self.view = view
        
        # indicators for ok button
        self._pattern_ok = False
        self._directory_ok = False

        # properties
        self.along = self.view.scene()._along
        self.inputAxes = ['t','x','y','z','c']
        self.shape = self.view.scene()._posModel.shape5D
        self.sliceAxes = [i for i in range(len(self.inputAxes)) if not i in self.along]
        self.sliceCoords = ''.join([a for i,a in enumerate(self.inputAxes) 
                                    if not i in self.along])

        # Init child widgets
        self._initSubregionWidget()
        self._initFileOptionsWidget()
        self._initExportInfoWidget()
        
        # disable OK button if file path/pattern are invalid
        self._updateOkButton()
        
        # See self.eventFilter()
        self.installEventFilter(self)

        self.directoryEdit.setText(os.path.expanduser("~"))

    def eventFilter(self, watched, event):
        # Ignore 'enter' keypress events, since the user may just be entering settings.
        # The user must manually click the 'OK' button to close the dialog.
        if watched == self and \
           event.type() == QEvent.KeyPress and \
           ( event.key() == Qt.Key_Enter or event.key() == Qt.Key_Return):
            return True
        return False
        
    def getRoi(self):
        # return roi with 'real' numbers instead of 'None' for full range
        self.roi_start = tuple([s if not s is None else 0 for s in self.roi_start])
        self.roi_stop = tuple([s if not s is None else self.shape[i] 
                      for i,s in enumerate(self.roi_stop)])
        return self.roi_start, self.roi_stop
    
    def getIterAxes(self):
        # return axes to iterate over (e.g. time t) in format: axes indices, axes symbols, stack size
        start, stop = self.getRoi()
        axes = [i for i in self.along if stop[i]-start[i] > 1]
        return axes, [self.inputAxes[i] for i in axes], [stop[i]-start[i] for i in axes]
    
    def getExportInfo(self):
        # return directory, file name pattern and extension
        return str(self.directoryEdit.text()), self.filePattern, self.fileExt
    
    def showMarkers(self):
        return self.displayMarkersCheckbox.isChecked()
    
    def _initExportInfoWidget(self):
        self._updateExportDesc()
    
    def _initSubregionWidget(self):
        # initialize roi for current viewport
        start = [None,] * len(self.shape)
        stop = [None,] * len(self.shape)
        pos5d = self.view.scene()._posModel.slicingPos5D
        rect = self.view.viewportRect()
        for i in range(len(self.shape)):
            if self.shape[i] > 1:
                start[i] = pos5d[i]
                stop[i] = pos5d[i]+1
        start[self.sliceAxes[0]] = rect.left()
        stop[self.sliceAxes[0]] = rect.right()
        start[self.sliceAxes[1]] = rect.top()
        stop[self.sliceAxes[1]] = rect.bottom()
        
        # set class attributes
        self.roi_start = tuple(start)
        self.roi_stop = tuple(stop)
        
        # initialize widget
        self.roiWidget.initWithExtents(self.inputAxes[:-1], self.shape[:-1],
                                       self.roi_start[:-1], self.roi_stop[:-1])

        # if user changes roi in widget, save new values to class        
        def _handleRoiChange(newstart, newstop):
            self.roi_start = newstart + (0,)
            self.roi_stop = newstop + (1,)
            self._updateExportDesc()
            self._updateFilePattern()

        self.roiWidget.roiChanged.connect(_handleRoiChange)

    def _initFileOptionsWidget(self):        
        # List all image formats supported by QImageWriter
        exts = [str(QString(ext)) for ext in list(QImageWriter.supportedImageFormats())]
        
        # insert them into file format combo box
        for ext in exts:
            self.fileFormatCombo.addItem(ext+' sequence')        
        
        # connect handles
        self.fileFormatCombo.currentIndexChanged.connect(self._handleFormatChange)
        self.filePatternEdit.textEdited.connect(self._handlePatternChange)
        self.directoryEdit.textChanged.connect(self._validateFilePath)
        self.selectDirectoryButton.clicked.connect(self._browseForPath)
            
        # set default file format to png
        self.fileFormatCombo.setCurrentIndex(exts.index('png'))
        self._updateFilePattern()
        self._validateFilePath()
    
    def _updateExportDesc(self):
        # if iterator axes or slice shape changes, update export description accordingly
        ax, co, it = self.getIterAxes()
        w = self.roi_stop[self.sliceAxes[0]] - self.roi_start[self.sliceAxes[0]]
        h = self.roi_stop[self.sliceAxes[1]] - self.roi_start[self.sliceAxes[1]]

        stack_list = ("{} stacked along {}-direction".format(i, d.upper()) for d, i in zip(co, it))

        stack = ("({})" if ax else "{}").format(" times ".join(stack_list))
        description = "{count} {dim}-image{s} {stack} of size {w} x {h}".format(
            count=reduce(mul, it, 1),
            dim=self.sliceCoords.upper(),
            s="s" if ax else "",
            stack=stack,
            w=int(w),
            h=int(h)
        )

        self.exportDesc.setText(description)
    
    def _updateFilePattern(self):
        # if iterator axes change, update file pattern accordingly
        _, co, _ = self.getIterAxes()
        iters = "".join(["_%s={%s}" % (c.upper(), c) for c in co])
        txt = "export" + iters
        self.filePattern = txt
        self.filePatternEdit.setText(txt + "." + self.fileExt)
        self._validateFilePattern(txt)
        return txt
    
    def _validateFilePattern(self, txt):
        # check if placeholders for iterator axes are there (e.g. {t})
        _, co, _ = self.getIterAxes()
        valid = len([1 for c in co if not ("{%s}" % c.lower()) in txt]) < 1
        if valid:
            self.filePatternInvalidLabel.setVisible(False)
            self._pattern_ok = True
        else:
            plc = ", ".join([("{%s}" % c.lower()) for c in co])
            txt = "File pattern invalid! Pattern has to contain placeholder(s) %s." % plc
            self.filePatternInvalidLabel.setText('<font color="red">'+txt+'</font>')
            self.filePatternInvalidLabel.setVisible(True)
            self._pattern_ok = False
        self._updateOkButton()
        return valid
    
    def _updateOkButton(self):
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(self._pattern_ok and self._directory_ok)
    
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
        
    def _browseForPath(self):
        default_path = self.directoryEdit().text()
        export_dir = QFileDialog.getExistingDirectory(self, "Export Directory", default_path)
        if not export_dir.isNull():
            self.directoryEdit.setText(export_dir)
            
    def _validateFilePath(self):
        txt = str(self.directoryEdit.text())
        # check if txt is a valid directory and writable
        valid = os.path.isdir(txt) and os.access(txt, os.W_OK)
        if valid:
            self.directoryInvalidLabel.setVisible(False)
            self._directory_ok = True
        else:
            txt = "Directory invalid! Please select a writable directory."
            self.directoryInvalidLabel.setText('<font color="red">'+txt+'</font>')
            self.directoryInvalidLabel.setVisible(True)
            self._directory_ok = False
        self._updateOkButton()
        return valid

# this is not a lazyflow operator on purpose -> it's supposed to work with volumina only
class WysiwygExportHelper(MultiStepProgressDialog):
    """
    MultiStepProgressDialog capable of handling the WYSIWYG export including canceling
    """
        
    def __init__(self, view, settingsDlg):
        MultiStepProgressDialog.__init__(self, view)
        
        self.view = view
        self.posModel = view.scene()._posModel
        self.dlg = settingsDlg
        
        self.exportloop = None
        self.timer = None
        
        # connect signals
        self.buttonBox.button(QDialogButtonBox.Cancel).clicked.connect(self.cancel)
    
    def run(self):
        # disable Ok button until export is finished
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)
        
        # start exporting
        self.timer = self.startTimer(0)   
        
        # show dialog     
        MultiStepProgressDialog.exec_(self)
    
    def prepareExport(self):
        if self.dlg is None:
            return
        
        self.setNumberOfSteps(1)
        
        # grab settings from dialog
        start, stop = self.dlg.getRoi()
        iter_axes, iter_coords, iter_n = self.dlg.getIterAxes()
        slice_axes = self.dlg.sliceAxes
        show_markers = self.dlg.showMarkers()
        folder, pattern, fileExt = self.dlg.getExportInfo()
        
        # width and height of images
        w = stop[slice_axes[0]] - start[slice_axes[0]]
        h = stop[slice_axes[1]] - start[slice_axes[1]]

        # scene rectangle to render
        rect = QRectF(start[slice_axes[0]], start[slice_axes[1]], w, h)
        
        # remember current position to correctly place view afterwards
        self.currentPos5D = list(self.posModel.slicingPos5D)
        pos = list(start)
        
        # show/hide slice intersection markers
        self.showed_markers = self.view._sliceIntersectionMarker.isVisible()
        if show_markers:
            self.view._sliceIntersectionMarker.setVisible(True)
            # to correctly display slice intersection markers
            for a in slice_axes: 
                pos[a] = self.currentPos5D[a]
        else:            
            self.view._sliceIntersectionMarker.setVisible(False)

        # create plain image and painter
        self.img = QImage(w, h, QImage.Format_RGB16)
        self.img.fill(Qt.black)
        self.painter = QPainter(self.img)
                        
        # prepare export loop
        self.exportloop = self.loopGenerator(rect, pos, start, stop, iter_axes, 
                                             iter_coords, folder, pattern, fileExt)

    # Idea from: http://stackoverflow.com/a/7226877
    def loopGenerator(self, rect, base_pos, start, stop, iter_axes,
                      iter_coords, folder, pattern, fileExt):

        ranges = [xrange(a, b) if i in iter_axes else [base_pos[i]] for i, (a, b) in enumerate(zip(start, stop))]
        padding = ["0{}".format(len(str(len(r) - 1))) for r in ranges if len(r) > 1]
        steps = reduce(mul, map(len, ranges), 1.0)

        getter = itemgetter(*iter_axes if iter_axes else [slice(0)])
        for i, pos in enumerate(product(*ranges)):
            coords = getter(pos)
            self._saveImg(pos, rect, self._filename(folder, pattern, fileExt, iter_coords, coords, padding))
            self.setStepProgress(100 * i / steps)
            yield
        self.setStepProgress(100)
        self.finishStep()

    def cancel(self):
        # kill timer
        if self.timer is not None:
            self.killTimer(self.timer)
        self.exportloop = None
        self.timer = None
        self.cleanUp()
        
    def cleanUp(self):
        # re-enable ok/finish button
        self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        
        # close painter
        self.painter.end()
        
        # reset viewer position
        self._setPos5D(self.currentPos5D)
        self.view._sliceIntersectionMarker.setVisible(self.showed_markers)

    def timerEvent(self, event):
        if not self.exportloop is None:
            try:
                QApplication.processEvents()
                # if not canceled, process next image in export loop
                next(self.exportloop)
            except StopIteration:
                # if loop finished, call cancel to wrap up the process
                self.cancel()
    
    def _setPos5D(self, pos5d):
        self.posModel.time = pos5d[0]
        self.posModel.slicingPos = pos5d[1:4]
        self.posModel.channel = pos5d[4]
    
    def _saveImg(self, pos, rect, fname):
        #img.fill(0)
        self._setPos5D(pos)
        self.view.scene().joinRenderingAllTiles(viewport_only=False, rect=rect)
        self.view.scene().render(self.painter, source=rect)
        self.img.save(fname)
    
    def _filename(self, folder, pattern, extension, iters, coords, padding):
        if not hasattr(coords, "__iter__"):
            coords = [coords]

        replace = dict(zip(iters, map(format, coords, padding)))
        fname = "{pattern}.{ext}".format(pattern=pattern.format(**replace), ext=extension)
        return os.path.join(folder, fname)

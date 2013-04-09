#Python
import os
import threading
from collections import OrderedDict
from functools import partial

#PyQt
from PyQt4.QtGui import QDialog, QFileDialog, QRegExpValidator, QPalette,\
                        QDialogButtonBox, QMessageBox, QProgressDialog, QLabel
from PyQt4.QtCore import QRegExp, Qt, QTimer, pyqtSignal
from PyQt4 import uic

#SciPy
import h5py

#volumina
from multiStepProgressDialog import MultiStepProgressDialog

#ilastik
from ilastik.utility.gui.threadRouter import threadRouted
from ilastik.utility.gui import ThunkEventHandler

###
### lazyflow input
###
_has_lazyflow = True
try:
    from lazyflow.operators import OpSubRegion
    from lazyflow.operators.ioOperators import OpStackWriter 
    from lazyflow.operators.vigraOperators import OpH5WriterBigDataset
    from lazyflow.roi import TinyVector, sliceToRoi
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False

class ExportDialog(QDialog):
    
    progressSignal = pyqtSignal(float)
    
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        if not _has_lazyflow:
            QDialog.setEnabled(self,False)
        self.initUic()

    def initUic(self):
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        uic.loadUi(p+"ui/exporterDlg.ui", self)
        
        self.line_outputShape = OrderedDict()
        self.line_outputShape['t'] = self.lineEditOutputShapeT
        self.line_outputShape['x'] = self.lineEditOutputShapeX
        self.line_outputShape['y'] = self.lineEditOutputShapeY
        self.line_outputShape['z'] = self.lineEditOutputShapeZ
        self.line_outputShape['c'] = self.lineEditOutputShapeC
        
        #=======================================================================
        # connections
        #=======================================================================
        self.pushButtonPath.clicked.connect(self.on_pushButtonPathClicked)
        self.radioButtonH5.clicked.connect(self.on_radioButtonH5Clicked)
        self.radioButtonStack.clicked.connect(self.on_radioButtonStackClicked)
        self.comboBoxStackFileType.currentIndexChanged.connect(self.comboBoxStackFileTypeChanged)
        self.check_xy.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.check_xz.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.check_yz.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.check_xt.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.check_yt.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.check_zt.stateChanged.connect(self.on_checkBoxDummyClicked)
        self.checkBoxNormalize.stateChanged.connect(self.on_checkBoxNormalizeClicked)
        self.lineEditOutputShapeX.textEdited.connect(self.lineEditOutputShapeChanged)
        self.lineEditOutputShapeY.textEdited.connect(self.lineEditOutputShapeChanged)
        self.lineEditOutputShapeZ.textEdited.connect(self.lineEditOutputShapeChanged)
        self.lineEditOutputShapeT.textEdited.connect(self.lineEditOutputShapeChanged)
        self.lineEditOutputShapeC.textEdited.connect(self.lineEditOutputShapeChanged)
        #=======================================================================
        # style
        #=======================================================================
        self.on_radioButtonH5Clicked()
        self.checkBoxNormalize.setCheckState(False)
        
        folderPath = os.path.abspath(os.getcwd())
        folderPath = folderPath.split("/")
        #folderPath = folderPath[0:-1]
        folderPath.append("Untitled.h5")
        folderPath = "/".join(folderPath)
        self.setLineEditFilePath(folderPath)
        
        
#===============================================================================
# set input data informations
#===============================================================================
    def setInput(self, inputSlot):
        self.input = inputSlot
        self.setVolumeShapeInfo()
        self.setRegExToLineEditOutputShape()
        self.setDefaultComboBoxHdf5DataType()
        
    def _volumeMetaString(self, slot):
        v = "shape = {"
        for i, (axis, extent) in enumerate(zip(slot.meta.axistags, slot.meta.shape)):
            v += axis.key + ": " + str(extent)
            assert axis.key in self.line_outputShape.keys()
            if i < len(slot.meta.shape)-1:
                v += " "
        v += "}, dtype = " + str(slot.meta.dtype)
        return v
        
    def setVolumeShapeInfo(self):
        for i, (axis, extent) in enumerate(zip(self.input.meta.axistags, self.input.meta.shape)):
            self.line_outputShape[axis.key].setText("0 - %d" % (extent-1))
        self.inputVolumeDescription.setText(self._volumeMetaString(self.input))
        self.lineEditOutputShapeListValidation()
            
    def setRegExToLineEditOutputShape(self):
        r = QRegExp("([0-9]*)(-|\W)+([0-9]*)")
        for i in self.line_outputShape.values():
            i.setValidator(QRegExpValidator(r, i))
            
    def setDefaultComboBoxHdf5DataType(self):
        dtype = str(self.input.meta.dtype)
        for i in range(self.comboBoxHdf5DataType.count()):
            if dtype == str(self.comboBoxHdf5DataType.itemText(i)):
                self.comboBoxHdf5DataType.setCurrentIndex(i)
#===============================================================================
# file
#===============================================================================
    def on_pushButtonPathClicked(self):
        oldPath = self.lineEditFilePath.displayText()
        fileDlg = QFileDialog()
        fileDlg.setOption( QFileDialog.DontUseNativeDialog, True )
        newPath = str(fileDlg.getSaveFileName(self, "Save File", str(self.lineEditFilePath.displayText())))
        if newPath == "":
            newPath = oldPath
        self.lineEditFilePath.setText(newPath)
        self.correctFilePathSuffix()
    
    def correctFilePathSuffix(self):
        path = str(self.lineEditFilePath.displayText())
        path = path.split("/")
        if self.radioButtonH5.isChecked():
            filetype = "h5"
        if self.radioButtonStack.isChecked():
            filetype = str(self.comboBoxStackFileType.currentText())
        if not path[-1].endswith("."+filetype):
            if "." not in path[-1]:
                path[-1] = path[-1] + "." + filetype
            else:
                path[-1] = path[-1].split(".")
                path[-1] = path[-1][0:-1]
                path[-1].append(filetype)
                path[-1] = ".".join(path[-1])
        path = "/".join(path)
        self.lineEditFilePath.setText(path)
        
#===============================================================================
# output formats
#===============================================================================
    def on_radioButtonH5Clicked(self):
        self.widgetOptionsHDF5.setVisible(True)
        self.widgetOptionsStack.setVisible(False)
        self.correctFilePathSuffix()

        self.checkBoxNormalize.setDisabled(False)
        self.spinBoxNormalizeStart.setDisabled(False)
        self.spinBoxNormalizeStop.setDisabled(False)
        
    def on_radioButtonStackClicked(self):
        self.widgetOptionsHDF5.setVisible(False)
        self.widgetOptionsStack.setVisible(True)
        self.correctFilePathSuffix()

        # normalization not implemented for stack writer
        self.checkBoxNormalize.setDisabled(True)
        self.spinBoxNormalizeStart.setDisabled(True)
        self.spinBoxNormalizeStop.setDisabled(True)

        
#===============================================================================
# options
#===============================================================================
    def on_checkBoxNormalizeClicked(self, int):
        if int == 0:
            self.spinBoxNormalizeStart.setDisabled(True)
            self.spinBoxNormalizeStop.setDisabled(True)
        else:
            self.spinBoxNormalizeStart.setDisabled(False)
            self.spinBoxNormalizeStop.setDisabled(False)
            
    def on_checkBoxDummyClicked(self):
        checkedList = []
        #for i in range(len(self.checkBoxDummyList)):
        #    if self.checkBoxDummyList[i].isChecked():
        #        checkedList.append(str(self.checkBoxDummyList[i].text()))
        return checkedList
    
    def comboBoxStackFileTypeChanged(self, int):
        self.correctFilePathSuffix()
    #===========================================================================
    # lineEditOutputShape    
    #===========================================================================
    def lineEditOutputShapeListValidation(self):

        lineEditOutputShapeList = []
        isValidDict = OrderedDict()
        volumeShape = self.input.meta.getTaggedShape()
        for key,value in self.line_outputShape.items():
            if key not in volumeShape:
                isValidDict[key] = "Disabled" 
                continue
            limits = [int(token) for token in str(value.text()).split() if token.isdigit()]

            isValidDict[key] = False
            if len(limits) != 2:
                continue
            elif limits[0] >= volumeShape[key] or limits[1] >= volumeShape[key]:
                continue
            elif limits[1] < limits[0]:
                continue
            lineEditOutputShapeList.append(slice(limits[0],limits[1] + 1))
            isValidDict[key] = True

        isValid = True
        for key,value in isValidDict.items():
            p = QPalette()
            if value == True:
                p.setColor(QPalette.Base, Qt.white)
                p.setColor(QPalette.Text,Qt.black)
            elif value == False:
                allValid = False
                p.setColor(QPalette.Base, Qt.red)
                p.setColor(QPalette.Text,Qt.white)
            elif value == "Disabled":
                p.setColor(QPalette.Base, Qt.gray)
                p.setColor(QPalette.Text,Qt.gray)
                
            self.line_outputShape[key].setPalette(p)

        if isValid:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(True)
        else:
            self.buttonBox.button(QDialogButtonBox.Ok).setEnabled(False)

        self.roi = tuple(lineEditOutputShapeList)

    def setLineEditFilePath(self, filePath):
        self.lineEditFilePath.setText(filePath)
        
    def lineEditOutputShapeChanged(self):
        self.lineEditOutputShapeListValidation()
        
#===============================================================================
# create values
#===============================================================================
    def createNormalizeValue(self):
        if self.checkBoxNormalize.isChecked():
            return [int(self.spinBoxNormalizeStart.value()),
                    int(self.spinBoxNormalizeStop.value())]
        else:
            return -1
    
    def createKeyForOutputShape(self):
        
        return key
    
    def createRoiForOutputShape(self):
        start = []
        stop = []
        for key, extent in self.line_outputShape.iteritems():
            r = extent.validator().regExp()
            r.indexIn(extent.displayText())
            #TODO: FIX THIS, its hacky
            if r.cap(1) != '' and r.cap(3) != '':
                c1 = int(r.cap(1))
                c3 = int(r.cap(3)) + 1 # GUI input is [start, stop] but keys are [start, stop), so add 1
                start.append(c1)
                stop.append(c3)
        roi = [TinyVector(start), TinyVector(stop)]
        print "[ExportDlg] export roi =", roi
        return roi
        
    def accept(self, *args, **kwargs):
        dlg = MultiStepProgressDialog(self)
        #thunkEventHandler = ThunkEventHandler(dlg)
        
        if self.radioButtonStack.isChecked():
            key = self.createKeyForOutputShape()
            
            writer = OpStackWriter(self.input.getRealOperator())
            writer.inputs["input"].connect(self.input)
            writer.inputs["filepath"].setValue(str(self.lineEditFilePath.displayText()))
            writer.inputs["dummy"].setValue(["zt"])
            writer.outputs["WritePNGStack"][key].allocate().wait()

        elif self.radioButtonH5.isChecked():
            h5f = h5py.File(str(self.lineEditFilePath.displayText()), 'w')
            hdf5path = str(self.lineEditHdf5Path.displayText())
            roi = sliceToRoi(self.roi,self.input.meta.shape)
            subRegion = OpSubRegion(self.input.getRealOperator())

            subRegion.Start.setValue(tuple([k for k in roi[0]]))
            subRegion.Stop.setValue(tuple([k for k in roi[1]]))
            subRegion.Input.connect(self.input)
   
            writerH5 = OpH5WriterBigDataset(self.input.getRealOperator())
            writerH5.hdf5File.setValue(h5f)
            writerH5.hdf5Path.setValue(hdf5path)
            writerH5.Image.connect(subRegion.Output)

            self._storageRequest = writerH5.WriteImage[...]
            finishedEvent = threading.Event()
            
            def handleFinish(result):
                finishedEvent.set()
            def handleCancel():
                print "Full volume prediction save CANCELLED."
            def cancelRequest():
                print "Cancelling request"
                self._storageRequest.cancel()
            def onProgressGUI(x):
                print "xxx",x
                dlg.setStepProgress(x)
            self.progressSignal.connect(onProgressGUI)
            def onProgressLazyflow(x):
                self.progressSignal.emit(x)

            # Trigger the write and wait for it to complete or cancel.
            self._storageRequest.notify_finished(handleFinish)
            self._storageRequest.notify_cancelled(handleCancel)
            
            dlg.rejected.connect(cancelRequest)
            writerH5.progressSignal.subscribe( onProgressLazyflow )
            self._storageRequest.submit() 
            
            dlg.exec_()
            
            finishedEvent.wait()
            writerH5.cleanUp()
        
        else:
            raise RuntimeError("unhandled button")
        
        return QDialog.accept(self, *args, **kwargs)
    
    def show(self):
        if not _has_lazyflow:
            popUp = QMessageBox(parent=self)
            popUp.setTextFormat(1)
            popUp.setText("<font size=\"4\"> Lazyflow could not be imported:</font> <br><br><b><font size=\"4\" color=\"#8A0808\">%s</font></b>"%(exceptStr))
            popUp.show()
            popUp.exec_()
        QDialog.show(self)
        
if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    from lazyflow.operators import OpArrayPiper
    from lazyflow.graph import Graph
    app = QApplication(list())
   
    g = Graph()
    arr = vigra.Volume((600,800,400), dtype=numpy.uint8)
    a = OpArrayPiper(graph=g)
    a.Input.setValue(arr)
    
    d = ExportDialog()
    d.setInput(a.Output)
    
    d.show()
    app.exec_()

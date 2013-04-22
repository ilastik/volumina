#Python
import os
import threading
from collections import OrderedDict
from itertools import combinations
import re
import logging

#PyQt
from PyQt4.QtGui import QDialog, QFileDialog, QRegExpValidator, QPalette,\
                        QDialogButtonBox, QMessageBox,QProgressDialog,QLabel,QWidget,\
QHBoxLayout, QSpacerItem, QSizePolicy, QCheckBox
from PyQt4.QtCore import QRegExp, Qt, QTimer, QObject, pyqtSignal
from PyQt4 import uic

#numpy
import numpy

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
    from lazyflow.operators import OpSubRegion, OpPixelOperator 
    from lazyflow.operators.ioOperators import OpStackWriter 
    from lazyflow.operators.ioOperators import OpH5WriterBigDataset
    from lazyflow.roi import TinyVector, sliceToRoi
except ImportError as e:
    exceptStr = str(e)
    _has_lazyflow = False

from volumina.widgets.multiStepProgressDialog import MultiStepProgressDialog

logger = logging.getLogger(__name__)
traceLogger = logging.getLogger('TRACE.' + __name__)

#for writer:
from lazyflow.graph import Operator
import vigra
from collections import deque

from valueRangeWidget import ValueRangeWidget


class Writer(QObject):
    progressSignal = pyqtSignal(float)
    finishedStepSignal = pyqtSignal()

    def __init__(self):
        QObject.__init__(self)
        self.graph = Graph()
        self.stackWriter = OpStackWriter(graph=self.graph)
        self.h5Writer = OpH5WriterBigDataset(graph=self.graph)
        self.h5f = None

    def setupH5Writer(self, h5Group, h5Path):
        self.h5Writer.hdf5Path.setValue(h5Path)
        self.h5f = h5py.File(h5Group, 'a')
        self.h5Writer.hdf5File.setValue(self.h5f)
        

    def setupStackWriter(self, filePath, fileName, fileType, imageAxesNames):
    
        self.stackWriter.Filepath.setValue(filePath)
        self.stackWriter.Filename.setValue(fileName)
        self.stackWriter.Filetype.setValue(fileType)
        self.stackWriter.ImageAxesNames.setValue(imageAxesNames)

    def getStackWriterPreview(self, inputData):
        self.stackWriter.Image.connect(inputData)
        if self.stackWriter.FilePattern.ready():
            return self.stackWriter.FilePattern[:].wait()
        else:
            return ""


    def write(self, inputData, slicing, ranges, outputDType, fileWriter = "h5"):
        dlg = MultiStepProgressDialog()
        #thunkEventHandler = ThunkEventHandler(dlg)
        dlg.setNumberOfSteps(2)
        #Step1: 
        
        roi = sliceToRoi(slicing,inputData.meta.shape)

        subRegion = OpSubRegion(graph = self.graph)

        subRegion.Start.setValue(tuple([k for k in roi[0]]))
        subRegion.Stop.setValue(tuple([k for k in roi[1]]))
        subRegion.Input.connect(inputData)

        inputVolume = subRegion

        #handle different outputTypes

        if ranges is not None:

            normalizer = OpPixelOperator(graph = self.graph)
            normalizer.Input.connect(inputVolume.Output)
            minVal, maxVal = numpy.nan, numpy.nan

            inputVolume = normalizer.Output
            minVal,maxVal = ranges[0]
            outputMinVal, outputMaxVal = ranges[1]
                
            def normalize(val):
                invVal = 1./(maxVal - minVal)
                return outputMinVal + (val - minVal)  * (outputMaxVal - outputMinVal) * invVal 
            
            normalizer.Function.setValue(normalize)
            inputVolume = normalizer


        if outputDType != inputData.meta.dtype:
            converter = OpPixelOperator(graph = self.graph)
            converter.Input.connect(inputVolume.Output)
            
            def convertToType(val):
                return outputDType(val)
            converter.Function.setValue(convertToType)
            inputVolume = converter

        dlg.finishStep()
        #step 2
        writer = None
        if fileWriter == "h5":
            writer = self.h5Writer
        elif fileWriter == "stack":
            writer = self.stackWriter

        writer.Image.connect(inputVolume.Output)
        self._storageRequest = writer.WriteImage[:]
        

        def handleFinish(result):
            self.finishedStepSignal.emit()
        def handleCancel():
            print "Full volume prediction save CANCELLED."
        def cancelRequest():
            print "Cancelling request"
            self._storageRequest.cancel()
        def onProgressGUI(x):
            print "xxx",x
            dlg.setStepProgress(x)
        def onProgressLazyflow(x):
            self.progressSignal.emit(x)
        
        self.progressSignal.connect(onProgressGUI)
        self.finishedStepSignal.connect(dlg.finishStep)
       
       # Trigger the write and wait for it to complete or cancel.
        self._storageRequest.notify_finished(handleFinish)
        self._storageRequest.notify_cancelled(handleCancel)
        
        dlg.rejected.connect(cancelRequest)
        writer.progressSignal.subscribe( onProgressLazyflow )
        self._storageRequest.submit() 
        
        dlg.exec_()
        
        writer.cleanUp()
        if self.h5f is not None:
            self.h5f.close()
            self.h5f = None
        
        return 0 
    

class ExportDialog(QDialog):
    
    
    def __init__(self, parent=None, layername = "Untitled"):
        QDialog.__init__(self, parent)
        if not _has_lazyflow:
            QDialog.setEnabled(self,False)
        #self.validRoi = True
        #self.validInputOutputRange = True
        self.validAxesComboBoxes = True
        self.layername = layername
        self.initUic()
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        self.writer = Writer()
        #self.valueRangeDialog = uic.loadUi(p+"ui/valueRangeDialog.ui", self)
        #self.valueRangeDialog.show()


    def initUic(self):
        p = os.path.split(__file__)[0]+'/'
        if p == "/": p = "."+p
        uic.loadUi(p+"ui/exporterDlg.ui", self)
        
        #=======================================================================
        # connections
        #=======================================================================
        self.pushButtonPath.clicked.connect(self.on_pushButtonPathClicked)
        self.pushButtonStackPath.clicked.connect(self.on_pushButtonStackPathClicked)
        self.radioButtonH5.clicked.connect(self.on_radioButtonH5Clicked)
        self.radioButtonStack.clicked.connect(self.on_radioButtonStackClicked)
        self.comboBoxStackFileType.currentIndexChanged.connect(self.comboBoxStackFileTypeChanged)
        self.comboBoxHdf5DataType.currentIndexChanged.connect(self.setLayerValueRangeInfo)
        self.normalizationComboBox.currentIndexChanged.connect(self.on_normalizationComboBoxChanged)
        
        self.axesComboBox1.currentIndexChanged.connect(self.validateAxesComboBoxes)
        self.axesComboBox2.currentIndexChanged.connect(self.validateAxesComboBoxes)
        self.axesComboBox3.currentIndexChanged.connect(self.validateAxesComboBoxes)
        self.lineEditStackFileName.textEdited.connect(self.updateStackWriter)
        #=======================================================================
        # style
        #=======================================================================
        self.on_radioButtonH5Clicked()
        self.on_normalizationComboBoxChanged()
        self.stackFilePatternPreview.setReadOnly(True)
        
        folderPath = os.path.abspath(os.getcwd())
        folderPath = folderPath.replace("\\","/")
        folderPath = folderPath + "/" + self.layername
        self.updateH5Paths(folderPath)
        self.updateStackPaths(folderPath)
         
        
#===============================================================================
# set input data informations
#===============================================================================
    def setInput(self, inputSlot):
        self.input = inputSlot
        self.setVolumeShapeInfo()
        self.setRoiWidgets()
        self.setAvailableImageAxes()
        #self.setRegExToLineEditOutputShape()
        self.setDefaultComboBoxHdf5DataType()
        #self.validateRoi()
        
    def setupWriters(self):

        filePath = str(self.lineEditStackPath.displayText())
        fileName = str(self.lineEditStackFileName.displayText())
        fileType = str(self.comboBoxStackFileType.currentText())
        imageAxesNames = [str(value.currentText()) for value in self.comboBoxes]

        self.writer.setupStackWriter(filePath, fileName, fileType,
                                     imageAxesNames)


    def updateStackWriter(self):
        pattern = [""]
        if hasattr(self, "input"):
            self.setupWriters()
            pattern = self.writer.getStackWriterPreview(self.input)
        #self.stackWriter.Input.disconnect()
        placeholders = re.findall("%04d", pattern[0])
        insertedPattern = pattern[0] % tuple([0 for i in xrange(len(placeholders))])
        self.stackFilePatternPreview.setText(insertedPattern)

    def _volumeMetaString(self, slot):
        v = "shape = {"
        for i, (axis, extent) in enumerate(zip(slot.meta.axistags, slot.meta.shape)):
            v += axis.key + ": " + str(extent)
            #assert axis.key in self.line_outputShape.keys()
            if i < len(slot.meta.shape)-1:
                v += " "
        v += "}, dtype = " + str(slot.meta.dtype)
        return v
        
    def setVolumeShapeInfo(self):
        self.inputVolumeDescription.setText(self._volumeMetaString(self.input))
    
        
    def setRoiWidgets(self):
        self.roiWidget.addRanges(self.input.meta.getAxisKeys(),
                                 self.input.meta.shape)

        self.inputVolumeDescription.setText(self._volumeMetaString(self.input))

    def setAvailableImageAxes(self):
        axisTags = self.input.meta.axistags
        extents  = self.input.meta.shape
        self.comboBoxes = [self.axesComboBox1, self.axesComboBox2, self.axesComboBox3]
        
        for index, tag in enumerate(axisTags):
            if extents[index] == 1:
                continue
            for box in self.comboBoxes[:-1]:
                box.addItem(tag.key, index)
            if extents[index] <= 4:
                self.comboBoxes[-1].addItem(tag.key, index)
        self.axesComboBox3.addItem("None", None)
        self.comboBoxes[-1].setCurrentIndex(self.comboBoxes[-1].findText("None"))
        #set to good defaults, i.e. x,y,c
        activeBox = 0
        for tag in 'xyztc':
            i = axisTags.index(tag)
            if i < len(axisTags):
                j = self.comboBoxes[activeBox].findText(tag)
                if j != -1:
                    self.comboBoxes[activeBox].setCurrentIndex(j)
                    activeBox = activeBox + 1
                    if activeBox == 3:
                        break


    def setLayerValueRangeInfo(self):
        #if not hasattr(self, "inputType"):
        inputDRange = [0,1]
        dtype = numpy.uint8
        if hasattr(self, "input"):
            dtype = self.input.meta.dtype 
            if hasattr(self.input.meta, "drange") and self.input.meta.drange: 
                inputDRange = self.input.meta.drange
            if hasattr(dtype, "type"):
                dtype = dtype.type
        
        self.inputValueRange.setDType(dtype)
        self.inputValueRange.setValues(inputDRange[0], inputDRange[1])
        self.inputType = dtype
        
        outputType = self.getOutputDType()

        self.outputType = outputType

        self.outputValueRange.setDType(outputType)
        #self.outputValueRange.setValues(0,1)

        self.checkTypeConversionNecessary()
            
    def setRegExToLineEditOutputShape(self):
        r = QRegExp("([0-9]*)(-|\W)+([0-9]*)")
        for i in self.line_outputShape.values():
            i.setValidator(QRegExpValidator(r, i))
            
    def setDefaultComboBoxHdf5DataType(self):
        dtype = self.input.meta.dtype
        if hasattr(self.input.meta.dtype, "type"):
            dtype = dtype.type
        dtype = str(dtype)
        for i in range(self.comboBoxHdf5DataType.count()):
            if str(self.comboBoxHdf5DataType.itemText(i)) in dtype:
                self.comboBoxHdf5DataType.setCurrentIndex(i)
#===============================================================================
# file
#===============================================================================
    def on_pushButtonPathClicked(self):
        fileDlg = QFileDialog()
        fileDlg.setOption( QFileDialog.DontUseNativeDialog, True )
        path = str(fileDlg.getSaveFileName(self, "Save File",
                                              str(self.lineEditH5FilePath.displayText())))
        self.updateH5Paths(path)
    
    def fixFilePath(self, oldPath, separateFile, suffix):
    
        path = oldPath.replace("\\","/")
        path = path.split("/")
        filename = path[-1]
        splitFileName = filename.split(".")
        if len(splitFileName) == 1:
            splitFileName.append(suffix)
        newFilename = ".".join(splitFileName)
        
        newPath = path
        if separateFile:
            newPath[-1] = ""
        else:
            newPath[-1] = newFilename

        newPath = "/".join(newPath)
        return newPath, newFilename


    def on_pushButtonStackPathClicked(self):
        folderDlg = QFileDialog() 
        suffix = str(self.comboBoxStackFileType.currentText())
        path = str(folderDlg.getSaveFileName(self, "Save File",
                                              str(self.lineEditStackPath.displayText()) + str(self.lineEditStackFileName.displayText()
                                                 + "." + suffix)))
        self.updateStackPaths(path)

    def updateH5Paths(self, path):
        
        newPath, newFilename = self.fixFilePath(path, separateFile = False, suffix =
                                      "h5")

        newSuffix = newFilename.split(".")[-1]
        self.lineEditH5FilePath.setText(newPath)


    def updateStackPaths(self, path):
        oldPath = self.lineEditStackPath.displayText()
        oldFilename = self.lineEditStackFileName.displayText()

        suffix = str(self.comboBoxStackFileType.currentText())
        newPath, newFilename = self.fixFilePath(path, separateFile = True, suffix =
                                      suffix)
        newSuffix = newFilename.split(".")[-1]
        newFilename = ".".join(newFilename.split(".")[:-1])

        if newPath == "":
            newPath = oldPath
        
        if newFilename == "":
            newFilename = oldFilename
        self.lineEditStackPath.setText(newPath)
        self.lineEditStackFileName.setText(newFilename)
        self.comboBoxStackFileType.setCurrentIndex(self.comboBoxStackFileType.findText(newSuffix))
        self.updateStackWriter()

        

#===============================================================================
# output formats
#===============================================================================
    def on_radioButtonH5Clicked(self):
        self.widgetOptionsHDF5.setVisible(True)
        self.widgetOptionsStack.setVisible(False)
        self.setLayerValueRangeInfo()
        self.checkTypeConversionNecessary()

    def on_radioButtonStackClicked(self):
        self.widgetOptionsHDF5.setVisible(False)
        self.widgetOptionsStack.setVisible(True)
        self.setLayerValueRangeInfo()
        self.checkTypeConversionNecessary()
        #self.correctFilePathSuffix()
        self.updateStackWriter()
    
    def getOutputDType(self):
        if self.radioButtonH5.isChecked():
            h5type = str(self.comboBoxHdf5DataType.currentText())
            return numpy.dtype(h5type).type
            #parse for type / bits
            
        elif self.radioButtonStack.isChecked():
            stacktype = str(self.comboBoxStackFileType.currentText())
            return self.convertFiletypeToDtype(stacktype)
            
    def comboBoxStackFileTypeChanged(self, int):
        self.setLayerValueRangeInfo()
        self.checkTypeConversionNecessary()
        self.updateStackWriter()


    def checkTypeConversionNecessary(self):
        if hasattr(self, "inputType"):
            t = self.inputType
            limits = []
            try:
                limits.append(numpy.iinfo(t).min)
                limits.append(numpy.iinfo(t).max)
            except:
                limits.append(numpy.finfo(t).min)
                limits.append(numpy.finfo(t).max)

            try:
                if not numpy.all(numpy.array(limits, dtype = self.getOutputDType()) == limits):
                    self.normalizationComboBox.setCurrentIndex(1)
            except:
                self.normalizationComboBox.setCurrentIndex(1)



#===============================================================================
# options
#===============================================================================
    def on_normalizationComboBoxChanged(self):
        self.normalizationMethod = self.normalizationComboBox.currentIndex()
        
        if self.normalizationMethod == 0:
            self.inputOutputValueRanges.hide()

        else:
            self.setLayerValueRangeInfo()
            self.inputOutputValueRanges.show()

        
        #self.validateInputOutputRange()



    #===========================================================================
    # lineEditOutputShape    
    #===========================================================================
    
    def getSlicing(self):
        slicing = []
        for check, roi in zip(self.roiWidget.roiCheckBoxes, self.roiWidget.roiWidgets):
            if check.isChecked():
                slicing.append(slice(None))
            else:
                minVal, maxVal = roi.getValues()
                slicing.append(slice(minVal, maxVal))
    
        return tuple(slicing)
    
    
    def validateOptions(self):
        allValid = True
        #allValid = self.validRoi and allValid
        okButton = self.buttonBox.button(QDialogButtonBox.Ok)
        if self.radioButtonStack.isChecked():
            allValid = self.validAxesComboBoxes and allValid
        if allValid:
            okButton.setEnabled(True)
        else:
            okButton.setEnabled(False)
        
        return allValid
    
    def validateAxesComboBoxes(self):
        axes = [str(axis.currentText()) for axis in self.comboBoxes]
         
        self.validAxesComboBoxes = True
        
        def changeComboBoxes(box1, box2):
            if box2.count() > 0:
                box2.setCurrentIndex((box2.currentIndex() + 1) % box2.count())

        for c in combinations(range(len(axes)), 2):
            if axes[c[0]] == axes[c[1]]:
                changeComboBoxes(self.comboBoxes[c[0]], self.comboBoxes[c[1]])
            
        if len(list(set(axes))) != len(axes): #if all entries are unique
            self.validAxesComboBoxes = False
        if self.validAxesComboBoxes:
            self.updateStackWriter()
        self.validateOptions()


#===============================================================================
# create values
#===============================================================================
    
    








    def accept(self, *args, **kwargs):
        dlg = MultiStepProgressDialog(self)
        #thunkEventHandler = ThunkEventHandler(dlg)
        dlg.setNumberOfSteps(2)
        #Step1: 
        
        slicing = self.getSlicing()
        ranges = [self.inputValueRange.getValues(),
                  self.outputValueRange.getValues()]
        outputDType = self.getOutputDType()


        fileWriter = "h5"
        if self.radioButtonStack.isChecked():
            fileWriter = "stack"

        elif self.radioButtonH5.isChecked():
            fileWriter = "h5"
            self.writer.setupH5Writer(str(self.lineEditH5FilePath.displayText()),
                                     str(self.lineEditH5DataPath.displayText()))

        retval = self.writer.write(self.input, slicing, ranges, outputDType,
                                 fileWriter)
        return QDialog.accept(self, *args, **kwargs)

    
    def show(self):
        if not _has_lazyflow:
            popUp = QMessageBox(parent=self)
            popUp.setTextFormat(1)
            popUp.setText("<font size=\"4\"> Lazyflow could not be imported:</font> <br><br><b><font size=\"4\" color=\"#8A0808\">%s</font></b>"%(exceptStr))
            popUp.show()
            popUp.exec_()
        QDialog.show(self)
  
    def convertFiletypeToDtype(self, ftype):
        if ftype == "png":
            return numpy.uint8
        if ftype == "jpeg":
            return numpy.uint8
        if ftype == "bmp":
            return numpy.uint8
        if ftype == "tiff":
            return numpy.uint32

if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    from lazyflow.operators import OpArrayPiper
    from lazyflow.graph import Graph
    app = QApplication(list())
   
    g = Graph()
    arr = vigra.Volume((60,800,400), dtype=numpy.float32)
    arr[:] = numpy.random.random_sample(arr.shape)
    a = OpArrayPiper(graph=g)
    w = Writer()
    a.Input.setValue(arr)
    
    d = ExportDialog()
    d.setInput(a.Output)
    
    d.show()
    app.exec_()

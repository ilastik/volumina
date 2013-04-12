#Python
import os
import threading
from collections import OrderedDict
from functools import partial
from itertools import combinations
import re
import logging

#PyQt
from PyQt4.QtGui import QDialog, QFileDialog, QRegExpValidator, QPalette,\
                        QDialogButtonBox, QMessageBox, QProgressDialog, QLabel
from PyQt4.QtCore import QRegExp, Qt, QTimer, pyqtSignal
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




class ExportDialog(QDialog):
    
    progressSignal = pyqtSignal(float)
    finishedStepSignal = pyqtSignal()
    
    def __init__(self, parent=None, layername = "Untitled"):
        QDialog.__init__(self, parent)
        if not _has_lazyflow:
            QDialog.setEnabled(self,False)
        self.validRoi = True
        self.validInputOutputRange = True
        self.validAxesComboBoxes = True
        self.layername = layername
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
        self.pushButtonStackPath.clicked.connect(self.on_pushButtonStackPathClicked)
        self.radioButtonH5.clicked.connect(self.on_radioButtonH5Clicked)
        self.radioButtonStack.clicked.connect(self.on_radioButtonStackClicked)
        self.comboBoxStackFileType.currentIndexChanged.connect(self.comboBoxStackFileTypeChanged)
        self.comboBoxHdf5DataType.currentIndexChanged.connect(self.setLayerValueRangeInfo)
        self.lineEditOutputShapeX.textEdited.connect(self.validateRoi)
        self.lineEditOutputShapeY.textEdited.connect(self.validateRoi)
        self.lineEditOutputShapeZ.textEdited.connect(self.validateRoi)
        self.lineEditOutputShapeT.textEdited.connect(self.validateRoi)
        self.lineEditOutputShapeC.textEdited.connect(self.validateRoi)
        self.normalizationComboBox.currentIndexChanged.connect(self.on_normalizationComboBoxChanged)
        
        self.inputValueRange.textEdited.connect(self.validateInputOutputRange)
        self.outputValueRange.textEdited.connect(self.validateInputOutputRange)
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
        self.setAvailableImageAxes()
        self.setRegExToLineEditOutputShape()
        self.setDefaultComboBoxHdf5DataType()
        self.validateRoi()
        
    def setupWriters(self):

        if not hasattr(self, "stackWriter"):
            self.stackWriter = OpStackWriter(self.input.getRealOperator())
        if not hasattr(self, "h5Writer"):
            self.h5Writer = OpH5WriterBigDataset(self.input.getRealOperator())
        
        if self.radioButtonStack.isChecked():
        
            self.stackWriter.Filepath.setValue(str(self.lineEditStackPath.displayText()))
            self.stackWriter.Filename.setValue(str(self.lineEditStackFileName.displayText()))
            self.stackWriter.Filetype.setValue(str(self.comboBoxStackFileType.currentText()))
            imageAxesNames = [str(value.currentText()) for value in self.comboBoxes]
            self.stackWriter.ImageAxesNames.setValue(imageAxesNames)
            

        elif self.radioButtonH5.isChecked():
            hdf5path = str(self.lineEditH5DataPath.displayText())
            self.h5Writer.hdf5Path.setValue(hdf5path)


    def updateStackWriter(self):
        pattern = [""]
        if hasattr(self, "input"):
            self.setupWriters()
            self.stackWriter.Image.connect(self.input)
            if self.stackWriter.FilePattern.ready():
                pattern = self.stackWriter.FilePattern[:].wait()
        #self.stackWriter.Input.disconnect()
        placeholders = re.findall("%04d", pattern[0])
        insertedPattern = pattern[0] % tuple([0 for i in xrange(len(placeholders))])
        self.stackFilePatternPreview.setText(insertedPattern)

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
        import sitecustomize
        sitecustomize.debug_trace()
        for i, (axis, extent) in enumerate(zip(self.input.meta.axistags, self.input.meta.shape)):
            self.line_outputShape[axis.key].setText("0 - %d" % (extent-1))
        for key in "txyzc":
            if key not in self.input.meta.getAxisKeys():
                self.line_outputShape[key].setEnabled(False)
        self.inputVolumeDescription.setText(self._volumeMetaString(self.input))
    
    def setAvailableImageAxes(self):
        axisTags = self.input.meta.axistags
        extents  = self.input.meta.shape
        self.comboBoxes = [self.axesComboBox1, self.axesComboBox2, self.axesComboBox3]
        
        for index, tag in enumerate(axisTags):
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
        inputDRange = [0,1]
        dtype = numpy.uint8
        if hasattr(self, "input"):
            dtype = self.input.meta.dtype 
            if hasattr(self.input.meta, "drange") and self.input.meta.drange: 
                inputDRange = self.input.meta.drange
            if hasattr(dtype, "type"):
                dtype = dtype.type
        stringifiedInputDRange = [str(dtype(i)) for i in inputDRange]
            
        self.inputValueRange.setText("%s - %s" % tuple(stringifiedInputDRange))
        
        outputType = self.getOutputDtype()
        typeLimits = []
        try:
            typeLimits.append(numpy.iinfo(outputType).min)
            typeLimits.append(numpy.iinfo(outputType).max)
        except:
            typeLimits = inputDRange


        self.inputType = dtype
        self.outputType = outputType

        stringifiedOutputDRange = [str(outputType(i)) for i in typeLimits]
        self.outputValueRange.setText("%s - %s" % tuple(stringifiedOutputDRange))

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
                                              str(self.lineEditStackFileName.displayText()
                                                 + "." + suffix)))
        self.updateStackPaths(path)

    def updateH5Paths(self, path):
        
        newPath, newFilename = self.fixFilePath(path, separateFile = False, suffix =
                                      "h5")

        newSuffix = newFilename.split(".")[-1]
        self.lineEditH5FilePath.setText(newPath)


    def updateStackPaths(self, path):
        suffix = str(self.comboBoxStackFileType.currentText())
        newPath, newFilename = self.fixFilePath(path, separateFile = True, suffix =
                                      suffix)
        newSuffix = newFilename.split(".")[-1]
        self.lineEditStackPath.setText(newPath)
        self.lineEditStackFileName.setText(".".join(newFilename.split(".")[:-1]))
        self.comboBoxStackFileType.setCurrentIndex(self.comboBoxStackFileType.findText(newSuffix))
        self.updateStackWriter()

        

#===============================================================================
# output formats
#===============================================================================
    def on_radioButtonH5Clicked(self):
        self.widgetOptionsHDF5.setVisible(True)
        self.widgetOptionsStack.setVisible(False)
        #self.correctFilePathSuffix()

    def on_radioButtonStackClicked(self):
        self.widgetOptionsHDF5.setVisible(False)
        self.widgetOptionsStack.setVisible(True)
        #self.correctFilePathSuffix()
        self.updateStackWriter()
    
    def getOutputDtype(self):
        if self.radioButtonH5.isChecked():
            h5type = str(self.comboBoxHdf5DataType.currentText())
            return numpy.dtype(h5type).type
            #parse for type / bits
            
        elif self.radioButtonStack.isChecked():
            stacktype = str(self.comboBoxStackFileType.currentText())
            return self.convertFiletypeToDtype(stacktype)
            
    def comboBoxStackFileTypeChanged(self, int):
        self.checkTypeConversionNecessary()
        self.updateStackWriter()


    def checkTypeConversionNecessary(self):
        if hasattr(self, "inputType") and hasattr(self, "outputType"):
            t = self.inputType
            limits = []
            try:
                limits.append(numpy.iinfo(t).min)
                limits.append(numpy.iinfo(t).max)
            except:
                limits.append(numpy.finfo(t).min)
                limits.append(numpy.finfo(t).max)

            try:
                if not numpy.all(numpy.array(limits, dtype = self.outputType) == limits):
                    self.normalizationComboBox.setCurrentIndex(1)
            except:
                self.normalizationComboBox.setCurrentIndex(1)



#===============================================================================
# options
#===============================================================================
    def on_normalizationComboBoxChanged(self):
        selection = str(self.normalizationComboBox.currentText())
        if selection == "No Normalization":
            self.normalizationMethod = 0
        elif selection == "Change range from":
            self.normalizationMethod = 1
        elif selection == "Auto Normalization":
            self.normalizationMethod = 2 #Currently not implemented
        
        p = QPalette()
        if self.normalizationMethod == 0:
            p.setColor(QPalette.Base,Qt.gray)
            p.setColor(QPalette.Text,Qt.gray)
            
            self.inputValueRange.setPalette(p)
            self.inputValueRange.setEnabled(False)
            self.outputValueRange.setPalette(p)
            self.outputValueRange.setEnabled(False)

        else:
            self.setLayerValueRangeInfo()
            p.setColor(QPalette.Base,Qt.white)
            p.setColor(QPalette.Text,Qt.black)
            self.inputValueRange.setPalette(p)
            self.inputValueRange.setEnabled(True)
            self.outputValueRange.setPalette(p)
            self.outputValueRange.setEnabled(True)

        
        self.validateInputOutputRange()



    #===========================================================================
    # lineEditOutputShape    
    #===========================================================================
    def validateOptions(self):
        allValid = True
        allValid = self.validRoi and allValid
        okButton = self.buttonBox.button(QDialogButtonBox.Ok)
        if self.radioButtonStack.isChecked():
            allValid = self.validAxesComboBoxes and allValid
        if self.normalizationMethod > 0:
            allValid = self.validInputOutputRange and allValid
        if allValid:
            okButton.setEnabled(True)
        else:
            okButton.setEnabled(False)
        
        return allValid
    
    def validateRoi(self):

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
                p.setColor(QPalette.Base,Qt.white)
                p.setColor(QPalette.Text,Qt.black)
            elif value == False:
                isValid = False
                p.setColor(QPalette.Base,Qt.red)
                p.setColor(QPalette.Text,Qt.white)
            elif value == "Disabled":
                p.setColor(QPalette.Base, Qt.gray)
                p.setColor(QPalette.Text,Qt.gray)
                
            self.line_outputShape[key].setPalette(p)

        self.roi = tuple(lineEditOutputShapeList)

        self.validRoi = isValid
        self.validateOptions()

        
    def lineEditOutputShapeChanged(self):
        self.lineEditOutputShapeListValidation()

    def validateInputOutputRange(self):
        allValid = True
        if self.normalizationMethod > 0:
            #validate input range:
            dtypes = [self.input.meta.dtype, self.getOutputDtype()]
            self.normalizationValues = [[] for dtype in dtypes]
            for i, valueRange in enumerate([self.inputValueRange,
                                            self.outputValueRange]):
                limits = []
                dtype = dtypes[i]
                if hasattr(dtype, 'type'):
                    dtype = dtype.type
                for token in str(valueRange.text()).split():
                    try:
                        num = dtype(token)
                        limits.append(num)
                    except:
                        pass
            
                p = QPalette()

                isValid = True
                if len(limits) != 2:
                    isValid = False
                elif not limits[1] > limits[0]:
                    isValid = False
                else:
                    self.normalizationValues[i] = limits
                
                if isValid:
                    p.setColor(QPalette.Base,Qt.white)
                    p.setColor(QPalette.Text,Qt.black)
                else:
                    logger.debug("range is invalid" +  str(limits))
                    p.setColor(QPalette.Base,Qt.red)
                    p.setColor(QPalette.Text,Qt.white)
                
                valueRange.setPalette(p) 

                allValid = allValid and isValid
        
        self.validInputOutputRange = allValid

        self.validateOptions()
        
    
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
        
        roi = sliceToRoi(self.roi,self.input.meta.shape)
        subRegion = OpSubRegion(self.input.getRealOperator())

        subRegion.Start.setValue(tuple([k for k in roi[0]]))
        subRegion.Stop.setValue(tuple([k for k in roi[1]]))
        subRegion.Input.connect(self.input)

        inputVolume = subRegion

        #handle different outputTypes


        if self.normalizationMethod in [1,2]:
            normalizer = OpPixelOperator(self.input.getRealOperator())
            normalizer.Input.connect(inputVolume.Output)
            minVal, maxVal = numpy.nan, numpy.nan

            if self.normalizationMethod == 1:
                inputVolume = normalizer.Output
                minVal,maxVal = self.normalizationValues[0]
                outputMinVal, outputMaxVal = self.normalizationValues[1]
            elif self.normalizationMethod == 2:
                raise Exception("Not Implemented yet")
                
            def normalize(val):
                invVal = 1./(maxVal - minVal)
                return outputMinVal + (val - minVal)  * (outputMaxVal - outputMinVal) * invVal 
            
            normalizer.Function.setValue(normalize)
            inputVolume = normalizer

        outputDtype = self.getOutputDtype()
        if outputDtype is not self.input.meta.dtype:
            converter = OpPixelOperator(self.input.getRealOperator())
            converter.Input.connect(inputVolume.Output)
            
            def convertToType(val):
                return outputDtype(val)
            converter.Function.setValue(convertToType)
            inputVolume = converter

        dlg.finishStep()
        #step 2
        writer = None
        h5f = None
        if self.radioButtonStack.isChecked():
            writer = self.stackWriter
        elif self.radioButtonH5.isChecked():
            writer = self.h5Writer
            h5f = h5py.File(str(self.lineEditH5FilePath.displayText()), 'a')
            writer.hdf5File.setValue(h5f)

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
        if h5f is not None:
            h5f.close()
        
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
        if ftype == "tiff":
            return numpy.uint32

if __name__ == '__main__':
    from PyQt4.QtGui import QApplication
    import vigra, numpy
    from lazyflow.operators import OpArrayPiper
    from lazyflow.graph import Graph
    app = QApplication(list())
   
    g = Graph()
    arr = vigra.Volume((60,80,40), dtype=numpy.float32)
    arr[:] = numpy.random.random_sample(arr.shape)
    a = OpArrayPiper(graph=g)
    a.Input.setValue(arr)
    
    d = ExportDialog()
    d.setInput(a.Output)
    
    d.show()
    app.exec_()

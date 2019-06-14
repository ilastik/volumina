###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2019, the ilastik developers
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
import pytest
from PyQt5.QtWidgets import QMainWindow
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtGui import QColor

import numpy as np
import vigra
from ilastik.applets.layerViewer.layerViewerGui import LayerViewerGui
from lazyflow.operators.opReorderAxes import OpReorderAxes
from volumina.volumeEditor import VolumeEditor
from volumina.volumeEditorWidget import VolumeEditorWidget
from volumina.layerstack import LayerStackModel
from volumina.pixelpipeline.datasources import LazyflowSource
from volumina.layer import AlphaModulatedLayer
from lazyflow.graph import Operator, InputSlot, OutputSlot, Graph


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.volumeEditorWidget = VolumeEditorWidget(parent=self)


class OpTestImgaeSlots(Operator):
    """test operator, containing 3-dim test data"""

    GrayscaleImageIn = InputSlot()
    Label1ImageIn = InputSlot()
    Label2ImageIn = InputSlot()

    GrayscaleImageOut = OutputSlot()
    Label1ImageOut = OutputSlot()
    Label2ImageOut = OutputSlot()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        width, height, depth = 300, 200, 40

        # create 2-dimensional images
        grayscaleImageSource = np.random.randint(0, 255, (depth, height, width, 1))
        label1ImageSource = np.zeros((depth, height, width, 3), dtype=np.int32)
        label2ImageSource = np.zeros((depth, height, width, 3), dtype=np.int32)

        for z, set1 in enumerate(grayscaleImageSource[:, :, :, 0]):
            for y, set2 in enumerate(set1):
                for x, set3 in enumerate(set2):
                    if z in range(5, 20) and y in range(20, 30) and x in range(80, 140):
                        label1ImageSource[z, y, x, :] = [255, 255, 255]
                    if z in range(25, 37) and y in range(100, 150) and x in range(10, 60):
                        label2ImageSource[z, y, x, :] = [255, 255, 255]

        self.GrayscaleImageIn.setValue(grayscaleImageSource, notify=False, check_changed=False)
        self.Label1ImageIn.setValue(label1ImageSource, notify=False, check_changed=False)
        self.Label2ImageIn.setValue(label2ImageSource, notify=False, check_changed=False)

        self.GrayscaleImageIn.meta.axistags = vigra.defaultAxistags("tzyxc"[5 - len(self.GrayscaleImageIn.meta.shape):])
        self.Label1ImageIn.meta.axistags = vigra.defaultAxistags("tzyxc"[5 - len(self.Label1ImageIn.meta.shape):])
        self.Label2ImageIn.meta.axistags = vigra.defaultAxistags("tzyxc"[5 - len(self.Label2ImageIn.meta.shape):])

        self.GrayscaleImageOut.connect(self.GrayscaleImageIn)
        self.Label1ImageOut.connect(self.Label1ImageIn)
        self.Label2ImageOut.connect(self.Label2ImageIn)


class TestSpinBoxImageView(object):

    def updateAllTiles(self, imageScenes):
        for scene in imageScenes:
            scene.joinRenderingAllTiles()

    @pytest.fixture(autouse=True)
    def setupClass(self, qtbot):

        self.qtbot = qtbot
        self.main = MainWindow()
        self.layerStack = LayerStackModel()

        g = Graph()
        self.op = OpTestImgaeSlots(graph=g)

        self.grayscaleLayer = LayerViewerGui._create_grayscale_layer_from_slot(self.op.GrayscaleImageOut, 1)
        self.labelLayer1 = AlphaModulatedLayer(LazyflowSource(self.op.Label1ImageOut), tintColor=QColor(Qt.cyan),
                                               range=(0, 255), normalize=(0, 255))
        self.labelLayer2 = AlphaModulatedLayer(LazyflowSource(self.op.Label2ImageOut), tintColor=QColor(Qt.yellow),
                                               range=(0, 255), normalize=(0, 255))

        self.labelLayer1.name = "Segmentation (Label 1)"
        self.labelLayer2.name = "Segmentation (Label 2)"

        self.layerStack.append(self.grayscaleLayer)
        self.layerStack.append(self.labelLayer1)
        self.layerStack.append(self.labelLayer2)

        activeOutSlot = self.op.GrayscaleImageOut  # take any out slot here
        if activeOutSlot.ready() and activeOutSlot.meta.axistags is not None:
            # Use an OpReorderAxes adapter to transpose the shape for us.
            op5 = OpReorderAxes(graph=g)
            op5.Input.connect(activeOutSlot)
            op5.AxisOrder.setValue('txyzc')
            shape = op5.Output.meta.shape

            # We just needed the op to determine the transposed shape.
            # Disconnect it so it can be garbage collected.
            op5.Input.disconnect()
            op5.cleanUp()

        self.editor = VolumeEditor(self.layerStack, self.main)
        self.editorWidget = self.main.volumeEditorWidget
        self.editorWidget.init(self.editor)

        self.editor.dataShape = shape

        # Find the xyz midpoint
        midpos5d = [x // 2 for x in shape]
        # center viewer there
        # set xyz position
        midpos3d = midpos5d[1:4]
        self.editor.posModel.slicingPos = midpos3d
        self.editor.navCtrl.panSlicingViews(midpos3d, [0, 1, 2])
        for i in range(3):
            self.editor.navCtrl.changeSliceAbsolute(midpos3d[i], i)

        self.main.setCentralWidget(self.editorWidget)
        self.main.show()
        self.qtbot.addWidget(self.main)

    def testAddingAndRemovingPosVal(self):
        assert 0 == len(self.editorWidget.quadViewStatusBar.layerValueWidgets)

        for layer in self.layerStack:
            if not layer.showPosValue:
                layer.showPosValue = True
            if not layer.visible:
                layer.visible = True

        for layer in self.layerStack:
            assert layer in self.editorWidget.quadViewStatusBar.layerValueWidgets

        self.layerStack[0].showPosValue = False
        assert self.layerStack[0] not in self.editorWidget.quadViewStatusBar.layerValueWidgets
        self.layerStack[2].showPosValue = False
        assert self.layerStack[2] not in self.editorWidget.quadViewStatusBar.layerValueWidgets
        self.layerStack[1].showPosValue = False
        assert self.layerStack[1] not in self.editorWidget.quadViewStatusBar.layerValueWidgets
        self.layerStack[2].showPosValue = True
        assert self.layerStack[2] in self.editorWidget.quadViewStatusBar.layerValueWidgets

    def testLayerPositionValueStrings(self):
        for layer in self.layerStack:
            if not layer.showPosValue:
                layer.showPosValue = True
            if not layer.visible:
                layer.visible = True

        x, y, z = 90, 25, 10

        posVal = 255-int(self.op.GrayscaleImageIn.value[z, y, x, 0])
        grayValidationStrings = ["Gray:" + str(posVal), "Gray:" + str(posVal+1), "Gray:" + str(posVal-1)]
        label1ValidationString = "Label 1"
        label2ValidationString = "Label 2"

        signal = self.editor.posModel.cursorPositionChanged
        with self.qtbot.waitSignal(signal, timeout=1000):
            self.editor.navCtrl.changeSliceAbsolute(z, 2)

        # After change of crosshair positions tiles are marked dirty.
        self.updateAllTiles(self.editor.imageScenes)  # Wait for all tiles being refreshed

        signals = [self.editorWidget.quadViewStatusBar.layerValueWidgets[self.grayscaleLayer].textChanged,
                   self.editorWidget.quadViewStatusBar.layerValueWidgets[self.labelLayer1].textChanged]
        with self.qtbot.waitSignals(signals, timeout=1000):
            self.editor.navCtrl.positionDataCursor(QPointF(x, y), 2)

        self.updateAllTiles(self.editor.imageScenes)  # Wait for all tiles being refreshed

        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.grayscaleLayer].text() in grayValidationStrings
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[self.labelLayer1].text() == label1ValidationString

        x, y, z = 39, 130, 30

        posVal = 255-int(self.op.GrayscaleImageIn.value[z, y, x, 0])
        grayValidationStrings = ["Gray:" + str(posVal), "Gray:" + str(posVal+1), "Gray:" + str(posVal-1)]

        with self.qtbot.waitSignal(signal, timeout=1000):
            self.editor.navCtrl.changeSliceAbsolute(y, 1)

        self.updateAllTiles(self.editor.imageScenes)  # Wait for all tiles being refreshed

        with self.qtbot.waitSignals(signals, timeout=1000):
            self.editor.navCtrl.positionDataCursor(QPointF(x, z), 1)

        self.updateAllTiles(self.editor.imageScenes)  # Wait for all tiles being refreshed

        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.grayscaleLayer].text() in grayValidationStrings
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[self.labelLayer2].text() == label2ValidationString


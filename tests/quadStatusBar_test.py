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
from PyQt5.QtCore import QPointF, Qt, QCoreApplication
from PyQt5.QtGui import QColor

import numpy as np
import vigra
from ilastik.applets.layerViewer.layerViewerGui import LayerViewerGui
from volumina.volumeEditor import VolumeEditor
from volumina.volumeEditorWidget import VolumeEditorWidget
from volumina.layerstack import LayerStackModel
from volumina.pixelpipeline.datasources import LazyflowSource
from volumina.layer import AlphaModulatedLayer, ColortableLayer, NormalizableLayer, RGBALayer
from lazyflow.graph import Operator, InputSlot, OutputSlot, Graph

# taken from https://sashat.me/2017/01/11/list-of-20-simple-distinct-colors/
default16_new = [
    QColor(0, 0, 0, 0).rgba(),  # transparent
    QColor(255, 225, 25).rgba(),  # yellow
    QColor(0, 130, 200).rgba(),  # blue
    QColor(230, 25, 75).rgba(),  # red
    QColor(70, 240, 240).rgba(),  # cyan
    QColor(60, 180, 75).rgba(),  # green
    QColor(250, 190, 190).rgba(),  # pink
    QColor(170, 110, 40).rgba(),  # brown
    QColor(145, 30, 180).rgba(),  # purple
    QColor(0, 128, 128).rgba(),  # teal
    QColor(245, 130, 48).rgba(),  # orange
    QColor(240, 50, 230).rgba(),  # magenta
    QColor(210, 245, 60).rgba(),  # lime
    QColor(255, 215, 180).rgba(),  # coral
    QColor(230, 190, 255).rgba(),  # lavender
    QColor(128, 128, 128).rgba(),  # gray
]

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.volumeEditorWidget = VolumeEditorWidget(parent=self)


class OpTestImageSlots(Operator):
    """test operator, containing 3-dim test data"""
    GrayscaleIn = InputSlot()
    RgbaIn = InputSlot(level=1)
    ColorTblIn1 = InputSlot()
    ColorTblIn2 = InputSlot()
    AlphaModulatedIn = InputSlot()
    Segmentation1In = InputSlot()
    Segmentation2In = InputSlot()

    GrayscaleOut = OutputSlot()
    RgbaOut = OutputSlot(level=1)
    ColorTblOut1 = OutputSlot()
    ColorTblOut2 = OutputSlot()
    AlphaModulatedOut = OutputSlot()
    Segmentation1Out = OutputSlot()
    Segmentation2Out = OutputSlot()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        time, width, height, depth = 4, 300, 200, 10
        self.dataShape = (time, width, height, depth, 1)
        shape4d = (time, width, height, depth, 1)
        shape5d1 = (4, time, width, height, depth, 1)
        shape5d2 = (time, width, height, depth, 3)

        # create images
        grayscaleImage = np.random.randint(0, 255, shape4d)
        rgbaImage = np.random.randint(0, 255, shape5d1)
        colorTblImage1 = np.random.randint(0, 10, shape4d)
        colorTblImage2 = np.random.randint(0, 10, shape4d)
        AlphaModImage = np.zeros(shape5d2, dtype=np.int32)
        Segment1Image = np.zeros(shape5d2, dtype=np.int32)
        Segment2Image = np.zeros(shape5d2, dtype=np.int32)

        # define some dummy segmentations
        for t in range(time):
            for x in range(width):
                for y in range(height):
                    for z in range(depth):
                        if t==3 and z in range(5, 9) and y in range(20, 30) and x in range(80, 140):
                            Segment1Image[t, x, y, z, :] = [255, 255, 255]
                            AlphaModImage[t, x, y, z, :] = [255, 255, 255]
                            colorTblImage1[t, x, y, z, :] = 0
                        if t==1 and z in range(0, 6) and y in range(100, 150) and x in range(10, 60):
                            Segment2Image[t, x, y, z, :] = [255, 255, 255]
                            colorTblImage2[t, x, y, z, :] = 0

        self.GrayscaleIn.setValue(grayscaleImage, notify=False, check_changed=False)
        self.RgbaIn.setValues(rgbaImage)
        self.ColorTblIn1.setValue(colorTblImage1, notify=False, check_changed=False)
        self.ColorTblIn2.setValue(colorTblImage2, notify=False, check_changed=False)
        self.AlphaModulatedIn.setValue(AlphaModImage, notify=False, check_changed=False)
        self.Segmentation1In.setValue(Segment1Image, notify=False, check_changed=False)
        self.Segmentation2In.setValue(Segment2Image, notify=False, check_changed=False)

        atags3d = "txyzc"[5 - len(shape4d):]
        atags4d2 = "txyzc"[5 - len(shape5d2):]
        self.GrayscaleIn.meta.axistags = vigra.defaultAxistags(atags3d)
        for i in range(4):
            self.RgbaIn[i].meta.axistags = vigra.defaultAxistags(atags3d)
        self.ColorTblIn1.meta.axistags = vigra.defaultAxistags(atags3d)
        self.ColorTblIn2.meta.axistags = vigra.defaultAxistags(atags3d)
        self.AlphaModulatedIn.meta.axistags = vigra.defaultAxistags(atags4d2)
        self.Segmentation1In.meta.axistags = vigra.defaultAxistags(atags4d2)
        self.Segmentation2In.meta.axistags = vigra.defaultAxistags(atags4d2)

        self.GrayscaleOut.connect(self.GrayscaleIn)
        self.RgbaOut.connect(self.RgbaIn)
        self.ColorTblOut1.connect(self.ColorTblIn1)
        self.ColorTblOut2.connect(self.ColorTblIn2)
        self.AlphaModulatedOut.connect(self.AlphaModulatedIn)
        self.Segmentation1Out.connect(self.Segmentation1In)
        self.Segmentation2Out.connect(self.Segmentation2In)


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
        self.op = OpTestImageSlots(graph=g)

        self.grayscaleLayer = LayerViewerGui._create_grayscale_layer_from_slot(self.op.GrayscaleOut, 1)
        self.segLayer1 = AlphaModulatedLayer(LazyflowSource(self.op.Segmentation1Out), tintColor=QColor(Qt.cyan),
                                             range=(0, 255), normalize=(0, 255))
        self.segLayer2 = AlphaModulatedLayer(LazyflowSource(self.op.Segmentation2Out), tintColor=QColor(Qt.yellow),
                                             range=(0, 255), normalize=(0, 255))
        self.alphaModLayer = AlphaModulatedLayer(LazyflowSource(self.op.AlphaModulatedOut),
                                                 tintColor=QColor(Qt.magenta), range=(0, 255), normalize=(0, 255))
        self.colorTblLayer1 = ColortableLayer(LazyflowSource(self.op.ColorTblOut1), default16_new)
        self.colorTblLayer2  = ColortableLayer(LazyflowSource(self.op.ColorTblOut2), default16_new)
        self.rgbaLayer = RGBALayer(red=LazyflowSource(self.op.RgbaOut[0]), green=LazyflowSource(self.op.RgbaOut[1]),
                                   blue=LazyflowSource(self.op.RgbaOut[2]), alpha=LazyflowSource(self.op.RgbaOut[3]))
        self.emptyRgbaLayer = RGBALayer()

        self.segLayer1.name = "Segmentation (Label 1)"
        self.segLayer2.name = "Segmentation (Label 2)"
        self.grayscaleLayer.name = "Raw Input"
        self.colorTblLayer1.name = "Labels"
        self.colorTblLayer2.name = "pos info in Normalizable"
        self.rgbaLayer.name = "rgba layer"
        self.emptyRgbaLayer.name = "empty rgba layer"
        self.alphaModLayer.name = "alpha modulated layer"

        self.layerStack.append(self.grayscaleLayer)
        self.layerStack.append(self.segLayer1)
        self.layerStack.append(self.segLayer2)
        self.layerStack.append(self.colorTblLayer1)
        self.layerStack.append(self.colorTblLayer2)
        self.layerStack.append(self.rgbaLayer)
        self.layerStack.append(self.emptyRgbaLayer)
        self.layerStack.append(self.alphaModLayer)

        self.editor = VolumeEditor(self.layerStack, self.main)
        self.editorWidget = self.main.volumeEditorWidget
        self.editorWidget.init(self.editor)

        self.editor.dataShape = self.op.dataShape

        # Find the xyz origin
        midpos5d = [x // 2 for x in self.op.dataShape]
        # center viewer there
        # set xyz position
        midpos3d = midpos5d[1:4]
        self.editor.posModel.slicingPos = midpos3d
        self.editor.navCtrl.panSlicingViews(midpos3d, [0, 1, 2])
        for i in range(3):
            self.editor.navCtrl.changeSliceAbsolute(midpos3d[i], i)

        self.main.setCentralWidget(self.editorWidget)
        self.main.setFixedSize(1000, 800)
        self.main.show()
        self.qtbot.addWidget(self.main)

    def testAddingAndRemovingPosVal(self):
        assert 0 == len(self.editorWidget.quadViewStatusBar.layerValueWidgets)

        for layer in self.layerStack:
            layer.visible = True
            if not layer.showPosValue:
                layer.showPosValue = True
            if not layer.visible:
                layer.visible = True

        for i in range(30):
            QCoreApplication.processEvents()

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

        t, x, y, z = 3, 90, 25, 6

        grayValidationString = "Raw I.:" + str(self.op.GrayscaleIn.value[t, x, y, z, 0])
        labelValidationString = "Label 1"
        colorTbl1ValidationString = "-"
        colorTbl2ValidationString = "pos i. i. N.:" + str(self.op.ColorTblOut2.value[t, x, y, z, 0])
        rgbaValidationString = "rgba l.:{};{};{};{}".format(*[str(slot.value[t, x, y, z, 0]) for slot in self.op.RgbaIn])
        emptyRgbaValidationString = "empty r. l.:0;0;0;255"
        alphaModValidationString = "alpha m. l.:" + str(self.op.AlphaModulatedOut.value[t, x, y, z, 0])


        signal = self.editor.posModel.cursorPositionChanged
        with self.qtbot.waitSignal(signal, timeout=1000):
            self.editor.navCtrl.changeSliceAbsolute(z, 2)
            self.editor.navCtrl.changeTime(t)

        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()
        QCoreApplication.processEvents()


        self.editor.navCtrl.positionDataCursor(QPointF(0, 0), 2)

        self.editor.navCtrl.positionDataCursor(QPointF(x, y), 2)

        assert self.editorWidget.quadViewStatusBar.xSpinBox.value() == x
        assert self.editorWidget.quadViewStatusBar.ySpinBox.value() == y
        assert self.editorWidget.quadViewStatusBar.zSpinBox.value() == z
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.grayscaleLayer].text() == grayValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.segLayer1].text() == labelValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.segLayer2].text() == labelValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.colorTblLayer1].text() == colorTbl1ValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.colorTblLayer2].text() == colorTbl2ValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.rgbaLayer].text() == rgbaValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.emptyRgbaLayer].text() == emptyRgbaValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.alphaModLayer].text() == alphaModValidationString

        t, x, y, z = 1, 39, 130, 3

        grayValidationString = "Raw I.:" + str(self.op.GrayscaleIn.value[t, x, y, z, 0])
        labelValidationString = "Label 2"
        colorTbl1ValidationString = "Labels:" + str(self.op.ColorTblIn1.value[t, x, y, z, 0])
        colorTbl2ValidationString = "pos i. i. N.:" + str(self.op.ColorTblIn2.value[t, x, y, z, 0])
        rgbaValidationString = "rgba l.:{};{};{};{}".format(*[str(slot.value[t, x, y, z, 0]) for slot in self.op.RgbaIn])
        emptyRgbaValidationString = "empty r. l.:0;0;0;255"
        alphaModValidationString = "alpha m. l.:" + str(self.op.AlphaModulatedIn.value[t, x, y, z, 0])

        with self.qtbot.waitSignal(signal, timeout=1000):
            self.editor.navCtrl.changeSliceAbsolute(y, 1)
            self.editor.navCtrl.changeTime(t)

        self.editor.navCtrl.positionDataCursor(QPointF(x, z), 1)

        assert self.editorWidget.quadViewStatusBar.xSpinBox.value() == x
        assert self.editorWidget.quadViewStatusBar.ySpinBox.value() == y
        assert self.editorWidget.quadViewStatusBar.zSpinBox.value() == z
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.grayscaleLayer].text() == grayValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.segLayer1].text() == labelValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.segLayer2].text() == labelValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.colorTblLayer1].text() == colorTbl1ValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.colorTblLayer2].text() == colorTbl2ValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.rgbaLayer].text() == rgbaValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.emptyRgbaLayer].text() == emptyRgbaValidationString
        assert self.editorWidget.quadViewStatusBar.layerValueWidgets[
                   self.alphaModLayer].text() == alphaModValidationString


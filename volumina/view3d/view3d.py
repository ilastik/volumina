# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# Copyright 2011-2014, the ilastik developers

import volumina
if volumina.NO3D:
    # For testing purposes, it is sometimes convenient to intentionally disable this module.
    raise ImportError("Intentionally skipping import of view3d module due to volumina.NO3D")

from vtk import vtkRenderer, vtkConeSource, vtkPolyDataMapper, vtkActor, \
                    vtkImplicitPlaneWidget2, vtkImplicitPlaneRepresentation, \
                    vtkObject, vtkPNGReader, vtkImageActor, QVTKWidget2, \
                    vtkRenderWindow, vtkOrientationMarkerWidget, vtkAxesActor, \
                    vtkTransform, vtkPolyData, vtkPoints, vtkCellArray, \
                    vtkTubeFilter, vtkQImageToImageSource, vtkImageImport, \
                    vtkDiscreteMarchingCubes, vtkWindowedSincPolyDataFilter, \
                    vtkMaskFields, vtkGeometryFilter, vtkThreshold, vtkDataObject, \
                    vtkDataSetAttributes, vtkCutter, vtkPlane, vtkPropAssembly, \
                    vtkGenericOpenGLRenderWindow, QVTKWidget, vtkOBJExporter, \
                    vtkPropCollection, vtkAppendPolyData, vtkCellPicker

from PyQt4.QtGui import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, \
                        QSizePolicy, QSpacerItem, QIcon, QFileDialog, \
                        QToolButton, QApplication
from PyQt4.QtCore import pyqtSignal, SIGNAL, QEvent, QTimer
from PyQt4.QtGui import QMenu, QAction, QColor
import volumina.icons_rc

import qimage2ndarray

from numpy2vtk import toVtkImageData

#from GenerateModelsFromLabels_thread import *

import platform #to check whether we are running on a Mac
import copy
from functools import partial

from slicingPlanesWidget import SlicingPlanesWidget
from volumina.events import Event
from volumina.layer import ColortableLayer
from GenerateModelsFromLabels_thread import MeshExtractorDialog

import logging
logger = logging.getLogger(__name__)

def convertVTPtoOBJ(vtpFilename, objFilename):
    f = open(vtpFilename, 'r')
    lines = f.readlines()
    inPoints = False
    inPolygons = False

    numPoints = -1
    readPoints = 0

    with open(objFilename, 'w') as o:
        for l in lines:
            l = l.strip()
            if l == "":
                continue
            
            if inPoints:
                i=0
                outLine = ""
                for n in l.split(" "):
                    if i==0:
                        outLine = "v"
                    
                    i+=1
                    
                    outLine += " "+n
                    readPoints += 1
                    
                    if i==3:
                        o.write(outLine+"\n")
                        i=0
                
                if readPoints == numPoints:
                    inPoints = False
            
            elif inPolygons:
                indices = l[2:].split(" ")
                o.write("f ")
                o.write(str(int(indices[0])+1)+" ")
                o.write(str(int(indices[1])+1)+" ")
                o.write(str(int(indices[2])+1)+" ")
                o.write("\n")
            
            else:
                if l.startswith("POINTS"):
                    m = l.split(" ")
                    numPoints = 3*int(m[1])
                    inPoints = True
                    inPolygons = False
                elif l.startswith("POLYGONS"):
                    inPoints = False
                    inPolygons = True

#*******************************************************************************
# Q V T K O p e n G L W i d g e t                                              *
#*******************************************************************************

class QVTKOpenGLWidget(QVTKWidget2):
    wireframe = False
    
    def __init__(self, parent = None):
        QVTKWidget2.__init__(self, parent)
        
    def init(self):

        self.renderer = vtkRenderer()
        self.renderer.SetUseDepthPeeling(1); ####
        self.renderer.SetBackground(1,1,1)
        self.renderWindow = vtkGenericOpenGLRenderWindow()
        self.renderWindow.SetAlphaBitPlanes(True) ####
        self.renderWindow.AddRenderer(self.renderer)
        self.SetRenderWindow(self.renderWindow)
        
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        self.actors = vtkPropCollection()
        #self.picker = vtkCellPicker()
        #self.picker = vtkPointPicker()
        #self.picker.PickFromListOn()
        
    def registerObject(self, o):
        #print "add item to prop collection"
        self.actors.AddItem(o)
        #self.picker.AddPickList(o)
        
    def update(self):
        QVTKWidget2.update(self)
        
        #Refresh the content, works around a bug on OS X
        self.paintGL()
    
    def keyPressEvent(self, e):
        if e.key() == Qt.Key_W:
            self.actors.InitTraversal();
            for i in range(self.actors.GetNumberOfItems()):
                if self.wireframe:
                    "to surface"
                    self.actors.GetNextProp().GetProperty().SetRepresentationToSurface()
                else:
                    self.actors.GetNextProp().GetProperty().SetRepresentationToWireframe()
            self.wireframe = not self.wireframe
            self.update()
    
    def mousePressEvent(self, e):
        if e.type() == QEvent.MouseButtonDblClick:
            logger.debug( "double clicked" )
            #self.picker.SetTolerance(0.05)
            picker = vtkCellPicker()
            picker.SetTolerance(0.05)
            res = picker.Pick(e.pos().x(), e.pos().y(), 0, self.renderer)
            if res > 0:
                c = picker.GetPickPosition()
                logger.debug( " picked at coordinate = {}".format( c ) )
                self.emit(SIGNAL("objectPicked"), c[0:3])
        else:
            QVTKWidget2.mousePressEvent(self, e)

#*******************************************************************************
# O u t l i n e r                                                              *
#*******************************************************************************

class Outliner(vtkPropAssembly):
    def SetPickable(self, pickable):
        props = self.GetParts()
        props.InitTraversal();
        for i in range(props.GetNumberOfItems()):
            props.GetNextProp().SetPickable(pickable)
    
    def __init__(self, mesh):
        self.cutter = vtkCutter()
        self.cutter.SetCutFunction(vtkPlane())
        self.tubes = vtkTubeFilter()
        self.tubes.SetInputConnection(self.cutter.GetOutputPort())
        self.tubes.SetRadius(1)
        self.tubes.SetNumberOfSides(8)
        self.tubes.CappingOn()
        self.mapper = vtkPolyDataMapper()
        self.mapper.SetInputConnection(self.tubes.GetOutputPort())
        self.actor = vtkActor()
        self.actor.SetMapper(self.mapper)
        self.cutter.SetInput(mesh)
        self.AddPart(self.actor)
    
    def GetOutlineProperty(self):
        return self.actor.GetProperty()
        
    def SetPlane(self, plane):
        self.cutter.SetCutFunction(plane)
        self.cutter.Update()


#*******************************************************************************
# O v e r v i e w S c e n e                                                    *
#*******************************************************************************

class OverviewScene(QWidget):
    
    #emitted when slice changes
    #  int -- slice number
    #  int -- axis number
    changedSlice = pyqtSignal(int,int)

    def resizeEvent(self, event):
        QWidget.resizeEvent(self,event)
        self.qvtk.update() #needed on OS X
        
    def slicingCallback(self, obj, event):
        def maybeUpdateSlice(old):
            num = obj.coordinate[obj.lastChangedAxis]
            axis = obj.lastChangedAxis
            if old == (num, axis):
                self.changedSlice.emit(num, axis)
        
        #when dragging the slice, wait for some milliseconds
        #to see whether the user is dragging on before
        #sending a signal            
        num = obj.coordinate[obj.lastChangedAxis]
        axis = obj.lastChangedAxis
        QTimer.singleShot(50, partial(maybeUpdateSlice, (num, axis)))
    
    def ShowPlaneWidget(self, axis, show):
        self.planes.ShowPlane(axis, show)
        self.qvtk.update()
        
    def TogglePlaneWidgetX(self):
        self.planes.TogglePlaneWidget(0)
        self.qvtk.update()
    def TogglePlaneWidgetY(self):
        self.planes.TogglePlaneWidget(1)
        self.qvtk.update()
    def TogglePlaneWidgetZ(self):
        self.planes.TogglePlaneWidget(2)
        self.qvtk.update()
   
    @property
    def dataShape(self):
        return self._dataShape
    @dataShape.setter
    def dataShape(self, shape):
        if shape == self._dataShape:
            return

        
        self._dataShape = shape
        
        if self.planes:
            #self.qvtk.renderer.RemoveAllViewProps()
            self.planes.SetVisibility(False)
            self.planes.RemoveObserver(self.coordEventObserver)
            #self.planes.RemoveAllParts()
            self.qvtk.renderer.RemoveActor(self.planes)
            self.qvtk.renderer.RemoveActor(self.axes)
            #self.qvtk.renderer.RemoveViewProp(self.planes)
            del self.planes

        self.planes = SlicingPlanesWidget(shape, self.qvtk.GetInteractor())
        #self.planes.SetInteractor(self.qvtk.GetInteractor())
        
        self.coordEventObserver = self.planes.AddObserver("CoordinatesEvent", self.slicingCallback)
        self.planes.SetCoordinate([0,0,0])
        self.planes.SetPickable(False)
        
        ## Add RGB arrow axes
        if self.axes:
            self.qvtk.renderer.RemoveActor(self.axes)
            del self.axes
        self.axes = vtkAxesActor();
        self.axes.AxisLabelsOff()
        self.axes.SetTotalLength(0.5*shape[0], 0.5*shape[1], 0.5*shape[2])
        self.axes.SetShaftTypeToCylinder()
        self.qvtk.renderer.AddActor(self.axes)
        
        self.qvtk.renderer.AddActor(self.planes)
        self.qvtk.renderer.ResetCamera() 
        #for some reason, we have to do this afterwards!
        self.planes.togglePlanesOn()

    def __init__(self, parent=None):
        super(OverviewScene, self).__init__(parent)
        self.coordEventObserver = None
        self.colorTable = None
        self.anaglyph = False
        self.sceneItems = []
        self.cutter = 3*[None]
        self.objects = []
        self.planes = None
        self.axes = None
        self._dataShape = None
        
        layout = QVBoxLayout()
        layout.setMargin(0)
        layout.setSpacing(0)
        self.qvtk = QVTKOpenGLWidget()
        layout.addWidget(self.qvtk)
        self.setLayout(layout)
        self.qvtk.init()
        hbox = QHBoxLayout(None)
        hbox.setMargin(0)
        hbox.setSpacing(5)
        hbox.setContentsMargins(5,3,5,3)
        
        def delete_gl_widget():
            # This is called just before the app quits to avoid this error during shutdown:
            # QGLContext::makeCurrent: Cannot make invalid context current
            self.qvtk.setParent(None)
            del self.qvtk
        QApplication.instance().aboutToQuit.connect( delete_gl_widget )
        
        b1 = QToolButton()
        b1.setIcon(QIcon(':icons/icons/x-axis.png'))
        b1.setToolTip("Show x slicing plane")
        b1.setCheckable(True); b1.setChecked(True)
        
        b2 = QToolButton()
        b2.setIcon(QIcon(':icons/icons/y-axis.png'))
        b2.setToolTip("Show y slicing plane")
        b2.setCheckable(True); b2.setChecked(True)
        
        b3 = QToolButton()
        b3.setIcon(QIcon(':icons/icons/z-axis.png'))
        b3.setToolTip("Show z slicing plane")
        b3.setCheckable(True); b3.setChecked(True)
        
        bAnaglyph = QToolButton()
        bAnaglyph.setIcon(QIcon(':icons/icons/3d_glasses.png'))
        bAnaglyph.setToolTip("Show in anaglyph 3D")
        bAnaglyph.setCheckable(True); bAnaglyph.setChecked(False)
        
        self.bUndock = QToolButton()
        self.bUndock.setIcon(QIcon(":/icons/icons/arrow_up.png"))
        self.bUndock.setToolTip("Dock/undock this view")
       
        '''
        bCutter = QToolButton()
        bCutter.setIcon(QIcon(':icons/icons/edit-cut.png'))
        bCutter.setCheckable(True); bCutter.setChecked(False)
        self.bCutter = bCutter
        
        bExportMesh = QToolButton()
        bExportMesh.setIcon(QIcon(':icons/icons/document-save-as.png'))
        '''
        
        hbox.addWidget(b1)
        hbox.addWidget(b2)
        hbox.addWidget(b3)
        hbox.addWidget(bAnaglyph)
        hbox.addWidget(self.bUndock)
        #hbox.addWidget(bCutter)
        hbox.addStretch()
        #hbox.addWidget(bExportMesh)
        layout.addLayout(hbox)
        
        self.connect(b1, SIGNAL("clicked()"), self.TogglePlaneWidgetX)
        self.connect(b2, SIGNAL("clicked()"), self.TogglePlaneWidgetY)
        self.connect(b3, SIGNAL("clicked()"), self.TogglePlaneWidgetZ)
        self.connect(bAnaglyph, SIGNAL("clicked()"), self.ToggleAnaglyph3D)
        #self.connect(bExportMesh, SIGNAL("clicked()"), self.exportMesh)
        #bCutter.toggled.connect(self.useCutterToggled)
        self.connect(self.qvtk, SIGNAL("objectPicked"), self.__onObjectPicked)
        
        def layerContextMenu(layer, menu):
          self.layerContextMenu(layer,menu)

        Event.register("layerContextMenuRequested", layerContextMenu)

    def layerContextMenu(self, layer, menu):
        if isinstance( layer, ColortableLayer ):
            def show3D():
                data = layer._datasources[0].request((slice(0,1,None),
                                                      slice(None,None,None), slice(None,None,None),
                                                      slice(None,None,None),
                                                      slice(0,1,None))).wait()[0,:,:,:,0]
                self.SetColorTable(layer._colorTable)
                self.DisplayObjectMeshes(data)#, suppressLabels=(), smooth=True):

        show3dAction = QAction("Show in 3D Overview", menu)
        show3dAction.triggered.connect(show3D)
        menu.addAction(show3dAction)

    @property
    def useCutter(self):
        return False
        #return self.bCutter.isChecked()

    def useCutterToggled(self):
        self.__updateCutter()
        if self.useCutter:
            for i in range(3): self.qvtk.renderer.AddActor(self.cutter[i])
        else:
            for i in range(3): self.qvtk.renderer.RemoveActor(self.cutter[i])
        self.qvtk.update()
    
    def exportMesh(self):
        filename = QFileDialog.getSaveFileName(self,"Save Meshes As")
        
        self.qvtk.actors.InitTraversal();
        for i in range(self.qvtk.actors.GetNumberOfItems()):
            p = self.qvtk.actors.GetNextProp()
            if p.GetPickable() and self.qvtk.actors.IsItemPresent(p):
                vtpFilename = "%s%02d.vtp" % (filename, i)
                objFilename = "%s%02d.obj" % (filename, i)
                
                logger.info( "writing VTP file '%s'" % vtpFilename )
                d = p.GetMapper().GetInput()
                w = vtkPolyDataWriter()
                w.SetFileTypeToASCII()
                w.SetInput(d)
                w.SetFileName("%s%02d.vtp" % (filename, i))
                w.Write()
                
                logger.info( "converting to OBJ file '%s'" % objFilename )
                convertVTPtoOBJ(vtpFilename, objFilename)
                
                #renWin = vtkRenderWindow()
                #ren = vtkRenderer()
                #renWin.AddRenderer(ren)
                #ren.AddActor(p)
                #exporter = vtkOBJExporter()
                #exporter.SetInput(renWin)
                #exporter.SetFilePrefix("%s%02d" % (filename, i))
                #exporter.Update()
                

    def __onObjectPicked(self, coor):
        self.ChangeSlice( coor[0], 0)
        self.ChangeSlice( coor[1], 1)
        self.ChangeSlice( coor[2], 2)
        
    def __onLeftButtonReleased(self):
        logger.debug( "CLICK" )
    
    def ToggleAnaglyph3D(self):
        self.anaglyph = not self.anaglyph
        if self.anaglyph:
            logger.debug( 'setting stero mode ON' )
            self.qvtk.renderWindow.StereoRenderOn()
            self.qvtk.renderWindow.SetStereoTypeToAnaglyph()
        else:
            logger.debug( 'setting stero mode OFF' )
            self.qvtk.renderWindow.StereoRenderOff()
        self.qvtk.update()
    
    def __updateCutter(self):
        if(self.useCutter):
            #print "Update cutter"
            for i in range(3):
                if self.cutter[i]: self.cutter[i].SetPlane(self.planes.Plane(i))
        else:
            pass
            #print "Do NOT update cutter"
    
    def ChangeSlice(self, num, axis):
        c = copy.copy(self.planes.coordinate)
        c[axis] = num
        self.planes.SetCoordinate(c)

        # set the current point as the camera's focal point
        cam = self.qvtk.renderer.GetActiveCamera()
        cam.SetFocalPoint( *c ) #rotate around this point
        cam.Modified();

        self.__updateCutter()
        self.qvtk.update()
    
    def display(self, axis):
        self.qvtk.update()
            
    def redisplay(self):
        self.qvtk.update()
        
    def DisplayObjectMeshes(self, v, suppressLabels=(), smooth=True):
        logger.debug( "OverviewScene::DisplayObjectMeshes {}".format( suppressLabels ) )
        self.dlg = MeshExtractorDialog(self)
        self.dlg.finished.connect(self.onObjectMeshesComputed)
        self.dlg.show()
        self.dlg.run(v, suppressLabels, smooth)
    
    def SetColorTable(self, table):
        self.colorTable = table
    
    def onObjectMeshesComputed(self):
        self.dlg.accept()
        logger.debug( "*** Preparing 3D view ***" )
        
        #Clean up possible previous 3D displays
        for c in self.cutter:
            if c: self.qvtk.renderer.RemoveActor(c)
        for a in self.objects:
            self.qvtk.renderer.RemoveActor(a) 
        
        self.polygonAppender = vtkAppendPolyData()
        for g in self.dlg.extractor.meshes.values():
            self.polygonAppender.AddInput(g)
        
        self.cutter[0] = Outliner(self.polygonAppender.GetOutput())
        self.cutter[0].GetOutlineProperty().SetColor(1,0,0)
        self.cutter[1] = Outliner(self.polygonAppender.GetOutput())
        self.cutter[1].GetOutlineProperty().SetColor(0,1,0)
        self.cutter[2] = Outliner(self.polygonAppender.GetOutput())
        self.cutter[2].GetOutlineProperty().SetColor(0,0,1)
        for c in self.cutter:
            c.SetPickable(False)
        
        ## 1. Use a render window with alpha bits (as initial value is 0 (false)):
        #self.renderWindow.SetAlphaBitPlanes(True);
        ## 2. Force to not pick a framebuffer with a multisample buffer
        ## (as initial value is 8):
        #self.renderWindow.SetMultiSamples(0);
        ## 3. Choose to use depth peeling (if supported) (initial value is 0 (false)):
        #self.renderer.SetUseDepthPeeling(True);
        ## 4. Set depth peeling parameters
        ## - Set the maximum number of rendering passes (initial value is 4):
        #self.renderer.SetMaximumNumberOfPeels(100);
        ## - Set the occlusion ratio (initial value is 0.0, exact image):
        #self.renderer.SetOcclusionRatio(0.0);

        for i, g in self.dlg.extractor.meshes.items():
            logger.debug( " - showing object with label = {}".format(i) )
            mapper = vtkPolyDataMapper()
            mapper.SetInput(g)
            actor = vtkActor()
            actor.SetMapper(mapper)
            self.qvtk.registerObject(actor)
            self.objects.append(actor)
            if self.colorTable:
                c = self.colorTable[i]
                c = QColor.fromRgba(c)
                actor.GetProperty().SetColor(c.red()/255.0, c.green()/255.0, c.blue()/255.0)
            
            self.qvtk.renderer.AddActor(actor)
        
        self.qvtk.update()

#*******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
#*******************************************************************************

if __name__ == '__main__':
    import numpy
    
    def updateSlice(num, axis):
        o.ChangeSlice(num,axis)
    
    from PyQt4.QtGui import QApplication
    import sys, h5py

    app = QApplication(sys.argv)

    o = OverviewScene(None)
    o.dataShape = [100,100,100]
    o.changedSlice.connect(updateSlice)
    o.show()
    o.resize(600,600)
    
    #f=h5py.File("/home/thorben/phd/src/vtkqt-test/seg.h5")
    #seg=f['volume/data'][0,:,:,:,0]
    #f.close()
    
    seg = numpy.ones((120,120,120), dtype=numpy.uint8)
    seg[20:40,20:40,20:40] = 2
    seg[50:70,50:70,50:70] = 3
    seg[80:100,80:100,80:100] = 4
    seg[80:100,80:100,20:50] = 5
    
    colorTable = [QColor(255,0,0).rgba(), QColor(0,255,0).rgba(), QColor(255,255,0).rgba(), QColor(255,0,255).rgba(), QColor(0,0,255).rgba(), QColor(128,0,128).rgba()]
    o.SetColorTable(colorTable)
    
    QTimer.singleShot(0, partial(o.DisplayObjectMeshes, seg, suppressLabels=(1,)))
    app.exec_()
    

# [vtkusers] Depth peeling not used, but I can't see why.
# http://public.kitware.com/pipermail/vtkusers/2010-August/111040.html

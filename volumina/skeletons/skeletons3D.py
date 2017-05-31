from __future__ import print_function
from __future__ import division
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
# optional dependency; catch import error to not break nosetests
from builtins import object
from past.utils import old_div
try:
    import vtk
except ImportError:
    print("Warning: could not import optional dependency VTK")

from numpy import asarray as A
from volumina.skeletons.frustum import cut

class Skeletons3D(object):
    def __init__(self, skeletons, view3D):
        self._skeletons = skeletons
        self._view3D = view3D       
        
        self._node2view = dict()
        self._edge2view = dict()
       
    def _cubeBoundsFromNode(self, cube, node):
        cube.SetBounds(node.pos[0]-old_div(node.shape[0],2.0), node.pos[0]+old_div(node.shape[0],2.0), \
                       node.pos[1]-old_div(node.shape[1],2.0), node.pos[1]+old_div(node.shape[1],2.0), \
                       node.pos[2]-old_div(node.shape[2],2.0), node.pos[2]+old_div(node.shape[2],2.0))
        
    def update(self):
        for n in self._skeletons._nodes:
            if n not in self._node2view:
                cube = vtk.vtkCubeSource()
                cubeMapper = vtk.vtkPolyDataMapper()
                cubeMapper.SetInputConnection(cube.GetOutputPort())
                cubeActor = vtk.vtkActor()
                cubeActor.SetMapper(cubeMapper)
                #cubeActor.GetProperty().SetRepresentationToWireframe()
                #cubeActor.GetProperty().SetColor(*color)
                self._view3D.qvtk.renderer.AddActor(cubeActor)
                self._node2view[n] = (cube, cubeActor)
            
            cube, cubeActor = self._node2view[n]
            
            self._cubeBoundsFromNode(cube, n)
            if n.isSelected():
                cubeActor.GetProperty().SetColor(1,0,0)
            else:
                c = n.color()
                r,g,b = old_div(c.red(),255.0), old_div(c.green(),255.0), old_div(c.blue(),255.0)
                cubeActor.GetProperty().SetColor(r,g,b)

        for e in self._skeletons._edges:
            if e not in self._edge2view:

                c1 = self._node2view[e[0]][0]
                c2 = self._node2view[e[1]][0]
                p1 = e[0]
                p2 = e[1]
                source = vtk.vtkLineSource()
                source.SetPoint1(*p1.pos)
                source.SetPoint2(*p2.pos)
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputConnection(source.GetOutputPort())
                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                c = p1.color() #TODO
                r,g,b = old_div(c.red(),255.0), old_div(c.green(),255.0), old_div(c.blue(),255.0)
                actor.GetProperty().SetColor(r,g,b)
                self._view3D.qvtk.renderer.AddActor(actor)
                self._edge2view[e] = source
               
                '''
                pointsSource = vtk.vtkProgrammableSource()
                
                def makePoints():
                    c1 = self._node2view[e[0]][0]
                    c2 = self._node2view[e[1]][0]
                    l = A(c2.GetCenter()) - A(c1.GetCenter())
                    p1 = cut(c1, l)
                    p2 = cut(c2, l)
                    thePoints = p1+p2
        
                    points = vtk.vtkPoints()
                    assert len(thePoints) >= 8 
                    for pt in thePoints:
                        points.InsertNextPoint(*pt)
                    
                    pointsSource.GetPolyDataOutput().SetPoints(points)
                
                pointsSource.SetExecuteMethod(makePoints) 
                
                delaunay = vtk.vtkDelaunay3D()
                delaunay.SetInputConnection(pointsSource.GetOutputPort())
                delaunay.Update()
                
                surfaceFilter = vtk.vtkDataSetSurfaceFilter()
                surfaceFilter.SetInputConnection(delaunay.GetOutputPort()) 
                
                mapper = vtk.vtkPolyDataMapper()
                mapper.SetInputConnection(surfaceFilter.GetOutputPort())
                actor = vtk.vtkActor()
                actor.SetMapper(mapper)
                actor.GetProperty().SetColor((0,0,1))
                self._view3D.qvtk.renderer.AddActor(actor)
                
                self._edge2view[e] = pointsSource
                '''
           
            pointsSource = self._edge2view[e]
            pointsSource.Modified()
        
        self._view3D.qvtk.update()

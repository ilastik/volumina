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
#!/usr/bin/env python

# optional dependency; catch import error to not break nosetests
has_vtk = True
try:
    import vtk
except ImportError:
    print("Warning: could not import optional dependency VTK")
    has_vtk = False


from numpy import asarray as A

if has_vtk:
    ren = vtk.vtkRenderer()
    renWin = vtk.vtkRenderWindow()
    renWin.AddRenderer(ren)
    
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(renWin)
 
def convexHull(thePoints, color):
    points = vtk.vtkPoints()
    for pt in thePoints:
        points.InsertNextPoint(*pt)
    polydata = vtk.vtkPolyData()
    polydata.SetPoints(points)
    delaunay = vtk.vtkDelaunay3D()
    delaunay.SetInput(polydata)
    delaunay.Update()
    surfaceFilter = vtk.vtkDataSetSurfaceFilter()
    surfaceFilter.SetInputConnection(delaunay.GetOutputPort()) 
    surfaceFilter.Update()
    
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInput(surfaceFilter.GetOutput())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetOpacity(0.5)
    ren.AddActor(actor)
    
def addLine(pos1, pos2, color):
    source = vtk.vtkLineSource()
    source.SetPoint1(*pos1)
    source.SetPoint2(*pos2)
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInput(source.GetOutput())
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    ren.AddActor(actor)

def addSphere(pos, size, color):
    # create source
    source = vtk.vtkSphereSource()
    source.SetCenter(*pos)
    source.SetRadius(size)
     
    # mapper
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInput(source.GetOutput())
     
    # actor
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
     
    # assign actor to the renderer
    ren.AddActor(actor)

def addCube(bounds, color):
    cube = vtk.vtkCubeSource()
    cube.SetBounds(*bounds)
     
    # mapper
    cubeMapper = vtk.vtkPolyDataMapper()
    cubeMapper.SetInput(cube.GetOutput())
     
    # actor
    cubeActor = vtk.vtkActor()
    cubeActor.SetMapper(cubeMapper)
    cubeActor.GetProperty().SetRepresentationToWireframe()
    cubeActor.GetProperty().SetColor(*color)
    
    addSphere((bounds[0]+(bounds[1]-bounds[0])/2.0, \
               bounds[2]+(bounds[3]-bounds[2])/2.0, \
               bounds[4]+(bounds[5]-bounds[4])/2.0), \
              0.05, color)
     
    # assign actor to the renderer
    ren.AddActor(cubeActor)
    
    return cube

def cut(cube, normal):
    plane=vtk.vtkPlane()
    plane.SetOrigin(cube.GetCenter())
    plane.SetNormal(*normal)
     
    #create cutter
    cutter=vtk.vtkCutter()
    cutter.SetCutFunction(plane)
    cutter.SetInputConnection(cube.GetOutputPort())
    cutter.Update()
    cutterMapper=vtk.vtkPolyDataMapper()
    cutterMapper.SetInputConnection( cutter.GetOutputPort())
     
    #create plane actor
    planeActor=vtk.vtkActor()
    planeActor.GetProperty().SetColor(1.0,1,0)
    planeActor.GetProperty().SetLineWidth(2)
    planeActor.SetMapper(cutterMapper)
     
    #create renderers and add actors of plane and cube
    ren.AddActor(planeActor)
   
    ret = [] 
    points = cutter.GetOutput().GetPoints()
    for i in range(points.GetNumberOfPoints()):
        point = points.GetPoint(i)
        ret.append( point )
    return ret 

if __name__ == "__main__":
    b1 = (0,1,0,1,0,1)
    b2 = (0.3,1.7,1.25,2.25,2.75,4)   
    
    c1 = addCube(b1, (1,0,0))
    c2 = addCube(b2, (0,1,0))
    
    l = A(c2.GetCenter()) - A(c1.GetCenter())
    
    p1 = cut(c1, l)
    p2 = cut(c2, l)
    
    '''
    for q in p1:
        for p in p2:
            addLine(p,q, (1,1,1))
    '''
    
    pts = []
    for i in [0,1]:
        for j in [2,3]:
            for k in [4,5]: 
                #addLine((b1[i], b1[j], b1[k]), (b2[i], b2[j], b2[k]), (1,1,1))
                pts.append( (b1[i], b1[j], b1[k]) )
                pts.append( (b2[i], b2[j], b2[k]) )
                
    #addLine((b1[0], b1[2], b1[4]), (b2[0], b2[2], b2[4]), (1,1,1))
    #addLine((b1[1], b1[3], b1[5]), (b2[1], b2[3], b2[5]), (1,1,1))
    
    #convexHull(pts, (0,0,1))
    
    #convexHull(p1+p2, (0,1,1))
    
    from munkres import Munkres, print_matrix
    import numpy
    M = numpy.zeros((4,4))
    for i in range(4):
        for j in range(4):
            M[i,j] = numpy.linalg.norm(A(p1[i]) - A(p2[j]))
    munkres = Munkres()
    indexes = munkres.compute(M)
    for row, col in indexes:
        addLine( p1[row], p2[col], (1,1,0))
     
    # enable user interface interactor
    iren.Initialize()
    renWin.Render()
    iren.Start()
    

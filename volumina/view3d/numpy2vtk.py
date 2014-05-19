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
try:
    from vtk import vtkImageImport
except:
    print 'Vtk not found in numpy2vtk'
    vtkfound = 'false'

import numpy

def __numpyTypeToVtkType(dtype):
    #from vtkType.h
    if dtype == numpy.int8:
        #define VTK_CHAR            2
        return 2
    elif dtype == numpy.uint8:
        #define VTK_UNSIGNED_CHAR   3
        return 3
    elif dtype == numpy.int16:
        #define VTK_SHORT           4
        return 4
    elif dtype == numpy.uint16:
        #define VTK_UNSIGNED_SHORT  5
        return 5
    elif dtype == numpy.int32:
        #define VTK_INT             6
        return 6
    elif dtype == numpy.uint32:
        #define VTK_UNSIGNED_INT    7
        return 7
    elif dtype == numpy.float32:
        #define VTK_FLOAT          10
        return 10
    elif dtype == numpy.float64:
        #define VTK_DOUBLE         11
        return 11
    else:
        raise RuntimeError("type conversion from nummpy.dtype=%r not implemented..." % dtype)
    #define VTK_VOID            0
    #define VTK_BIT             1
    #define VTK_LONG            8
    #define VTK_UNSIGNED_LONG   9
    #define VTK_ID_TYPE        12
    #define VTK_SIGNED_CHAR    15


def toVtkImageData(a):    
    importer = vtkImageImport()

    #FIXME
    #In all cases I have seen, it is needed to reverse the shape here
    #Does that hold universally, and do we understand why?
    reverseShape = True
    
    importer.SetDataScalarType(__numpyTypeToVtkType(a.dtype))
    if reverseShape:
        importer.SetDataExtent(0,a.shape[2]-1,0,a.shape[1]-1,0,a.shape[0]-1)
        importer.SetWholeExtent(0,a.shape[2]-1,0,a.shape[1]-1,0,a.shape[0]-1)
    else:
        importer.SetDataExtent(0,a.shape[0]-1,0,a.shape[1]-1,0,a.shape[2]-1)
        importer.SetWholeExtent(0,a.shape[0]-1,0,a.shape[1]-1,0,a.shape[2]-1)
    importer.SetImportVoidPointer(a)
    importer.Update()
    return importer.GetOutput() 

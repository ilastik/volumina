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
from PyQt4.QtGui import QApplication
import vtk
import numpy
import colorsys
# http://www.scipy.org/Cookbook/vtkVolumeRendering
import threading

NOBJECTS = 256

def makeVolumeRenderingPipeline(in_volume):
    dataImporter = vtk.vtkImageImport()

    if in_volume.dtype == numpy.uint8:
        dataImporter.SetDataScalarTypeToUnsignedChar()
    elif in_volume.dtype == numpy.uint16:
        dataImporter.SetDataScalarTypeToUnsignedShort()
    elif in_volume.dtype == numpy.int32:
        dataImporter.SetDataScalarTypeToInt()
    elif in_volume.dtype == numpy.int16:
        dataImporter.SetDataScalarTypeToShort()
    else:
        raise RuntimeError("unknown data type %r of volume" % (in_volume.dtype,))

    dataImporter.SetImportVoidPointer(in_volume, len(in_volume))
    dataImporter.SetNumberOfScalarComponents(1)
    extent = [0, in_volume.shape[2]-1, 0, in_volume.shape[1]-1, 0, in_volume.shape[0]-1]
    dataImporter.SetDataExtent(*extent)
    dataImporter.SetWholeExtent(*extent)

    alphaChannelFunc = vtk.vtkPiecewiseFunction()
    alphaChannelFunc.AddPoint(0, 0.0)
    for i in range(1, NOBJECTS):
        alphaChannelFunc.AddPoint(i, 1.0)

    colorFunc = vtk.vtkColorTransferFunction()

    volumeMapper = vtk.vtkSmartVolumeMapper()
    volumeMapper.SetInputConnection(dataImporter.GetOutputPort())

    volumeProperty = vtk.vtkVolumeProperty()
    volumeProperty.SetColor(colorFunc)
    volumeProperty.SetScalarOpacity(alphaChannelFunc)
    volumeProperty.ShadeOn()

    volume = vtk.vtkVolume()
    volume.SetMapper(volumeMapper)
    volume.SetProperty(volumeProperty)
    return dataImporter, colorFunc, volume, volumeMapper


class LabelManager(object):
    def __init__(self, n):
        self._available = set(range(1, n))
        self._used = set([])
        self._n = n

    def request(self):
        if len(self._available) == 0:
            raise RuntimeError('out of labels')
        label = min(self._available)
        self._available.remove(label)
        self._used.add(label)
        return label

    def free(self, label=None):
        if label is None:
            self._used = set([])
            self._available = set(range(1, self._n))
        elif label in self._used:
            self._used.remove(label)
            self._available.add(label)

class RenderingManager(object):
    """Encapsulates the work of adding/removing objects to the
    rendered volume and setting their colors.

    Conceptually very simple: given a volume containing integer labels
    (where zero labels represent transparent background) and a color
    map, renders the objects in the appropriate color.

    """
    def __init__(self, overview_scene):
        self._overview_scene = overview_scene
        self.labelmgr = LabelManager(NOBJECTS)
        self.ready = False
        self._cmap = {}
        self._dirty = False

        def _handle_scene_init():
            self.setup( self._overview_scene.dataShape )
            self.update()
        self._overview_scene.reinitialized.connect( _handle_scene_init )
        
    def setup(self, shape):
        shape = shape[::-1]
        self._volume = numpy.zeros(shape, dtype=numpy.uint8)
        #dataImporter, colorFunc, volume, volumeMapper = makeVolumeRenderingPipeline(self._volume)
        #self._overview_scene.set_volume(self._volume)
        #self._mapper = volumeMapper
        #self._volumeRendering = volume
        #self._dataImporter = dataImporter
        #self._colorFunc = colorFunc
        self.ready = True

    def update(self):
        assert threading.current_thread().name == 'MainThread', \
            "RenderingManager.update() must be called from the main thread to avoid segfaults."
        #for label, color in self._cmap.iteritems():
        #    self._colorFunc.AddRGBPoint(label, *color)
        #self._dataImporter.Modified()
        #self._volumeRendering.Update()
        if self._dirty:
            self._overview_scene.set_volume(self._volume)
            self._dirty = False

    def setColor(self, label, color):
        self._cmap[label] = color

    @property
    def volume(self):
        # We store the volume in reverse-transposed form, so un-transpose it when it is accessed.
        return numpy.transpose(self._volume)
    count = 0
    @volume.setter
    def volume(self, value):
        # Must copy here because a reference to self._volume was stored in the pipeline (see setup())
        # store in reversed-transpose order to match the wireframe axes
        new_volume = numpy.transpose(value)
        if numpy.any(new_volume != self._volume):
            self._volume[:] = new_volume
            self._dirty = True
            numpy.save(open("/home/nbuwen/numpy/volume_{}.npy".format(self.count), "w"), new_volume)
            self.count += 1

    def addObject(self, color=None):
        label = self.labelmgr.request()
        if color is None:
            color = colorsys.hsv_to_rgb(numpy.random.random(), 1.0, 1.0)
        self.setColor(label, color)
        return label

    def removeObject(self, label):
        self.labelmgr.free(label)

    def clear(self, ):
        self._volume[:] = 0
        self.labelmgr.free()

if __name__ == "__main__":

    # With almost everything else ready, its time to initialize the
    # renderer and window, as well as creating a method for exiting
    # the application
    renderer = vtk.vtkRenderer()
    renderWin = vtk.vtkRenderWindow()
    renderWin.AddRenderer(renderer)
    renderInteractor = vtk.vtkRenderWindowInteractor()
    renderInteractor.SetRenderWindow(renderWin)
    renderer.SetBackground(1, 1, 1) # white background
    renderWin.SetSize(400, 400)

    # A simple function to be called when the user decides to quit the
    # application.
    def exitCheck(obj, event):
        if obj.GetEventPending() != 0:
            obj.SetAbortRender(1)

    # Tell the application to use the function as an exit check.
    renderWin.AddObserver("AbortCheckEvent", exitCheck)

    # create the rendering manager
    mgr = RenderingManager(renderer)
    mgr.setup((256, 256, 256))

    # add some  squares
    for x in (10, 200):
        for y in (10, 200):
            for z in (10, 200):
                label = mgr.addObject()
                mgr.volume[x:x+50, y:y+50, z:z+50] = label
    mgr.update()

    renderInteractor.Initialize()

    # Because nothing will be rendered without any input, we order the
    # first render manually before control is handed over to the
    # main-loop.
    renderWin.Render()

    renderInteractor.Start()

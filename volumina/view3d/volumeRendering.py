import vtk
import h5py
import numpy
import colorsys
# http://www.scipy.org/Cookbook/vtkVolumeRendering

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

    return dataImporter, colorFunc, volume


class LabelManager(object):
    def __init__(self, n):
        self._available = set(range(1, n))
        self._used = set([])

    def request(self):
        if len(self._available) == 0:
            raise RuntimeError('out of labels')
        label = min(self._available)
        self._available.remove(label)
        self._used.add(label)
        return label

    def free(self, label):
        if label in self._used:
            self._used.remove(label)
            self._available.add(label)


class RenderingManager(object):
    """Encapsulates the work of adding/removing objects to the
    rendered volume and setting their colors.

    Conceptually very simple: given a volume containing integer labels
    (where zero labels represent transparent background) and a color
    map, renders the objects in the appropriate color.

    """
    def __init__(self, renderer, qvtk=None):
        self._renderer = renderer
        self._qvtk = qvtk
        self.labelmgr = LabelManager(NOBJECTS)
        self.ready = False
        self._cmap = {}

    def setup(self, shape):
        shape = shape[::-1]
        self._volume = numpy.zeros(shape, dtype=numpy.uint8)
        dataImporter, colorFunc, volume = makeVolumeRenderingPipeline(self._volume)
        self._renderer.AddVolume(volume)
        self._volumeRendering = volume
        self._dataImporter = dataImporter
        self._colorFunc = colorFunc
        self.ready = True

    def update(self):
        for label, color in self._cmap.iteritems():
            self._colorFunc.AddRGBPoint(label, *color)
        self._dataImporter.Modified()
        self._volumeRendering.Update()
        if self._qvtk is not None:
            self._qvtk.update()

    def setColor(self, label, color):
        self._cmap[label] = color

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, value):
        # transpose to match the wireframe axes
        self.volume[:] = numpy.transpose(value, range(value.ndim)[::-1])

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

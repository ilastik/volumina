import vtk
import h5py
import numpy
import colorsys
# http://www.scipy.org/Cookbook/vtkVolumeRendering

def makeVolumeRenderingPipeline(seg):
    dataImporter = vtk.vtkImageImport()
    
    if seg.dtype == numpy.uint8:
        dataImporter.SetDataScalarTypeToUnsignedChar()
    elif seg.dtype == numpy.uint16:
        dataImporter.SetDataScalarTypeToUnsignedShort()
    elif seg.dtype == numpy.int32:
        dataImporter.SetDataScalarTypeToInt()
    elif seg.dtype == numpy.int16:
        dataImporter.SetDataScalarTypeToShort()
    else:
        raise RuntimeError("unknown data type %r of segmentation volume" % (seg.dtype,))
    
    dataImporter.SetImportVoidPointer(seg, len(seg))
    dataImporter.SetNumberOfScalarComponents(1)
    extent = [0, seg.shape[0]-1, 0, seg.shape[1]-1, 0, seg.shape[2]-1]
    dataImporter.SetDataExtent(*extent)
    dataImporter.SetWholeExtent(*extent)

    # The following class is used to store transparency-values for later retrieval. In our case, we want the value 0 to be
    # completely opaque whereas the three different cubes are given different transparency-values to show how it works.
    alphaChannelFunc = vtk.vtkPiecewiseFunction()
    alphaChannelFunc.AddPoint(0, 0.0)
    for i in range(1, 256):
        alphaChannelFunc.AddPoint(i, 1.0)

    # This class stores color data and can create color tables from a few color points. For this demo, we want the three cubes
    # to be of the colors red green and blue.
    
    colorFunc = vtk.vtkColorTransferFunction()
    '''
    for i in range(1, maxLabel+1):
        rgb = colorsys.hsv_to_rgb(numpy.random.random(), 1.0, 1.0)
        colorFunc.AddRGBPoint(i, *rgb)
    '''

    # The previous two classes stored properties. Because we want to apply these properties to the volume we want to render,
    # we have to store them in a class that stores volume properties.
    
    volumeProperty = vtk.vtkVolumeProperty()
    volumeProperty.SetColor(colorFunc)
    volumeProperty.SetScalarOpacity(alphaChannelFunc)
    
    smart = True
    if not smart:
        #volumeProperty.ShadeOn()
        
        # This class describes how the volume is rendered (through ray tracing).
        compositeFunction = vtk.vtkVolumeRayCastCompositeFunction()
        # We can finally create our volume. We also have to specify the data for it, as well as how the data will be rendered.
        volumeMapper = vtk.vtkVolumeRayCastMapper()
        volumeMapper.SetVolumeRayCastFunction(compositeFunction)
        volumeMapper.SetInputConnection(dataImporter.GetOutputPort())
    else:
        volumeMapper = vtk.vtkSmartVolumeMapper()
        #volumeMapper.SetRequestedRenderMode(vtk.vtkSmartVolumeMapper.GPURenderMode)
        volumeMapper.SetInputConnection(dataImporter.GetOutputPort())
        volumeProperty.ShadeOff()
       
        #volumeProperty.ShadeOn()
        #volumeProperty.SetInterpolationType(vtk.VTK_LINEAR_INTERPOLATION)
        volumeProperty.SetInterpolationType(vtk.VTK_NEAREST_INTERPOLATION)
    
    # The class vtkVolume is used to pair the previously declared volume as well as the properties to be used when rendering that volume.
    volume = vtk.vtkVolume()
    volume.SetMapper(volumeMapper)
    volume.SetProperty(volumeProperty)
    
    return dataImporter, colorFunc, volume
    
if __name__ == "__main__": 
    #load file
    segF = h5py.File("/home/tkroeger/phd/src/mpi_denk2/mpi20121020-20nm/kai-carving/carve_result.h5")
    seg = segF["gt"].value
    maxLabel = seg.max()
    
    use_uint8 = True
    if use_uint8:
        assert maxLabel < 256
        seg = seg.astype(numpy.uint8)
    else:
        assert maxLabel < 2**16
        seg = seg.astype(numpy.uint16)
        
    segF.close()
    
    volume = makeVolumeRenderingPipeline(seg)
    
    # With almost everything else ready, its time to initialize the renderer and window, as well as creating a method for exiting the application
    renderer = vtk.vtkRenderer()
    renderWin = vtk.vtkRenderWindow()
    renderWin.AddRenderer(renderer)
    renderInteractor = vtk.vtkRenderWindowInteractor()
    renderInteractor.SetRenderWindow(renderWin)
    
    # We add the volume to the renderer ...
    renderer.AddVolume(volume)
    # ... set background color to white ...
    renderer.SetBackground(1, 1, 1)
    # ... and set window size.
    renderWin.SetSize(400, 400)
    
    # A simple function to be called when the user decides to quit the application.
    def exitCheck(obj, event):
        if obj.GetEventPending() != 0:
            obj.SetAbortRender(1)
    
    # Tell the application to use the function as an exit check.
    renderWin.AddObserver("AbortCheckEvent", exitCheck)
    
    renderInteractor.Initialize()
    # Because nothing will be rendered without any input, we order the first render manually before control is handed over to the main-loop.
    renderWin.Render()
    renderInteractor.Start()

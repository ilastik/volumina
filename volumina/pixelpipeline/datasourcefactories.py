import copy
from volumina.multimethods import multimethod
from imagesources import GrayscaleImageSource, ColortableImageSource, \
                         RGBAImageSource, AlphaModulatedImageSource
from datasources import ConstantSource,ArraySource,LazyflowSource
import numpy
from vigra import VigraArray
import lazyflow

@multimethod(lazyflow.graph.OutputSlot,bool)
def createDataSource(source,withShape = False):
    #has to handle Lazyflow source
    src = LazyflowSource(source)
    shape = src._outslot.shape
    if withShape:
        return src,shape
    else:
        return src

@multimethod(lazyflow.graph.OutputSlot)
def createDataSource(source):
    return createDataSource(source,False)

@multimethod(numpy.ndarray,bool)
def createDataSource(source,withShape = False):
    #has to handle NumpyArray
    #check if the array is 5d, if not so embed it in a canonical way
    if len(source.shape) == 2:
        tmp = numpy.ndarray((1,source.shape[0],source.shape[1],1,1))
        tmp[0,:,:,0,0] = source
        source = tmp
    elif len(source.shape) == 3 and source.shape[2] <= 4:
        tmp = numpy.ndarray((1,source.shape[0],source.shape[1],source.shape[2],1))
        tmp[0,:,:,0,:] = source
        source = tmp
    elif len(source.shape) == 3:
        tmp = numpy.ndarray((1,source.shape[0],source.shape[1],source.shape[2],1))
        tmp[0,:,:,:,0] = source
        source = tmp
    elif len(source.shape) == 4:
        tmp = numpy.ndarray((1,source.shape[0],source.shape[1],source.shape[2],source.shape[3]))
        tmp[0,:,:,:,:] = source
        source = tmp
    src = ArraySource(source)
    if withShape:
        return src,source.shape
    else:
        return src

@multimethod(numpy.ndarray)
def createDataSource(source):
    return createDataSource(source,False)

@multimethod(VigraArray,bool)
def createDataSource(source,withShape):
    #has to handle VigraArray
    source = source.withAxes('t','x','y','z','c')
    src = ArraySource(source)
    if withShape:
        return src,source.shape
    else:
        return src
    
@multimethod(VigraArray)
def createDataSource(source):
    return createDataSource(source,False)
import copy
from volumina.multimethods import multimethod
from imagesources import GrayscaleImageSource, ColortableImageSource, \
                         RGBAImageSource, AlphaModulatedImageSource
from datasources import ConstantSource,ArraySource,LazyflowSource
import numpy

hasLazyflow = True
try:
    import lazyflow
except:
    hasLazyflow = False

if hasLazyflow:
    def _createDataSourceLazyflow( slot, withShape ):
        #has to handle Lazyflow source
        src = LazyflowSource(slot)
        shape = src._op5.output.meta.shape
        if withShape:
            return src,shape
        else:
            return src

    @multimethod(lazyflow.graph.OutputSlot,bool)
    def createDataSource(source,withShape = False):
        return _createDataSourceLazyflow( source, withShape )

    @multimethod(lazyflow.graph.InputSlot,bool)
    def createDataSource(source,withShape = False):
        return _createDataSourceLazyflow( source, withShape )
    
    @multimethod(lazyflow.graph.OutputSlot)
    def createDataSource(source):
        return _createDataSourceLazyflow( source, False )

    @multimethod(lazyflow.graph.InputSlot)
    def createDataSource(source):
        return _createDataSourceLazyflow( source, False )

@multimethod(numpy.ndarray,bool)
def createDataSource(source,withShape = False):
    #has to handle NumpyArray
    #check if the array is 5d, if not so embed it in a canonical way
    if len(source.shape) == 2:
        source = source.reshape( (1,) + source.shape + (1,1) )
    elif len(source.shape) == 3 and source.shape[2] <= 4:
        source = source.reshape( (1,) + source.shape[0:2] + (1,) + source.shape[2] )
    elif len(source.shape) == 3:
        source = source.reshape( (1,) + source.shape + (1,) )
    elif len(source.shape) == 4:
        source = source.reshape( (1,) + source.shape )
    src = ArraySource(source)
    if withShape:
        return src,source.shape
    else:
        return src

@multimethod(numpy.ndarray)
def createDataSource(source):
    return createDataSource(source,False)

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
# 		   http://ilastik.org/license/
###############################################################################
from functools import singledispatch

import numpy

from .arraysource import ArraySource
from .cachesource import CacheSource

hasLazyflow = True
try:
    import lazyflow
    from .lazyflowsource import LazyflowSource
except ImportError:
    hasLazyflow = False

try:
    import h5py

    hasH5py = True
except ImportError:
    hasH5py = False

try:
    import vigra

    hasVigra = True
except ImportError:
    hasVigra = False


@singledispatch
def createDataSource(source, withShape=False):
    """
    Creates datasource based on type of supplied argument
    Resulting souce will have following dimensions: txyzc
    """
    raise NotImplementedError(f"createDataSource for {type(source)}")


def normalize_shape(shape):
    """
    :returns: Normalized shape and position of real axes to "txyzc" axes order
    """
    # xy
    if len(shape) == 2:
        return (1, shape[0], shape[1], 1, 1), (1, 2)

    # xyc shape[2] <= 4 implies that it's a channel dimension
    elif len(shape) == 3 and shape[2] <= 4:
        return (1, shape[0], shape[1], 1, shape[2]), (1, 2, 4)

    # xyz
    elif len(shape) == 3:
        return (1, shape[0], shape[1], shape[2], 1), (1, 2, 3)

    # xyzc
    elif len(shape) == 4:
        return (1, shape[0], shape[1], shape[2], shape[3]), (1, 2, 3, 4)

    # txyzc
    elif len(shape) == 5:
        return shape, (0, 1, 2, 3, 4)

    raise ValueError("Can process only shapes with ndims <= 5")


def _createArrayDataSource(source, withShape=False):
    # has to handle NumpyArray
    # check if the array is 5d, if not so embed it in a canonical way
    new_shp, _ = normalize_shape(source.shape)
    if new_shp != source.shape:
        source = source.reshape(new_shp)

    src = ArraySource(source)
    if withShape:
        return src, source.shape
    else:
        return src


@createDataSource.register(numpy.ndarray)
def _numpy_ds(source, withShape=False):
    return _createArrayDataSource(source, withShape)


if hasLazyflow:

    def _createDataSourceLazyflow(slot, withShape):
        # has to handle Lazyflow source
        src = LazyflowSource(slot)
        shape = src._op5.Output.meta.shape
        if withShape:
            return src, shape
        else:
            return src

    @createDataSource.register(lazyflow.graph.OutputSlot)
    def _lazyflow_out(slot, withShape=False):
        if withShape:
            src, shape = _createDataSourceLazyflow(slot, withShape)
            return CacheSource(src), shape
        else:
            src = _createDataSourceLazyflow(slot, withShape)
            return CacheSource(src)

    @createDataSource.register(lazyflow.graph.InputSlot)
    def _lazyflow_in(source, withShape=False):
        return _createDataSourceLazyflow(source, withShape)


if hasH5py:

    class H5pyDset5DWrapper(object):
        def __init__(self, dset):
            self.shape, self.real_axes = normalize_shape(dset.shape)
            self.dset = dset
            self.dtype = dset.dtype

        def __getitem__(self, slicing_5d):
            real_slicing = tuple(slicing_5d[i] for i in self.real_axes)
            data = self.dset[real_slicing]
            expanded_slicing = [None] * 5
            for axis in self.real_axes:
                expanded_slicing[axis] = slice(None)
            return data[expanded_slicing]

    @createDataSource.register(h5py.Dataset)
    def _h5py_ds(dset, withShape=False):
        dset_5d = H5pyDset5DWrapper(dset)
        src = ArraySource(dset_5d)
        if withShape:
            return src, dset_5d.shape
        else:
            return src


if hasVigra:

    @createDataSource.register(vigra.VigraArray)
    def _vigra_ds(source, withShape=False):
        source = source.withAxes(*"txyzc").view(numpy.ndarray)
        return _createArrayDataSource(source, withShape)

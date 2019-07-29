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

import contextlib
import functools
from typing import Sequence, Tuple, TypeVar, Union

import numpy

from volumina.pixelpipeline import datasources

_T = TypeVar("_T")


def _to_shape5d(
    shape: Sequence[int], fillval: _T = 1
) -> Tuple[Union[int, _T], Union[int, _T], Union[int, _T], Union[int, _T], Union[int, _T]]:
    """Make a 5D shape out of an ND shape.

    Examples:

        >>> _to_shape5d([5, 6])
        (1, 5, 6, 1, 1)
        >>> _to_shape5d([5, 6, 7])
        (1, 5, 6, 7, 1)
        >>> _to_shape5d([5, 6, 7, 8])
        (1, 5, 6, 7, 8)
        >>> _to_shape5d([5, 6, 7, 8, 9])
        (5, 6, 7, 8, 9)

        Custom fill value::

            >>> _to_shape5d([5, 6, 7], fillval=None)
            (None, 5, 6, 7, None)

        Only shapes with lengths from 2 to 5 are supported::

            >>> _to_shape5d([5])  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
              ...
            ValueError
            >>> _to_shape5d([5, 6, 7, 8, 9, 42])  # doctest: +IGNORE_EXCEPTION_DETAIL
            Traceback (most recent call last):
              ...
            ValueError

        Special case for 3D shapes with the small last dimension ``shape[2] <= 4``::

            >>> _to_shape5d([5, 6, 4])
            (1, 5, 6, 1, 4)
    """
    n = len(shape)

    if n == 2:
        return fillval, shape[0], shape[1], fillval, fillval
    if n == 3 and shape[2] <= 4:
        return fillval, shape[0], shape[1], fillval, shape[2]
    if n == 3:
        return fillval, shape[0], shape[1], shape[2], fillval
    if n == 4:
        return fillval, shape[0], shape[1], shape[2], shape[3]
    if n == 5:
        return shape[0], shape[1], shape[2], shape[3], shape[4]

    raise ValueError(f"invalid dimension count {n} for shape {shape}")


class _DatasetWrapper5D:
    def __init__(self, dset):
        self._dset = dset
        self.dtype = dset.dtype
        self.shape = _to_shape5d(dset.shape)

    def __getitem__(self, slicing_5d):
        assert len(slicing_5d) == 5

        # Index HDF5 dataset first to get an ndarray, then expand that array to 5D.

        h5_idx = []
        np_idx = []

        for idx, dim in zip(slicing_5d, _to_shape5d(self._dset.shape, fillval=None)):
            if dim is None:
                np_idx.append(numpy.newaxis)
            else:
                np_idx.append(slice(None))
                h5_idx.append(idx)

        return self._dset[tuple(h5_idx)][tuple(np_idx)]


@functools.singledispatch
def createDataSource(source, _withShape=False):
    raise TypeError(f"'createDataSource' not supported for 'source' instance of {source.__class__.__name__!r}")


with contextlib.suppress(ImportError):
    import lazyflow

    @createDataSource.register
    def _(slot: lazyflow.graph.Slot, withShape=False):
        src = datasources.LazyflowSource(slot)
        if withShape:
            return src, src._op5.Output.meta.shape
        else:
            return src


@createDataSource.register
def _(source: numpy.ndarray, withShape=False):
    source = source.reshape(_to_shape5d(source.shape))
    array_source = datasources.ArraySource(source)
    if withShape:
        return array_source, source.shape
    else:
        return array_source


with contextlib.suppress(ImportError):
    import vigra

    @createDataSource.register
    def _(source: vigra.VigraArray, withShape=False):
        source = source.withAxes(*"txyzc").view(numpy.ndarray)
        createDataSource.registry[numpy.ndarray](source, withShape)


with contextlib.suppress(ImportError):
    import h5py

    @createDataSource.register
    def _(dset: h5py.Dataset, withShape=False):
        dset_5d = _DatasetWrapper5D(dset)
        src = datasources.ArraySource(dset_5d)
        if withShape:
            return src, dset_5d.shape
        else:
            return src

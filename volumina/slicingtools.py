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
"""Provide tools to work with collections of slice instances.

A n-dimensional slicing is a sequence of n slice objects, for example:
slicing = [slice(10,23), slice(None), slice(14,None)]

The sequence has to support __iter__, __setitem__, and __getitem__,
as the common Python sequence types tuple and list do.

Additionally, a 1-dimensional slicing may consist of a single slice instance
not wrapped in a sequence.

"""
from builtins import range
import numpy as np
from qtpy.QtCore import QRect
import itertools


# *******************************************************************************
# S l                                                                          *
# *******************************************************************************


class Sl(object):
    """Helper to create slicings using nice subsprict syntax.

    sl = Sl()
    slicing = sl[1:2,:]

    """

    def __getitem__(self, slicing):
        return slicing


sl = Sl()


def box(sl, seq=tuple):
    """Wraps a single slice with a sequence.

    No effect on any other object.

    """
    if isinstance(sl, slice):
        return seq((sl,))
    else:
        return sl


def unbox(slicing, axis=0):
    """Extracts a slice object from a sequence of slices.

    No effect in any other case.

    """
    if hasattr(slicing, "__iter__"):
        if len(slicing) > axis and isinstance(slicing[axis], slice):
            return slicing[axis]
    return slicing


def is_bounded(slicing):
    """For all dimensions: stop value of slice is not None"""
    slicing = box(slicing)
    return all((sl.stop != None for sl in slicing))


def make_bounded(slicing, shape):
    """Convert unbounded slices to the size of the corresponding
    dimension.

    >>> make_bounded((slice(0, 1), slice(None)), shape=(10, 10, 10))
    (slice(0, 1), slice(0, 10), slice(0, 10))

    """
    assert len(slicing) <= len(shape)
    slicing = index2slice(slicing)
    result = []
    for slc, dim in itertools.zip_longest(slicing, shape):
        if slc is None:
            slc = slice(None)
        start, stop, step = slc.start, slc.stop, slc.step
        if start is None:
            start = 0
        if stop is None:
            stop = dim
        result.append(slice(start, stop, step))
    return tuple(result)


def is_pure_slicing(slicing):
    """Test if slicing is a single slice instance or sequence of instances.

    Impure slicings may additionally contain integer indices,
    ellipses, booleans, or newaxis.
    """
    slicing = box(slicing)
    if not hasattr(slicing, "__iter__"):
        return False
    for thing in slicing:
        if not isinstance(thing, slice):
            return False
    return True


def slicing2rect(slicing):
    h, v = slicing
    return QRect(h.start, v.start, h.stop - h.start, v.stop - v.start)


def rect2slicing(qrect, seq=tuple):
    result = seq((slice(qrect.x(), qrect.x() + qrect.width()), slice(qrect.y(), qrect.y() + qrect.height())))
    return result


def slicing2shape(slicing):
    assert is_bounded(slicing)
    slicing = box(slicing)
    shape = []
    for sl in slicing:
        shape.append(sl.stop - sl.start)
    return tuple(shape)


def index2slice(slicing):
    """Convert integer indices to proper slice instances.

    For example: (2, slice(4,8)) => (slice(2,3), slice(4,8))

    """
    pure_sl = list(slicing)
    for i in range(len(pure_sl)):
        if isinstance(pure_sl[i], int):
            index = pure_sl[i]
            pure_sl[i] = slice(index, index + 1)
    return tuple(pure_sl)


def intersection(lhs, rhs):
    """Calculate intersection between two slicings of same dimensions.

    Intersection is represented as a slicing, too.
    Returns None if the intersection is empty.

    """
    assert len(lhs) == len(rhs), "%d <-> %d" % (len(lhs), len(rhs))
    assert is_pure_slicing(lhs) and is_pure_slicing(rhs)

    def _min_stop(stop1, stop2):
        if stop1 is None:
            return stop2
        if stop2 is None:
            return stop1
        return min(stop1, stop2)

    dim = len(lhs)
    inter = [None] * dim
    for d in range(dim):
        if lhs[d].start is None:
            start = rhs[d].start
        elif rhs[d].start is None:
            start = lhs[d].start
        else:
            start = max(lhs[d].start, rhs[d].start)

        stop = _min_stop(lhs[d].stop, rhs[d].stop)

        if start and stop:
            if (stop - start) <= 0:
                return None
        inter[d] = slice(start, stop)
    return tuple(inter)


# *******************************************************************************
# S l i c e P r o j e c t i o n                                                *
# *******************************************************************************


class SliceProjection(object):
    @property
    def abscissa(self):
        return self._abscissa

    @property
    def ordinate(self):
        return self._ordinate

    @property
    def along(self):
        return self._along

    @property
    def domainDim(self):
        return self._dim

    def __init__(self, abscissa=1, ordinate=2, along=[0, 3, 4]):
        assert hasattr(along, "__iter__")

        self._abscissa = abscissa
        self._ordinate = ordinate
        self._along = along
        self._dim = len(self.along) + 2

        # sanity checks
        axes_set = set(along)
        axes_set.add(abscissa)
        axes_set.add(ordinate)
        if len(axes_set) != self._dim:
            raise ValueError("duplicate axes")
        if axes_set != set(range(self._dim)):
            raise ValueError("axes not from range(0,dim)")

    def handednessSwitched(self):
        if self.ordinate < self.abscissa:
            return True
        return False

    def domain(self, through, abscissa_range=slice(None, None), ordinate_range=slice(None, None)):
        """Slicing describing the embedding of the 2d slice in the n-dim domain space.

        Use this slicing to cut out a n-dim subspace containing the desired slice.

        """
        assert len(through) == len(self.along)
        slicing = list(range(self.domainDim))
        slicing[self.abscissa] = abscissa_range
        slicing[self.ordinate] = ordinate_range
        for i in range(len(self.along)):
            # @param through contains np.int64 types which some iterator based classes don't accept in slices.
            slicing[self.along[i]] = slice(int(through[i]), int(through[i] + 1))

        return tuple(slicing)

    def __call__(self, domainArray):
        """Projects the n-d slicing 'domainArray' to 2 dimensions"""

        assert domainArray.ndim == self.domainDim, "ndim %d != %d (domainArray.shape=%r, domainDim=%r)" % (
            domainArray.ndim,
            self.domainDim,
            domainArray.shape,
            self.domainDim,
        )
        slicing = self.domainDim * [0]
        slicing[self._abscissa], slicing[self._ordinate] = slice(None, None), slice(None, None)

        projectedArray = domainArray[tuple(slicing)]
        assert projectedArray.ndim == 2, "dim %d != 2" % projectedArray.ndim
        if self.handednessSwitched():
            projectedArray = np.swapaxes(projectedArray, 0, 1)
        return projectedArray


# *******************************************************************************
# T e s t                                                                      *
# *******************************************************************************

import unittest as ut


class SlTest(ut.TestCase):
    def runTest(self):
        self.assertEqual(sl[1, :34, :], (1, slice(34), slice(None)))


class toolsTest(ut.TestCase):
    def testIntersection(self):
        i = intersection(sl[5:8, 3:7, 2:9], sl[0:50, 0:50, 4:5])
        self.assertEqual(i, sl[5:8, 3:7, 4:5])
        ni = intersection(sl[5:8, 3:7, 2:9], sl[0:50, 0:50, 9:10])
        self.assertEqual(ni, None)

    def testIndex2slice(self):
        pure = index2slice(sl[3:4, 5, :, 10])
        self.assertEqual(pure, sl[3:4, 5:6, :, 10:11])


class SliceProjectionTest(ut.TestCase):
    def testArgumentCheck(self):
        SliceProjection(1, 2, [0, 3, 4])
        SliceProjection(2, 1, [3, 0, 4])
        self.assertRaises(ValueError, SliceProjection, 2, 1, [3, 0, 7])
        self.assertRaises(ValueError, SliceProjection, 2, 1, [3, 1, 4])
        self.assertRaises(ValueError, SliceProjection, 2, 5, [3, 1, 4])

    def testDomain(self):
        sp = SliceProjection(2, 1, [3, 0, 4])
        unbounded = sp.domain([3, 23, 1])
        self.assertEqual(unbounded, (slice(23, 24), slice(None), slice(None), slice(3, 4), slice(1, 2)))

        bounded = sp.domain([3, 23, 1], slice(5, 9), slice(12, None))
        self.assertEqual(bounded, (slice(23, 24), slice(12, None), slice(5, 9), slice(3, 4), slice(1, 2)))

    def testSliceDomain(self):
        sp = SliceProjection(2, 1, [3, 0, 4])
        slicing = sp.domain([3, 7, 1], slice(1, 3), slice(0, None))
        raw = np.random.randint(0, 100, (10, 3, 3, 128, 3))
        domainArray = raw[slicing]
        sl = sp(domainArray)
        self.assertTrue(np.all(sl == raw[7, :, 1:3, 3, 1].swapaxes(0, 1)))


if __name__ == "__main__":
    ut.main()

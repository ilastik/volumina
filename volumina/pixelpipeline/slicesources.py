from __future__ import print_function
from __future__ import absolute_import

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
import logging
from builtins import range
from PyQt5.QtCore import QObject, pyqtSignal
from .asyncabcs import ISlice2DSource, RequestABC
from .datasources import IDataSource
import numpy as np
import volumina
from volumina.slicingtools import SliceProjection, is_pure_slicing, intersection, sl
from volumina.config import CONFIG

projectionAlongTXC = SliceProjection(abscissa=2, ordinate=3, along=[0, 1, 4])
projectionAlongTYC = SliceProjection(abscissa=1, ordinate=3, along=[0, 2, 4])
projectionAlongTZC = SliceProjection(abscissa=1, ordinate=2, along=[0, 3, 4])

# *******************************************************************************
# S l i c e R e q u e s t                                                      *
# *******************************************************************************

logger = logging.getLogger(__name__)


class SliceRequest(RequestABC):
    def __init__(self, domainArrayRequest, sliceProjection):
        self._ar = domainArrayRequest
        self._sp = sliceProjection

    def wait(self):
        return self._sp(self._ar.wait())

    def getResult(self):
        return self._sp(self._ar.getResult())

    def cancel(self):
        self._ar.cancel()

    def submit(self):
        self._ar.submit()
        return self

    def adjustPriority(self, delta):
        self._ar.adjustPriority(delta)
        return self

    def handednessSwitched(self):
        return self._sp.handednessSwitched()


# *******************************************************************************
# S l i c e S o u r c e                                                        *
# *******************************************************************************


class SliceSource(QObject, ISlice2DSource):
    areaDirty = pyqtSignal(object)
    isDirty = pyqtSignal(object)
    throughChanged = pyqtSignal(tuple, tuple)  # old, new
    idChanged = pyqtSignal(object, object)  # old, new

    @property
    def id(self):
        return (self, tuple(self._through))

    @property
    def through(self):
        return list(self._through)  # make a copy

    @through.setter
    def through(self, value):
        value = list(value)
        if len(value) != len(self.sliceProjection.along):
            raise ValueError(
                "SliceSource.through.setter: length of value differs from along length: %s != %s "
                % (str(len(value)), str(len(self.sliceProjection.along)))
            )
        if value != self._through:
            old = self._through
            old_id = self.id
            self._through = value
            self.throughChanged.emit(tuple(old), tuple(value))
            self.idChanged.emit(old_id, self.id)

    def __init__(self, datasource, sliceProjection=projectionAlongTZC):
        assert isinstance(datasource, IDataSource), "wrong type: %s" % str(type(datasource))
        super(SliceSource, self).__init__()

        self.sliceProjection = sliceProjection
        self._datasource = datasource
        self._datasource.isDirty.connect(self._onDatasourceDirty)
        self._through = len(sliceProjection.along) * [0]

    def setThrough(self, index, value):
        assert index < len(self.through)
        through = list(self.through)
        through[index] = value
        self.through = through

    def request(self, slicing2D, along_through=None):
        """Return a SliceRequest for a subregion of the slice.

        By default the currently set through value is used for
        the slicing. Optionally, some or all through values can
        be set to a another value (useful for requesting out-of-view
        slices as necessary for prefetching).

        Arguments:
        slicing2D    -- pair of 'slice' objects: abscissa, ordinate
        along_trough -- sequence of pairs or None;
                        pair is '(along axis, through value)'

        Returns: a SliceRequest for a 2d array

        """
        assert len(slicing2D) == 2
        # override through with caller values
        if along_through:
            through = list(self._through)
            for axis, value in along_through:
                through[axis] = value
        else:
            through = tuple(self._through)

        slicing = self.sliceProjection.domain(through, slicing2D[0], slicing2D[1])

        if CONFIG.verbose_pixelpipeline:
            logger.info("SliceSource requests '%r' from data source '%s'", slicing, type(self._datasource).__qualname__)

        return SliceRequest(self._datasource.request(slicing), self.sliceProjection)

    def setDirty(self, slicing):
        assert isinstance(slicing, tuple)
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        self.areaDirty.emit(slicing)

    def _onDatasourceDirty(self, ds_slicing):
        # embedding of slice in datasource space
        embedding = self.sliceProjection.domain(self.through)
        inter = intersection(embedding, ds_slicing)

        if inter:  # there is an intersection
            dirty_area = [None] * 2
            dirty_area[0] = inter[self.sliceProjection.abscissa]
            dirty_area[1] = inter[self.sliceProjection.ordinate]
            self.setDirty(tuple(dirty_area))

        # Even if no intersection with the current slice projection, mark this area
        #  dirty in all parallel slices that may not be visible at the moment.
        dirty_area = [None] * 2
        dirty_area[0] = ds_slicing[self.sliceProjection.abscissa]
        dirty_area[1] = ds_slicing[self.sliceProjection.ordinate]
        self.isDirty.emit(tuple(dirty_area))


# *******************************************************************************
# S y n c e d S l i c e S o u r c e s                                          *
# *******************************************************************************


class SyncedSliceSources(QObject):
    throughChanged = pyqtSignal(tuple, tuple)  # old , new
    idChanged = pyqtSignal(object, object)

    @property
    def id(self):
        return (self, tuple(zip(self._sync_along, self._through)))

    @property
    def through(self):
        return list(self._through)  # make a copy

    @through.setter
    def through(self, value):
        value = list(value)
        if len(value) != len(self._sync_along):
            raise ValueError(
                "SyncedSliceSources.through.setter: length of value differs from along length: %s != %s "
                % (str(len(value)), str(len(self._sync_along)))
            )

        if value != self._through:
            old = self._through
            old_id = self.id
            self._through = value
            for src in self._srcs:
                self._syncSliceSource(src)
            self.throughChanged.emit(tuple(old), tuple(value))
            self.idChanged.emit(old, self.id)

    def __init__(self, sync_along=(0, 1), initial_through=None):
        super(SyncedSliceSources, self).__init__()
        if len(sync_along) != len(set(sync_along)):
            raise ValueError(
                "SyncedSliceSources.__init__(): sync_along contains duplicate entries: %s" % str(sync_along)
            )
        self._sync_along = tuple(sync_along)

        if not initial_through:
            self._through = [0] * len(self._sync_along)
        else:
            initial_through = list(initial_through)
            if len(initial_through) != len(self._sync_along):
                raise ValueError(
                    "SyncedSliceSources.__init__(): len(initial_through) != len(sync_along): %s != %s"
                    % (str(len(initial_through)), str(len(self._sync_along)))
                )
            self._through = initial_through
        self._srcs = set()

    def __len__(self):
        return len(self._srcs)

    def __iter__(self):
        return iter(self._srcs)

    def getSyncAlong(self):
        return self._sync_along

    def setThrough(self, index, value):
        assert index < len(self.through)
        through = list(self.through)
        through[index] = value
        self.through = through

    def add(self, sliceSrc):
        assert isinstance(sliceSrc, SliceSource), "wrong type: %s" % str(type(sliceSrc))
        self._syncSliceSource(sliceSrc)
        self._srcs.add(sliceSrc)

    def remove(self, sliceSrc):
        assert isinstance(sliceSrc, SliceSource)
        self._srcs.remove(sliceSrc)

    def _syncSliceSource(self, sliceSrc):
        through = sliceSrc.through
        for i in range(len(self._through)):
            through[self._sync_along[i]] = self._through[i]
        sliceSrc.through = through


import unittest as ut

# *******************************************************************************
# S l i c e S o u r c e T e s t                                                *
# *******************************************************************************


class SliceSourceTest(ut.TestCase):
    def setUp(self):
        import numpy as np
        from .datasources import ArraySource

        self.raw = np.random.randint(0, 100, (10, 3, 3, 128, 3))
        self.a = ArraySource(self.raw)
        self.ss = SliceSource(self.a, projectionAlongTZC)

    def testRequest(self):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        sl = self.ss.request((slice(None), slice(None))).wait()
        self.assertTrue(np.all(sl == self.raw[1, :, :, 127, 2]))

        sl_bounded = self.ss.request((slice(0, 3), slice(1, None))).wait()
        self.assertTrue(np.all(sl_bounded == self.raw[1, 0:3, 1:, 127, 2]))

    def testDirtynessPropagation(self):
        self.ss.setThrough(0, 1)
        self.ss.setThrough(2, 2)
        self.ss.setThrough(1, 127)

        self.triggered = False

        def check1(dirty_area):
            self.triggered = True
            self.assertEqual(dirty_area, sl[:, 1:2])

        self.ss.isDirty.connect(check1)
        self.a.setDirty(sl[1:2, :, 1:2, 127:128, 2:3])
        self.ss.isDirty.disconnect(check1)
        self.assertTrue(self.triggered)
        del self.triggered

        def check2(dirty_area):
            assert False

        self.ss.isDirty.connect(check2)
        self.a.setDirty(sl[1:2, :, 1:2, 127:128, 3:4])
        self.ss.isDirty.disconnect(check2)


# *******************************************************************************
# i f   _ _ n a m e _ _   = =   " _ _ m a i n _ _ "                            *
# *******************************************************************************

if __name__ == "__main__":
    ut.main()

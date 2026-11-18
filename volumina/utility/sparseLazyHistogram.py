###############################################################################
#   volumina: volume slicing and editing library
#
#       Copyright (C) 2011-2026, the ilastik developers
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
#          http://ilastik.org/license/
###############################################################################
from collections import defaultdict
from threading import RLock
from typing import Any, Optional

import numpy as np
import numpy.typing as npt


class NoHistogramData(Exception):
    pass


class SparseLazyHistogram:
    """'Live' histogram that updates counts and sparse bins

    Bins will be 'sparse', meaning that only bins with occurrences in data will
    exist. Gaps are represented as wide bins with 0 counts.

    If no `bin_width` is supplied, it will be estimated using the first array
    that is passed to the `update` method (based on dtype). For float arrays
    `bin_width` will be estimated using 'Freedman Diaconis Estimator', for
    integer arrays it will be set to `1.0`. Subsequent updates will not change
    `bin_width`.

    Updates are thread-safe.
    """

    def __init__(self, bin_width: Optional[float] = None):
        self._bin_width = bin_width
        self._counts: defaultdict[int, int] = defaultdict(lambda: 0)
        self._pixel_count: int = 0
        self._min: float | None = None
        self._max: float | None = None
        self._defer: list[npt.NDArray[np.floating[Any]]] = []
        self.__lock = RLock()

    @property
    def pixel_count(self):
        return self._pixel_count

    @property
    def data_range(self):
        return self._min, self._max

    def _estimate_bin_width_float(self, arr: npt.NDArray[np.floating[Any]]) -> float | None:
        n = arr.size
        assert n > 1, f"array too small to estimate bin width: size = {n}"

        q1, q99 = np.percentile(arr, [1.0, 99.0])
        iqr = float(q99 - q1)

        if iqr <= np.finfo(arr.dtype).eps:
            return

        # Freedman Diaconis Estimator
        bins = np.histogram_bin_edges(arr.flat, bins="fd")
        self._bin_width = bins[1] - bins[0]
        return self._bin_width

    def _estimate_bin_width(self, arr) -> bool:
        with self.__lock:
            if self._bin_width is not None:
                return False
            if np.issubdtype(arr.dtype, np.integer) and self._bin_width is None:
                self._bin_width = 1.0
                return True
            if self._estimate_bin_width_float(arr) is None:
                self._defer.append(arr)
                return False

            return True

    def update(self, arr: npt.NDArray[np.number[Any]]):
        if arr.size == 0:
            return

        if self._bin_width is None:
            if self._estimate_bin_width(arr):
                for a in self._defer:
                    self.update(a)
            else:
                return

        assert self._bin_width is not None
        bins = np.floor(arr / self._bin_width).astype(np.int64)
        unique_ids, counts = np.unique(bins, return_counts=True)
        batch_min = float(unique_ids[0] * self._bin_width)
        batch_max = float(unique_ids[-1] * self._bin_width)

        with self.__lock:
            self._min = batch_min if self._min is None else min(self._min, batch_min)
            self._max = batch_max if self._max is None else max(self._max, batch_max)
            for _id, count in zip(unique_ids, counts):
                self._counts[_id] += count
            self._pixel_count += sum(counts)

    def get_sparse_histogram(self, normalize: bool = True):
        """
        Args:
          normalize: counts will be normalized by total count if `True`.

        Raises: NoHistogramData if histogram has not seen any data
        """
        if self._bin_width is None:
            raise NoHistogramData()
        keys = sorted(self._counts.keys())
        bins = [keys[0]]
        counts = [self._counts[keys[0]]]
        for k in keys[1:]:
            if k - bins[-1] != 1:
                bins.append(bins[-1] + 1)
                counts.append(0)

            bins.append(k)
            counts.append(self._counts[k])
        bins.append(bins[-1] + 1)
        counts = np.array(counts)
        if normalize:
            counts = counts.astype(np.float64) / self._pixel_count
        return np.array(bins) * self._bin_width, counts

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}: {self._bin_width=} {self._min=} {self._max=} {self._pixel_count=} {len(self._counts)=}"

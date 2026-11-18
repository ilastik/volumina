from concurrent.futures import ThreadPoolExecutor
from typing import Any

import numpy as np
import pytest

from volumina.utility.sparseLazyHistogram import NoHistogramData, SparseLazyHistogram


def test_get_histogram_raises_before_first_update():
    hist = SparseLazyHistogram()
    with pytest.raises(NoHistogramData):
        _ = hist.get_sparse_histogram()


@pytest.mark.parametrize("dtype", (np.uint8, np.int8, np.uint16, np.int16, np.uint32, np.int32, np.uint64, np.int64))
def test_integer_defaults_to_unit_bin_width_and_normalizes(dtype: np.dtype[np.integer[Any]]):
    hist = SparseLazyHistogram()

    hist.update(np.array([0, 1, 1, 3], dtype=dtype))

    bins, counts = hist.get_sparse_histogram(normalize=True)

    np.testing.assert_array_equal(bins, np.array([0.0, 1.0, 2.0, 3.0, 4.0]))
    np.testing.assert_allclose(counts, np.array([1, 2, 0, 1]) / 4)

    assert hist.pixel_count == 4
    assert hist.data_range == (0.0, 3.0)


@pytest.mark.parametrize("dtype", (np.int8, np.int16, np.int32, np.int64))
def test_signed_integer_histogram_with_negative_values(dtype: np.dtype[np.integer[Any]]):
    hist = SparseLazyHistogram()

    hist.update(np.array([-2, -1, -1, 1], dtype=dtype))

    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([-2.0, -1.0, 0.0, 1.0, 2.0]))
    np.testing.assert_array_equal(counts, np.array([1, 2, 0, 1]))

    assert hist.pixel_count == 4
    assert hist.data_range == (-2.0, 1.0)


@pytest.mark.parametrize("dtype", (np.float16, np.float32, np.float64))
def test_explicit_float_bin_width(dtype: np.dtype[np.integer[Any]]):
    hist = SparseLazyHistogram(bin_width=0.5)

    hist.update(np.array([-0.6, -0.1, 0.1, 0.2, 0.6], dtype=dtype))

    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([-1.0, -0.5, 0.0, 0.5, 1.0]))
    np.testing.assert_array_equal(counts, np.array([1, 1, 2, 1]))

    assert hist.pixel_count == 5
    assert hist.data_range == (-1.0, 0.5)


def test_multiple_updates_accumulate_counts_and_range():
    hist = SparseLazyHistogram()

    hist.update(np.array([1, 2], dtype=np.int64))
    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([1.0, 2.0, 3.0]))
    np.testing.assert_array_equal(counts, np.array([1, 1]))

    assert hist.pixel_count == 2
    assert hist.data_range == (1.0, 2.0)

    hist.update(np.array([2, 4], dtype=np.int64))
    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([1.0, 2.0, 3.0, 4.0, 5.0]))
    np.testing.assert_array_equal(counts, np.array([1, 2, 0, 1]))

    assert hist.pixel_count == 4
    assert hist.data_range == (1.0, 4.0)


def test_histogram_is_sparse():
    hist = SparseLazyHistogram()

    hist.update(np.array([0, 0, 5], dtype=np.int64))

    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([0.0, 1.0, 5.0, 6.0]))
    np.testing.assert_array_equal(counts, np.array([2, 0, 1]))

    assert hist.pixel_count == 3
    assert hist.data_range == (0.0, 5.0)


def test_normalized_counts_sum_to_one():
    hist = SparseLazyHistogram()

    hist.update(np.array([0, 0, 1, 2, 2, 2], dtype=np.uint8))

    _, counts = hist.get_sparse_histogram(normalize=True)

    assert counts.dtype == np.float64
    np.testing.assert_allclose(counts.sum(), 1.0)


def test_float_array_is_deferred_when_bin_width_cannot_be_estimated():
    hist = SparseLazyHistogram()

    arr = np.ones(8, dtype=np.float32)
    hist.update(arr)

    assert hist.pixel_count == 0
    assert hist.data_range == (None, None)
    assert arr in hist._defer  # pyright: ignore [reportPrivateUsage]


def test_deferred_arrays_are_calculated_after_bin_width_estimation():
    hist = SparseLazyHistogram()

    deferred = np.ones(8, dtype=np.float32)

    hist.update(deferred)
    assert deferred in hist._defer  # pyright: ignore [reportPrivateUsage]

    arr = np.linspace(0.0, 10.0, 100, dtype=np.float32)

    hist.update(arr)

    assert hist.pixel_count == deferred.size + arr.size

    _, counts = hist.get_sparse_histogram(normalize=False)
    assert counts.sum() == hist.pixel_count


def test_threadsafe_updates():
    hist = SparseLazyHistogram()

    arrays = [
        np.ones((1000,), dtype=np.uint8),
        np.ones((1000,), dtype=np.uint8),
        np.ones((1000,), dtype=np.uint8) * 3,
        np.ones((1000,), dtype=np.uint8) * 42,
    ]

    with ThreadPoolExecutor(max_workers=2) as executor:
        _ = executor.map(hist.update, arrays, timeout=1.0)

    bins, counts = hist.get_sparse_histogram(normalize=False)

    np.testing.assert_allclose(bins, np.array([1.0, 2.0, 3.0, 4.0, 42.0, 43.0]))
    np.testing.assert_array_equal(counts, np.array([2000, 0, 1000, 0, 1000]))

    assert hist.pixel_count == 4000
    assert hist.data_range == (1.0, 42.0)

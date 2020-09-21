from types import SimpleNamespace

import pytest
import numpy as np

from numpy.random import rand
from numpy.testing import assert_array_equal

from volumina.pixelpipeline import datasources as ds


@pytest.fixture
def lazyflow_op():
    graph = pytest.importorskip("lazyflow.graph")
    operators = pytest.importorskip("lazyflow.operators.operators")

    g = graph.Graph()
    op = operators.OpArrayPiper(graph=g)

    return op


@pytest.fixture
def vigra():
    return pytest.importorskip("vigra")


def select(dims, keys):
    return tuple(getattr(dims, k) for k in keys)


@pytest.fixture(params=["h5py", "numpy"])
def make_source(request):
    if request.param == "h5py":
        h5py = pytest.importorskip("h5py")

        def _make_source(shape):
            f = h5py.File("file", driver="core", backing_store=False)
            data = f.create_dataset("ds", shape)
            data[:] = rand(*shape)
            return data

    if request.param == "numpy":

        def _make_source(shape):
            return rand(*shape)

    return _make_source


DIMS = SimpleNamespace(t=2, c=3, z=10, x=32, y=64)


@pytest.mark.parametrize(
    "dims,expected_shape,transpose",
    [
        ["xy", (1, DIMS.x, DIMS.y, 1, 1), (0, 1)],
        ["xyz", (1, DIMS.x, DIMS.y, DIMS.z, 1), (0, 1, 2)],
        ["cxyz", (1, DIMS.x, DIMS.y, DIMS.z, DIMS.c), (1, 2, 3, 0)],
        ["tcxyz", (DIMS.t, DIMS.x, DIMS.y, DIMS.z, DIMS.c), (0, 2, 3, 4, 1)],
    ],
)
def test_lazyflow_tagged_shape_embedding(lazyflow_op, vigra, dims, expected_shape, transpose):
    shape = select(DIMS, dims)
    len_ = np.product(shape)

    array = np.array(range(len_)).reshape(shape).view(vigra.VigraArray)
    array.axistags = vigra.defaultAxistags(dims)
    lazyflow_op.Input.setValue(array)

    src = ds.createDataSource(lazyflow_op.Input)
    assert isinstance(src, ds.LazyflowSource)
    assert src._op5.Output.meta.shape == expected_shape

    outsrc = ds.createDataSource(lazyflow_op.Output)
    assert isinstance(outsrc, ds.LazyflowSource)
    assert outsrc._op5.Output.meta.shape == expected_shape

    src_array = outsrc.request(np.s_[:, :, :, :, :]).wait()
    expected_array = np.array(array[:]).transpose(*transpose)
    expected_array.shape = src_array.shape
    assert_array_equal(expected_array, src_array)


@pytest.mark.parametrize(
    "shape,expected_shape",
    [
        ((3, 5), (1, 3, 5, 1, 1)),  # xy
        # For if shape if 3D and last element is <= 4 then we should guess that it's a channel dimension
        ((3, 5, 2), (1, 3, 5, 1, 2)),  # xyc
        ((3, 5, 3), (1, 3, 5, 1, 3)),  # xyc
        ((3, 5, 4), (1, 3, 5, 1, 4)),  # xyc
        # Now we are done with channels and continue with z dimension
        ((3, 7, 5), (1, 3, 7, 5, 1)),  # xyz
        ((3, 5, 6, 7), (1, 3, 5, 6, 7)),  # xyzc
        ((9, 3, 5, 6, 7), (9, 3, 5, 6, 7)),  # txyzc
    ],
)
def test_array_untagged_shape_embedding(make_source, shape, expected_shape):
    array = make_source(shape)

    source, src_shape = ds.createDataSource(array, True)

    assert isinstance(source, ds.ArraySource)
    assert np.squeeze(np.ndarray(source._array.shape)).shape == array.shape
    assert src_shape == expected_shape
    src_array = source.request(np.s_[:, :, :, :, :]).wait()
    array = array[:]
    array.shape = src_array.shape
    assert_array_equal(array, src_array)

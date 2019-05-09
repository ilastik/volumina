import pytest
import numpy as np

from numpy.random import rand

from volumina.pixelpipeline import datasourcefactories as factories
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


def select(dct, keys):
    return tuple(dct[k] for k in keys)


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


DIMS = {"t": 2, "c": 3, "z": 10, "x": 32, "y": 64}


@pytest.mark.parametrize(
    "dims,expected_shape",
    [
        [("x", "y"), (1, DIMS["x"], DIMS["y"], 1, 1)],
        [("x", "y", "z"), (1, DIMS["x"], DIMS["y"], DIMS["z"], 1)],
        [("c", "x", "y", "z"), (1, DIMS["x"], DIMS["y"], DIMS["z"], DIMS["c"])],
        [
            ("t", "c", "x", "y", "z"),
            (DIMS["t"], DIMS["x"], DIMS["y"], DIMS["z"], DIMS["c"]),
        ],
    ],
)
def test_lazyflow_factory(lazyflow_op, vigra, dims, expected_shape):
    shape = select(DIMS, dims)
    len_ = np.product(shape)

    array = np.array(range(len_)).reshape(shape).view(vigra.VigraArray)
    array.axistags = vigra.defaultAxistags("".join(dims))
    lazyflow_op.Input.setValue(array)

    src = factories.createDataSource(lazyflow_op.Input)
    assert isinstance(src, ds.LazyflowSource)
    assert src._op5.Output.meta.shape == expected_shape

    outsrc = factories.createDataSource(lazyflow_op.Output)
    assert isinstance(outsrc, ds.LazyflowSource)
    assert outsrc._op5.Output.meta.shape == expected_shape


@pytest.mark.parametrize(
    "shape,expected_shape",
    [
        ((3, 5), (1, 3, 5, 1, 1)),
        ((3, 5, 3), (1, 3, 5, 1, 3)),  # xyc see datasourcefactories normalize_shape
        ((3, 5, 6), (1, 3, 5, 6, 1)),  # xyz
        ((3, 5, 6, 7), (1, 3, 5, 6, 7)),
        ((9, 3, 5, 6, 7), (9, 3, 5, 6, 7)),
    ],
)
def test_shapes(make_source, shape, expected_shape):
    array = make_source(shape)
    source, shape = factories.createDataSource(array, True)
    assert isinstance(source, ds.ArraySource)
    assert np.squeeze(np.ndarray(source._array.shape)).shape == array.shape
    assert shape == expected_shape

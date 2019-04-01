import pytest
import numpy as np

from numpy.random import rand

from volumina.pixelpipeline import datasourcefactories as factories
from volumina.pixelpipeline import datasources as ds


@pytest.fixture
def lazyflow_op():
    graph = pytest.importorskip("lazyflow.graph")

    class OpPiper(graph.Operator):

        Input = graph.InputSlot()
        Output = graph.OutputSlot()

        def setupOutputs(self):
            self.outputs["Output"].meta.assignFrom(self.inputs["Input"].meta)
            self.outputs["Output"].connect(self.inputs["Input"])

        def execute(self, slot, subindex, roi, result):
            result[:] = self.outputs["Output"](roi).wait()
            return result

        def propagateDirty(self, inputSlot, subindex, roi):
            self.Output.setDirty(roi)

    g = graph.Graph()
    op = OpPiper(graph=g)

    return op


@pytest.fixture
def vigra():
    return pytest.importorskip("vigra")


@pytest.mark.parametrize("ndims", range(2, 6))
def test_lazyflow_factory(lazyflow_op, vigra, ndims):
    shape = (10,) * ndims

    array = rand(*shape).view(vigra.VigraArray)
    array.axistags = vigra.defaultAxistags("txyzc"[:ndims])
    lazyflow_op.inputs["Input"].setValue(array)

    src = factories.createDataSource(lazyflow_op.Input)
    assert isinstance(src, ds.LazyflowSource)
    assert np.squeeze(np.ndarray(src._op5.Output.meta.shape)).shape == array.shape

    outsrc = factories.createDataSource(lazyflow_op.Output)
    assert isinstance(outsrc, ds.LazyflowSource)
    assert np.squeeze(np.ndarray(outsrc._op5.Output.meta.shape)).shape == array.shape


@pytest.mark.parametrize("ndims", range(2, 6))
def test_numpy_factory(ndims):
    shape = (10,) * ndims
    array = rand(*shape)
    source = factories.createDataSource(array)
    assert isinstance(source, ds.ArraySource)
    assert np.squeeze(np.ndarray(source._array.shape)).shape == array.shape


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
def test_shapes(shape, expected_shape):
    array = rand(*shape)
    source, shape = factories.createDataSource(array, True)
    assert isinstance(source, ds.ArraySource)
    assert np.squeeze(np.ndarray(source._array.shape)).shape == array.shape
    assert shape == expected_shape

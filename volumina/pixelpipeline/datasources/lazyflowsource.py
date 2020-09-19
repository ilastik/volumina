import logging
import sys
import weakref
from functools import wraps, partial

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal
from future.utils import raise_with_traceback
from lazyflow.graph import Slot
from lazyflow.operators import opReorderAxes
from lazyflow.roi import sliceToRoi, roiToSlice

from volumina.pixelpipeline.interface import DataSourceABC, RequestABC, IndeterminateRequestError
from volumina.slicingtools import is_pure_slicing, slicing2shape, make_bounded
from volumina.config import CONFIG

try:
    _has_vigra = True
    import vigra
except ImportError:
    _has_vigra = False

logger = logging.getLogger(__name__)


def strSlicing(slicing):
    str = "("
    for i, s in enumerate(slicing):
        str += "%d:%d" % (s.start, s.stop)
        if i != len(slicing) - 1:
            str += ","
    str += ")"
    return str


def translate_lf_exceptions(func):
    """
    Decorator.
    Since volumina doesn't know about lazyflow, this datasource is responsible
    for translating SlotNotReady errors into the volumina equivalent.
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Slot.SlotNotReadyError as ex:
            # Translate lazyflow not-ready errors into the volumina equivalent.
            raise_with_traceback(IndeterminateRequestError(ex)).with_traceback(sys.exc_info()[2])

    wrapper.__wrapped__ = func  # Emulate python 3 behavior of @functools.wraps
    return wrapper


class LazyflowRequest(RequestABC):
    @translate_lf_exceptions
    def __init__(self, op, slicing, prio, objectName="Unnamed LazyflowRequest"):
        shape = op.Output.meta.shape
        if shape is not None:
            slicing = make_bounded(slicing, shape)
        self._req = op.Output[slicing]
        self._slicing = slicing
        self._shape = slicing2shape(slicing)
        self._objectName = objectName

    @translate_lf_exceptions
    def wait(self):
        a = self._req.wait()
        assert isinstance(a, np.ndarray)
        assert a.shape == self._shape, (
            "LazyflowRequest.wait() [name=%s]: we requested shape %s (slicing: %s), but lazyflow delivered shape %s"
            % (self._objectName, self._shape, self._slicing, a.shape)
        )
        return a

    def cancel(self):
        self._req.cancel()


def weakref_setDirtyLF(wref, *args, **kwargs):
    """
    LazyflowSource uses this function to subscribe to dirty notifications without giving out a shared reference to itself.
    Otherwise, LazyflowSource.__del__ would never be called.
    """
    wref()._setDirtyLF(*args, **kwargs)


class LazyflowSource(QObject, DataSourceABC):
    isDirty = pyqtSignal(object)
    numberOfChannelsChanged = pyqtSignal(int)

    @property
    def dataSlot(self):
        return self._orig_outslot

    def __init__(self, outslot, priority=0):
        super(LazyflowSource, self).__init__()

        self._orig_outslot = outslot
        self._orig_meta = outslot.meta.copy()

        # Attach an OpReorderAxes to ensure the data will display correctly
        # (We include the graph parameter, too, since tests sometimes provide an operator with no parent.)
        self._op5 = opReorderAxes.OpReorderAxes(
            parent=outslot.getRealOperator().parent, graph=outslot.getRealOperator().graph
        )
        self._op5.Input.connect(outslot)
        self._op5.AxisOrder.setValue("txyzc")

        self._priority = priority
        self._dirtyCallback = partial(weakref_setDirtyLF, weakref.ref(self))
        self._op5.Output.notifyDirty(self._dirtyCallback)
        self._op5.externally_managed = True

        self.additional_owned_ops = []

        self._shape = self._op5.Output.meta.shape
        self._op5.Output.notifyMetaChanged(self._checkForNumChannelsChanged)

    @property
    def numberOfChannels(self):
        return self._shape[-1]

    def _checkForNumChannelsChanged(self, *args):
        if self._op5 and self._op5.Output.ready() and self._shape[-1] != self._op5.Output.meta.shape[-1]:
            self._shape = tuple(self._op5.Output.meta.shape)
            self.numberOfChannelsChanged.emit(self._shape[-1])

    def clean_up(self):
        self._op5.cleanUp()
        self._op5 = None
        for op in reversed(self.additional_owned_ops):
            op.cleanUp()

    def dtype(self):
        dtype = self._orig_outslot.meta.dtype
        assert (
            dtype is not None
        ), "Your LazyflowSource doesn't have a dtype! Is your lazyflow slot properly configured in setupOutputs()?"
        return dtype

    @translate_lf_exceptions
    def request(self, slicing):
        if CONFIG.verbose_pixelpipeline:
            logger.info("%s '%s' requests %s'", type(self).__name__, self.objectName(), strSlicing(slicing))

        if not is_pure_slicing(slicing):
            raise Exception("LazyflowSource: slicing is not pure")
        assert (
            self._op5 is not None
        ), "Underlying operator is None.  Are you requesting from a datasource that has been cleaned up already?"

        start, stop = sliceToRoi(slicing, self._op5.Output.meta.shape)
        clipped_roi = np.maximum(start, (0, 0, 0, 0, 0)), np.minimum(stop, self._op5.Output.meta.shape)
        clipped_slicing = roiToSlice(*clipped_roi)
        return LazyflowRequest(self._op5, clipped_slicing, self._priority, objectName=self.objectName())

    def _setDirtyLF(self, slot, roi):
        clipped_roi = np.maximum(roi.start, (0, 0, 0, 0, 0)), np.minimum(roi.stop, self._op5.Output.meta.shape)
        self.setDirty(roiToSlice(*clipped_roi))

    def setDirty(self, slicing):
        if not is_pure_slicing(slicing):
            raise Exception("dirty region: slicing is not pure")
        self.isDirty.emit(slicing)

    def __eq__(self, other):
        if other is None:
            return False
        if self._orig_meta != other._orig_meta:
            return False
        return self._orig_outslot is other._orig_outslot

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self._orig_meta, self._orig_outslot))


class LazyflowSinkSource(LazyflowSource):
    def __init__(self, outslot, inslot, priority=0, *, eraser_value=100):
        self._inputSlot = inslot
        self._priority = priority
        self._eraser_value = eraser_value
        super().__init__(outslot)

    @property
    def eraser_value(self):
        return self._eraser_value

    def put(self, slicing, array):
        assert _has_vigra, "Lazyflow SinkSource requires lazyflow and vigra."
        taggedArray = array.view(vigra.VigraArray)
        taggedArray.axistags = vigra.defaultAxistags("txyzc")

        inputTags = self._inputSlot.meta.axistags
        inputKeys = [tag.key for tag in inputTags]
        transposedArray = taggedArray.withAxes(*inputKeys)
        taggedSlicing = dict(list(zip("txyzc", slicing)))
        transposedSlicing = ()
        for k in inputKeys:
            if k in "txyzc":
                transposedSlicing += (taggedSlicing[k],)

        self._inputSlot[transposedSlicing] = transposedArray.view(np.ndarray)

    def __eq__(self, other):
        if other is None:
            return False
        result = super(LazyflowSinkSource, self).__eq__(other)
        result &= self._inputSlot == other._inputSlot
        return result

    def __ne__(self, other):
        return not (self == other)

    def __hash__(self):
        return hash((self._orig_meta, self._orig_outslot, self._inputSlot))

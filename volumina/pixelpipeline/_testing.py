from __future__ import print_function
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
#		   http://ilastik.org/license/
###############################################################################
try:
    import lazyflow
    has_lazyflow = True
except ImportError:
    has_lazyflow = False

if has_lazyflow:
    from lazyflow.graph import Operator, InputSlot, OutputSlot
    from lazyflow import operators
    import time
    import vigra

#*******************************************************************************
# O p D e l a y                                                                *
#*******************************************************************************

    class OpDelay(operators.OpArrayPiper):
        def __init__( self, g, delay_factor = 0.000001 ):
            super(OpDelay, self).__init__(graph=g)
            self._delay_factor = delay_factor

        def execute(self, slot, subindex, roi, result):
            key = roi.toSlice()
            req = self.inputs["Input"][key].writeInto(result)
            req.wait()
            t = self._delay_factor*result.nbytes
            print("Delay: " + str(t) + " secs.")
            time.sleep(t)
            return result

#*******************************************************************************
# O p D a t a P r o v i d e r                                                  *
#*******************************************************************************

    class OpDataProvider(Operator):
        name = "Data Provider"
        category = "Input"

        Changedata = InputSlot(optional=True)
        Data = OutputSlot("Data")

        def __init__(self, voluminaData, graph=None, parent=None):
            """
            voluminaData - An array in txyzc order.
            """
            Operator.__init__(self, graph=graph, parent=parent)
            # We store the data in a custom order
            self._data = voluminaData.transpose([0,3,2,1,4])
            oslot = self.outputs["Data"]
            oslot.meta.shape = self._data.shape
            oslot.meta.dtype = self._data.dtype

            oslot.meta.axistags = vigra.defaultAxistags('tzyxc') # Non-volumina ordering: datasource will re-order
            self.inputs["Changedata"].meta.axistags = oslot.meta.axistags

        def execute(self, slot, subindex, roi, result):
            key = roi.toSlice()
            result[:] = self._data[key]
            return result

        def setInSlot(self, slot, subindex, roi, value):
            key = roi.toSlice()
            self._data[key] = value
            self.outputs["Data"].setDirty(key)

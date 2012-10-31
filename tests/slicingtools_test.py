import unittest
import numpy as np
import volumina.slicingtools as st
from PyQt4.QtCore import QRect


class SlicingToolsTest(unittest.TestCase):
    slicing = (slice(5, 7), slice(10, 18))
    qrect = QRect(5, 10, 2, 8)

    def test_slicing2rect(self):
        qrect = st.slicing2rect(self.slicing)
        self.assertEquals(qrect, self.qrect)

    def test_rect2slicing(self):
        slicing = st.rect2slicing(self.qrect)
        self.assertEquals(slicing, self.slicing)

    def test_slicing_rect_inversion(self):
        """Ensures that slicing2rect and rect2slicing are inverse
        operations.

        """
        a = self.slicing
        b = st.slicing2rect(a)
        c = st.rect2slicing(b)

        self.assertEquals(a, c)

        a = self.qrect
        b = st.rect2slicing(a)
        c = st.slicing2rect(c)

        self.assertEquals(a, c)


if __name__=='__main__':
    unittest.main()

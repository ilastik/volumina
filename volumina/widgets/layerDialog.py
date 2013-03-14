#Python
import os

#PyQt
from PyQt4 import uic
from PyQt4.QtGui import QDialog

#===----------------------------------------------------------------------------------------------------------------===

class GrayscaleLayerDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        p = os.path.split(os.path.abspath(__file__))[0]
        uic.loadUi(p+"/ui/grayLayerDialog.ui", self)
        self.setLayername("testname")
    def setLayername(self, n):
        self._layerLabel.setText("<b>%s</b>" % n)
    
class RGBALayerDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        p = os.path.split(os.path.abspath(__file__))[0]
        uic.loadUi(p+"/ui/rgbaLayerDialog.ui", self)
        self.setLayername("testname")
    
    def showRedThresholds(self, show):
        self.redChannel.setVisible(show)
    def showGreenThresholds(self, show):
        self.greenChannel.setVisible(show)
    def showBlueThresholds(self, show):
        self.blueChannel.setVisible(show)
    def showAlphaThresholds(self, show):
        self.alphaChannel.setVisible(show)
    
    def setLayername(self, n):
        self._layerLabel.setText("<b>%s</b>" % n)
 
#===----------------------------------------------------------------------------------------------------------------===
#=== __name__ == "__main__"                                                                                         ===
#===----------------------------------------------------------------------------------------------------------------===
        
if __name__ == "__main__":
    import optparse
    import sys
    from PyQt4.QtGui import QApplication
     
    parser = optparse.OptionParser()
    parser.add_option("--gray", action="store_true")
    parser.add_option("--rgb",  action="store_true")
    (options, args) = parser.parse_args()
    
    app = QApplication([])
    if options.gray:
        l = GrayscaleLayerDialog()
    elif options.rgb:
        l = RGBALayerDialog()
    else:
        print parser.usage
        sys.exit()
    l.show()
    app.exec_()

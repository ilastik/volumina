import unittest as ut
from PyQt4.QtCore import QTimer
from PyQt4.QtGui import qApp, QApplication, QWidget, QHBoxLayout, QPixmap
                         
from volumina.layer import Layer
from volumina.layerstack import LayerStackModel
from volumina.widgets.layerwidget import LayerWidget

class TestLayerWidget( ut.TestCase ):
    """
    Create two layers and add them to a LayerWidget.
    Then change one of the layer visibilities and verify that the layer widget appearance updates.
    
    At the time of this writing, the widget doesn't properly repaint the selected layer (all others repaint correctly).
    """
    
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication([])
        cls.errors = False

    @classmethod
    def tearDownClass(cls):
        del cls.app
    
    def impl(self):
        try:
            # Capture the window before we change anything
            beforeImg = QPixmap.grabWindow( self.w.winId() ).toImage()
            
            # Change the visibility of the *selected* layer
            self.o2.visible = False
            
            # Make sure the GUI is caught up on paint events
            QApplication.processEvents()

            # Capture the window now that we've changed a layer.
            afterImg = QPixmap.grabWindow( self.w.winId() ).toImage()
    
            # Optional: Save the files so we can inspect them ourselves...
            #beforeImg.save('before.png')
            #afterImg.save('after.png')

            # Before and after should NOT match.
            assert beforeImg != afterImg
        except:
            # Catch all exceptions and print them
            # We must finish so we can quit the app.
            import traceback
            traceback.print_exc()
            TestLayerWidget.errors = True

        qApp.quit()

    def test_repaint_after_visible_change(self):
        self.model = LayerStackModel()

        self.o1 = Layer()
        self.o1.name = "Fancy Layer"
        self.o1.opacity = 0.5
        self.model.append(self.o1)
        
        self.o2 = Layer()
        self.o2.name = "Some other Layer"
        self.o2.opacity = 0.25
        self.model.append(self.o2)
        
        self.view = LayerWidget(None, self.model)
        self.view.show()
        self.view.updateGeometry()
    
        self.w = QWidget()
        self.lh = QHBoxLayout(self.w)
        self.lh.addWidget(self.view)
        self.w.setGeometry(100, 100, 300, 300)
        self.w.show()

        # Run the test within the GUI event loop
        QTimer.singleShot(500, self.impl )
        self.app.exec_()
        
        # Were there errors?
        assert not TestLayerWidget.errors, "There were GUI errors/failures.  See above."        
        
        
if __name__=='__main__':
    ut.main()

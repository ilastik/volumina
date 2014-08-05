from PyQt4.QtCore import pyqtSignal, QTimer
from PyQt4.QtGui import QSpinBox

class DelayedSpinBox(QSpinBox):
    """
    Same as a QSpinBox, but provides the delayedValueChanged() signal, 
    which waits for a bit before signaling with the user's new input.
    """
    delayedValueChanged = pyqtSignal(int)
    
    def __init__(self, delay_ms, *args, **kwargs):
        super(DelayedSpinBox, self).__init__(*args, **kwargs)
        self.delay_ms = delay_ms

        self._timer = QTimer(self)
        self._timer.setInterval(self.delay_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect( self._handleTimeout )

        self.valueChanged.connect( self._handleValueChanged )
    
    def _handleValueChanged(self, value):
        # Reset the timer.
        self._timer.start()

    def _handleTimeout(self):
        self.delayedValueChanged.emit( self.value() )

if __name__ == "__main__":
    from PyQt4.QtGui import QApplication, QWidget, QLabel, QVBoxLayout
    
    app = QApplication([])

    label = QLabel()
    box = DelayedSpinBox(1000)
    
    def update_label(value):
        print "updating label to: {}".format(value)
        label.setText(str(value))
    box.delayedValueChanged.connect( update_label )
    
    layout = QVBoxLayout()
    layout.addWidget(label)
    layout.addWidget(box)

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()
    
    app.exec_()

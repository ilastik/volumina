from __future__ import print_function
from builtins import str
from PyQt5.QtCore import pyqtSignal, QTimer
from PyQt5.QtWidgets import QSpinBox

class DelayedSpinBox(QSpinBox):
    """
    Same as a QSpinBox, but provides the delayedValueChanged() signal, 
    which waits for a bit before signaling with the user's new input.
    """
    delayedValueChanged = pyqtSignal(int)
    
    def __init__(self, delay_ms, *args, **kwargs):
        super(DelayedSpinBox, self).__init__(*args, **kwargs)
        self.delay_ms = delay_ms
        self._blocksignal = False

        self._timer = QTimer(self)
        self._timer.setInterval(self.delay_ms)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect( self._handleTimeout )

        self.valueChanged.connect( self._handleValueChanged )
        self._lastvalue = self.value()
    
    def _handleValueChanged(self, value):
        if not self._blocksignal:
            # If it looks like the user is NOT typing, then update immediately.
            # (i.e. if the value is changing by just 1 or exactly 10)
            diff = abs(value - self._lastvalue)
            if diff == 1 or diff == 10:
                self._lastvalue = self.value()
                self.delayedValueChanged.emit( self.value() )
            else:
                # The user is typing a new value into the box.
                # Don't update immediately.
                # Instead, reset the timer.
                self._timer.start()

    def _handleTimeout(self):
        self._lastvalue = self.value()
        self.delayedValueChanged.emit( self.value() )
    
    def setValueWithoutSignal(self, value):
        self._blocksignal = True
        self.setValue(value)
        self._blocksignal = False

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
    
    app = QApplication([])

    label = QLabel()
    box = DelayedSpinBox(1000)
    
    def update_label(value):
        print("updating label to: {}".format(value))
        label.setText(str(value))
    box.delayedValueChanged.connect( update_label )
    
    layout = QVBoxLayout()
    layout.addWidget(label)
    layout.addWidget(box)

    widget = QWidget()
    widget.setLayout(layout)
    widget.show()
    widget.raise_()
    
    app.exec_()

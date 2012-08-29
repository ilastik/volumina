from PyQt4.QtCore import QObject, pyqtSignal, QEvent, Qt

class ClickReportingInterpreter(QObject):
    rightClickReceived = pyqtSignal(object) # list of indexes
    leftClickReceived = pyqtSignal(object)  # ditto
    
    def __init__(self, navigationInterpreter, positionModel):
        QObject.__init__(self)
        self.baseInterpret = navigationInterpreter
        self.posModel      = positionModel

    def start( self ):
        self.baseInterpret.start()

    def stop( self ):
        self.baseInterpret.stop()

    def eventFilter( self, watched, event ):
        if event.type() == QEvent.MouseButtonPress:
            pos = self.posModel.cursorPos
            pos = [int(i) for i in pos]
            pos = [0,] + pos + [0,]

            if event.button() == Qt.LeftButton:
                self.leftClickReceived.emit( pos )
            if event.button() == Qt.RightButton:
                self.rightClickReceived.emit( pos )                

        # Event is always forwarded to the navigation interpreter.
        return self.baseInterpret.eventFilter(watched, event)


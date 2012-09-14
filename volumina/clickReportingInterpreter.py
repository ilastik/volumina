from PyQt4.QtCore import QObject, pyqtSignal, QEvent, Qt, QPoint

class ClickReportingInterpreter(QObject):
    rightClickReceived = pyqtSignal(object, QPoint) # list of indexes, global window coordinate of click
    leftClickReceived = pyqtSignal(object, QPoint)  # ditto
    
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
                gPos = watched.mapToGlobal( event.pos() )
                self.leftClickReceived.emit( pos, gPos )
            if event.button() == Qt.RightButton:
                gPos = watched.mapToGlobal( event.pos() )
                self.rightClickReceived.emit( pos, gPos )                

        # Event is always forwarded to the navigation interpreter.
        return self.baseInterpret.eventFilter(watched, event)


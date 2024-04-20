import numpy as np
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QTransform
import pyqtgraph as pg


class SelectViewBox(pg.ViewBox):


    sigSelectedRegion = Signal(object, object, object)


    def __init__(self, channel, *args, **kwargs):
        pg.ViewBox.__init__(self, *args, **kwargs)
        self.setMouseMode(pg.ViewBox.RectMode)
        self.rbScaleBox.setPen(pg.mkPen((200, 200, 200), width=1))
        self.rbScaleBox.setBrush(pg.mkBrush(200, 200, 200, 100))
        self.channel = channel


    def keyPressEvent(self, ev):
        ev.ignore()
        
        
    def mouseDragEvent(self, ev, axis=None):
        ## if axis is specified, event will only affect that axis.
        ev.accept()  ## we accept all buttons

        pos = ev.pos()
        lastPos = ev.lastPos()
        dif = pos - lastPos
        dif = dif * -1

        ## Ignore axes if mouse is disabled
        mouseEnabled = np.array(self.state['mouseEnabled'], dtype=np.float64)
        mask = mouseEnabled.copy()
        if axis is not None:
            mask[1-axis] = 0.0

        ## Scale or translate based on mouse button
        if ev.button() in [Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton]:
            if self.state['mouseMode'] == pg.ViewBox.RectMode and axis is None:
                if ev.isFinish():
                    # This is the final move in the drag; change the view scale now
                    rect = QRectF(pg.Point(ev.buttonDownPos(ev.button())), pg.Point(pos))
                    rect = self.childGroup.mapRectFromParent(rect) # in data coordinates
                    self.sigSelectedRegion.emit(self.channel, self, rect)
                else:
                    ## update shape of scale box
                    self.updateScaleBox(ev.buttonDownPos(), ev.pos())
            else:
                tr = self.childGroup.transform()
                tr = pg.functions.invertQTransform(tr)
                tr = tr.map(dif*mask) - tr.map(pg.Point(0,0))

                x = tr.x() if mask[0] == 1 else None
                y = tr.y() if mask[1] == 1 else None

                self._resetTarget()
                if x is not None or y is not None:
                    self.translateBy(x=x, y=y)
                self.sigRangeChangedManually.emit(self.state['mouseEnabled'])
                if ev.isFinish():
                    self.add_region(self.viewRect())
        elif ev.button() & Qt.MouseButton.RightButton:
            #print "vb.rightDrag"
            if self.state['aspectLocked'] is not False:
                mask[0] = 0

            dif = ev.screenPos() - ev.lastScreenPos()
            dif = np.array([dif.x(), dif.y()])
            dif[0] *= -1
            s = ((mask * 0.02) + 1) ** dif

            tr = self.childGroup.transform()
            tr = pg.functions.invertQTransform(tr)

            x = s[0] if mouseEnabled[0] == 1 else None
            y = s[1] if mouseEnabled[1] == 1 else None

            center = pg.Point(tr.map(ev.buttonDownPos(Qt.MouseButton.RightButton)))
            self._resetTarget()
            self.scaleBy(x=x, y=y, center=center)
            self.sigRangeChangedManually.emit(self.state['mouseEnabled'])
            if ev.isFinish():
                self.add_region(self.viewRect())


    def updateScaleBox(self, p1, p2):
        r = QRectF(p1, p2)
        r = self.childGroup.mapRectFromParent(r)
        self.rbScaleBox.setPos(r.topLeft())
        tr = QTransform.fromScale(r.width(), r.height())
        self.rbScaleBox.setTransform(tr)
        self.rbScaleBox.show()

        
    def hide_region(self):
        self.rbScaleBox.hide()

        
    def add_region(self, rect):
        self.axHistoryPointer += 1
        self.axHistory = self.axHistory[:self.axHistoryPointer] + [rect]

        
    def zoom_region(self, rect):
        self.hide_region()
        self.showAxRect(rect)
        self.add_region(rect)


    def zoom_back(self):
        self.scaleHistory(-1)


    def zoom_forward(self):
        self.scaleHistory(1)


    def zoom_home(self):
        self.scaleHistory(-len(self.axHistory))


    def init_zoom_history(self):
        self.add_region(self.viewRect())

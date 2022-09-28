from PyQt5.QtCore import Signal
import pyqtgraph as pg


class TimePlot(pg.PlotItem):

    
    def __init__(self, channel, xwidth, tmax):
        pg.PlotItem.__init__(self)
        
        # axis:
        self.showAxes(True, False)
        #self.getAxis('bottom').setPen('black')
        #self.getAxis('left').setPen('black')
        self.getAxis('left').setWidth(8*xwidth)

        # design:
        self.getViewBox().setBackgroundColor(None)
        self.getViewBox().setDefaultPadding(padding=0.0)

        # functionality:
        self.hideButtons()
        self.setMenuEnabled(False)
        self.enableAutoRange(False, False)

        # view:
        self.setLimits(xMin=0, xMax=tmax,
                       minXRange=tmax, maxXRange=tmax)
        self.setXRange(0, tmax)
            

from PyQt5.QtCore import Signal
import pyqtgraph as pg


class TimePlot(pg.PlotItem):


    sigRegionChanged = Signal(object, object)

    
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
        self.setMouseEnabled(False, False)
        self.enableAutoRange(False, False)

        # region marker:
        self.region = pg.LinearRegionItem(pen=dict(color='#110353', width=2),
                                          brush=(34, 6, 167, 127),
                                          hoverPen=dict(color='#2206a7', width=2),
                                          hoverBrush=(34, 6, 167, 255))
        self.region.setZValue(10)
        super().addItem(self.region, ignoreBounds=True)
        self.region.sigRegionChanged.connect(self.update_time_range)

        # view:
        self.setLimits(xMin=0, xMax=tmax,
                       minXRange=tmax, maxXRange=tmax)
        self.setXRange(0, tmax)


    def addItem(self, item, *args, **kwargs):
        item.set_color('#2206a7')
        super().addItem(item, *args, **kwargs)
        self.region.setClipItem(item)

        
    def update_region(self, vbox, viewrange):
        self.region.setRegion(viewrange[0])


    def update_time_range(self):
        xmin, xmax = self.region.getRegion()
        self.sigRegionChanged.emit(xmin, xmax)

from math import floor
from PyQt5.QtCore import Signal
from PyQt5.QtWidgets import QGraphicsSimpleTextItem
import pyqtgraph as pg


def secs_to_str(time):
    hours = int(time//3600)
    time -= 3600*hours
    mins = int(time//60)
    time -= 60*mins
    secs = int(floor(time))
    time -= secs
    if hours > 0:
        return f'{hours}:{mins:02d}:{secs:02d}'
    elif mins > 0:
        return f'{mins:02d}:{secs:02d}'
    elif secs > 0:
        return f'{secs}.{1000*time:03.0f}s'
    else:
        return msecs


def secs_format(time):
    if time >= 3600.0:
        return 'h:mm:ss'
    elif time >= 60.0:
        return 'mm:ss'
    elif time > 1.0:
        return 's.ms'
    else:
        return 'ms'

    
class FullTracePlot(pg.GraphicsLayoutWidget):

    
    def __init__(self, data, rate, axtraces, *args, **kwargs):
        pg.GraphicsLayoutWidget.__init__(self, *args, **kwargs)

        self.data = data
        self.rate = rate
        self.tmax = len(self.data)/self.rate
        self.axtraces = axtraces

        self.setBackground(None)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setVerticalSpacing(0)

        # for each channel prepare a plot panel:
        xwidth = self.fontMetrics().averageCharWidth()
        self.axs = []
        self.regions = []
        self.labels = []
        for c in range(self.data.channels):
            # setup plot panel:
            axt = pg.PlotItem()
            axt.showAxes(True, False)
            axt.getAxis('left').setWidth(8*xwidth)
            axt.getViewBox().setBackgroundColor(None)
            axt.getViewBox().setDefaultPadding(padding=0.0)
            axt.hideButtons()
            axt.setMenuEnabled(False)
            axt.setMouseEnabled(False, False)
            axt.enableAutoRange(False, False)
            axt.setLimits(xMin=0, xMax=self.tmax,
                          minXRange=self.tmax, maxXRange=self.tmax)
            axt.setXRange(0, self.tmax)

            # add region marker:
            region = pg.LinearRegionItem(pen=dict(color='#110353', width=2),
                                         brush=(34, 6, 167, 127),
                                         hoverPen=dict(color='#2206a7', width=2),
                                         hoverBrush=(34, 6, 167, 255))
            region.setZValue(10)
            region.setRegion((self.axtraces[c].viewRange()[0]))
            region.sigRegionChanged.connect(self.update_time_range)
            self.axtraces[c].sigXRangeChanged.connect(self.update_region)
            axt.addItem(region, ignoreBounds=True)
            self.regions.append(region)

            # add time label:
            label = QGraphicsSimpleTextItem(axt.getAxis('left'))
            label.setToolTip(f'Total duration in {secs_format(self.tmax)}')
            label.setText(secs_to_str(self.tmax))
            label.setPos(int(xwidth), xwidth/2)
            self.labels.append(label)
            
            self.addItem(axt, row=c, col=0)
            self.axs.append(axt)

            # add data:
            #data = TraceItem(self.data, self.rate, c)
            #axt.addItem(data)
            #axt.update_region(axt.getViewBox(),
            #                  ((self.toffset, self.toffset + self.twindow),
            #                   (trace.ymin, trace.ymin)))
            #item.set_color('#2206a7')
            #self.setLimits(yMin=item.ymin, yMax=item.ymax,
            #               minYRange=1/2**16,
            #               maxYRange=item.ymax - item.ymin)
            ## autoscale the yrange!
            #self.region.setClipItem(item)


    def update_layout(self, channels, data_height):
        first = True
        for c in range(self.data.channels):
            self.axs[c].setVisible(c in channels)
            if c in channels:
                self.ci.layout.setRowFixedHeight(c, data_height)
                self.labels[c].setVisible(first)
                first = False
            else:
                self.ci.layout.setRowFixedHeight(c, 0)
                self.labels[c].setVisible(False)
        self.setFixedHeight(len(channels)*data_height)


    def update_time_range(self, region):
        xmin, xmax = region.getRegion()
        for ax, reg in zip(self.axtraces, self.regions):
            if reg is region:
                ax.setXRange(xmin, xmax)
                break


    def update_region(self, vbox, x_range):
        for ax, region in zip(self.axtraces, self.regions):
            if ax.getViewBox() is vbox:
                region.setRegion(x_range)
                break

        
    def mousePressEvent(self, ev):
        for ax, region in zip(self.axs, self.regions):
            pos = ax.getViewBox().mapSceneToView(ev.pos())
            [xmin, xmax], [ymin, ymax] = ax.viewRange()
            if xmin <= pos.x() <= xmax and ymin <= pos.y() <= ymax:
                dx = (xmax - xmin)/self.width()
                x = pos.x()
                xmin, xmax = region.getRegion()
                if x < xmin-2*dx or x > xmax + 2*dx:
                    dx = xmax - xmin
                    xmin = max(0, x - dx/2)
                    xmax = xmin + dx
                    if xmax > self.tmax:
                        xmin = max(0, xmax - dx)
                    region.setRegion((xmin, xmax))
                    ev.accept()
                    return
                break
        ev.ignore()
        super().mousePressEvent(ev)

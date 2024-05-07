"""FullTracePlot

## TODO
- secs_to_str and secs_format to extra module or even thunderlab?
- Have a class for a single channel that we could add to the toolbar.
- Only use Data class
"""

from math import floor, fabs
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QGraphicsSimpleTextItem, QApplication
import pyqtgraph as pg
from .traceitem import down_sample_peak


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
    elif time >= 0.01:
        return f'{1000*time:03.0f}ms'
    elif time >= 0.001:
        return f'{1000*time:.2f}ms'
    else:
        return f'{1e6*time:.0f}\u00b5s'


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

    
    def __init__(self, data, axtraces, *args, **kwargs):
        pg.GraphicsLayoutWidget.__init__(self, *args, **kwargs)

        self.data = data
        self.frames = self.data.frames
        self.tmax = self.frames/self.data.rate
        self.axtraces = axtraces
        self.no_signal = False

        self.setBackground(None)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setVerticalSpacing(0)

        # for each channel prepare a plot panel:
        xwidth = self.fontMetrics().averageCharWidth()
        self.axs = []
        self.lines = []
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
                                         hoverPen=dict(color='#aa77ff', width=2),
                                         hoverBrush=(34, 6, 167, 255),
                                         movable=True,
                                         swapMode='block')
            region.setZValue(50)
            region.setBounds((0, self.tmax))
            region.setRegion((self.axtraces[c].viewRange()[0]))
            region.sigRegionChanged.connect(self.update_time_range)
            self.axtraces[c].sigXRangeChanged.connect(self.update_region)
            axt.addItem(region)
            self.regions.append(region)

            # add time label:
            label = QGraphicsSimpleTextItem(axt.getAxis('left'))
            label.setToolTip(f'Total duration in {secs_format(self.tmax)}')
            label.setText(secs_to_str(self.tmax))
            label.setPos(int(xwidth), xwidth/2)
            self.labels.append(label)

            # init data:
            max_pixel = QApplication.desktop().screenGeometry().width()
            self.step = max(1, self.frames//max_pixel)
            self.index = 0
            self.nblock = int(20.0*self.data.rate//self.step)*self.step
            self.times = np.arange(0, self.frames, self.step/2)/self.data.rate
            self.datas = np.zeros((len(self.times), self.data.channels))
            
            # add data:
            line = pg.PlotDataItem(antialias=True,
                                   pen=dict(color='#2206a7', width=1.1),
                                   skipFiniteCheck=True, autDownsample=False)
            line.setZValue(10)
            axt.addItem(line)
            self.lines.append(line)

            # add zero line:
            zero_line = axt.addLine(y=0, movable=False, pen=dict(color='grey', width=1))
            zero_line.setZValue(20)
            
            self.addItem(axt, row=c, col=0)
            self.axs.append(axt)
            
        QTimer.singleShot(10, self.load_data)


    def load_data(self):
        i = 2*self.index//self.step
        n = min(self.nblock, self.frames - self.index)
        buffer = np.zeros((n, self.data.channels))
        self.data.load_buffer(self.index, n, buffer)
        for c in range(self.data.channels):
            data = down_sample_peak(buffer[:,c], self.step)
            self.datas[i:i+len(data), c] = data
            self.lines[c].setData(self.times, self.datas[:,c])
        self.index += n
        if self.index < self.frames:
            QTimer.singleShot(10, self.load_data)
        else:
            # TODO: do we really datas? Couldn't we take it from lines? 
            for c in range(self.data.channels):
                ymin = np.min(self.datas[:,c])
                ymax = np.max(self.datas[:,c])
                y = max(fabs(ymin), fabs(ymax))
                self.axs[c].setYRange(-y, y)
                self.axs[c].setLimits(yMin=-y, yMax=y,
                                      minYRange=2*y, maxYRange=2*y)
            self.times = None
            self.datas = None

        
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
        if self.no_signal:
            return
        self.no_signal = True
        xmin, xmax = region.getRegion()
        for ax, reg in zip(self.axtraces, self.regions):
            if reg is region:
                ax.setXRange(xmin, xmax)
                break
        self.no_signal = False


    def update_region(self, vbox, x_range):
        for ax, region in zip(self.axtraces, self.regions):
            if ax.getViewBox() is vbox:
                region.setRegion(x_range)
                break

        
    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
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

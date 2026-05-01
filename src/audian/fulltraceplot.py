"""FullTracePlot
"""

import numpy as np
import pyqtgraph as pg

from pathlib import Path
from math import floor
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QGraphicsSimpleTextItem, QLabel
from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QPalette

from .compresseddata import CompressedData


def secs_to_str(time, msec_level=10, precision=10):
    days = time//(24*3600)
    time -= (24*3600)*days
    hours = time//3600
    time -= 3600*hours
    mins = time//60
    time -= 60*mins
    secs = int(floor(time))
    time -= secs
    msecs = 1000*time
    if msecs >= 100:
        msec_str = f'{msecs:03.0f}ms'
    elif msecs >= 10:
        msec_str = f'{msecs:04.1f}ms'
    elif msecs >= 1:
        msec_str = f'{msecs:4.2f}ms'
    else:
        msec_str = f'{msecs:5.3f}ms'
    ts = []
    if days > 0:
        ts = [f'{days:.0f}d', f'{hours:.0f}h', f'{mins:.0f}m',
              f'{secs:.0f}s']
        if msec_level >= 4:
            ts.append(msec_str)
    elif hours > 0:
        ts = [f'{hours:.0f}h', f'{mins:.0f}m', f'{secs:.0f}s']
        if msec_level >= 3:
            ts.append(msec_str)
    elif mins > 0:
        ts = [f'{mins:.0f}m', f'{secs:.0f}s']
        if msec_level >= 2:
            ts.append(msec_str)
    elif secs > 0:
        ts = [f'{secs:.0f}s']
        if msec_level >= 1:
            ts.append(msec_str)
    elif msecs >= 1:
        ts = [msec_str]
    else:
        ts = [f'{1000*msecs:.0f}\u00b5s']
    if precision < 1:
        precision = 1
    return ''.join(ts[:precision])

    
class FullTracePlot(pg.GraphicsLayoutWidget):
    
    def __init__(self, data, axtraces, left_margin, *args, **kwargs):
        pg.GraphicsLayoutWidget.__init__(self, *args, **kwargs)

        self.data = data
        self.tmax = self.data.data.frames/self.data.rate
        self.axtraces = axtraces
        self.no_signal = False

        self.setBackground(None)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setVerticalSpacing(-1.7)
        
        # for each channel prepare a plot panel:
        xwidth = self.fontMetrics().averageCharWidth()
        self.axs = []
        self.lines = []
        self.regions = []
        self.labels = []
        self.data_height = None
        for c in range(self.data.channels):
            # setup plot panel:
            axt = pg.PlotItem()
            axt.showAxes(True, False)
            axt.getAxis('left').setWidth(left_margin)
            axt.getViewBox().setBackgroundColor(None)
            axt.getViewBox().setDefaultPadding(padding=0)
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
                                         hoverBrush=(34, 6, 167, 192),
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
            label.setToolTip('Total duration of the recording')
            label.setText(secs_to_str(self.tmax, 1, 2))
            label.setPos(int(xwidth), 0)
            self.labels.append(label)
            
            # add data:
            line = pg.PlotDataItem(antialias=True,
                                   pen=dict(color='#2206a7', width=1.1),
                                   skipFiniteCheck=True, autDownsample=False)
            line.setZValue(10)
            axt.addItem(line)
            self.lines.append(line)

            # add zero line:
            zero_line = axt.addLine(y=0, movable=False,
                                    pen=dict(color='grey', width=1))
            zero_line.setZValue(20)
            
            self.addItem(axt, row=c, col=0)
            self.axs.append(axt)

        self.time_info = QLabel(self)
        self.time_info.setWindowFlags(self.windowFlags()
                                      | Qt.BypassWindowManagerHint
                                      | Qt.FramelessWindowHint)
        self.time_info.setVisible(False)
        
        self.compressed_data = CompressedData(self.data.data)
            

    def __del__(self):
        self.close()

        
    def close(self):
        self.compressed_data.close()

        
    def polish(self):
        text_color = self.palette().color(QPalette.WindowText)
        for label in self.labels:
            label.setBrush(text_color)
        QTimer.singleShot(500, self.plot_data)


    def prepare(self):
        self.compressed_data.load_data()
        max_pixel = QApplication.desktop().screenGeometry().width()
        self.compressed_data.start(max_pixel, self.data.load_kwargs)
            

    def plot_data(self):

        def set_plot_ranges():
            for c in range(self.compressed_data.datas.shape[1]):
                ymin = np.min(self.compressed_data.datas[:, c])
                ymax = np.max(self.compressed_data.datas[:, c])
                y = max(abs(ymin), abs(ymax))
                self.axs[c].setYRange(-y, y)
                self.axs[c].setLimits(yMin=-y, yMax=y,
                                      minYRange=2*y, maxYRange=2*y)

        if not self.compressed_data.is_busy():
            for c in range(self.compressed_data.datas.shape[1]):
                self.lines[c].setData(self.compressed_data.times,
                                      self.compressed_data.datas[:, c])
            set_plot_ranges()
            self.compressed_data.save_data()
        else:
            lock = self.compressed_data.get_lock()
            if lock.acquire(block=False):
                for c in range(self.compressed_data.datas.shape[1]):
                    self.lines[c].setData(self.compressed_data.times,
                                          self.compressed_data.datas[:, c])
                lock.release()
            QTimer.singleShot(500, self.plot_data)

                    
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
        self.data_height = data_height


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
                if not ax.isVisible():
                    continue
                vb = ax.getViewBox()
                pos = vb.mapSceneToView(ev.pos())
                [xmin, xmax], [ymin, ymax] = ax.viewRange()
                if xmin <= pos.x() <= xmax and ymin <= pos.y() <= ymax:
                    dx = (xmax - xmin)/self.width()
                    x = pos.x()
                    rxmin, rxmax = region.getRegion()
                    if x < rxmin - 2*dx or x > rxmax + 2*dx:
                        rdx = rxmax - rxmin
                        rx0 = max(0, x - rdx/2)
                        rx1 = rx0 + rdx
                        if rx1 > self.tmax:
                            rx0 = max(0, rx1 - rdx)
                        region.setRegion((rx0, rx1))
                        ev.accept()
                        return
                    break
        ev.ignore()
        super().mousePressEvent(ev)


    def mouseMoveEvent(self, ev):
        for c, ax in enumerate(self.axs):
            if not ax.isVisible():
                continue
            vb = ax.getViewBox()
            pos = vb.mapSceneToView(ev.pos())
            [xmin, xmax], [ymin, ymax] = ax.viewRange()
            if xmin <= pos.x() <= xmax and ymin <= pos.y() <= ymax:
                ts = '<style type="text/css"> td { padding: 0 4px; } </style>'
                ts += f'<table><tr><td colspan="2">channel</td><td><b>{c}</b></td><td></td></tr>'
                taxis = self.axtraces[c].getAxis('bottom')
                for sm in range(3):
                    label, units, vals, fname = \
                        taxis.makeStrings([pos.x()], 1, 1, sm, True)
                    if sm > 0 and label == 'REC':
                        continue
                    if label == 'File':
                        fname = Path(fname).name
                    else:
                        fname = ''
                    ts += f'<tr><td>{label}</td><td>({units})</td><td align="right"><b>{vals[0]}</b></td><td>{fname}</td></tr>'
                ts += '</table>'
                self.time_info.setText(ts)
                self.time_info.setVisible(True)
                x = ev.globalPos().x() + 10
                pos = self.mapToGlobal(self.pos())
                if x + self.time_info.width() > pos.x() + self.width():
                    x = pos.x() + self.width() - self.time_info.width()
                y = ev.globalPos().y()
                y -= self.time_info.height() + self.data_height//2
                self.time_info.move(x, y)
                break
        else:
            self.time_info.setVisible(False)
        super().mouseMoveEvent(ev)
        

    def leaveEvent(self, ev):
        self.time_info.setVisible(False)
        super().leaveEvent(ev)

"""FullTracePlot

## TODO
- secs_to_str to extra module or even thunderlab?
- Have a class for a single channel that we could add to the toolbar.
- Only use Data class
"""

import os
from math import floor
import numpy as np
import ctypes as c
from multiprocessing import Process, Array
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QGraphicsSimpleTextItem, QApplication
from PyQt5.QtGui import QPalette
import pyqtgraph as pg
from thunderlab.dataloader import DataLoader
from .traceitem import down_sample_peak


def secs_to_str(time, msec_level=10):
    days = time//(24*3600)
    time -= (24*3600)*days
    hours = time//3600
    time -= 3600*hours
    mins = time//60
    time -= 60*mins
    secs = int(np.floor(time))
    time -= secs
    msecs = f'{1000*time:03.0f}ms'
    if days > 0:
        if msec_level < 4:
            msecs = ''
        return f'{days:.0f}d{hours:.0f}h{mins:.0f}m{secs:.0f}s{msecs}'
    elif hours > 0:
        if msec_level < 3:
            msecs = ''
        return f'{hours:.0f}h{mins:.0f}m{secs:.0f}s{msecs}'
    elif mins > 0:
        if msec_level < 2:
            msecs = ''
        return f'{mins:.0f}m{secs:.0f}s{msecs}'
    elif secs > 0:
        if msec_level < 1:
            msecs = ''
        return f'{secs:.0f}s{msecs}'
    elif time >= 0.01:
        return msecs
    elif time >= 0.001:
        return f'{1000*time:.2f}ms'
    else:
        return f'{1e6*time:.0f}\u00b5s'

    
def down_sample(proc_idx, num_proc, nblock, step, array,
                file_paths, tbuffer, rate, channels, unit, amax, end_indices,
                unwrap_thresh, unwrap_clips, load_kwargs):
    """ Worker for prepare() """
    if end_indices is None:
        data = DataLoader(file_paths, tbuffer, 0,
                          verbose=0, **load_kwargs)
    else:
        data = DataLoader(file_paths, tbuffer, 0,
                          verbose=0, rate=rate, channels=channels,
                          unit=unit, amax=amax, end_indices=end_indices,
                          **load_kwargs)
    data.set_unwrap(unwrap_thresh, unwrap_clips, False, data.unit)
    datas = np.frombuffer(array.get_obj()).reshape((-1, data.channels))
    buffer = np.zeros((nblock, data.channels))
    for index in range(proc_idx*nblock, data.frames, num_proc*nblock):
        if data.frames - index < nblock:
            nblock = data.frames - index
            buffer = np.zeros((nblock, data.channels))
        data.load_buffer(index, nblock, buffer)
        i = 2*index//step
        n = 2*len(buffer)//step
        with array.get_lock():
            ds_data = down_sample_peak(buffer, step,
                                       datas[i:i + n, :])
    return None
        
    
class FullTracePlot(pg.GraphicsLayoutWidget):

    
    def __init__(self, data, axtraces, *args, **kwargs):
        pg.GraphicsLayoutWidget.__init__(self, *args, **kwargs)

        self.data = data
        self.tmax = self.data.data.frames/self.data.rate
        self.axtraces = axtraces
        self.no_signal = False
        self.procs = []

        self.setBackground(None)
        self.ci.layout.setContentsMargins(0, 0, 0, 0)
        self.ci.layout.setVerticalSpacing(-1.7)
        
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
            label.setToolTip('Total duration of the recording')
            label.setText(secs_to_str(self.tmax, 1))
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

        self.shared_array = None
        self.times = None
        self.datas = None
        self.index = 0


    def __del__(self):
        self.close()

        
    def close(self):
        for proc in self.procs:
            proc.terminate()
            proc.join()
            proc.close()
        self.procs = []

        
    def polish(self):
        text_color = self.palette().color(QPalette.WindowText)
        for label in self.labels:
            label.setBrush(text_color)
        QTimer.singleShot(500, self.plot_data)


    def prepare(self):
        max_pixel = QApplication.desktop().screenGeometry().width()
        step = max(1, self.data.frames//max_pixel)
        nblock = int(20.0*self.data.rate//step)*step
        end_indices = None
        if len(self.data.data.file_paths) > 1:
            end_indices = self.data.data.end_indices
        self.times = np.arange(0, self.data.data.frames,
                               step/2)/self.data.rate
        self.shared_array = Array(c.c_double, len(self.times)*self.data.channels)
        self.datas = np.frombuffer(self.shared_array.get_obj())
        self.datas = self.datas.reshape((len(self.times), self.data.channels))
        self.procs = []
        nprocs = os.cpu_count() - 1 # the more processes the more memory is used!
        for i in range(max(1, nprocs)):
            p = Process(target=down_sample,
                        args=(i, nprocs, nblock, step,
                              self.shared_array,
                              self.data.data.file_paths,
                              nblock/self.data.rate + 0.1,
                              self.data.rate, self.data.channels,
                              self.data.data.unit, self.data.data.ampl_max,
                              end_indices,
                              self.data.data.unwrap_thresh,
                              self.data.data.unwrap_clips,
                              self.data.load_kwargs))
            p.start()
            self.procs.append(p)
            

    def plot_data(self):
        with self.shared_array.get_lock():
            for c in range(self.data.channels):
                self.lines[c].setData(self.times, self.datas[:,c])
        done = True
        for proc in self.procs:
            if proc.is_alive():
                done = False
                break
        if done:
            for proc in self.procs:
                proc.close()
            self.procs = []
            for c in range(self.data.channels):
                ymin = np.min(self.datas[:,c])
                ymax = np.max(self.datas[:,c])
                y = max(abs(ymin), abs(ymax))
                self.axs[c].setYRange(-y, y)
                self.axs[c].setLimits(yMin=-y, yMax=y,
                                      minYRange=2*y, maxYRange=2*y)
        else:
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

from math import floor, ceil
import numpy as np
from PyQt5.QtWidgets import QApplication
import pyqtgraph as pg

has_numba = False
try:
    from numba import jit
    has_numba = True
except ImportError:
    def jit(*args, **kwargs):
        def decorator_jit(func):
            return func
        return decorator_jit


@jit(nopython=True)
def down_sample_peak(data, step):
    n = len(data)//step
    ddata = np.zeros(2*n)
    for k in range(n):
        dd = data[k*step:(k+1)*step]
        ddata[2*k] = np.min(dd)
        ddata[2*k+1] = np.max(dd)
    return ddata

    
class TraceItem(pg.PlotDataItem):
    
    def __init__(self, data, rate, channel, *args, color='#00ee00', **kwargs):
        self.data = data
        self.rate = rate
        self.channel = channel
        self.color = color
        self.ymin = -1.0
        self.ymax = +1.0
        
        pg.PlotDataItem.__init__(self, *args, connect='all',
                                 antialias=False, skipFiniteCheck=True,
                                 **kwargs)
        self.setPen(dict(color=self.color, width=2))
        self.setSymbolSize(8)
        self.setSymbolBrush(color=self.color)
        self.setSymbolPen(color=self.color)
        self.setSymbol(None)


    def set_color(self, color):
        self.color = color
        self.setPen(dict(color=self.color, width=2))
        self.setSymbolBrush(color=self.color)
        self.setSymbolPen(color=self.color)

        
    def viewRangeChanged(self):
        self.updateTrace()
    

    def updateTrace(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return

        # time:
        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        max_pixel = QApplication.desktop().screenGeometry().width()
        step = max(1, (stop - start)//max_pixel)
        if step > 1:
            start = int(floor(start/step)*step)
            stop = int(ceil(stop/step)*step)
            self.setPen(dict(color=self.color, width=1.1))
            step2 = step//2
            step = step2*2
            n = (stop-start)//step
            data = np.zeros(2*n)
            i = 0
            nb = int(60*self.rate//step)*step
            for dd in self.data.blocks(nb, 0, start, stop):
                if has_numba:
                    dsd = down_sample_peak(dd[:, self.channel], step)
                    data[i:i+len(dsd)] = dsd
                    i += len(dsd)
                #else:
                #    data = np.array([(np.min(self.data[start+k*step:start+(k+1)*step, self.channel]), np.max(self.data[start+k*step:start+(k+1)*step, self.channel])) for k in range(n)]).reshape((-1))
            time = np.arange(start, start + len(data)*step2, step2)/self.rate
            self.setData(time, data) #, connect='pairs')???
        elif step > 1:  # TODO: not used
            # subsample:
            self.setData(np.arange(start, stop, step)/self.rate,
                         self.data[start:stop:step, self.channel])
            self.setPen(dict(color=self.color, width=1.1))
        else:
            # all data:
            self.setData(np.arange(start, stop)/self.rate,
                         self.data[start:stop, self.channel])
            self.setPen(dict(color=self.color, width=2))
            if stop - start <= 50:
                self.setSymbol('o')
            else:
                self.setSymbol(None)


    def zoom_ampl_in(self):
        h = 0.25*(self.ymax - self.ymin)
        c = 0.5*(self.ymax + self.ymin)
        if h > 1/2**16:
            self.ymin = c - h
            self.ymax = c + h

        
    def zoom_ampl_out(self):
        h = self.ymax - self.ymin
        c = 0.5*(self.ymax + self.ymin)
        self.ymin = c - h
        self.ymax = c + h
        if self.ymax > 1:
            self.ymax = 1
            self.ymin = 1 - 2*h
        if self.ymin < -1:
            self.ymin = -1
        
        
    def auto_ampl(self, toffset, twindow):
        t0 = int(np.round(toffset * self.rate))
        t1 = int(np.round((toffset + twindow) * self.rate))
        ymin = np.min(self.data[t0:t1, self.channel])
        ymax = np.max(self.data[t0:t1, self.channel])
        h = 0.5*(ymax - ymin)
        
        c = 0.5*(ymax + ymin)
        if h < 1/2**16:
            h = 1/2**16
        self.ymin = c - h
        self.ymax = c + h

        
    def reset_ampl(self):
        self.ymin = -1.0
        self.ymax = +1.0


    def center_ampl(self):
        dy = self.ymax - self.ymin
        self.ymin = -dy/2
        self.ymax = +dy/2
        

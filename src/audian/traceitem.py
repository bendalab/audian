from math import fabs, floor, ceil
import numpy as np
import scipy.signal as sig
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
        self.step = 1
        self.color = color
        self.ymin = self.data.ampl_min
        self.ymax = self.data.ampl_max
        self.highpass_cutoff = None
        self.lowpass_cutoff = None
        self.sos = None
        
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
        sstop = int(trange[1]*self.rate+1)
        max_pixel = QApplication.desktop().screenGeometry().width()
        self.step = max(1, (sstop - start)//max_pixel)
        if self.step > 1:
            step2 = self.step//2
            self.step = step2*2
            start = int(floor(start/self.step)*self.step)
            stop = int(ceil(stop/self.step)*self.step)
            self.setPen(dict(color=self.color, width=1.1))
            n = (stop-start)//self.step
            data = np.zeros(2*n)
            i = 0
            nb = int(60*self.rate//self.step)*self.step
            for dd in self.data.blocks(nb, 0, start, stop):
                db = dd[:, self.channel]
                if self.sos is not None:
                    # TODO: extend data!!!
                    db = sig.sosfiltfilt(self.sos, db)
                if has_numba:
                    dsd = down_sample_peak(db, self.step)
                    data[i:i+len(dsd)] = dsd
                    i += len(dsd)
                #else:
                #    data = np.array([(np.min(self.data[start+k*self.step:start+(k+1)*self.step, self.channel]), np.max(self.data[start+k*self.step:start+(k+1)*self.step, self.channel])) for k in range(n)]).reshape((-1))
            time = np.arange(start, start + len(data)*step2, step2)/self.rate
            #print('T', time[0], time[-1])
            self.setData(time, data) #, connect='pairs')???
        elif self.step > 1:  # TODO: not used
            # subsample:
            self.setData(np.arange(start, stop, self.step)/self.rate,
                         self.data[start:stop:self.step, self.channel])
            self.setPen(dict(color=self.color, width=1.1))
        else:
            # all data:
            self.setData(np.arange(start, stop)/self.rate,
                         self.data[start:stop, self.channel])
            self.setPen(dict(color=self.color, width=2))
            if max_pixel/(stop - start) >= 10:
                self.setSymbol('o')
            else:
                self.setSymbol(None)


    def get_amplitude(self, x, y, x1=None):
        """Get trace amplitude next to cursor position. """
        idx = int(np.round(x*self.rate))
        step = self.step
        if x1 is not None:
            idx1 = int(np.round(x1*self.rate))
            step = max(1, idx1 - idx)
        if step > 1:
            idx = (idx//step)*step
            data_block = self.data[idx:idx + step, self.channel]
            mini = np.argmin(data_block)
            maxi = np.argmax(data_block)
            amin = data_block[mini]
            amax = data_block[maxi]
            if fabs(y - amax) < fabs(y - amin):
                return (idx+maxi)/self.rate, amax
            else:
                return (idx+mini)/self.rate, amin
        else:
            return idx/self.rate, self.data[idx, self.channel]

        
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
        if self.ymax > self.data.ampl_max:
            self.ymax = self.data.ampl_max
            self.ymin = 1 - 2*h
        if self.ymin < self.data.ampl_min:
            self.ymin = self.data.ampl_min
        
        
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
        self.ymin = self.data.ampl_min
        self.ymax = self.data.ampl_max


    def center_ampl(self):
        dy = self.ymax - self.ymin
        self.ymin = -dy/2
        self.ymax = +dy/2


    def set_filter(self, highpass_cutoff, lowpass_cutoff):
        if highpass_cutoff is not None:
            self.highpass_cutoff = highpass_cutoff
        if lowpass_cutoff is not None:
            self.lowpass_cutoff = lowpass_cutoff
        if self.highpass_cutoff < 1e-8 and \
           self.lowpass_cutoff >= self.rate/2-1e-8:
            self.sos = None
        elif self.highpass_cutoff < 1e-8:
            self.sos = sig.butter(2, self.lowpass_cutoff,
                                  'lowpass', fs=self.rate, output='sos')
        elif self.lowpass_cutoff >= self.rate/2-1e-8:
            self.sos = sig.butter(2, self.highpass_cutoff,
                                  'highpass', fs=self.rate, output='sos')
        else:
            self.sos = sig.butter(2, (self.highpass_cutoff, self.lowpass_cutoff),
                                  'bandpass', fs=self.rate, output='sos')
        self.updateTrace()
        

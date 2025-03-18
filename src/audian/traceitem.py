"""PlotDataItem for time series trace as a function of time.
"""

from math import fabs, floor, ceil
import numpy as np
from PyQt5.QtWidgets import QApplication
import pyqtgraph as pg


class TraceItem(pg.PlotDataItem):
    
    def __init__(self, data, channel, *args, **kwargs):
        self.data = data
        self.rate = self.data.rate
        self.channel = channel
        self.step = 1
        self.color = self.data.color
        self.lw_thin = self.data.lw_thin
        self.lw_thick = self.data.lw_thick

        self.data.plot_items[self.channel] = self
        
        pg.PlotDataItem.__init__(self, *args, connect='all',
                                 antialias=False, skipFiniteCheck=True,
                                 **kwargs)
        self.setPen(dict(color=self.color, width=self.lw_thin))
        self.setSymbolSize(8)
        self.setSymbolBrush(color=self.color)
        self.setSymbolPen(color=self.color)
        self.setSymbol(None)


    def update_plot(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return
        t0, t1 = vb.viewRange()[0]
        
        start = max(0, int(t0*self.rate))
        tstop = int(t1*self.rate+1)
        stop = min(len(self.data), tstop)
        max_pixel = QApplication.desktop().screenGeometry().width()
        self.step = max(1, (tstop - start)//max_pixel)
        if self.step > 1:
            start = int(floor(start/self.step)*self.step)
            stop = int(ceil(stop/self.step + 1)*self.step)
            self.setPen(dict(color=self.color, width=self.lw_thin))
            self.setSymbol(None)
            npdata = (stop - start)//self.step
            pdata = np.zeros(2*npdata)
            i = 0
            nb = (self.data.bufferframes//self.step)*self.step
            # downsample using min and max during step frames:
            for dd in self.data.blocks(nb, 0, start, stop):
                n = 2*len(dd)//self.step
                dbuffer = dd.reshape(-1, self.step, dd.shape[1])
                pdata[i + 0:i + n:2] = np.min(dbuffer[:, :, self.channel], 1)
                pdata[i + 1:i + n:2] = np.max(dbuffer[:, :, self.channel], 1)
                i += n
            step2 = self.step/2
            time = np.arange(start, start + len(pdata)*step2, step2)/self.rate
            self.setData(time, pdata)
        elif self.step > 1:  # TODO: not used
            # subsample:
            self.setData(np.arange(start, stop, self.step)/self.rate,
                         self.data[start:stop:self.step, self.channel])
            self.setPen(dict(color=self.color, width=self.lw_thin))
        else:
            # all data:
            self.setData(np.arange(start, stop)/self.rate,
                         self.data[start:stop, self.channel])
            self.setPen(dict(color=self.color, width=self.lw_thick))
            if max_pixel/(stop - start) >= 10:
                self.setSymbol('o')
            else:
                self.setSymbol(None)
        self.data.buffer_changed[self.channel] = False


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


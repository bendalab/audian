"""PlotDataItem for time series trace as a function of time.
"""

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
        # index range and steps that needs to be drawn:
        t0, t1 = vb.viewRange()[0]
        start = max(0, int(t0*self.rate))
        tstop = int(t1*self.rate + 1)
        stop = min(len(self.data), tstop)
        max_pixel = QApplication.desktop().screenGeometry().width()
        self.step = max(1, (tstop - start)//max_pixel)
        if self.step > 1:
            # downsample aligned to multiple of step:
            start = (start//self.step)*self.step
            tstop = (stop//self.step + 1)*self.step
            stop = min(len(self.data), tstop)
            # stay within loaded buffer:
            while start < self.data.offset:
                start += step
            while stop > self.data.offset + len(self.data.buffer):
                stop -= step
            # init plot buffer:
            plot_size = (stop - start + self.step - 1)//self.step
            plot_data = np.zeros(2*plot_size)
            # downsample using min and max during step frames:
            segments = np.arange(0, stop - start, self.step)
            mind = np.minimum.reduceat(self.data[start:stop, self.channel],
                                       segments)
            maxd = np.maximum.reduceat(self.data[start:stop, self.channel],
                                       segments)
            plot_data[0::2] = mind
            plot_data[1::2] = maxd
            step2 = self.step/2
            time = np.arange(start, start + len(plot_data)*step2, step2)/self.rate
            self.setPen(dict(color=self.color, width=self.lw_thin))
            self.setSymbol(None)
            self.setData(time, plot_data)
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
            if abs(y - amax) < abs(y - amin):
                return (idx+maxi)/self.rate, amax
            else:
                return (idx+mini)/self.rate, amin
        else:
            return idx/self.rate, self.data[idx, self.channel]

        
if __name__ == '__main__':
    """Runtime of various ways to compute the miminum and maximum of
    chunks of data as used by audian for downsampling for plotting.

    See also https://stackoverflow.com/questions/61255208/finding-the-maximum-in-a-numpy-array-every-nth-instance

    reduceat_arange() is fastest!

    step = 1:
      full                : 0.0066
      numba               : 0.0868
      reshaped            : 0.0111
      reduceat            : 0.0205
      reduceat_arange     : 0.0194
      reduceat_range      : 0.1545
    step = 10:
      full                : 0.0110
      numba               : 0.0974
      reshaped            : 0.1193
      reduceat            : 0.0700
      reduceat_arange     : 0.0687
      reduceat_range      : 0.2231
    step = 100:
      full                : 0.0611
      numba               : 0.3395
      reshaped            : 0.2093
      reduceat            : 0.1425
      reduceat_arange     : 0.1185
      reduceat_range      : 0.2648
    step = 1000:
      full                : 1.0589
      numba               : 2.8914
      reshaped            : 1.2120
      reduceat            : 1.1114
      reduceat_arange     : 1.0893
      reduceat_range      : 1.2402
    """
    
    from numba import njit
    from timeit import Timer


    def setup(step=100):
        x = np.random.randn(1000*step)
        n = 2*len(x)//step
        y = np.zeros(n)
        return x, y, step


    def full(x, y, step):
        y[0] = np.min(x)
        y[1] = np.max(x)


    @njit()
    def numba(x, y, step):
        for i in range(0, len(x)//step):
            i0 = i*step
            y[2*i + 0] = np.min(x[i0:i0 + step])
            y[2*i + 1] = np.max(x[i0:i0 + step])


    def reshaped(x, y, step):
        n = len(y)
        y[0:n:2] = np.min(x.reshape(-1, step), 1)
        y[1:n:2] = np.max(x.reshape(-1, step), 1)


    def reduceat(x, y, step):
        n = len(y)
        y[0:n:2] = np.minimum.reduceat(x, np.arange(0, len(x), step))
        y[1:n:2] = np.maximum.reduceat(x, np.arange(0, len(x), step))


    def reduceat_arange(x, y, step):
        n = len(y)
        r = np.arange(0, len(x), step)
        y[0:n:2] = np.minimum.reduceat(x, r)
        y[1:n:2] = np.maximum.reduceat(x, r)


    def reduceat_range(x, y, step):
        n = len(y)
        r = range(0, len(x), step)
        y[0:n:2] = np.minimum.reduceat(x, r)
        y[1:n:2] = np.maximum.reduceat(x, r)

    def timeit():
        # init numba:
        x, y, step = setup(10)
        numba(x, y, step)
        # time it:
        repeats = 20
        for step in [1, 10, 100, 1000]:
            print(f'step = {step}:')
            for f in ['full', 'numba', 'reshaped', 'reduceat',
                      'reduceat_arange', 'reduceat_range']:
                t = Timer(f'{f}(x, y, step)', f'x, y, step = setup({step})',
                          globals=globals())
                times = sorted(t.repeat(repeats, 1000))
                print(f'  {f:<20s}: {np.mean(times[:5]):.4f}')

    #########################################################
    timeit()
    


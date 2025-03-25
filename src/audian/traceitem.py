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
            # downsample aligned to multiples of step:
            start = (start//self.step)*self.step
            tstop = (stop//self.step + 1)*self.step
            stop = min(len(self.data), tstop)
            # stay within loaded buffer:
            while start < self.data.offset:
                start += self.step
            while stop > self.data.offset + len(self.data.buffer):
                stop -= self.step
            # init plot buffer:
            segments = np.arange(0, stop - start, self.step)
            plot_data = np.zeros(2*len(segments))
            # downsample using min and max during step frames:
            np.minimum.reduceat(self.data[start:stop, self.channel],
                                segments, out=plot_data[0::2])
            np.maximum.reduceat(self.data[start:stop, self.channel],
                                segments, out=plot_data[1::2])
            step2 = self.step/2
            plot_time = np.arange(start, start + len(plot_data)*step2,
                                  step2)/self.rate
            self.setPen(dict(color=self.color, width=self.lw_thin))
            self.setSymbol(None)
            self.setData(plot_time, plot_data)
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

        
    def reduce(x, y, step):
        y[0] = np.minimum.reduce(x)
        y[1] = np.maximum.reduce(x)

        
    @njit()
    def numba(x, y, step):
        for i in range(0, len(x)//step):
            i0 = i*step
            y[2*i + 0] = np.min(x[i0:i0 + step])
            y[2*i + 1] = np.max(x[i0:i0 + step])

            
    def reshape(x, y, step):
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

        
    def reduceat_out(x, y, step):
        n = len(y)
        r = np.arange(0, len(x), step)
        np.minimum.reduceat(x, r, out=y[0:n:2])
        np.maximum.reduceat(x, r, out=y[1:n:2])

        
    def reduceat_range(x, y, step):
        n = len(y)
        r = range(0, len(x), step)
        y[0:n:2] = np.minimum.reduceat(x, r)
        y[1:n:2] = np.maximum.reduceat(x, r)


    def timeit():
        """Runtime of various ways to compute the miminum and maximum of
        chunks of data as used by audian for downsampling for plotting.

        See also https://stackoverflow.com/questions/61255208/finding-the-maximum-in-a-numpy-array-every-nth-instance

        reduceat_out() is fastest!
        
        step = 1:
          full                : 0.0055
          reduce              : 0.0028
          numba               : 0.0784
          reshape             : 0.0091
          reduceat            : 0.0193
          reduceat_arange     : 0.0182
          reduceat_out        : 0.0166
          reduceat_range      : 0.1446
        step = 10:
          full                : 0.0094
          reduce              : 0.0062
          numba               : 0.0884
          reshape             : 0.1113
          reduceat            : 0.0667
          reduceat_arange     : 0.0656
          reduceat_out        : 0.0629
          reduceat_range      : 0.2028
        step = 100:
          full                : 0.0543
          reduce              : 0.0479
          numba               : 0.2973
          reshape             : 0.1922
          reduceat            : 0.1289
          reduceat_arange     : 0.1265
          reduceat_out        : 0.1248
          reduceat_range      : 0.2853
        step = 1000:
          full                : 1.3660
          reduce              : 1.3529
          numba               : 2.7436
          reshape             : 1.5176
          reduceat            : 1.4344
          reduceat_arange     : 1.4289
          reduceat_out        : 1.4229
          reduceat_range      : 1.6014
        """
        # init numba:
        x, y, step = setup(10)
        numba(x, y, step)
        # time it:
        repeats = 20
        for step in [1, 10, 100, 1000]:
            print(f'step = {step}:')
            for f in ['full', 'reduce', 'numba', 'reshape', 'reduceat',
                      'reduceat_arange', 'reduceat_out', 'reduceat_range']:
                t = Timer(f'{f}(x, y, step)', f'x, y, step = setup({step})',
                          globals=globals())
                times = sorted(t.repeat(repeats, 1000))
                print(f'  {f:<20s}: {np.mean(times[:5]):.4f}')


    def reduceat_output():
        """len of reduceat is same as len of indices.
        """
        step = 4
        for n in range(1, 15):
            x = np.arange(0, n, 1.0)
            r = np.arange(0, len(x), step)
            y = np.maximum.reduceat(x, r)
            print(f'x:{len(x):3d}  s:{step:2d}  r:{len(r):2d}  y:{len(y):2d}  (x+step-1)/s:{(len(x) + step - 1)//step:2d} ',
                  x, '->', y)

        
    #######################################################################
    reduceat_output()
    print()
    #timeit()
    


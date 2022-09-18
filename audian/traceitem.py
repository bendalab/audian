import numpy as np
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
def down_sample_peak(data, n, step):
    ddata = np.zeros(2*n)
    for k in range(n):
        ddata[2*k] = np.min(data[k*step:(k+1)*step])
        ddata[2*k+1] = np.max(data[k*step:(k+1)*step])
    return ddata

    
class TraceItem(pg.PlotDataItem):
    
    def __init__(self, data, rate, channel, *args, **kwargs):
        self.data = data
        self.rate = rate
        self.channel = channel
        self.ymin = -1.0
        self.ymax = +1.0
        
        pg.PlotDataItem.__init__(self, *args, connect='all',
                                 antialias=False, skipFiniteCheck=True,
                                 **kwargs)
        self.setPen(dict(color='#00ff00', width=2))
        self.setSymbolSize(8)
        self.setSymbolBrush(color='#00ff00')
        self.setSymbolPen(color='#00ff00')
        self.setSymbol(None)

        
    def viewRangeChanged(self):
        self.updateTrace()
    

    def updateTrace(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return

        # amplitude:
        yrange = vb.viewRange()[1]
        self.ymin = yrange[0]
        self.ymax = yrange[1]

        # time:
        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        step = max(1, (stop - start)//10000)
        if step > 1:
            self.setPen(dict(color='#00ff00', width=1.1))
            # min - max: (good but a bit slow - let numba do it!)
            step2 = step//2
            step = step2*2
            n = (stop-start)//step
            if has_numba:
                data = down_sample_peak(self.data[start:stop, self.channel],
                                        n, step)
            else:
                data = np.array([(np.min(self.data[start+k*step:start+(k+1)*step, self.channel]), np.max(self.data[start+k*step:start+(k+1)*step, self.channel])) for k in range(n)]).reshape((-1))
            time = np.arange(start, start + len(data)*step2, step2)/self.rate
            self.setData(time, data) #, connect='pairs')???
        elif step > 1:  # TODO: not used
            # subsample:
            self.setData(np.arange(start, stop, step)/self.rate,
                         self.data[start:stop:step, self.channel])
            self.setPen(dict(color='#00ff00', width=1.1))
        else:
            # all data:
            self.setData(np.arange(start, stop)/self.rate,
                         self.data[start:stop, self.channel])
            self.setPen(dict(color='#00ff00', width=2))
            if stop - start <= 50:
                self.setSymbol('o')
            else:
                self.setSymbol(None)


    def zoom_ampl_in(self):
        h = 0.25*(self.ymax - self.ymin)
        c = 0.5*(self.ymax + self.ymin)
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
        self.ymin = c - h
        self.ymax = c + h

        
    def reset_ampl(self):
        self.ymin = -1.0
        self.ymax = +1.0


    def center_ampl(self):
        dy = self.ymax - self.ymin
        self.ymin = -dy/2
        self.ymax = +dy/2
        

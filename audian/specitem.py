import numpy as np
from scipy.signal import spectrogram
import pyqtgraph as pg


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, rate, channel, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data
        self.rate = rate
        self.channel = channel
        self.fmin = 0.0
        self.fmax = 0.5/self.rate
        self.zmin = -100.0
        self.zmax = 0.0

        self.nfft = 2048//4
        freq, time, Sxx = spectrogram(self.data[:, self.channel], self.rate, nperseg=self.nfft, noverlap=self.nfft/2)
        Sxx = 10*np.log10(Sxx)
        #print(np.max(Sxx))
        self.zmax = np.percentile(Sxx, 99.9) + 5.0
        #self.zmin = np.percentile(Sxx, 70.0)
        #self.zmax = -20
        self.zmin = self.zmax - 60
        self.fmax = freq[-1]

        self.setImage(Sxx, autoLevels=False)
        self.scale(time[-1]/len(time), freq[-1]/len(freq))

        
    def viewRangeChanged(self):
        self.update()
    

    def update(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return

        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        step = max(1, (stop - start)//10000)

import numpy as np
from scipy.signal import spectrogram
from thunderlab.powerspectrum import decibel
from PyQt5.QtCore import QRectF
import pyqtgraph as pg


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, channel, nfft, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data.data  # or data.filtered?
        self.rate = self.data.rate
        self.channel = channel
        self.offset = -1
        self.buffer_size = 0
        self.nfft = nfft
        self.tresolution = None
        self.fresolution = self.rate/self.nfft
        self.step_frac = 0.5
        self.current_nfft = 1
        self.current_step = 1
        self.fmax = 0.5/self.rate
        self.zmin, self.zmax = self.set_resolution(nfft, 0.5, True)
        self.f0 = 0.0
        self.f1 = self.fmax
        self.cbar = None
        #self.spectrum = None


    def set_resolution(self, nfft=None, step_frac=None, update=True):
        if not nfft is None:
            self.nfft = nfft
        self.fresolution = self.rate/self.nfft
        if not step_frac is None:
            self.step_frac = step_frac
            if self.step_frac > 1.0:
                self.step_frac = 1.0
        self.step = int(np.round(self.step_frac * self.nfft))
        if self.step < 1:
            self.step = 1
        if update:
            return self.update_spectrum()


    def setCBar(self, cbar):
        self.cbar = cbar


    def set_power(self, zmin, zmax):
        if not zmin is None:
            self.zmin = zmin
        if not zmax is None:
            self.zmax = zmax
        self.setLevels((self.zmin, self.zmax), update=True)
        if not self.cbar is None:
            self.cbar.setLevels((self.zmin, self.zmax))

        
    def viewRangeChanged(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return
        
        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        if start < self.data.offset or stop >= self.data.offset + len(self.data.buffer):
            self.data.update_buffer(start, stop)
        self.update_spectrum()
    

    def update_spectrum(self):
        if len(self.data.buffer) == 0:
            return 0, 1
        if self.offset == self.data.offset and \
           self.buffer_size == len(self.data.buffer) and \
           self.current_nfft == self.nfft and \
           self.current_step == self.step:
            return 0, 1
        
        # takes very long:
        freq, time, Sxx = spectrogram(self.data.buffer[:, self.channel],
                                      self.rate, nperseg=self.nfft,
                                      noverlap=self.nfft-self.step)
        self.tresolution = time[1] - time[0]
        self.fresolution = freq[1] - freq[0]
        self.spectrum = decibel(Sxx)
        # estimate noise floor for color map:
        nf = len(freq)//16
        if nf < 1:
            nf = 1
        zmin = np.percentile(self.spectrum[-nf:,:], 95.0)
        if not np.isfinite(zmin):
            zmin = -100.0
        zmax = zmin + 60.0
        self.fmax = freq[-1]
        self.setImage(self.spectrum, autoLevels=False)
        self.setRect(QRectF(self.data.offset/self.rate, 0,
                            time[-1] + self.tresolution,
                            freq[-1] + self.fresolution))
        self.offset = self.data.offset
        self.buffer_size = len(self.data.buffer)
        self.current_nfft = self.nfft
        self.current_step = self.step
        return zmin, zmax

                
    def zoom_freq_in(self):
        df = self.f1 - self.f0
        if df > 0.1:
            df *= 0.5
            self.f1 = self.f0 + df
            
        
    def zoom_freq_out(self):
        if self.f1 - self.f0 < self.fmax:
            df = self.f1 - self.f0
            df *= 2.0
            if df > self.fmax:
                df = self.fmax
            self.f1 = self.f0 + df
            if self.f1 > self.fmax:
                self.f1 = self.fmax
                self.f0 = self.fmax - df
            if self.f0 < 0:
                self.f0 = 0
                self.f1 = df
                
        
    def freq_down(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 -= 0.5*df
            self.f1 -= 0.5*df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df

            
    def freq_up(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f0 += 0.5*df
            self.f1 += 0.5*df


    def freq_home(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 = 0.0
            self.f1 = df

            
    def freq_end(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f1 = ceil(self.fmax/(0.5*df))*(0.5*df)
            self.f0 = self.f1 - df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df

        
    def freq_resolution_down(self):
        if self.nfft > 16:
            self.set_resolution(nfft=self.nfft//2)

        
    def freq_resolution_up(self):
        if self.nfft*2 < len(self.data):
            self.set_resolution(nfft=self.nfft*2)


    def step_frac_down(self):
        if 0.5 * self.step_frac * self.nfft >= 1:
            self.set_resolution(step_frac=self.step_frac*0.5)


    def step_frac_up(self):
        if self.step_frac < 1.0:
            self.set_resolution(step_frac=self.step_frac*2.0)


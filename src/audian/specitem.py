"""PlotDataItem for spectrogram.
"""

import numpy as np
import pyqtgraph as pg
from thunderlab.powerspectrum import decibel


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, channel, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data
        self.channel = channel
        self.zmin = None
        self.zmax = None
        self.fmax = 0.5*self.data.source.rate
        self.f0 = 0.0
        self.f1 = self.fmax
        self.cbar = None


    def estimate_noiselevels(self):
        nf = self.data.buffer.shape[2]//16
        if nf < 1:
            nf = 1
        zmin = np.percentile(decibel(self.data.buffer[:, self.channel, -nf:]), 95)
        if not np.isfinite(zmin):
            zmin = -100.0
        self.zmin = zmin
        self.zmax = zmin + 60.0

            
    def setCBar(self, cbar):
        self.cbar = cbar


    def set_power(self, zmin=None, zmax=None):
        if not zmin is None:
            self.zmin = zmin
        if not zmax is None:
            self.zmax = zmax
        self.setLevels((self.zmin, self.zmax), update=True)
        if not self.cbar is None:
            self.cbar.setLevels((self.zmin, self.zmax))


    def update_plot(self):
        if self.data.buffer_changed[self.channel]:
            if self.zmin is None:
                self.estimate_noiselevels()
                self.set_power()
            self.setImage(decibel(self.data.buffer[:, self.channel, :].T),
                          autoLevels=False)
            self.setRect(*self.data.spec_rect)
            self.data.buffer_changed[self.channel] = False

            
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


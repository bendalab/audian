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

            
    def set_cbar(self, cbar):
        self.cbar = cbar
        self.cbar.setLevels([self.zmin, self.zmax])
        self.cbar.setImageItem(self)


    def set_power(self, zmin=None, zmax=None):
        if not zmin is None:
            self.zmin = zmin
        if not zmax is None:
            self.zmax = zmax
        self.setLevels((self.zmin, self.zmax), update=True)
        if not self.cbar is None:
            self.cbar.setLevels((self.zmin, self.zmax))


    def update_plot(self):
        if not self.data.buffer_changed[self.channel]:
            return
        if self.zmin is None:
            self.estimate_noiselevels()
            self.set_power()
        self.setImage(decibel(self.data.buffer[:, self.channel, :].T),
                      autoLevels=False)
        self.setRect(*self.data.spec_rect)
        self.data.buffer_changed[self.channel] = False


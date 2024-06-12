"""PlotDataItem for spectrogram.
"""

from math import floor
import numpy as np
import pyqtgraph as pg
from thunderlab.powerspectrum import decibel


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, channel, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data
        self.channel = channel

        self.data.plot_items[self.channel] = self


    def get_power(self, t, f):
        """Get power next to cursor position. """
        ti = int(floor(t*self.data.rate))
        fi = int(floor(f/self.data.fresolution))
        if ti < self.data.shape[0] and fi < self.data.shape[2]:
            return decibel(self.data[ti, self.channel, fi])
        else:
            return None

        
    def update_plot(self):
        if not self.data.buffer_changed[self.channel]:
            return
        self.setImage(decibel(self.data.buffer[:, self.channel, :].T),
                      autoLevels=False)
        self.setRect(*self.data.spec_rect)
        self.data.buffer_changed[self.channel] = False


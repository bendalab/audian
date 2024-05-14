"""Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

"""

import numpy as np
from audioio import get_datetime
from thunderlab.dataloader import DataLoader
from .bufferedfilter import BufferedFilter
from .bufferedspectrogram import BufferedSpectrogram


class Data(object):

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.load_buffer_orig = None
        self.rate = None
        self.channels = 0
        self.tbefore = 0
        self.tafter = 0
        self.tmax = 0.0
        self.toffset = 0.0
        self.twindow = 10.0
        self.start_time = None
        self.meta_data = {}
        self.filtered = BufferedFilter()
        self.spectrum = BufferedSpectrogram()

        
    def __del__(self):
        if not self.data is None:
            self.data.close()

        
    def open(self, unwrap, unwrap_clip, highpass_cutoff, lowpass_cutoff):
        if not self.data is None:
            self.data.close()
        # expand buffer times:
        tbefore = 0
        tafter = 0
        tbefore, tafter = self.spectrum.expand_times(tbefore, tafter)
        tbefore, tafter = self.filtered.expand_times(tbefore, tafter)
        self.tbefore = tbefore
        self.tafter = tafter
        # raw data:        
        tbuffer = 60 + tbefore + tafter
        try:
            self.data = DataLoader(self.file_path, tbuffer, tbuffer/2)
        except IOError:
            self.data = None
            return
        self.data.set_unwrap(unwrap, unwrap_clip, False, self.data.unit)
        self.data.allocate_buffer()
        self.file_path = self.data.filepath
        self.rate = self.data.rate
        self.channels = self.data.channels
        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = self.tmax
        # metadata:
        self.meta_data = dict(Format=self.data.format_dict())
        self.meta_data.update(self.data.metadata())
        self.start_time = get_datetime(self.meta_data)
        # filter:
        self.filtered.open(self.data, highpass_cutoff, lowpass_cutoff)
        # spectrogram:
        self.spectrum.open(self.data, 256, 0.5)
        # load data, apply filter, and compute spectrograms:
        self.data.reload_buffer()
        self.update_times()


    def update_times(self):
        self.data.update_time(self.toffset - self.tbefore,
                              self.toffset + self.twindow + self.tafter)
        self.filtered.update_time(self.toffset, self.toffset + self.twindow)
        #self.spectrum.update_time(self.toffset, self.toffset + self.twindow)
        
        
    def set_time_limits(self, ax):
        ax.setLimits(xMin=0, xMax=self.tmax,
                     minXRange=10/self.rate, maxXRange=self.tmax)
        # TODO: limit maxXRange to 60s or so!

        
    def set_time_range(self, ax):
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        
        
    def zoom_time_in(self):
        if self.twindow * self.rate >= 20:
            self.twindow *= 0.5
            return True
        return False
        
        
    def zoom_time_out(self):
        if self.toffset + self.twindow < self.tmax:
            self.twindow *= 2.0
            return True
        return False

                
    def time_seek_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            return True
        return False

            
    def time_seek_backward(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            return True
        return False

                
    def time_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            return True
        return False

                
    def time_backward(self, toffs):
        if toffs > 0.0:
            self.toffset = toffs - 0.05*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            return True
        return False

                
    def time_home(self):
        if self.toffset > 0.0:
            self.toffset = 0.0
            return True
        return False

                
    def time_end(self):
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            return True
        return False

                
    def snap_time(self):
        twindow = 10.0 * 2**np.round(log(self.twindow/10.0)/log(2.0))
        toffset = np.round(self.toffset / (0.5*twindow)) * (0.5*twindow)
        if twindow != self.twindow or toffset != self.toffset:
            self.toffset = toffset
            self.twindow = twindow
            return True
        return False


    def set_amplitude_limits(self, ax):
        if np.isfinite(self.data.ampl_min) and np.isfinite(self.data.ampl_max):
            ax.setLimits(yMin=self.data.ampl_min, yMax=self.data.ampl_max,
                         minYRange=1/2**16,
                         maxYRange=self.data.ampl_max - self.data.ampl_min)

        
    def freq_resolution_down(self):
        self.spectrum.set_resolution(nfft=self.spectrum.nfft//2)

        
    def freq_resolution_up(self):
        self.spectrum.set_resolution(nfft=2*self.spectrum.nfft)


    def hop_frac_down(self):
        self.spectrum.set_resolution(hop_frac=self.spectrum.hop_frac/2)


    def hop_frac_up(self):
        self.spectrum.set_resolution(hop_frac=2*self.spectrum.hop_frac)


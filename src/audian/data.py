"""Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

## TODO
- update use_spec on visibility of databrowser, and whether spectra are shown at all

"""

import numpy as np
from scipy.signal import spectrogram
from audioio import get_datetime
from audioio import BufferedArray
from thunderlab.dataloader import DataLoader
from thunderlab.powerspectrum import decibel
from .bufferedfilter import BufferedFilter


class Data(object):

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.load_buffer_orig = None
        self.rate = None
        self.channels = 0
        self.tmax = 0.0
        self.toffset = 0.0
        self.twindow = 10.0
        self.start_time = None
        self.meta_data = {}
        # filter:
        self.filtered = BufferedFilter()
        # spectrogram:
        self.spectrum = None
        self.nfft = []
        self.step_frac = []
        self.step = []
        self.fresolution = []
        self.tresolution = []
        self.spec_rect = []
        self.zmin = []
        self.zmax = []
        self.use_spec = True

        
    def __del__(self):
        if not self.data is None:
            self.data.close()

        
    def open(self, unwrap, unwrap_clip, highpass_cutoff, lowpass_cutoff):
        if not self.data is None:
            self.data.close()
        try:
            self.data = DataLoader(self.file_path, 60.0, 10.0)
        except IOError:
            self.data = None
            return
        self.load_buffer_orig = self.data.load_buffer
        self.data.load_buffer = self.data_buffer
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
        self.nfft = 256
        self.step_frac = 0.5
        self.step = 256//2
        self.fresolution = self.rate/self.nfft
        self.tresolution = self.step/self.rate
        self.spec_rect = []
        self.zmin = [None]*self.channels
        self.zmax = [None]*self.channels
        self.use_spec = True
        self.spectrum = BufferedArray(self.rate/self.step,
                                      self.channels,
                                      self.data.frames//self.step,
                                      self.data.bufferframes//self.step,
                                      self.data.backframes//self.step)
        self.spectrum.shape = (self.data.frames//self.step - 1,
                               self.channels, self.nfft//2 + 1)
        self.spectrum.ndim = 3
        self.spectrum.init_buffer()
        self.spectrum.load_buffer = self.spectrum_buffer
        # load data, apply filter, and compute spectrograms:
        self.data.reload_buffer()

        
    def set_time_limits(self, ax):
        ax.setLimits(xMin=0, xMax=self.tmax,
                     minXRange=10/self.rate, maxXRange=self.tmax)

        
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

            
    def data_buffer(self, offset, nframes, buffer):
        # bound method, self is Data instance!
        # data:
        self.load_buffer_orig(offset, nframes, buffer)
        # filter:
        self.filtered.update_buffer(offset, offset + nframes)
        # spectrum:
        self.spectrum.update_buffer(int(offset/self.spectrum.rate),
                                    int((offset + nframes)/self.spectrum.rate) - 1)
        
        
    def freq_resolution_down(self):
        self.set_resolution(nfft=self.nfft//2)

        
    def freq_resolution_up(self):
        self.set_resolution(nfft=2*self.nfft)


    def step_frac_down(self, channel):
        self.set_resolution(step_frac=self.step_frac/2)


    def step_frac_up(self, channel):
        self.set_resolution(channel, step_frac=2*self.step_frac)


    def set_resolution(self, nfft=None, step_frac=None):
        if nfft is not None:
            if nfft < 8:
                nfft = 8
            max_nfft = min(len(self.data)//2, 2**30)
            if nfft > max_nfft:
                nfft = max_nfft
            if self.nfft != nfft:
                self.nfft = nfft
                spec_update = True
        if step_frac is not None:
            if step_frac > 1.0:
                step_frac = 1.0
            self.step_frac = step_frac
        step = int(np.round(self.step_frac*self.nfft))
        if step < 1:
            step = 1
        if step > self.nfft:
            step = self.nfft
        if self.step != step:
            self.step = step
            spec_update = True
        if spec_update:
            self.spectrum.shape = (self.data.frames//self.step - 1,
                                   self.channels, self.nfft//2 + 1)
            self.tresolution = self.step/self.rate
            self.fresolution = self.rate/self.nfft
            self.spectrum.allocate_bufer()
            self.spectrum.reload_bufer()


    def estimate_noiselevels(self, nf):
        if nf < 1:
            nf = 1
        for c in range(self.channels):
            if zmin[c] is not None:
                continue
            zmin = np.percentile(self.spectrum.buffer[:, c, -nf:], 95)
            if not np.isfinite(zmin):
                zmin = -100.0
            self.zmin[c] = zmin
            self.zmax[c] = zmin + 60.0


    def update_spectra(self):
        # called from SpecItem when viewRange is changed.
        pass


    def spectrum_buffer(self, offset, nframes, buffer):
        return
        # bound method, self is Data instance!
        #t0 = offset/self.rate
        #t1 = t0 + nframes/self.rate
        freq, time, Sxx = spectrogram(self.data.buffer, self.data.rate,
                                      nperseg=self.nfft,
                                      noverlap=self.nfft - self.step,
                                      axis=0)
        self.tresolution = time[1] - time[0]
        self.fresolution = freq[1] - freq[0]
        buffer[:,:,:] = decibel(Sxx).transpose((2, 1, 0))
        self.spec_rect = [self.data.offset/self.data.rate, 0,
                          time[-1] + self.tresolution,
                          freq[-1] + self.fresolution]
        # estimate noise floor for color map:
        self.estimate_noiselevels(len(freq)//16)

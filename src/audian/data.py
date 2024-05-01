"""Data

Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

## TODO
- update use_spec on visibility of databrowser, and whether spectra are shown at all

"""

import numpy as np
from scipy.signal import spectrogram
from audioio import get_datetime
from audioio import BufferArray
from thunderlab.dataloader import DataLoader
from thunderlab.powerspectrum import decibel


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
        self.highpass_cutoff = []
        self.lowpass_cutoff = []
        self.filter_order = []
        self.sos = []
        self.filtered = None
        # spectrogram:
        self.spectrum = []
        self.nfft = []
        self.step_frac = []
        self.step = []
        self.fresolution = []
        self.tresolution = []
        self.spec_rect = []
        self.zmin = []
        self.zmax = []
        self.use_spec = np.zeros(0, dtype=bool)
        self.spec_update = np.zeros(0, dtype=bool)
        self.offset = -1
        self.buffer_size = 0

        
    def __del__(self):
        if not self.data is None:
            self.data.close()

            
    def load_buffer(self, offset, size, buffer):
        # data:
        self.load_buffer_orig(offset, size, buffer)
        # filter:
        if self.filtered is not None and self.filtered is not self.data:
            self.filtered.update_buffer(offset, offset + size)
        # spectrum:    
        if len(self.data.buffer) == 0 or \
           (self.offset == self.data.offset and \
            self.buffer_size == len(self.data.buffer):
            return
        self.spec_update[:] = True
        self.update_spectra()
        self.offset = self.data.offset
        self.buffer_size = len(self.data.buffer)
        
        
    def open(self, unwrap, unwrap_clip, highpass_cutoff, lowpass_cutoff):
        if not self.data is None:
            self.data.close()
        try:
            self.data = DataLoader(self.file_path, 60.0, 10.0)
        except IOError:
            self.data = None
            return
        self.load_buffer_orig = self.data.load_buffer
        self.data.load_buffer = self.load_buffer
        self.data.set_unwrap(unwrap, unwrap_clip, False, self.data.unit)
        self.file_path = self.data.filepath
        self.rate = self.data.samplerate
        self.channels = self.data.channels
        # filter:
        if highpass_cutoff is None:
            self.highpass_cutoff = [0]*self.channels
        else:
            self.highpass_cutoff = [highpass_cutoff]*self.channels
        if lowpass_cutoff is None:
            self.lowpass_cutoff = [lowpass_cutoff]*self.channels
        else:
            self.lowpass_cutoff = [self.rate/2]*self.channels
        self.filter_order = [2]*self.channels
        self.sos = [None]*self.channels
        self.filtered = self.data
        self.set_filter()
        
        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = self.tmax
        # metadata:
        self.meta_data = dict(Format=self.data.format_dict())
        self.meta_data.update(self.data.metadata())
        self.start_time = get_datetime(self.meta_data)
        # spectrogram:
        self.spectrum = [None]*self.channels
        self.nfft = [256]*self.channels
        self.step_frac = [0.5]*self.channels
        self.step = [256//2]*self.channels
        self.fresolution = [1]*self.channels
        self.tresolution = [1]*self.channels
        self.spec_rect = [None]*self.channels
        self.zmin = [None]*self.channels
        self.zmax = [None]*self.channels
        self.use_spec = np.ones(self.channels, dtype=bool)
        self.spec_update = np.ones(self.channels, dtype=bool)
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


    def filter_buffer(self, offset, nframes, buffer):
        for c in range(self.channels):
            if self.sos[c] is None:
                buffer[:, c] = self.data[offset:offset + nframes, c]
            else:
                buffer[:, c] = sig.sosfiltfilt(self.sos[c],
                                               self.data[offset:offset + nframes, c])


    def make_filter(self, channel):
        if self.highpass_cutoff[channel] < 1e-8 and \
           self.lowpass_cutoff[channel] >= self.rate/2 - 1e-8:
            self.sos[channel] = None
        elif self.highpass_cutoff[channel] < 1e-8:
            self.sos[channel] = sig.butter(self.filter_order[channel],
                                           self.lowpass_cutoff[channel],
                                           'lowpass', fs=self.rate,
                                           output='sos')
        elif self.lowpass_cutoff[channel] >= self.rate/2-1e-8:
            self.sos[channel] = sig.butter(self.filter_order[channel],
                                           self.highpass_cutoff[channel],
                                           'highpass', fs=self.rate,
                                           output='sos')
        else:
            self.sos[channel] = sig.butter(self.filter_order[channel],
                                           (self.highpass_cutoff[channel],
                                            self.lowpass_cutoff[channel]),
                                           'bandpass', fs=self.rate,
                                           output='sos')

        
    def set_filter(self, highpass_cutoffs=None, lowpass_cutoffs=None,
                   channel=None):
        do_filter = False
        if channel is None:
            if highpass_cutoff is not None:
                for c in range(min(len(highpass_cutoff), self.channels)):
                    self.highpass_cutoff[c] = highpass_cutoff[c]
                else:
                    for cf in range(c + 1, self.channels):
                        self.highpass_cutoff[c] = highpass_cutoff[-1]
            if lowpass_cutoff is not None:
                for c in range(min(len(lowpass_cutoff), self.channels)):
                    self.lowpass_cutoff[c] = lowpass_cutoff[c]
                else:
                    for cf in range(c + 1, self.channels):
                        self.lowpass_cutoff[c] = lowpass_cutoff[-1]
            for c in range(self.channels):
                self.make_filter(c)
                if self.sos[c] is not None:
                    do_filter = True
        else:
            if highpass_cutoff is not None:
                self.highpass_cutoff[channel] = highpass_cutoff
            if lowpass_cutoff is not None:
                self.lowpass_cutoff[channel] = lowpass_cutoff
            self.make_filter(channel)
            if self.sos[channel] is not None:
                do_filter = True
        if do_filter:
            if self.filtered is self.data:
                self.filtered = BufferArray(self.rate, self.channels,
                                            self.data.frames,
                                            self.data.ampl_min,
                                            self.data.ampl_max,
                                            self.buffersize,
                                            self.backsize)
                self.filtered.load_buffer = self.filter_buffer
            self.filtered.reload_buffer()
            # still need to update plots!
        elif not do_filter and self.filtered is not self.data:
            self.filtered = self.data

        
    def freq_resolution_down(self, channel):
        if self.nfft[channel] > 8:
            self.set_resolution(channel, nfft=self.nfft[channel]//2)

        
    def freq_resolution_up(self, channel):
        if 2*self.nfft[channel] < min(len(self.data)//2, 2**30):
            self.set_resolution(channel, nfft=2*self.nfft[channel])


    def step_frac_down(self, channel):
        sfrac = self.step_frac[channel]
        if 0.5*sfrac*self.nfft[channel] >= 1:
            self.set_resolution(channel, step_frac=sfrac/2)


    def step_frac_up(self, channel):
        sfrac = self.step_frac[channel]
        if sfrac < 1:
            self.set_resolution(channel, step_frac=2*sfrac)


    def set_resolution(self, channel, nfft=None, step_frac=None):
        if nnft is not None:
            if nfft < 8:
                nfft = 8
            if nfft > 2**30:
                nfft = 2**30
            if self.nfft[channel] != nfft:
                self.nfft[channel] = nfft
                self.spec_update[channel] = True
        if step_frac is not None:
            if step_frac > 1.0:
                step_frac = 1.0
            self.step_frac[channel] = step_frac
        step = int(np.round(self.step_frac[channel]* \
                            self.nfft[channel]))
        if step < 1:
            step = 1
        if self.step[channel] != step:
            self.step[channel] = step
            self.spec_update[channel] = True
        self.tresolution[channel] = self.step/self.rate
        self.fresolution[channel] = self.rate/self.nfft[channel]


    def estimate_noiselevel(self, channel, nf):
        if nf < 1:
            nf = 1
        zmin = np.percentile(self.spectrum[channel][-nf:, :], 95.0)
        if not np.isfinite(zmin):
            zmin = -100.0
        self.zmin[channel] = zmin
        self.zmax[channel] = zmin + 60.0


    def update_spectra(self):
        for c in range(len(self.spec_update)):
            if not self.use_spec[c] or not self.spec_update[c]:
                continue
            # compute spectrum for channel c:
            # takes very long:
            freq, time, Sxx = spectrogram(self.data.buffer[:, c],
                                          self.rate,
                                          nperseg=self.nfft[c],
                                          noverlap=self.nfft[c] -
                                            self.step[c])
            self.tresolution[c] = time[1] - time[0]
            self.fresolution[c] = freq[1] - freq[0]
            self.spectrum[c] = decibel(Sxx)
            self.spec_rect[c] = [self.data.offset/self.rate, 0,
                                 time[-1] + self.tresolution[c],
                                 freq[-1] + self.fresolution[c]]
            # estimate noise floor for color map:
            if self.zmin[c] is None:
                self.estimate_noiselevel(c, len(freq)//16)
            self.spec_update[c] = False
            # somehow notify spectrum plots to update!

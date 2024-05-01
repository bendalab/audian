"""Data

Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

"""

from audioio import get_datetime
from audioio import BufferArray
from thunderlab.dataloader import DataLoader


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
        self.meta_data = {}
        self.start_time = None
        self.highpass_cutoff = []
        self.lowpass_cutoff = []
        self.filter_order = []
        self.sos = []
        self.filtered = None

        
    def __del__(self):
        if not self.data is None:
            self.data.close()

            
    def load_buffer(self, offset, size, buffer):
        self.load_buffer_orig(offset, size, buffer)
        if self.filtered is not None and self.filtered is not self.data:
            self.filtered.update_buffer(offset, offset + size)
        
        
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
        self.data.update_buffer(0, self.data.buffersize)  # load data
            
        self.meta_data = dict(Format=self.data.format_dict())
        self.meta_data.update(self.data.metadata())
        self.start_time = get_datetime(self.meta_data)


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

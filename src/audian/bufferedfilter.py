"""Filter source data on the fly.
"""

from scipy.signal import butter, sosfiltfilt
from audioio import BufferedArray


class BufferedFilter(BufferedArray):

    def __init_(self, verbose=0):
        self.verbose = verbose
        self.highpass_cutoff = []
        self.lowpass_cutoff = []
        self.filter_order = []
        self.sos = []
        self.need_filter = False

        
    def open(self, source, highpass_cutoff=None, lowpass_cutoff=None):
        self.source = source
        self.rate = self.source.rate
        self.channels = self.source.channels
        self.frames = self.source.frames
        self.shape = (self.frames, self.channels)
        self.ndim = 2
        self.size = self.frames * self.channels
        self.bufferframes = self.source.bufferframes
        self.backframes = self.source.backframes
        self.ampl_min = self.source.ampl_min
        self.ampl_max = self.source.ampl_max
        self.offset = 0
        self.init_buffer()
        if highpass_cutoff is None:
            self.highpass_cutoff = [0]*self.channels
        else:
            self.highpass_cutoff = [highpass_cutoff]*self.channels
        if lowpass_cutoff is None:
            self.lowpass_cutoff = [self.rate/2]*self.channels
        else:
            self.lowpass_cutoff = [lowpass_cutoff]*self.channels
        self.filter_order = [2]*self.channels
        self.sos = [None]*self.channels
        self.need_filter = False
        self.set_filter()

        
    def load_buffer(self, offset, nframes, buffer):
        if self.need_filter:
            for c in range(self.channels):
                if self.sos[c] is None:
                    buffer[:, c] = self.source[offset:offset + nframes, c]
                else:
                    buffer[:, c] = sosfiltfilt(self.sos[c],
                                               self.source[offset:offset
                                                           + nframes, c])
        else:
            self.buffer = self.source.buffer
            self.offset = self.source.offset

            
    def make_filter(self, channel):
        if self.highpass_cutoff[channel] < 1e-8 and \
           self.lowpass_cutoff[channel] >= self.rate/2 - 1e-8:
            self.sos[channel] = None
        elif self.highpass_cutoff[channel] < 1e-8:
            self.sos[channel] = butter(self.filter_order[channel],
                                       self.lowpass_cutoff[channel],
                                       'lowpass', fs=self.rate,
                                       output='sos')
        elif self.lowpass_cutoff[channel] >= self.rate/2-1e-8:
            self.sos[channel] = butter(self.filter_order[channel],
                                       self.highpass_cutoff[channel],
                                       'highpass', fs=self.rate,
                                       output='sos')
        else:
            self.sos[channel] = butter(self.filter_order[channel],
                                       (self.highpass_cutoff[channel],
                                        self.lowpass_cutoff[channel]),
                                       'bandpass', fs=self.rate,
                                       output='sos')

            
    def set_filter(self):
        need_filter = False
        for c in range(self.channels):
            self.make_filter(c)
            if self.sos[c] is not None:
                need_filter = True
        if need_filter != self.need_filter and need_filter:
            self.allocate_buffer(self.source.bufferframes, True)
        self.need_filter = need_filter
        self.reload_buffer()


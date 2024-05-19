"""Filter source data on the fly.
"""

from scipy.signal import butter, sosfiltfilt
from .buffereddata import BufferedData


class BufferedFilter(BufferedData):

    def __init__(self, verbose=0):
        super().__init__(name='filtered', tbefore=10, tafter=0,
                         verbose=verbose)
        self.highpass_cutoff = []
        self.lowpass_cutoff = []
        self.filter_order = []
        self.sos = []

        
    def open(self, source, highpass_cutoff=None, lowpass_cutoff=None):
        self.ampl_min = source.ampl_min
        self.ampl_max = source.ampl_max
        super().open(source)
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
        self.set_filter()

        
    def load_buffer(self, offset, nframes, buffer):
        print(f'load {self.name} {offset/self.rate:.3f} - {(offset + nframes)/self.rate:.3f}')
        nbefore = int(self.source_tbefore/self.source.rate)
        for c in range(self.channels):
            if self.sos[c] is None:
                offs = offset - self.source.offset
                buffer[:, c] = self.source.buffer[offs:offs + nframes, c]
            else:
                nbfr = nbefore
                offs = offset - nbfr
                nfrs = nframes + nbfr
                if offs < 0:
                    nbfr += offs
                    nfrs += offs
                    offs = 0
                offs -= self.source.offset
                buffer[:, c] = sosfiltfilt(self.sos[c],
                                           self.source.buffer[offs:offs + nfrs, c])[nbfr:]

            
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
        for c in range(self.channels):
            self.make_filter(c)
        self.reload_buffer()


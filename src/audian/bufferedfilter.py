"""Filter source data on the fly.
"""

from scipy.signal import butter, sosfilt
from .buffereddata import BufferedData


class BufferedFilter(BufferedData):

    def __init__(self):
        super().__init__(name='filtered', tbefore=10, tafter=0)
        self.highpass_cutoff = []
        self.lowpass_cutoff = []
        self.filter_order = []
        self.sos = []

        
    def open(self, source, highpass_cutoff=None, lowpass_cutoff=None):
        super().open(source)
        self.ampl_min = source.ampl_min
        self.ampl_max = source.ampl_max
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
        self.update()


    def process(self, source, dest, nbefore):
        for c in range(self.channels):
            if self.sos[c] is None:
                dest[:, c] = source[nbefore:, c]
            else:
                dest[:, c] = sosfilt(self.sos[c], source[:, c],)[nbefore:]

                
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

            
    def update(self):
        for c in range(self.channels):
            self.make_filter(c)
        self.recompute()


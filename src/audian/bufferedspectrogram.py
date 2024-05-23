"""Spectrogram of source data on the fly.

"""


import numpy as np
from scipy.signal import spectrogram
from thunderlab.powerspectrum import decibel
from .buffereddata import BufferedData


class BufferedSpectrogram(BufferedData):

    def __init__(self, name='spectrogram', source='filtered', panel='spectrum'):
        super().__init__(name, source, tafter=10, panel=panel)
        self.nfft = 256
        self.hop_frac = 0.5
        self.hop = self.nfft//2
        self.fresolution = 1
        self.tresolution = 1
        self.spec_rect = []
        self.use_spec = True

        
    def open(self, source):
        self.hop = int(self.nfft*self.hop_frac)
        self.fresolution = source.rate/self.nfft
        self.tresolution = self.hop/source.rate
        self.spec_rect = []
        self.use_spec = True
        super().open(source, self.hop, more_shape=(self.nfft//2 + 1,))

        
    def process(self, source, dest, nbefore):
        nsource = (len(dest) - 1)*self.hop + self.nfft
        if nsource > len(source):
            nsource = len(source)
        freq, time, Sxx = spectrogram(source[:nsource],
                                      self.source.rate,
                                      nperseg=self.nfft,
                                      noverlap=self.nfft - self.hop,
                                      axis=0)
        n = Sxx.shape[2]
        dest[:n] = Sxx.transpose((2, 1, 0))
        dest[n:] = 0
        # extent of the full buffer:
        self.spec_rect = [self.offset/self.rate, 0,
                          len(self.buffer)/self.rate,
                          freq[-1] + self.fresolution]

        
    def update(self, nfft=None, hop_frac=None):
        spec_update = False
        if nfft is not None:
            if nfft < 8:
                nfft = 8
            max_nfft = min(len(self.source)//2, 2**30)
            if nfft > max_nfft:
                nfft = max_nfft
            if self.nfft != nfft:
                self.nfft = nfft
                spec_update = True
        if hop_frac is not None:
            if hop_frac > 1.0:
                hop_frac = 1.0
            self.hop_frac = hop_frac
        hop = int(np.round(self.hop_frac*self.nfft))
        if hop < 1:
            hop = 1
        if hop > self.nfft:
            hop = self.nfft
        if self.hop != hop:
            self.hop = hop
            self.hop_frac = self.hop/self.nfft
            spec_update = True
        if spec_update:
            self.tresolution = self.hop/self.source.rate
            self.fresolution = self.source.rate/self.nfft
            self.update_step(self.hop, more_shape=(self.nfft//2 + 1,))
            self.recompute()

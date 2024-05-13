"""Spectrogram of source data on the fly.

## TODO
- update use_spec on visibility of databrowser, and whether spectra are shown at all

"""


import numpy as np
from scipy.signal import spectrogram
from thunderlab.powerspectrum import decibel
from .buffereddata import BufferedData


class BufferedSpectrogram(BufferedData):

    def __init__(self, verbose=0):
        super().__init__(tbefore=0, tafter=10, verbose=verbose)
        self.nfft = []
        self.hop_frac = []
        self.hop = []
        self.fresolution = []
        self.tresolution = []
        self.spec_rect = []
        self.use_spec = True

        
    def open(self, source, nfft=256, hop_frac=0.5):
        self.nfft = nfft
        self.hop_frac = hop_frac
        self.hop = int(self.nfft*self.hop_frac)
        if self.hop < 1:
            self.hop = 1
        if self.hop > self.nfft:
            self.hop = self.nfft
        self.fresolution = source.rate/self.nfft
        self.tresolution = self.hop/source.rate
        self.spec_rect = []
        self.use_spec = True
        super().open(source, self.hop, more_shape=(self.nfft//2 + 1,))

        
    def load_buffer(self, offset, nframes, buffer):
        print(f'compute spectrum: {offset/self.rate:.3f} - {(offset + nframes)/self.rate:.3f}')
        start = offset*self.hop - self.source.offset
        stop = start + nframes*self.hop
        if stop > len(self.source.buffer):
            print('    source buffer overflow', stop, len(self.source.buffer))
            stop = len(self.source.buffer)
        # TODO: sometimes start is negative, but must not!
        print('    buffer', start, stop - start, len(self.source.buffer))
        freq, time, Sxx = spectrogram(self.source.buffer[start:stop],
                                      self.source.rate,
                                      nperseg=self.nfft,
                                      noverlap=self.nfft - self.hop,
                                      axis=0)
        n = Sxx.shape[2]
        buffer[:n, :, :] = Sxx.transpose((2, 1, 0))
        buffer[n:, :, :] = 0
        # extent of the full buffer:
        self.spec_rect = [self.offset/self.rate, 0,
                          (self.offset + len(self.buffer))/self.rate + self.tresolution,
                          freq[-1] + self.fresolution]

        
    def set_resolution(self, nfft=None, hop_frac=None):
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
            spec_update = True
        if spec_update:
            self.update_hop(self.hop, more_shape=(self.nfft//2 + 1,))
            self.tresolution = self.hop/self.source.rate
            self.fresolution = self.source.rate/self.nfft
            self.allocate_buffer()
            self.reload_buffer()

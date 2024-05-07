"""Spectrogram of source data on the fly.

## TODO
- update use_spec on visibility of databrowser, and whether spectra are shown at all

"""


import numpy as np
from scipy.signal import spectrogram
from audioio import BufferedArray
from thunderlab.powerspectrum import decibel


class BufferedSpectrogram(BufferedArray):
    def __init_(self, verbose=0):
        self.verbose = verbose
        self.nfft = []
        self.hop_frac = []
        self.hop = []
        self.fresolution = []
        self.tresolution = []
        self.spec_rect = []
        self.zmin = []
        self.zmax = []
        self.use_spec = True

    def open(self, source, nfft=256, hop_frac=0.5):
        self.source = source
        self.nfft = nfft
        self.hop_frac = hop_frac
        self.hop = int(self.nfft*self.hop_frac)
        if self.hop < 1:
            self.hop = 1
        if self.hop > self.nfft:
            self.hop = self.nfft
        self.rate = self.source.rate/self.hop
        self.channels = self.source.channels
        self.frames = self.source.frames//self.hop
        self.shape = (self.frames, self.channels, self.nfft//2 + 1)
        self.ndim = 3
        self.size = np.prod(self.shape)
        self.bufferframes = self.source.bufferframes//self.hop
        self.backframes = self.source.backframes//self.hop
        self.fresolution = self.source.rate/self.nfft
        self.tresolution = self.hop/self.source.rate
        self.spec_rect = []
        self.zmin = [None]*self.channels
        self.zmax = [None]*self.channels
        self.use_spec = True
        self.init_buffer()
                
    def load_buffer(self, offset, nframes, buffer):
        print('compute spectrum', offset, nframes)
        start = offset*self.hop
        stop = start + nframes*self.hop
        print('    buffer', start, stop - start, len(self.source.buffer))
        freq, time, Sxx = spectrogram(self.source[start:stop],
                                      self.source.rate,
                                      nperseg=self.nfft,
                                      noverlap=self.nfft - self.hop,
                                      axis=0)
        n = Sxx.shape[2]
        buffer[:n, :, :] = Sxx.transpose((2, 1, 0))
        buffer[n:, :, :] = 0
        self.spec_rect = [self.offset/self.rate, 0,
                          (self.offset + len(self.buffer))/self.rate + self.tresolution,
                          freq[-1] + self.fresolution]
        # estimate noise floor for color map:
        self.estimate_noiselevels(len(freq)//16)

    def estimate_noiselevels(self, nf):
        if nf < 1:
            nf = 1
        for c in range(self.channels):
            if self.zmin[c] is not None:
                continue
            zmin = np.percentile(decibel(self.buffer[:, c, -nf:]), 95)
            if not np.isfinite(zmin):
                zmin = -100.0
            self.zmin[c] = zmin
            self.zmax[c] = zmin + 60.0

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
            self.rate = self.source.rate/self.hop
            self.frames = self.source.frames//self.hop
            self.shape = (self.frames, self.channels, self.nfft//2 + 1)
            self.size = np.prod(self.shape)
            self.bufferframes = self.source.bufferframes//self.hop
            self.backframes = self.source.backframes//self.hop
            self.tresolution = self.hop/self.source.rate
            self.fresolution = self.source.rate/self.nfft
            self.allocate_buffer()
            self.reload_buffer()


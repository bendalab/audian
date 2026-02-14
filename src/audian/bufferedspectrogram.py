"""Spectrogram of source data on the fly.

"""

import numpy as np

from thunderlab.powerspectrum import spectrogram, decibel

from .buffereddata import BufferedData


class BufferedSpectrogram(BufferedData):

    def __init__(self, name='spectrogram', source='filtered',
                 panel='spectrogram', nfft=256,
                 overlap_frac=0.5):
        super().__init__(name, source, tafter=10, panel=panel,
                         panel_type='spectrogram')
        self.nfft = nfft
        self.hop = 0
        self.overlap_frac = overlap_frac
        self.set_hop()
        self.frequencies = np.zeros(0)
        self.fresolution = 1
        self.tresolution = 1
        self.spec_rect = []
        self.use_spec = True
        self.init = True

        
    def open(self, source):
        self.hop = int(self.nfft*(1 - self.overlap_frac))
        self.fresolution = source.rate/self.nfft
        self.frequencies = np.arange(0, source.rate/2 + self.fresolution/2,
                                     self.fresolution)
        self.tresolution = self.hop/source.rate
        self.spec_rect = []
        self.use_spec = True
        super().open(source, self.hop, more_shape=(self.nfft//2 + 1,))
        self.unit = f'{self.unit}^2/Hz'
        self.ampl_min = 0
        self.ampl_max = self.source.rate/2

        
    def process(self, source, dest, nbefore):
        nsource = (len(dest) - 1)*self.hop + self.nfft
        if nsource > len(source):
            nsource = len(source)
        if nsource >= self.nfft:
            with np.errstate(under='ignore'):
                freq, time, Sxx = spectrogram(source[:nsource],
                                              self.source.rate,
                                              freq_resolution=None,
                                              overlap_frac=None,
                                              n_fft=self.nfft,
                                              n_overlap=self.nfft - self.hop)
            n = Sxx.shape[1]
            dest[:n] = Sxx.transpose((1, 2, 0))
            dest[n:] = 0
            self.frequencies = freq
        else:
            dest[:] = 0
        # extent of the full buffer:
        self.spec_rect = [self.offset/self.rate, 0,
                          len(self.buffer)/self.rate,
                          self.source.rate/2 + self.fresolution]


    def set_hop(self):
        hop = int(np.round((1 - self.overlap_frac)*self.nfft))
        if hop < 1:
            hop = 1
        if hop > self.nfft:
            hop = self.nfft
        if self.hop != hop:
            self.hop = hop
            self.overlap_frac = 1 - self.hop/self.nfft
            return True
        else:
            return False

        
    def update(self, nfft=None, overlap_frac=None):
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
        if overlap_frac is not None:
            if overlap_frac < 0.0:
                overlap_frac = 0.0
            elif overlap_frac > 0.99999:
                overlap_frac = 0.99999
            self.overlap_frac = overlap_frac
        if self.set_hop():
            spec_update = True
        if spec_update:
            self.tresolution = self.hop/self.source.rate
            self.fresolution = self.source.rate/self.nfft
            self.update_step(self.hop, more_shape=(self.nfft//2 + 1,))
            self.recompute_all()

            
    def estimate_noiselevels(self, channel):
        if not self.init or len(self.buffer) == 0 or len(self.buffer.shape) < 3:
            return None, None
        nf = self.buffer.shape[2]//16
        if nf < 1:
            nf = 1
        with np.errstate(all='ignore'):  # TODO: check what is going on!!!
            zmin = np.percentile(decibel(self.buffer[:, channel, -nf:]), 95)
        zmax = np.max(decibel(self.buffer[:, channel, :]))
        if not np.isfinite(zmin) or not np.isfinite(zmax):
            return None, None
        self.init = False
        zmax = zmin + 0.95*(zmax - zmin)
        if zmax - zmin < 20:
            zmax = zmin + 20
        if zmax - zmin > 80:
            zmin = zmax - 80
        return zmin, zmax


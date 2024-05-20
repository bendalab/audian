"""Compute envelope on the fly.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt
from .buffereddata import BufferedData


class BufferedEnvelope(BufferedData):

    def __init__(self):
        super().__init__(name='envelope', tbefore=1, tafter=0)
        self.envelope_cutoff = 500
        self.filter_order = 2
        self.sos = None

        
    def open(self, source, lowpass_cutoff=None, filter_order=2):
        super().open(source)
        self.ampl_min = 0
        self.ampl_max = source.ampl_max
        if lowpass_cutoff is not None:
            self.envelope_cutoff = lowpass_cutoff
        if filter_order is not None:
            self.filter_order = filter_order
        self.sos = None
        self.set_filter()

        
    def load_buffer(self, offset, nframes, buffer):
        print(f'load {self.name} {offset/self.rate:.3f} - {(offset + nframes)/self.rate:.3f}')
        nbefore = int(self.source_tbefore/self.source.rate)
        offset -= nbefore
        nframes += nbefore
        if offset < 0:
            nbefore += offset
            nframes += offset
            offset = 0
        offset -= self.source.offset
        # the integral over one hump of the sine wave is 2, the mean is 2/pi:
        tmp_buffer = (np.pi/2)*np.abs(self.source.buffer[offset:offset + nframes])
        buffer[:] = sosfiltfilt(self.sos, tmp_buffer, axis=0)[nbefore:]
        # TODO: downsample!!!

            
    def set_filter(self):
        self.sos = butter(self.filter_order, self.envelope_cutoff,
                          'lowpass', fs=self.rate, output='sos')
        self.reload_buffer()


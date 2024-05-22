"""Compute envelope on the fly.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt
from .buffereddata import BufferedData


class BufferedEnvelope(BufferedData):

    def __init__(self):
        super().__init__('envelope', 'filtered', tbefore=1)
        self.envelope_cutoff = 500
        self.filter_order = 2
        self.sos = None

        
    def open(self, source):
        super().open(source)
        self.ampl_min = 0
        self.ampl_max = source.ampl_max
        self.sos = None
        self.update()

        
    def process(self, source, dest, nbefore):
        # the integral over one hump of the sine wave is 2, the mean is 2/pi:
        dest[:] = sosfiltfilt(self.sos, (np.pi/2)*np.abs(source), axis=0)[nbefore:]
        # TODO: downsample!!!

            
    def update(self):
        self.sos = butter(self.filter_order, self.envelope_cutoff,
                          'lowpass', fs=self.rate, output='sos')
        self.recompute()

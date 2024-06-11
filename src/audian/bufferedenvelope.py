"""Compute envelope on the fly.
"""

import numpy as np
from scipy.signal import butter, sosfiltfilt
from .buffereddata import BufferedData


class BufferedEnvelope(BufferedData):

    def __init__(self, name='envelope', source='filtered',
                 panel='trace', color='#ff8800',
                 lw_thin=2.5, lw_thick=4, envelope_cutoff=500,
                 filter_order=2, highpass_cutoff=0):
        super().__init__(name, source, tbefore=1, panel=panel,
                         panel_type='trace', color=color,
                         lw_thin=lw_thin, lw_thick=lw_thick)
        self.envelope_cutoff = envelope_cutoff
        self.highpass_cutoff = highpass_cutoff
        self.filter_order = filter_order
        self.sos = None

        
    def open(self, source):
        super().open(source)
        #self.ampl_min = 0
        #self.ampl_max = source.ampl_max
        self.sos = None
        self.update()

        
    def process(self, source, dest, nbefore):
        if self.sos is None:
            dest[:] = np.zeros_like(dest)
        else:
            # the integral over one hump of the sine wave is 2, the mean is 2/pi:
            dest[:] = sosfiltfilt(self.sos, (np.pi/2)*np.abs(source), axis=0)[nbefore:]
            if self.highpass_cutoff == 0:
                dest[dest < 0] = 0

            
    def update(self):
        try:
            if self.highpass_cutoff > 0:
                self.sos = butter(self.filter_order,
                                  (self.highpass_cutoff, self.envelope_cutoff),
                                  'bandpass', fs=self.rate, output='sos')
            else:
                self.sos = butter(self.filter_order, self.envelope_cutoff,
                                  'lowpass', fs=self.rate, output='sos')
        except ValueError:
            self.sos = None
        self.recompute_all()


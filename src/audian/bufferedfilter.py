"""Filter data on the fly.
"""

from scipy.signal import butter, sosfilt
from .buffereddata import BufferedData


class BufferedFilter(BufferedData):

    def __init__(self, name='filtered', source='data', panel='trace',
                 color='#00ee00', lw_thin=1.1, lw_thick=2):
        super().__init__(name, source, tbefore=10, panel=panel,
                         panel_type='trace', color=color,
                         lw_thin=lw_thin, lw_thick=lw_thick)
        self.highpass_cutoff = 0
        self.lowpass_cutoff = 1
        self.filter_order = 2
        self.sos = None

        
    def open(self, source):
        super().open(source)
        self.highpass_cutoff = 0
        self.lowpass_cutoff = self.rate/2
        self.filter_order = 2
        self.sos = None
        self.update()


    def process(self, source, dest, nbefore):
        if self.sos is None:
            dest[:, :] = source[nbefore:, :]
        else:
            for c in range(self.channels):
                dest[:, c] = sosfilt(self.sos, source[:, c],)[nbefore:]

            
    def update(self):
        if self.highpass_cutoff < 0.001*self.rate/2 and \
           self.lowpass_cutoff >= self.rate/2 - 1e-8:
            self.sos = None
        elif self.highpass_cutoff < 0.001*self.rate/2:
            self.sos = butter(self.filter_order, self.lowpass_cutoff,
                              'lowpass', fs=self.rate, output='sos')
        elif self.lowpass_cutoff >= self.rate/2 - 1e-8:
            self.sos = butter(self.filter_order, self.highpass_cutoff,
                              'highpass', fs=self.rate, output='sos')
        else:
            self.sos = butter(self.filter_order,
                              (self.highpass_cutoff, self.lowpass_cutoff),
                              'bandpass', fs=self.rate, output='sos')
        self.recompute_all()


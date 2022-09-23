import numpy as np
from scipy.signal import spectrogram
from PyQt5.QtCore import pyqtSignal
import pyqtgraph as pg


def decibel(power, ref_power=1.0, min_power=1e-20):
    """Transform power to decibel relative to ref_power.

    \\[ decibel = 10 \\cdot \\log_{10}(power/ref\\_power) \\]
    Power values smaller than `min_power` are set to `-np.inf`.

    Parameters
    ----------
    power: float or array
        Power values, for example from a power spectrum or spectrogram.
    ref_power: float or None or 'peak'
        Reference power for computing decibel.
        If set to `None` or 'peak', the maximum power is used.
    min_power: float
        Power values smaller than `min_power` are set to `-np.inf`.

    Returns
    -------
    decibel_psd: array
        Power values in decibel relative to `ref_power`.
    """
    if isinstance(power, (list, tuple, np.ndarray)):
        tmp_power = power
        decibel_psd = power.copy()
    else:
        tmp_power = np.array([power])
        decibel_psd = np.array([power])
    if ref_power is None or ref_power == 'peak':
        ref_power = np.max(decibel_psd)
    decibel_psd[tmp_power <= min_power] = float('-inf')
    decibel_psd[tmp_power > min_power] = 10.0 * np.log10(decibel_psd[tmp_power > min_power]/ref_power)
    if isinstance(power, (list, tuple, np.ndarray)):
        return decibel_psd
    else:
        return decibel_psd[0]


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, rate, channel, nfft, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data
        self.rate = rate
        self.channel = channel
        self.offset = -1
        self.buffer_size = 0
        self.current_nfft = 1
        self.current_step = 1
        self.fmax = 0.5/self.rate
        self.zmin, self.zmax = self.setNFFT(nfft, 0.5, True)
        self.cbar = None


    def setNFFT(self, nfft, step_frac, update):
        self.nfft = nfft
        self.step = int(np.round(step_frac * self.nfft))
        if self.step < 1:
            self.step = 1
        if update:
            return self.updateSpec()


    def setCBar(self, cbar):
        self.cbar = cbar


    def setCBarLevels(self, zmin, zmax):
        self.zmin = zmin
        self.zmax = zmax
        self.setLevels((self.zmin, self.zmax), update=True)
        if not self.cbar is None:
            self.cbar.setLevels((self.zmin, self.zmax))
        self.update()

        
    def viewRangeChanged(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return
        
        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        if start < self.data.offset or stop >= self.data.offset + len(self.data.buffer):
            self.data.update_buffer(start, stop)
        self.updateSpec()
    

    def updateSpec(self):
        if len(self.data.buffer) == 0:
            return 0, 1
        if self.offset == self.data.offset and \
           self.buffer_size == len(self.data.buffer) and \
           self.current_nfft == self.nfft and \
           self.current_step == self.step:
            return
        
        freq, time, Sxx = spectrogram(self.data.buffer[:, self.channel],
                                      self.rate, nperseg=self.nfft,
                                      noverlap=self.nfft-self.step)
        self.fresolution = freq[1] - freq[0]
        Sxx = decibel(Sxx)
        #print(np.max(Sxx))
        zmax = np.percentile(Sxx, 99.9) + 5.0
        #zmin = np.percentile(Sxx, 70.0)
        #zmax = -20
        zmin = zmax - 60
        self.fmax = freq[-1]
        self.setImage(Sxx, autoLevels=False)
        self.resetTransform()
        self.translate(self.data.offset/self.rate, 0)
        self.scale(time[-1]/len(time), freq[-1]/len(freq))
        self.offset = self.data.offset
        self.buffer_size = len(self.data.buffer)
        self.current_nfft = self.nfft
        self.current_step = self.step
        return zmin, zmax

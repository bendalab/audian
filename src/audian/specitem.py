from PyQt5.QtCore import QRectF
import pyqtgraph as pg


class SpecItem(pg.ImageItem):
    
    def __init__(self, data, channel, *args, **kwargs):
        pg.ImageItem.__init__(self, **kwargs)
        self.setOpts(axisOrder='row-major')
        
        self.data = data
        self.rate = self.data.rate
        self.channel = channel
        self.zmin = data.zmin[channel]
        self.zmax = data.zmax[channel]
        self.fmax = 0.5/self.rate
        self.f0 = 0.0
        self.f1 = self.fmax
        self.cbar = None


    def setCBar(self, cbar):
        self.cbar = cbar


    def set_power(self, zmin, zmax):
        if not zmin is None:
            self.zmin = zmin
        if not zmax is None:
            self.zmax = zmax
        self.setLevels((self.zmin, self.zmax), update=True)
        if not self.cbar is None:
            self.cbar.setLevels((self.zmin, self.zmax))

        
    def viewRangeChanged(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return
        
        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data.data), int(trange[1]*self.rate+1))
        if start < self.data.data.offset or stop >= self.data.data.offset + len(self.data.data.buffer):
            self.data.data.update_buffer(start, stop)
        self.update_spectrum()
    

    def update_spectrum(self):
        self.data.update_spectra()
        self.setImage(self.data.spectrum[self.channel],
                      autoLevels=False)
        self.setRect(QRectF(*self.data.spec_rect[self.channel]))

                
    def zoom_freq_in(self):
        df = self.f1 - self.f0
        if df > 0.1:
            df *= 0.5
            self.f1 = self.f0 + df
            
        
    def zoom_freq_out(self):
        if self.f1 - self.f0 < self.fmax:
            df = self.f1 - self.f0
            df *= 2.0
            if df > self.fmax:
                df = self.fmax
            self.f1 = self.f0 + df
            if self.f1 > self.fmax:
                self.f1 = self.fmax
                self.f0 = self.fmax - df
            if self.f0 < 0:
                self.f0 = 0
                self.f1 = df
                
        
    def freq_down(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 -= 0.5*df
            self.f1 -= 0.5*df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df

            
    def freq_up(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f0 += 0.5*df
            self.f1 += 0.5*df


    def freq_home(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 = 0.0
            self.f1 = df

            
    def freq_end(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f1 = ceil(self.fmax/(0.5*df))*(0.5*df)
            self.f0 = self.f1 - df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df


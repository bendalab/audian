from math import ceil
import numpy as np


class PlotRange(object):

    def __init__(self, axspec, nchannels):
        self.axspec = axspec
        self.rmin = None
        self.rmax = None
        self.min_dr = None
        self.r0 = [None]*nchannels
        self.r1 = [None]*nchannels
        self.axxs = [[]]*nchannels
        self.axys = [[]]*nchannels


    def add_xaxis(self, ax, channel, has_data=False):
        if has_data:
            amin, amax = ax.range()
            if self.rmin is None or amin < self.rmin:
                self.rmin = amin
            if self.rmax is None or amax > self.rmax:
                self.rmax = amax
        self.axxs[channel].append(ax)
        

    def add_yaxis(self, ax, channel, has_data=False):
        if has_data:
            amin, amax = ax.range()
            if self.rmin is None or amin < self.rmin:
                self.rmin = amin
            if self.rmax is None or amax > self.rmax:
                self.rmax = amax
        self.axys[channel].append(ax)


    def is_used(self):
        n = 0
        for axx in self.axxs:
            n += len(axx)
        for axy in self.axys:
            n += len(axy)
        return n > 0
        

    def set_limits(self):
        if not self.is_used():
            return
        if np.isfinite(self.rmin) and np.isfinite(self.rmax):
            # TODO: min_dr should eventually come from the data!!!
            self.min_dr = (self.rmax - self.rmin)/2**16
        else:
            self.min_dr = 2/2**16
        # limits:
        for axx in self.axxs:
            for ax in axx:
                if np.isfinite(self.rmin):
                    self.setLimits(xMin=self.rmin)
                if np.isfinite(self.rmax):
                    self.setLimits(xMax=self.rmax)
                if np.isfinite(self.rmin) and np.isfinite(self.rmax):
                    self.setLimits(minXRange=self.min_dr,
                                   maxXRange=self.rmax - self.rmin)
        for axy in self.axys:
            for ax in axy:
                if np.isfinite(self.rmin):
                    ax.setLimits(yMin=self.rmin)
                if np.isfinite(self.rmax):
                    ax.setLimits(yMax=self.rmax)
                if np.isfinite(self.rmin) and np.isfinite(self.rmax):
                    ax.setLimits(minYRange=self.min_dr,
                                 maxYRange=self.rmax - self.rmin)
        # ranges:
        for c in range(len(self.r0)):
            self.r0[c] = self.rmin
            self.r1[c] = self.rmax
            if not np.isfinite(self.r0[c]):
                self.r0[c] = -1
            if not np.isfinite(self.r1[c]):
                self.r1[c] = +1


    def set_ranges(self, r0=None, r1=None, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if len(self.axxs[c]) + len(self.axys[c]) == 0:
                continue
            if r0 is not None:
                self.r0[c] = r0
            if r1 is not None:
                self.r1[c] = r1
            dr = self.r1[c] - self.r0[c]
            if self.r0[c] < self.rmin:
                self.r0[c] = self.rmin
                self.r1[c] = self.rmin + dr
            if self.r1[c] > self.rmax:
                self.r1[c] = self.rmax
                self.r0[c] = self.rmax - dr
            if self.r0[c] < self.rmin:
                self.r0[c] = self.rmin
            if do_set:
                for ax in self.axxs[c]:
                    ax.setXRange(self.r0[c], self.r1[c])
                for ax in self.axys[c]:
                    ax.setYRange(self.r0[c], self.r1[c])


    def zoom_in(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.rmin < 0:
                h = 0.25*(self.r1[c] - self.r0[c])
                m = 0.5*(self.r1[c] + self.r0[c])
                if h > self.min_dr:
                    self.set_ranges(m - h, m + h, [c], do_set)
            else:
                dr = self.r1[c] - self.r0[c]
                if dr > self.min_dr:
                    dr *= 0.5
                    self.set_ranges(self.r0[c], self.r0[c] + dr, [c], do_set)
                
        
    def zoom_out(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.rmin < 0:
                h = self.r1[c] - self.r0[c]
                m = 0.5*(self.r1[c] + self.r0[c])
                self.set_ranges(m - h, m + h, [c], do_set)
            else:
                dr = self.r1[c] - self.r0[c]
                dr *= 2.0
                if dr > self.rmax:
                    dr = self.rmax
                self.set_ranges(self.r0[c], self.r0[c] + dr, [c], do_set)

                
    def down(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r0[c] > self.rmin:
                dr = self.r1[c] - self.r0[c]
                self.set_ranges(self.r0[c] - 0.5*dr, self.r1[c] - 0.5*dr,
                                [c], do_set)
                
                
    def up(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r1[c] < self.rmax:
                dr = self.r1[c] - self.r0[c]
                self.set_ranges(self.r0[c] + 0.5*dr, self.r1[c] + 0.5*dr,
                                [c], do_set)
                
                
    def home(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r0[c] > self.rmin:
                dr = self.r1[c] - self.r0[c]
                self.set_ranges(self.rmin, self.rmin + dr, [c], do_set)
                
                
    def end(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r1[c] < self.rmax:
                dr = self.r1[c] - self.r0[c]
                r1 = ceil(self.rmax/(0.5*dr))*(0.5*dr)
                self.set_ranges(r1 - dr, r1, [c], do_set)
                
        
    def auto(self, t0, t1, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        rmin = None
        rmax = None
        for c in channels:
            for ax in self.axxs[c] + self.axys[c]:
                r0, r1 = ax.amplitudes(t0, t1)
                if rmin is None or r0 < rmin:
                    rmin = r0
                if rmax is None or r1 > rmax:
                    rmax = r1
        self.set_ranges(rmin, rmax, channels, do_set)

        
    def reset(self, channels=None, do_set=True):
        if not self.is_used():
            return
        rmin = self.rmin
        if not np.isfinite(rmin):
            rmin = -1
        rmax = self.rmax
        if not np.isfinite(rmax):
            rmax = +1
        self.set_ranges(rmin, rmax, channels, do_set)

        
    def center(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            r = max(np.abs(self.r0[c]), np.abs(self.r1[c]))
            self.set_ranges(-r, +r, [c], do_set)

            
    def show_crosshair(self, show):
        for axx in self.axxs:
            for ax in axx:
                ax.xline.setVisible(show)
        for axy in self.axys:
            for ax in axy:
                ax.yline.setVisible(show)
        

    def set_crosshair(self, pos):
        for axx in self.axxs:
            for ax in axx:
                ax.xline.setPos(pos)
        for axy in self.axys:
            for ax in axy:
                ax.yline.setPos(pos)
        

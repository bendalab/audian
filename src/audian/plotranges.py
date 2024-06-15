""" Manage ranges of plot axes.

`class PlotRange`: a single axis range
`class PlotRanges`: manage all ranges
"""

from math import ceil
import numpy as np
from functools import partial
from .panels import Panel


class PlotRange(object):

    def __init__(self, axspec, nchannels):
        self.axspec = axspec
        self.rmin = None
        self.rmax = None
        self.rstep = None
        self.min_dr = None
        self.r0 = [None]*nchannels
        self.r1 = [None]*nchannels
        self.axxs = [[] for i in range(nchannels)]
        self.axys = [[] for i in range(nchannels)]
        self.axzs = [[] for i in range(nchannels)]
        self.marker_channel = None
        self.marker_ax = None
        self.marker_pos = None


    def _add_axis(self, axs, ax, rmin, rmax, rstep):
        if rmin is None or rmax is None:
            rmin, rmax = ax.range()
        if rmin is not None and (self.rmin is None or rmin < self.rmin):
            self.rmin = rmin
        if rmax is not None and (self.rmax is None or rmax > self.rmax):
            self.rmax = rmax
        if rstep is not None and (self.rstep is None or rstep < self.rstep):
            self.rstep = rstep
        axs.append(ax)
        

    def add_xaxis(self, ax, channel, rmin=None, rmax=None, rstep=None):
        self._add_axis(self.axxs[channel], ax, rmin, rmax, rstep)
        

    def add_yaxis(self, ax, channel, rmin=None, rmax=None, rstep=None):
        self._add_axis(self.axys[channel], ax, rmin, rmax, rstep)


    def add_zaxis(self, ax, channel, rmin=None, rmax=None, rstep=None):
        self._add_axis(self.axzs[channel], ax, rmin, rmax, rstep)


    def is_used(self):
        n = 0
        for axx in self.axxs:
            n += len(axx)
        for axy in self.axys:
            n += len(axy)
        for axz in self.axzs:
            n += len(axz)
        return n > 0

    
    def is_amplitude(self):
        return self.axspec in Panel.amplitudes
        
    
    def is_frequency(self):
        return self.axspec in Panel.frequencies
        
    
    def is_power(self):
        return self.axspec in Panel.powers
        

    def get_axspec(self, viewbox):
        for axx in self.axxs:
            for ax in axx:
                if ax.getViewBox() is viewbox:
                    return self.axspec
        for axy in self.axys:
            for ax in axy:
                if ax.getViewBox() is viewbox:
                    return self.axspec
        for axz in self.axzs:
            for ax in axz:
                if ax.getViewBox() is viewbox:
                    return self.axspec
        return None


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
                    ax.setLimits(xMin=self.rmin)
                if np.isfinite(self.rmax):
                    ax.setLimits(xMax=self.rmax)
                if np.isfinite(self.rmin) and np.isfinite(self.rmax):
                    ax.setLimits(minXRange=self.min_dr,
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
            if len(self.axxs[c]) + len(self.axys[c]) + len(self.axzs[c]) == 0:
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
                for ax in self.axzs[c]:
                    ax.setZRange(self.r0[c], self.r1[c])

                    
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
                
                
    def step_down(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r0[c] > self.rmin:
                self.set_ranges(self.r0[c] - self.rstep,
                                self.r1[c] - self.rstep,
                                [c], do_set)
                
                
    def step_up(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r1[c] < self.rmax:
                self.set_ranges(self.r0[c] + self.rstep,
                                self.r1[c] + self.rstep,
                                [c], do_set)
                
                
    def min_down(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r0[c] > self.rmin:
                self.set_ranges(self.r0[c] - self.rstep, self.r1[c],
                                [c], do_set)
                
                
    def min_up(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r0[c] < self.rmax:
                self.set_ranges(self.r0[c] + self.rstep, self.r1[c],
                                [c], do_set)
                
                
    def max_down(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r1[c] > self.rmin:
                self.set_ranges(self.r0[c], self.r1[c] - self.rstep,
                                [c], do_set)
                
                
    def max_up(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            if self.r1[c] < self.rmax:
                self.set_ranges(self.r0[c], self.r1[c] + self.rstep,
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


    def set_powers(self):
        if not self.is_power() or not self.is_used():
            return
        zmin = None
        zmax = None
        for c in range(len(self.axzs)):
            for ax in self.axzs[c]:
                if hasattr(ax, 'data_items'):
                    for item in ax.data_items:
                        if hasattr(item, 'data'):
                            z0, z1 = item.data.estimate_noiselevels(c)
                            if z0 is not None and z1 is not None:
                                if zmin is None or z0 < zmin:
                                    zmin = z0
                                if zmax is None or z1 > zmax:
                                    zmax = z1
        if zmin is not None and zmax is not None:
            self.set_ranges(zmin, zmax)
        
                
    def clear_marker(self):
        self.marker_channel = None
        self.marker_ax = None
        self.marker_pos = None

        
    def set_marker(self, channel, ax, pos):
        self.marker_channel = channel
        self.marker_ax = ax
        self.marker_pos = pos


    def update_crosshair(self):
        for axx in self.axxs:
            for ax in axx:
                if self.marker_pos is not None:
                    ax.xline.setPos(self.marker_pos)
                ax.xline.setVisible(self.marker_pos is not None)
        for axy in self.axys:
            for ax in axy:
                if self.marker_pos is not None:
                    ax.yline.setPos(self.marker_pos)
                ax.yline.setVisible(self.marker_pos is not None)

        
class PlotRanges(dict):
    
    def __init__(self):
        super().__init__()
        for m in ['zoom_in', 'zoom_out', 'down', 'up', 'step_down', 'step_up',
                  'min_down', 'min_up', 'max_down', 'max_up',
                  'home', 'end', 'auto', 'reset', 'center']:
            setattr(self, m, partial(PlotRanges._apply, self, m))


    def setup(self, nchannels):
        for s in Panel.amplitudes + Panel.frequencies + Panel.powers:
            self[s] = PlotRange(s, nchannels)


    def set_limits(self):
        for r in self.values():
            r.set_limits()
        

    def set_ranges(self):
        for r in self.values():
            r.set_ranges()


    def set_powers(self):
        for r in self.values():
            r.set_powers()


    def get_axspec(self, viewbox):
        for r in self.values():
            axspec = r.get_axspec(viewbox)
            if axspec:
                return axspec
        return None


    def clear_marker(self):
        for r in self.values():
            r.clear_marker()


    def _marker_pos(self, ranges):
        for r in ranges:
            if self[r].marker_pos is not None:
                return r, self[r].marker_pos
        return None, None


    def marker_amplitude(self):
        return self._marker_pos(Panel.amplitudes)


    def marker_frequency(self):
        return self._marker_pos(Panel.frequencies)


    def marker_power(self):
        return self._marker_pos(Panel.powers)

            
    def update_crosshair(self):
        for r in self.values():
            r.update_crosshair()

            
    def _apply(self, rfunc, axspec, *args, **kwargs):
        for s in axspec:
            getattr(self[s], rfunc)(*args, **kwargs)
            

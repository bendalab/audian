""" Manage ranges of plot axes.

`class PlotRange`: a single axis range
`class PlotRanges`: manage all ranges
"""

from math import ceil, log
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
        self.stored_marker_channel = None
        self.stored_marker_ax = None
        self.stored_marker_pos = None


    def __str__(self):
        rmins = f'{"-":>8}' if self.rmin is None else f'{self.rmin:8.5g}' 
        rmaxs = f'{"-":>8}' if self.rmax is None else f'{self.rmax:8.5g}' 
        rsteps = f'{"-":>8}' if self.rstep is None else f'{self.rstep:8.5g}' 
        mindrs = f'{"-":>8}' if self.min_dr is None else f'{self.min_dr:8.3g}'
        r0s = f'{"-":>8}' if self.r0[0] is None else f'{self.r0[0]:8.5g}'
        r1s = f'{"-":>8}' if self.r1[0] is None else f'{self.r1[0]:8.5g}'
        return f'{self.axspec}: rmin={rmins} rmax={rmaxs} rstep={rsteps} min_dr={mindrs} r0={r0s} r1={r1s}'


    def _add_axis(self, axs, ax):
        rmin, rmax, rstep = ax.range(self.axspec)
        if rmin is not None and (self.rmin is None or rmin < self.rmin):
            self.rmin = rmin
        if rmax is not None and (self.rmax is None or rmax > self.rmax):
            self.rmax = rmax
        if rstep is not None and (self.rstep is None or rstep < self.rstep):
            self.rstep = rstep
        axs.append(ax)
        

    def add_xaxis(self, ax, channel):
        self._add_axis(self.axxs[channel], ax)
        

    def add_yaxis(self, ax, channel):
        self._add_axis(self.axys[channel], ax)


    def add_zaxis(self, ax, channel):
        self._add_axis(self.axzs[channel], ax)


    def is_used(self):
        n = 0
        for axx in self.axxs:
            n += len(axx)
        for axy in self.axys:
            n += len(axy)
        for axz in self.axzs:
            n += len(axz)
        return n > 0

    
    def is_time(self):
        return self.axspec in Panel.times
        
    
    def is_amplitude(self):
        return self.axspec in Panel.amplitudes
        
    
    def is_frequency(self):
        return self.axspec in Panel.frequencies
        
    
    def is_power(self):
        return self.axspec in Panel.powers
        

    def enable_starttime(self, enable):
        for axx in self.axxs:
            for ax in axx:
                ax.enable_starttime(enable)


    def at_end(self, channel=0):
        return self.r1[channel] >= self.rmax


    def at_home(self, channel=0):
        return self.r0[channel] <= self.rmin

                
    def set_limits(self):
        if not self.is_used():
            return
        if np.isfinite(self.rmin) and np.isfinite(self.rmax):
            # TODO: min_dr should eventually come from the data!!!
            if self.is_time():
                self.min_dr = 0.001
            else:
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
            if self.is_time():
                self.r1[c] = 10
            else:
                self.r1[c] = self.rmax
            if not np.isfinite(self.r0[c]):
                self.r0[c] = -1
            if not np.isfinite(self.r1[c]):
                self.r1[c] = +1


    def set_ranges(self, r0=None, r1=None, dr=None,
                   channels=None, do_set=True):
        if not self.is_used():
            return
        # time ranges are all the same over all the channels!
        if channels is None or self.is_time():
            channels = range(len(self.r0))
        cc = -1
        for c in channels:
            if len(self.axxs[c]) + len(self.axys[c]) + len(self.axzs[c]) == 0:
                continue
            if cc >= 0:
                self.r0[c] = self.r0[cc]
                self.r1[c] = self.r1[cc]
            else:
                if r0 is not None:
                    self.r0[c] = r0
                if r1 is not None:
                    self.r1[c] = r1
                if dr is not None:
                    if r1 is None:
                        self.r1[c] = self.r0[c] + dr
                    else:
                        self.r0[c] = self.r1[c] - dr
                dr = self.r1[c] - self.r0[c]
                if self.r0[c] < self.rmin:
                    self.r0[c] = self.rmin
                    self.r1[c] = self.rmin + dr
                if self.r1[c] > self.rmax and self.is_time():
                    self.r1[c] = self.rmax
                    self.r0[c] = self.rmax - dr
                if self.r0[c] < self.rmin:
                    self.r0[c] = self.rmin
                if self.is_time():
                    cc = c
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
        if self.is_time():
            channels = [0]
        for c in channels:
            if self.rmin < 0:
                h = 0.25*(self.r1[c] - self.r0[c])
                m = 0.5*(self.r1[c] + self.r0[c])
                if h > self.min_dr:
                    self.set_ranges(m - h, m + h, None, [c], do_set)
            else:
                dr = self.r1[c] - self.r0[c]
                if dr > self.min_dr:
                    dr *= 0.5
                    self.set_ranges(self.r0[c], None, dr, [c], do_set)
                
        
    def zoom_out(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if self.rmin < 0:
                h = self.r1[c] - self.r0[c]
                m = 0.5*(self.r1[c] + self.r0[c])
                self.set_ranges(m - h, m + h, None, [c], do_set)
            else:
                dr = 2*(self.r1[c] - self.r0[c])
                self.set_ranges(self.r0[c], None, dr, [c], do_set)

                
    def move(self, move_fac, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if (move_fac > 0 and self.r1[c] < self.rmax) or \
               (move_fac < 0 and self.r0[c] > self.rmin):
                dr = self.r1[c] - self.r0[c]
                self.set_ranges(self.r0[c] + move_fac*dr,
                                self.r1[c] + move_fac*dr,
                                None, [c], do_set)
                
    def down(self, channels=None, do_set=True):
        self.move(-0.5, channels, do_set)
                
                
    def up(self, channels=None, do_set=True):
        self.move(+0.5, channels, do_set)
                
                
    def small_down(self, channels=None, do_set=True):
        self.move(-0.05, channels, do_set)
                
                
    def small_up(self, channels=None, do_set=True):
        self.move(+0.05, channels, do_set)
                
                
    def step(self, step_fac, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if (step_fac > 0 and self.r1[c] < self.rmax) or \
               (step_fac < 0 and self.r0[c] > self.rmin):
                self.set_ranges(self.r0[c] + step_fac*self.rstep,
                                self.r1[c] + step_fac*self.rstep,
                                None, [c], do_set)
                
                
    def step_down(self, channels=None, do_set=True):
        self.step(-1, channels, do_set)
                
                
    def step_up(self, channels=None, do_set=True):
        self.step(+1, channels, do_set)
                
                
    def min_step(self, step_fac, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if (step_fac > 0 and self.r0[c] < self.r1[c]) or \
               (step_fac < 0 and self.r0[c] > self.rmin):
                self.set_ranges(self.r0[c] + step_fac*self.rstep, self.r1[c],
                                None, [c], do_set)
                
                
    def min_down(self, channels=None, do_set=True):
        self.min_step(-1, channels, do_set)
                
                
    def min_up(self, channels=None, do_set=True):
        self.min_step(+1, channels, do_set)
                
                
    def max_step(self, step_fac, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if (step_fac > 0 and self.r1[c] < self.rmax) or \
               (step_fac < 0 and self.r1[c] > self.r0[c]):
                self.set_ranges(self.r0[c], self.r1[c] + step_fac*self.rstep,
                                None, [c], do_set)
                
                
    def max_down(self, channels=None, do_set=True):
        self.max_step(-1, channels, do_set)
                
                
    def max_up(self, channels=None, do_set=True):
        self.max_step(+1, channels, do_set)
                
                
    def home(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if self.r0[c] > self.rmin:
                dr = self.r1[c] - self.r0[c]
                self.set_ranges(self.rmin, None, dr, [c], do_set)
                
                
    def end(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            if self.r1[c] < self.rmax:
                dr = self.r1[c] - self.r0[c]
                r1 = ceil(self.rmax/(0.5*dr))*(0.5*dr)
                self.set_ranges(None, r1, dr, [c], do_set)
        """
        Former time range:
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            return True
        return False

        """
                
                
    def snap(self, channels=None, do_set=True):
        if not self.is_used():
            return
        if channels is None:
            channels = range(len(self.r0))
        if self.is_time():
            channels = [0]
        for c in channels:
            dr = self.r1[c] - self.r0[c]
            dr = 10 * 2**round(log(dr/10)/log(2))
            r0 = round(self.r0[c]/(dr/2))*(dr/2)
            self.set_ranges(r0, None, dr, [c], do_set)
    
        
    def auto(self, t0, t1, channels=None, do_set=True):
        if not self.is_used() or self.is_time():
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
        self.set_ranges(rmin, rmax, None, channels, do_set)

        
    def reset(self, channels=None, do_set=True):
        if not self.is_used():
            return
        rmin = self.rmin
        if not np.isfinite(rmin):
            rmin = -1
        rmax = self.rmax
        if not np.isfinite(rmax):
            rmax = +1
        self.set_ranges(rmin, rmax, None, channels, do_set)

        
    def center(self, channels=None, do_set=True):
        if not self.is_used() or self.is_time():
            return
        if channels is None:
            channels = range(len(self.r0))
        for c in channels:
            r = max(np.abs(self.r0[c]), np.abs(self.r1[c]))
            self.set_ranges(-r, +r, None, [c], do_set)


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

                
    def store_marker(self):
        self.stored_marker_channel = self.marker_channel
        self.stored_marker_ax = self.marker_ax
        self.stored_marker_pos = self.marker_pos
        if self.stored_marker_channel is None:
            return None, None, None
        for ax in self.axxs[self.stored_marker_channel]:
            if ax is self.stored_marker_ax:
                return self.stored_marker_ax, self.stored_marker_pos, None
        for ax in self.axys[self.stored_marker_channel]:
            if ax is self.stored_marker_ax:
                return self.stored_marker_ax, None, self.stored_marker_pos
        return None, None, None


    def clear_stored_marker(self):
        for axx in self.axxs:
            for ax in axx:
                ax.stored_marker.setVisible(False)
        for axy in self.axys:
            for ax in axy:
                ax.stored_marker.setVisible(False)
        self.stored_marker_channel = None
        self.stored_marker_ax = None
        self.stored_marker_pos = None


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
        for m in ['zoom_in', 'zoom_out', 'down', 'up', 'small_down', 'small_up',
                  'step_down', 'step_up', 'min_down', 'min_up',
                  'max_down', 'max_up', 'home', 'end', 'snap',
                  'auto', 'reset', 'center']:
            setattr(self, m, partial(PlotRanges._apply, self, m))


    def __str__(self):
        s = []
        for r in self.values():
            s.append(str(r))
        return '\n'.join(s)


    def setup(self, nchannels):
        for s in Panel.times + Panel.amplitudes + Panel.frequencies + Panel.powers:
            self[s] = PlotRange(s, nchannels)


    def add_plot(self, ax):
        self[ax.x()].add_xaxis(ax, ax.channel)
        self[ax.y()].add_yaxis(ax, ax.channel)
        if ax.z():
            self[ax.z()].add_zaxis(ax, ax.channel)


    def set_limits(self):
        for r in self.values():
            r.set_limits()
        

    def set_ranges(self):
        for r in self.values():
            r.set_ranges()


    def set_powers(self):
        for r in self.values():
            r.set_powers()

            
    def _apply(self, rfunc, axspec, *args, **kwargs):
        for s in axspec:
            getattr(self[s], rfunc)(*args, **kwargs)
            

    def clear_marker(self):
        for r in self.values():
            r.clear_marker()


    def store_marker(self):
        axm = None
        xpos = None
        ypos = None
        for r in self.values():
            r.clear_stored_marker()
            ax, x, y = r.store_marker()
            if ax is not None:
                if axm is None:
                    axm = ax
                    xpos = x
                    ypos = y
                elif axm is ax:
                    if xpos is None and x is not None:
                        xpos = x
                    if ypos is None and y is not None:
                        ypos = y
        if axm is not None and xpos is not None and ypos is not None:
            axm.set_stored_marker(xpos, ypos)


    def clear_stored_marker(self):
        for r in self.values():
            r.clear_stored_marker()

            
    def _marker_pos(self, ranges):
        for r in ranges:
            if self[r].marker_pos is not None:
                return r, self[r].marker_pos
        return None, None


    def marker_time(self):
        return self._marker_pos(Panel.times)


    def marker_amplitude(self):
        return self._marker_pos(Panel.amplitudes)


    def marker_frequency(self):
        return self._marker_pos(Panel.frequencies)


    def marker_power(self):
        return self._marker_pos(Panel.powers)

            
    def _marker_delta(self, ranges):
        for r in ranges:
            if self[r].marker_pos is not None and \
               self[r].stored_marker_pos is not None:
                return r, self[r].marker_pos - self[r].stored_marker_pos
        return None, None


    def marker_delta_time(self):
        return self._marker_delta(Panel.times)


    def marker_delta_amplitude(self):
        return self._marker_delta(Panel.amplitudes)


    def marker_delta_frequency(self):
        return self._marker_delta(Panel.frequencies)


    def marker_delta_power(self):
        return self._marker_delta(Panel.powers)

            
    def update_crosshair(self):
        for r in self.values():
            r.update_crosshair()


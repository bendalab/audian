""" Manage plot panels.

`class Panel`: a single plot panel
`class Panels`: manage all plot panels
"""

import numpy as np
from .traceitem import TraceItem
from .specitem import SpecItem


class Panel(object):


    times = 't'
    amplitudes = 'xyu'
    frequencies = 'fw'
    powers = 'pq'
    spacer = 'spacer'
    
    
    def __init__(self, name, ax_spec, row):
        self.name = name
        self.ax_spec = ax_spec
        self.row = row
        self.axs = []
        self.axcs = []   # associated color bars


    def __str__(self):
        return f'{self.name:20}: {self.ax_spec:6} @ {self.row:2} with {len(self.axs):2} plots'


    def __len__(self):
        return len(self.axs)


    def __eq__(self, ax_spec):
        return self.ax_spec == ax_spec


    def x(self):
        return self.ax_spec[0]


    def y(self):
        return self.ax_spec[1]


    def z(self):
        return self.ax_spec[2] if len(self.ax_spec) > 2 else ''


    def is_time(self):
        return self.x() in self.times


    def is_xamplitude(self):
        return self.x() in self.amplitudes


    def is_yamplitude(self):
        return self.y() in self.amplitudes


    def is_xfrequency(self):
        return self.x() in self.frequencies


    def is_yfrequency(self):
        return self.y() in self.frequencies


    def is_xpower(self):
        return self.x() in self.powers


    def is_ypower(self):
        return self.y() in self.powers


    def is_zpower(self):
        z = self.z()
        return z and z in self.powers


    def is_trace(self):
        return self.is_time() and self.is_yamplitude()


    def is_spectrogram(self):
        return self.is_time() and self.is_yfrequency()


    def is_power(self):
        return self.is_xpower() and self.is_yfrequency()


    def is_spacer(self):
        return self.ax_spec == self.spacer

    
    def add_ax(self, row, ax, axc=None):
        self.row = row
        self.axs.append(ax)
        if axc is not None:
            self.axcs.append(axc)


    def is_used(self):
        return len(self.axs) > 0


    def is_visible(self, channel):
        return self.axs[channel].isVisible()


    def set_visible(self, visible):
        changed = False
        for ax in self.axs:
            if ax.isVisible() != visible:
                changed = True
            ax.setVisible(visible)
        return changed


    def has_visible_traces(self, channel):
        if self.is_spacer():
            return False
        for di in self.axs[channel].data_items:
            if di.isVisible():
                return True
        return False


    def has_viewbox(self, viewbox):
        for ax in self.axs:
            if ax.getViewBox() is viewbox:
                return True
        return False


    def show_grid(self, grids):
        if self.is_spacer():
            return False
        for ax in self.axs:
            ax.showGrid(x=(grids & 1) > 0, y=(grids & 2) > 0,
                        alpha=0.8)
            """
            # fix grid bug:
            ax.getAxis('bottom').setGrid(False)
            ax.getAxis('left').setGrid(False)
            for axis in ['right', 'top']:
                ax.showAxis(axis)
                ax.getAxis(axis).setStyle(showValues=False)
            """

    def is_cbar_visible(self, channel):
        return self.axcs[channel].isVisible()


    def set_cbar_visible(self, visible):
        changed = False
        for ax in self.axcs:
            if ax.isVisible() != visible:
                changed = True
            ax.setVisible(visible)
        return changed


    def set_colormap(self, color_map):
        for ax in self.axcs:
            ax.setColorMap(color_map)

            
    def add_item(self, plot_item, channel=-1, is_data=False):
        if channel >= 0:
            self.axs[channel].add_item(plot_item, is_data)
        else:
            for ax in self.axs:
                ax.add_item(plot_item, is_data)


    def add_traces(self, channel, data): 
        for trace in data.traces:
            if trace.panel != self.name:
                continue
            if self.is_trace():
                item = TraceItem(trace, channel)
            if self.is_spectrogram():
                item = SpecItem(trace, channel)
            self.add_item(item, channel, True)


    def get_amplitude(self, channel, t, x, t1=None):
        if not self.is_yamplitude() or len(self.axs[channel].data_items) == 0:
            return t, None
        trace = self.axs[channel].data_items[-1]
        return trace.get_amplitude(t, x, t1)


    def get_power(self, channel, t, f):
        if not self.is_yfrequency() or len(self.axs[channel].data_items) == 0:
            return None
        trace = self.axs[channel].data_items[0]
        return trace.get_power(t, f)


    def update_plots(self):
        for ax in self.axs:
            if ax.isVisible() and not self.is_spacer():
                ax.update_plot()


class Panels(dict):

    def __init__(self):
        super().__init__(self)


    def __str__(self):
        s = []
        for panel in self.values():
            s.append(str(panel))
        return '\n'.join(s)


    def add(self, name, axes, row=None, adjust_rows=True):
        if row is None:
            row = self.max_row() + 1
        if adjust_rows:
            for panel in self.values():
                if panel.row >= row:
                    panel.row += 1
        self[name] = Panel(name, axes, row)
        if len(self) > 1:
            names = np.array(list(self.keys()))
            rows = [self[name].row for name in names]
            inx = np.argsort(rows)
            panels = dict(self)
            self.clear()
            for name in names[inx]:
                self[name] = panels[name]


    def add_trace(self, name='trace', row=None):
        # find amplitude that is not used yet:
        amps = [False]*len(Panel.amplitudes)
        for panel in self.values():
            if panel.is_trace():
                amps[Panel.amplitudes.index(panel.y())] = True
        axspec = Panel.times[0] + Panel.amplitudes[0]
        for k in range(len(amps)):
            if not amps[k]:
                axspec = axspec[0] + Panel.amplitudes[k]
                break
        self.add(name, axspec, row)

        
    def add_spectrogram(self, name='spectrogram', row=None):
        # find frequencies and powers that are not used yet:
        freqs = [False]*len(Panel.frequencies)
        pwrs = [False]*len(Panel.powers)
        for panel in self.values():
            if panel.is_spectrogram():
                freqs[Panel.frequencies.index(panel.y())] = True
                pwrs[Panel.powers.index(panel.z())] = True
        axspec = Panel.times[0] + Panel.frequencies[0] + Panel.powers[0]
        for k in range(len(freqs)):
            if not freqs[k]:
                axspec = axspec[0] + Panel.frequencies[k] + axspec[2]
                break
        for k in range(len(pwrs)):
            if not pwrs[k]:
                axspec = axspec[:2] + Panel.powers[k]
                break
        self.add(name, axspec, row)
        self.add(name + '-power', axspec[2] + axspec[1], self[name].row, False)


    def fill(self, data):
        for trace in data.traces:
            if trace.panel not in self:
                if trace.panel_type == 'trace':
                    self.add_trace(trace.panel)
                elif trace.panel_type == 'spectrogram':
                    self.add_spectrogram(trace.panel)
        

    def remove(self, name):
        del self[name]

        
    def max_row(self):
        if len(self) > 0:
            return  np.max([panel.row for panel in self.values()])
        else:
            return -1

        
    def add_power_ax(self, name, row, ax):
        name = name + '-power'
        if name in self:
            self[name].add_ax(row, ax)
            

    def get_panel(self, viewbox):
        for panel in self.values():
            if panel.has_viewbox(viewbox):
                return panel
        return None

    
    def show_grid(self, grids):
        for panel in self.values():
            panel.show_grid(grids)

            
    def update_plots(self):
        for panel in self.values():
            panel.update_plots()


    def insert_spacers(self):
        panels = {}
        row = 0
        spacer = 0
        for name in self:
            if row > 0 and not self[name].is_power():
                panels[f'spacer{spacer}'] = Panel(f'spacer{spacer}',
                                                  Panel.spacer, 0)
                spacer += 1
            panels[name] = self[name]
            row += 1
        self.clear()
        for name, value in panels.items():
            self[name] = value
        
            
    def show_spacers(self, channel):
        prev_panel = None
        prev_spacer = None
        for panel in self.values():
            if panel.is_spacer():
                if prev_panel:
                    prev_visible = prev_panel.is_visible(channel)
                    panel.set_visible(prev_visible)
                    if prev_visible:
                        prev_spacer = panel
            elif not panel.is_power():
                prev_panel = panel
                if panel.is_visible(channel):
                    prev_spacer = None
        if prev_spacer:
            panel.set_visible(False)

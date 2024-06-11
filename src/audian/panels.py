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
    powers = 'pP'
    spacer = 'spacer'
    
    
    def __init__(self, name, ax_spec, row):
        self.name = name
        self.ax_spec = ax_spec
        self.row = row
        self.axs = []
        self.items = []


    def __len__(self):
        return len(self.axs)


    def __eq__(self, ax_spec):
        return self.ax_spec == ax_spec


    def is_time(self):
        return self.ax_spec[1] in self.times


    def is_xamplitude(self):
        return self.ax_spec[1] in self.amplitudes


    def is_yamplitude(self):
        return self.ax_spec[0] in self.amplitudes


    def is_xfrequency(self):
        return self.ax_spec[1] in self.frequencies


    def is_yfrequency(self):
        return self.ax_spec[0] in self.frequencies


    def is_ypower(self):
        return self.ax_spec[0] in self.powers


    def is_trace(self):
        return self.is_time() and self.is_yamplitude()


    def is_spectrogram(self):
        return self.is_time() and self.is_yfrequency()


    def is_spacer(self):
        return self.ax_spec == self.spacer

    
    def add_ax(self, ax):
        self.axs.append(ax)
        self.items.append([])


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

            
    def add_item(self, channel, plot_item, is_data):
        self.axs[channel].add_item(plot_item, is_data)
        self.items[channel].append(plot_item)


    def add_traces(self, channel, data):        
        for trace in data.traces:
            if trace.panel != self.name:
                continue
            if self.is_trace():
                item = TraceItem(trace, channel)
            if self.is_spectrogram():
                item = SpecItem(trace, channel)
            self.add_item(channel, item, True)


    def get_amplitude(self, channel, t, x, t1=None):
        if not self.is_amplitude() or len(self.axs[channel].data_items) == 0:
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


    def add(self, name, axes, row=None):
        if row is None:
            row = len(self)
        for panel in self.values():
            if panel.row >= row:
                panel.row += 1
        self[name] = Panel(name, axes, row)
        if len(self) > 1:
            names = np.array(list(self.keys()))
            rows = [self[name].row for name in names]
            inx = np.argsort(rows)
            self = {name: self[name] for name in names[inx]}

            
    def remove(self, name):
        del self[name]


    def clear(self):
        self = {}


    def update_plots(self):
        for panel in self.values():
            panel.update_plots()


    def insert_spacers(self):
        panels = {}
        row = 0
        spacer = 0
        for name in self:
            if row > 0:
                panels[f'spacer{spacer}'] = Panel(f'spacer{spacer}',
                                                  Panel.spacer, 0)
                spacer += 1
            panels[name] = self[name]
            row += 1
        self = panels
        
            
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
            else:
                prev_panel = panel
                if panel.is_visible(channel):
                    prev_spacer = None
        if prev_spacer:
            panel.set_visible(False)

from .traceitem import TraceItem
from .specitem import SpecItem


class Panel(object):
    
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
        return self.ax_spec[1] == 't'


    def is_amplitude(self):
        return self.ax_spec[0] in 'xyu'


    def is_xfrequency(self):
        return self.ax_spec[1] == 'f'


    def is_yfrequency(self):
        return self.ax_spec[0] == 'f'

    
    def add_ax(self, ax):
        self.axs.append(ax)
        self.items.append([])


    def is_used(self):
        return len(self.axs) > 0


    def is_visible(self, channel):
        return self.axs[channel].isVisible()


    def set_visible(self, visible):
        for ax in self.axs:
            ax.setVisible(visible)

            
    def add_item(self, channel, plot_item, is_data):
        self.axs[channel].add_item(plot_item, is_data)
        self.items[channel].append(plot_item)


    def add_traces(self, channel, data):        
        for trace in data.traces:
            if trace.panel != self.name:
                continue
            if self.ax_spec in ['xt', 'yt', 'ut']:
                item = TraceItem(trace, channel)
            elif self.ax_spec == 'ft':
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
            if ax.isVisible() and self.ax_spec != 'spacer':
                ax.update_plot()

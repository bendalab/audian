
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

    
    def add_ax(self, ax):
        self.axs.append(ax)
        self.items.append([])


    def is_visible(self, channel):
        return self.axs[channel].isVisible()


    def set_visible(self, visible):
        for ax in self.axs:
            ax.setVisible(visible)

            
    def add_item(self, channel, plot_item, is_data):
        self.axs[channel].add_item(plot_item, is_data)
        self.items[channel].append(plot_item)


    def update_plots(self):
        for ax in self.axs:
            if ax.isVisible() and self.ax_spec != 'spacer':
                ax.update_plot()

from math import floor, log10
import pyqtgraph as pg
from thunderlab.tabledata import TableData


class Analyzer(object):

    def __init__(self, browser, name, source_name):
        self.browser = browser
        self.name = name
        self.source_name = source_name
        self.source = self.trace(self.source_name)
        self.data = TableData()
        self.events = {}
        self.browser.add_analyzer(self)

        
    def analyze(self, t0, t1, channel, traces):
        pass


    def traces(self):
        return self.browser.data.keys()


    def trace(self, name):
        if name in self.browser.data:
            return self.browser.data[name]
        else:
            return None


    def make_column(self, label, unit=None, formats=None):
        self.data.append(label, unit, formats)

        
    def store(self, *args):
        self.data.append_data(args, 0)

        
    def make_trace_events(self, name, trace_name, symbol, color, size):
        self.events[name] = []
        for c in range(self.browser.data.data.channels):
            spi = pg.ScatterPlotItem()
            spi.setSymbol(symbol)
            spi.setBrush(color)
            spi.setSize(size)
            self.events[name].append(spi)
            self.browser.add_to_panel_trace(trace_name, c, spi)

        
    def make_panel_events(self, name, panel_name, symbol, color, size):
        self.events[name] = []
        panel = self.browser.panels[panel_name]
        for ax in panel.axs:
            spi = pg.ScatterPlotItem()
            spi.setSymbol(symbol)
            spi.setBrush(color)
            spi.setSize(size)
            self.events[name].append(spi)
            ax.add_item(spi)

        
    def set_events(self, name, channel, x, y):
        for c in range(self.browser.data.data.channels):
            if c == channel or channel < 0:
                self.events[name][c].setData(x, y)
            else:
                self.events[name][c].clear()
        
        
    def add_events(self, name, channel, x, y):
        for c in range(self.browser.data.data.channels):
            if c == channel or channel < 0:
                self.events[name][c].addPoints(x, y)
        
        
class PlainAnalyzer(Analyzer):

    def __init__(self, browser):
        super().__init__(browser, 'plain', 'data')
        nd = int(floor(-log10(1/self.source.rate)))
        if nd < 0:
            nd = 0
        self.make_column('tstart', 's', f'%.{nd}f')
        self.make_column('tend', 's', f'%.{nd}f')
        self.make_column('duration', 's', f'%.{nd}f')
        self.make_column('channel', '', '%.0f')

        
    def analyze(self, t0, t1, channel, traces):
        self.store(t0, t1, t1 - t0, channel)

        

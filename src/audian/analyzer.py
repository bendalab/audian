from math import floor, log10
import pyqtgraph as pg
from thunderlab.tabledata import TableData


class Analyzer(object):

    def __init__(self, browser, name):
        self.browser = browser
        self.name = name
        self.data = TableData()
        self.events = {}
        self.browser.add_analyzer(self)

        
    def analyze(self, t0, t1, channel, traces):
        pass


    def traces(self):
        return self.browser.data.keys()


    def trace(self, name):
        return self.browser.data[name]


    def add_column(self, label, unit=None, formats=None):
        self.data.append(label, unit, formats)

        
    def store(self, *args):
        self.data.append_data(args, 0)

        
    def add_events(self, name, trace_name, symbol, color, size):
        self.events[name] = []
        for c in range(self.browser.data.data.channels):
            spi = pg.ScatterPlotItem()
            spi.setSymbol(symbol)
            spi.setBrush(color)
            spi.setSize(size)
            self.events[name].append(spi)
            self.browser.add_to_panel(trace_name, c, spi)

        
    def set_events(self, name, channel, x, y):
        for c in range(self.browser.data.data.channels):
            if c == channel or channel < 0:
                self.events[name][c].setData(x, y)
            else:
                self.events[name][c].clear()
        
        
class PlainAnalyzer(Analyzer):

    def __init__(self, browser):
        super().__init__(browser, 'plain')
        source = self.trace('data')
        nd = int(floor(-log10(1/source.rate)))
        if nd < 0:
            nd = 0
        self.add_column('tstart', 's', f'%.{nd}f')
        self.add_column('tend', 's', f'%.{nd}f')
        self.add_column('duration', 's', f'%.{nd}f')
        self.add_column('channel', '', '%.0f')

        
    def analyze(self, t0, t1, channel, traces):
        self.store(t0, t1, t1 - t0, channel)

        

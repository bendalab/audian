from math import floor, log10
from thunderlab.tabledata import TableData


class Analyzer(object):

    def __init__(self, browser, name):
        self.name = name
        self.data = TableData()
        browser.add_analyzer(self)

        
    def analyze(self, t0, t1, channel, traces):
        pass


    def add_column(self, label, unit=None, formats=None):
        self.data.append(label, unit, formats)

        
    def store(self, *args):
        self.data.append_data(args, 0)



class PlainAnalyzer(Analyzer):

    def __init__(self, browser):
        super().__init__(browser, 'plain')
        source = browser.data['data']
        nd = int(floor(-log10(1/source.rate)))
        if nd < 0:
            nd = 0
        self.add_column('tstart', 's', f'%.{nd}f')
        self.add_column('tend', 's', f'%.{nd}f')
        self.add_column('duration', 's', f'%.{nd}f')
        self.add_column('channel', '', '%.0f')

        
    def analyze(self, t0, t1, channel, traces):
        self.store(t0, t1, t1 - t0, channel)

        

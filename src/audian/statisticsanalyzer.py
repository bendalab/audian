import numpy as np
from .analyzer import Analyzer


class StatisticsAnalyzer(Analyzer):
    
    def __init__(self, browser, source='filtered'):
        super().__init__(browser, 'statistics')
        self.source = source if source in browser.data.keys() else 'data'
        nd = int(-np.floor(np.log10(browser.data[self.source].ampl_max/4e4)))
        if nd < 0:
            nd = 0
        us = browser.data[self.source].unit
        self.make_column(f'{source} mean', us, f'%.{nd}f')
        self.make_column(f'{source} stdev', us, f'%.{nd}f')

        
    def analyze(self, t0, t1, channel, traces):
        source = traces[self.source][1]
        self.store(np.mean(source), np.std(source))


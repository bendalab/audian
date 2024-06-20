import numpy as np
from .analyzer import Analyzer


class StatisticsAnalyzer(Analyzer):
    
    def __init__(self, browser, source_name='filtered'):
        super().__init__(browser, 'statistics', source_name)
        nd = int(-np.floor(np.log10(self.source.ampl_max/4e4)))
        if nd < 0:
            nd = 0
        us = self.source.unit
        self.make_column(f'{self.source_name} mean', us, f'%.{nd}f')
        self.make_column(f'{self.source_name} stdev', us, f'%.{nd}f')

        
    def analyze(self, t0, t1, channel, traces):
        source = traces[self.source_name][1]
        self.store(np.mean(source), np.std(source))


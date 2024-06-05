import numpy as np
from .analyzer import Analyzer


class StatisticsAnalyzer(Analyzer):
    
    def __init__(self):
        super().__init__('statistics')
        # TODO: missing units!

        
    def analyze(self, t0, t1, channel, traces):
        trace = traces['filtered'] if 'filtered' in traces else traces['data']
        self.data.append({'mean': np.mean(trace),
                          'stdev': np.std(trace)})


import numpy as np
from .analyzer import Analyzer


class StatisticsAnalyzer(Analyzer):
    
    def __init__(self):
        super().__init__('statistics')
        self.data = {'mean': [], 'stdev': []}
        # TODO: missing units!

        
    def analyze(self, t0, t1, channel, traces):
        trace = traces['filtered'] if 'filtered' in traces else traces['data']
        self.data['mean'].append(np.mean(trace))
        self.data['stdev'].append(np.std(trace))


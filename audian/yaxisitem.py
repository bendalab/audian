from math import ceil, floor, log10
import numpy as np
from PyQt5.QtGui import QFontMetrics
import pyqtgraph as pg


class YAxisItem(pg.AxisItem):
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPen('white')


    def setLogMode(self, *args, **kwargs):
        # no log mode!
        pass


    def tickSpacing(self, minVal, maxVal, size):
        diff = abs(maxVal - minVal)
        if diff == 0:
            return []

        # hight of ytick labels:
        xwidth = QFontMetrics(self.font()).averageCharWidth()

        # minimum spacing:
        max_ticks = max(2, int(size / (3*xwidth)))
        min_spacing = diff / max_ticks
        p10unit = 10 ** floor(log10(min_spacing))

        # major ticks:
        factors = [1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0]
        for fac in factors:
            spacing = fac * p10unit
            if spacing >= min_spacing:
                break

        # minor ticks:
        factors = [100.0, 10.0, 1.0, 0.1]
        for fac in factors:
            minor_spacing = fac * p10unit
            if minor_spacing < spacing:
                break
            
        return [(spacing, 0), (minor_spacing, 0)]

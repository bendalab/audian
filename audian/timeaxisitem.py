from math import ceil, floor, log10
import numpy as np
from PyQt5.QtGui import QFontMetrics
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    
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

        # estimate width of xtick labels:
        xwidth = QFontMetrics(self.font()).averageCharWidth()
        if maxVal < 1.0:
            nx = 0
        elif maxVal >= 3600:
            nx = 8
        elif maxVal >= 60:
            nx = 5
        else:
            nx = 2
        spacing = diff/5
        if spacing < 0.00001:
            nx += 7
        elif spacing < 0.0001:
            nx += 6
        elif spacing < 0.001:
            nx += 5
        elif spacing < 1.0:
            nx += 4
        nx += 4

        # minimum spacing:
        max_ticks = max(2, int(size / (nx*xwidth)))
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

    
    def tickStrings(self, values, scale, spacing):
        if len(values) == 0:
            return []
        
        if scale > 1:
            self.setLabel('Time', units='s')
            return [f'{v*scale:.5g}' for v in values]

        if np.max(values) >= 3600:
            self.setLabel('Time (h:m:s)', units=None)
            fs = '{hours:.0f}:{mins:02.0f}:{secs:02.0f}'
        elif np.max(values) >= 60:
            self.setLabel('Time (m:s)', units=None)
            fs = '{mins:.0f}:{secs:02.0f}'
        else:
            self.setLabel('Time', units='s')
            fs = '{secs:.0f}'
        if spacing < 1:
            fs += '.{micros}'
        
        vals = []
        for time in values:
            hours = np.floor(time/3600)
            time -= hours*3600
            mins = np.floor(time/60)
            time -= mins*60
            secs = np.floor(time)
            time -= secs
            if spacing < 0.00001:
                micros = f'{1000000*time:06.0f}'
            elif spacing < 0.0001:
                micros = f'{100000*time:05.0f}'
            elif spacing < 0.001:
                micros = f'{10000*time:04.0f}'
            else:
                micros = f'{1000*time:03.0f}'
            time = dict(hours=hours, mins=mins, secs=secs, micros=micros)
            vals.append(fs.format(**time))
        return vals

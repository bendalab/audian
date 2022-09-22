import numpy as np
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):

    def tickStrings(self, values, scale, spacing):
        if scale > 1:
            return [f'{v*scale:.0f}' for v in values]
        vals = []
        for secs in values:
            hours = np.floor(secs/3600)
            secs -= hours*3600
            mins = np.floor(secs/60)
            secs -= mins*60
            if values[-1] > 3600:
                vals.append(f'{hours}:{mins:02.0f}:{secs:.5g}')
            elif values[-1] > 60:
                vals.append(f'{mins:02.0f}:{secs:.5g}')
            else:
                vals.append(f'{secs:.3f}')
        return vals

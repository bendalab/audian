import numpy as np
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):

    def tickStrings(self, values, scale, spacing):
        if scale > 1:
            if spacing*scale < 1:
                return [f'{v*scale:.3f}' for v in values]
            else:
                return [f'{v*scale:.0f}' for v in values]
        vals = []
        for secs in values:
            hours = np.floor(secs/3600)
            secs -= hours*3600
            mins = np.floor(secs/60)
            secs -= mins*60
            if spacing < 1:
                s = f'{secs:06.3f}'
            else:
                s = f'{secs:02.0f}'
            if np.max(values) > 3600:
                vals.append(f'{hours}:{mins:02.0f}:{s}')
            elif np.max(values) > 60:
                vals.append(f'{mins:02.0f}:{s}')
            else:
                if spacing < 1:
                    vals.append(f'{secs:.3f}')
                else:
                    vals.append(f'{secs:.0f}')
        return vals

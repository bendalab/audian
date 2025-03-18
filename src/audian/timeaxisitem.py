from math import ceil, floor, log10
import datetime as dt
import numpy as np
from PyQt5.QtGui import QFontMetrics
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    
    def __init__(self, file_times, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPen('white')
        self._file_times = file_times
        self._starttime = None
        self._starttime_mode = 0


    def setLogMode(self, *args, **kwargs):
        # no log mode!
        pass


    def set_start_time(self, time):
        """ Set time of first data element.

        Parameters
        ----------
        time: datetime or None
            A datetime object for the data and time of the first data element. 
        """
        self._starttime = time
        self.enableAutoSIPrefix(self._starttime is None or
                                self._starttime_mode == 0)


    def set_starttime_mode(self, mode):
        self._starttime_mode = mode
        self.enableAutoSIPrefix(self._starttime is None or
                                self._starttime_mode == 0)


    def tickSpacing(self, minVal, maxVal, size):
        diff = abs(maxVal - minVal)
        if diff == 0:
            return []

        if self._starttime_mode == 2:
            min_idx = np.nonzero(self._file_times <= minVal)[0][-1]
            max_idx = np.nonzero(self._file_times <= maxVal)[0][-1]
            if min_idx != max_idx:
                max_value = self._file_times[max_idx] - self._file_times[min_idx]
            else:
                max_value = maxVal - self._file_times[max_idx]
        else:
            max_value = maxVal

        # estimate width of xtick labels:
        xwidth = QFontMetrics(self.font()).averageCharWidth()
        if self._starttime and self._starttime_mode == 1:
            nx = 8
        elif max_value < 1.0:
            nx = 0
        elif max_value >= 3600:
            nx = 8
        elif max_value >= 60:
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

        if self._starttime_mode == 2:
            vals = []
            for time in values:
                toffs = self._file_times[np.nonzero(self._file_times <= time)[0][-1]]
                vals.append(time - toffs)
            values = vals
        max_value = np.max(values)

        if (self._starttime and self._starttime_mode == 1) or \
           max_value > 3600:
            self.setLabel('Time (h:m:s)', units=None)
            fs = '{hours:.0f}:{mins:02.0f}:{secs:02.0f}'
        elif max_value > 60:
            self.setLabel('Time (m:s)', units=None)
            fs = '{mins:.0f}:{secs:02.0f}'
        else:
            self.setLabel('Time', units='s')
            fs = '{secs:.0f}'
        if spacing < 1:
            fs += '.{micros}'
        
        basetime = dt.datetime(1, 1, 1, 0, 0, 0, 0)
        if self._starttime and self._starttime_mode == 1:
            basetime = self._starttime
        vals = []
        for time in values:
            t = basetime + dt.timedelta(seconds=time)
            if spacing < 0.00001:
                micros = f'{1.0*t.microsecond:06.0f}'
            elif spacing < 0.0001:
                micros = f'{0.1*t.microsecond:05.0f}'
            elif spacing < 0.001:
                micros = f'{0.01*t.microsecond:04.0f}'
            else:
                micros = f'{0.001*t.microsecond:03.0f}'
            time = dict(hours=t.hour, mins=t.minute, secs=t.second,
                        micros=micros)
            vals.append(fs.format(**time))
        return vals

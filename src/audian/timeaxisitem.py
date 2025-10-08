from math import ceil, floor, log10
import datetime as dt
import numpy as np
from PyQt5.QtCore import QPointF, Qt
from PyQt5.QtWidgets import QLabel
from PyQt5.QtGui import QFontMetrics
import pyqtgraph as pg


class TimeAxisItem(pg.AxisItem):
    
    def __init__(self, file_times, file_paths, left_margin, *args, **kwargs):
        self._left_margin = left_margin
        super().__init__(*args, **kwargs)
        self.setPen('white')
        self._file_times = file_times
        self._file_paths = file_paths
        self._starttime = None
        self._starttime_mode = 0
        # 0: tick values are recording time starting with zero
        #    at the beginning of the first file.
        # 1: tick values are absolute times of the day,
        #    i.e. the recording's start time is added.
        # 2: tick values are relative to each file's beginning.


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


    def get_file_pos(self):
        time = self.linkedView().viewRange()[0][0]
        fidx = np.nonzero(self._file_times <= time)[0][-1]
        toffs = self._file_times[fidx]
        filename = self._file_paths[fidx]
        return filename, time - toffs


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


    def makeStrings(self, values, scale, spacing, starttime_mode,
                    add_date=False):
        label = None
        units = None
        filename = self._file_paths[0] if len(self._file_paths) > 0 else None
        
        if len(values) == 0:
            return label, units, [], filename
        
        if scale > 1:
            return 'Time', 's', [f'{v*scale:.5g}' for v in values], filename

        if starttime_mode == 1 and not self._starttime:
            starttime_mode = 0
        if starttime_mode == 2 and len(self._file_times) <= 1:
            starttime_mode = 0

        if starttime_mode == 1:
            label = 'Time'
        elif starttime_mode == 2:
            label = 'File'
            fidx = np.nonzero(self._file_times <= values[0])[0][-1]
            filename = self._file_paths[fidx]
            vals = []
            for time in values:
                fidx = np.nonzero(self._file_times <= time)[0][-1]
                toffs = self._file_times[fidx]
                vals.append(time - toffs)
            values = vals
        else:
            # starttime_mode == 0
            label = 'REC'
        max_value = np.max(values)

        if starttime_mode == 1:
            if add_date:
                units = 'Y-M-D h:m:s'
                fs = '{year:04d}-{month:02d}-{day:02d} {hours:.0f}:{mins:02.0f}:{secs:02.0f}'
            else:
                units = 'h:m:s'
                fs = '{hours:.0f}:{mins:02.0f}:{secs:02.0f}'
        elif max_value > 3600:
            units = 'h:m:s'
            fs = '{hours:.0f}:{mins:02.0f}:{secs:02.0f}'
        elif max_value > 60:
            units = 'm:s'
            fs = '{mins:.0f}:{secs:02.0f}'
        else:
            units = 's'
            fs = '{secs:.0f}'
            spacing = 0.01
        if spacing < 1:
            fs += '.{micros}'
        
        basetime = dt.datetime(1, 1, 1, 0, 0, 0, 0)
        if starttime_mode == 1:
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
            time = dict(year=t.year, month=t.month, day=t.day,
                        hours=t.hour, mins=t.minute, secs=t.second,
                        micros=micros)
            vals.append(fs.format(**time))
        return label, units, vals, filename

    
    def tickStrings(self, values, scale, spacing):
        label, units, vals, _ = self.makeStrings(values, scale, spacing,
                                                 self._starttime_mode)
        if len(vals) == 0:
            return []
        if units == 's':
            self.setLabel(label, units=units)
        elif label == 'Time':
            self.setLabel(units, units=None)
        else:
            self.setLabel(f'{label} ({units})', units=None)
        return vals

    
    def resizeEvent(self, ev=None):
        # overwrite the AxisItem resizeEvent to place the label somewhere else
        # self.label is set to None on close, but resize events can still occur.
        if self.label is None:
            self.picture = None
            return

        br = self.label.boundingRect()
        p = QPointF(-self._left_margin, 0)
        if self.orientation == 'top':
            p.setY(br.height())
        self.label.setPos(p)
        self.picture = None

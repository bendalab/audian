"""PlotItem for displaying any data as a function of time.
"""

import numpy as np
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
import pyqtgraph as pg
from .rangeplot import RangePlot
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class TimePlot(RangePlot):

    def __init__(self, aspec, channel, browser, xwidth, ylabel=''):
        
        # axis:
        bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
        bottom_axis.setLabel('Time', 's', color='black')
        bottom_axis.setPen('white')
        bottom_axis.setTextPen('black')
        bottom_axis.set_start_time(browser.data.start_time)
        top_axis = TimeAxisItem(orientation='top', showValues=False)
        top_axis.set_start_time(browser.data.start_time)
        left_axis = YAxisItem(orientation='left', showValues=True)
        left_axis.setPen('white')
        left_axis.setTextPen('black')
        left_axis.setWidth(8*xwidth)
        if ylabel:
            left_axis.setLabel(ylabel, color='black')
        else:
            if browser.data.channels > 4:
                left_axis.setLabel(f'C{channel}', color='black')
            else:
                left_axis.setLabel(f'channel {channel}', color='black')
        right_axis = YAxisItem(orientation='right', showValues=False)

        # plot:
        RangePlot.__init__(self, aspec, channel, browser,
                           axisItems={'bottom': bottom_axis,
                                      'top': top_axis,
                                      'left': left_axis,
                                      'right': right_axis})

        # design:
        self.getViewBox().setBackgroundColor('black')

        # audio marker:
        self.vmarker = pg.InfiniteLine(angle=90, movable=False)
        self.vmarker.setPen(pg.mkPen('white', width=2))
        self.vmarker.setZValue(100)
        self.vmarker.setValue(-1)
        self.addItem(self.vmarker, ignoreBounds=True)


    def range(self, axspec):
        if axspec == self.x():
            if len(self.data_items) > 0:
                tmax = self.data_items[0].data.frames/self.data_items[0].data.rate
                return 0, tmax, min(10, tmax)
            else:
                return 0, None, 10
        elif axspec == self.y():
            amin = None
            amax = None
            astep = 1
            for item in self.data_items:
                a0 = item.data.ampl_min
                a1 = item.data.ampl_max
                if amin is None or a0 < amin:
                    amin = a0
                if amax is None or a1 > amax:
                    amax = a1
            if amin is None:
                amin = -1
            if amax is None:
                amax = +1
            return amin, amax, astep


    def amplitudes(self, t0, t1):
        amin = None
        amax = None
        for item in self.data_items:
            i0 = int(np.round(t0*item.rate))
            i1 = int(np.round(t1*item.rate))
            a0 = np.min(item.data[i0:i1, item.channel])
            a1 = np.max(item.data[i0:i1, item.channel])
            if amin is None or a0 < amin:
                amin = a0
            if amax is None or a1 > amax:
                amax = a1
        return amin, amax

    
    def get_marker_pos(self, x0, x1, y):
        for item in reversed(self.data_items):
            if item.isVisible():
                i0 = int(np.round(x0*item.rate))
                i1 = int(np.round(x1*item.rate))
                y0 = np.min(item.data[i0:i1, item.channel])
                y1 = np.max(item.data[i0:i1, item.channel])
                yc = (y0 + y1)/2
                if y >= yc:
                    return x0, y1, None
                else:
                    return x0, y0, None
        return x0, y, None


    def enable_starttime(self, enable):
        """ Enable addition of start time to tick labels.

        Parameters
        ----------
        enable: bool
            If True enable addition of start time to tick labels.
        """
        self.getAxis('bottom').enable_start_time(enable)
        self.getAxis('top').enable_start_time(enable)


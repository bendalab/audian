"""PlotItem for displaying any data as a function of time.
"""

import numpy as np
from pathlib import Path
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import QLabel
import pyqtgraph as pg
from .rangeplot import RangePlot
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class TimePlot(RangePlot):

    def __init__(self, aspec, channel, browser, xwidth, ylabel=''):
        left_margin = 8*xwidth
        # axis:
        bottom_axis = TimeAxisItem(browser.data.data.file_start_times(),
                                   browser.data.data.file_paths,
                                   left_margin, orientation='bottom',
                                   showValues=True)
        bottom_axis.set_start_time(browser.data.start_time)
        top_axis = TimeAxisItem(browser.data.data.file_start_times(),
                                browser.data.data.file_paths,
                                left_margin, orientation='top',
                                showValues=False)
        top_axis.set_start_time(browser.data.start_time)
        left_axis = YAxisItem(orientation='left', showValues=True)
        left_axis.setWidth(left_margin)
        if ylabel:
            left_axis.setLabel(ylabel)
        else:
            if browser.data.channels > 4:
                left_axis.setLabel(f'C{channel}')
            else:
                left_axis.setLabel(f'channel {channel}')
        right_axis = YAxisItem(orientation='right', showValues=False)

        # plot:
        RangePlot.__init__(self, aspec, channel, browser,
                           axisItems={'bottom': bottom_axis,
                                      'top': top_axis,
                                      'left': left_axis,
                                      'right': right_axis})

        # design:
        self.getViewBox().setBackgroundColor('black')

        # time info box:
        self.time_info = QLabel()
        self.time_info.setWindowFlags(self.windowFlags()
                                      | Qt.BypassWindowManagerHint
                                      | Qt.FramelessWindowHint)
        self.time_info.setVisible(False)

        # audio marker:
        self.vmarker = pg.InfiniteLine(angle=90, movable=False)
        self.vmarker.setPen(pg.mkPen('white', width=2))
        self.vmarker.setZValue(100)
        self.vmarker.setValue(-1)
        self.addItem(self.vmarker, ignoreBounds=True)


    def polish(self):
        text_color = self.palette().color(QPalette.Text)
        for axis in ['left', 'right', 'top', 'bottom']:
            self.getAxis(axis).setPen(style=Qt.NoPen)
            self.getAxis(axis).setTickPen(style=Qt.SolidLine)
            self.getAxis(axis).setTextPen(text_color)
        self.getAxis('left').setLabel(self.getAxis('left').labelText,
                                      self.getAxis('left').labelUnits,
                                      color=text_color)
        self.getAxis('bottom').setLabel(self.getAxis('bottom').labelText,
                                        self.getAxis('bottom').labelUnits,
                                        color=text_color)
        
        
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

    
    def get_marker_pos(self, x, dx, y, dy):
        for item in reversed(self.data_items):
            if item.isVisible():
                i0 = max(int(np.round(x*item.rate)), 0)
                i1 = max(int(np.round((x + dx)*item.rate)), i0 + 1)
                if i1 > len(item.data):
                    i1 = len(item.data)
                if i1 <= i0:
                    i0 = max(0, i1 - 1)
                if i0 >= i1:
                    i1 = i0 + 1
                k0 = i0 + np.argmin(item.data[i0:i1, item.channel])
                k1 = i0 + np.argmax(item.data[i0:i1, item.channel])
                y0 = item.data[k0, item.channel]
                y1 = item.data[k1, item.channel]
                yc = (y0 + y1)/2
                if y >= yc:
                    return k1/item.rate, y1, None
                else:
                    return k0/item.rate, y0, None
        return x0, y, None


    def set_starttime(self, mode):
        self.getAxis('bottom').set_starttime_mode(mode)
        self.getAxis('top').set_starttime_mode(mode)
        

    def show_times(self, screen_pos, pixel_pos):
        brect = self.boundingRect()
        brect.setBottom(brect.bottom() - 10)
        if not brect.contains(pixel_pos):
            self.time_info.setVisible(False)
            return
        pos = self.getViewBox().mapSceneToView(pixel_pos)
        [xmin, xmax], [ymin, ymax] = self.viewRange()
        if xmin <= pos.x() <= xmax and pos.y() < ymin:
            deltax = xmax - xmin
            spacing = 0.001 if deltax < 100 else 1
            ts = '<style type="text/css"> td { padding: 0 4px; } </style>'
            ts += f'<table>'
            taxis = self.getAxis('bottom')
            nm = 0
            for sm in range(3):
                label, units, vals, fname = \
                    taxis.makeStrings([pos.x()], 1, spacing, sm, True)
                if sm > 0 and label == 'REC':
                    continue
                if label == 'File':
                    fname = Path(fname).name
                else:
                    fname = ''
                ts += f'<tr><td>{label}</td><td>({units})</td><td align="right"><b>{vals[0]}</b></td><td>{fname}</td></tr>'
                nm += 1
            ts += '</table>'
            if nm <= 1:
                self.time_info.setVisible(False)
                return
            self.time_info.setText(ts)
            self.time_info.setVisible(True)
            x = screen_pos.x() + pixel_pos.x() + 1
            if x + self.time_info.width() > screen_pos.x() + self.width():
                x = screen_pos.x() + self.width() - self.time_info.width()
            y = screen_pos.y() + pixel_pos.y() + 10
            self.time_info.move(int(x), int(y))
        else:
            self.time_info.setVisible(False)


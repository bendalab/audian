"""PlotItem for displaying any data as a function of time.
"""

try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
import pyqtgraph as pg
from .selectviewbox import SelectViewBox
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class TimePlot(pg.PlotItem):

    def __init__(self, channel, xwidth, browser):

        self.channel = channel

        # view box:
        view = SelectViewBox(channel)
        
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
        if browser.data.channels > 4:
            left_axis.setLabel(f'C{channel}', color='black')
        else:
            left_axis.setLabel(f'channel {channel}', color='black')
        right_axis = YAxisItem(orientation='right', showValues=False)

        # plot:
        pg.PlotItem.__init__(self,  viewBox=view,
                             axisItems={'bottom': bottom_axis,
                                        'top': top_axis,
                                        'left': left_axis,
                                        'right': right_axis})
        self.data_items = []

        # design:
        self.getViewBox().setBackgroundColor('black')
        self.getViewBox().setDefaultPadding(padding=0)

        # functionality:
        self.hideButtons()
        self.setMenuEnabled(False)
        self.enableAutoRange(False, False)
        self.getViewBox().init_zoom_history()

        # audio marker:
        self.vmarker = pg.InfiniteLine(angle=90, movable=False)
        self.vmarker.setPen(pg.mkPen('white', width=2))
        self.vmarker.setZValue(100)
        self.vmarker.setValue(-1)
        self.addItem(self.vmarker, ignoreBounds=True)

        # cross hair:
        self.xline = pg.InfiniteLine(angle=90, movable=False)
        self.xline.setPen(pg.mkPen('white', width=1))
        self.xline.setZValue(100)
        self.xline.setValue(0)
        self.xline.setVisible(False)
        self.addItem(self.xline, ignoreBounds=True)
        
        self.yline = pg.InfiniteLine(angle=0, movable=False)
        self.yline.setPen(pg.mkPen('white', width=1))
        self.yline.setZValue(100)
        self.yline.setValue(0)
        self.yline.setVisible(False)
        self.addItem(self.yline, ignoreBounds=True)

        # previous cross hair marker:
        self.prev_marker = pg.ScatterPlotItem(
            size=14,
            pen=pg.mkPen('white'),
            brush=pg.mkBrush((255, 255, 255, 128)),
            symbol='o',
            hoverable=False
        )
        self.prev_marker.setZValue(20)
        self.addItem(self.prev_marker, ignoreBounds=True)

        # ranges:
        browser.data.set_time_limits(self)
        browser.data.set_time_range(self)

        # signals:
        self.sigXRangeChanged.connect(browser.update_times)
        view.sigSelectedRegion.connect(browser.region_menu)


    def add_item(self, item):
        self.data_items.append(item)
        self.addItem(item)


    def update_plot(self):
        for item in self.data_items:
            if item.isVisible():
                item.update_plot()


    def enable_start_time(self, enable):
        """ Enable addition of start time to tick labels.

        Parameters
        ----------
        enable: bool
            If True enable addition of start time to tick labels.
        """
        self.getAxis('bottom').enable_start_time(enable)
        self.getAxis('top').enable_start_time(enable)


"""Basic PlotItem that can be managed by PlotRange.
"""

import numpy as np
import pyqtgraph as pg
from .selectviewbox import SelectViewBox


class RangePlot(pg.PlotItem):

    def __init__(self, aspec, channel, browser, *args, **kwargs):

        self.aspec = aspec
        self.channel = channel
        self.data_items = []

        # view box:
        view = SelectViewBox(channel)

        # plot:
        pg.PlotItem.__init__(self, viewBox=view, *args, **kwargs)

        # design:
        self.getViewBox().setDefaultPadding(padding=0)

        # functionality:
        self.hideButtons()
        self.setMenuEnabled(False)
        self.enableAutoRange(False, False)
        self.getViewBox().init_zoom_history()

        # signals:
        self.sigRangeChanged.connect(browser.update_ranges)
        self.getViewBox().sigSelectedRegion.connect(browser.region_menu)

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

        # stored cross hair marker:
        self.stored_marker = pg.ScatterPlotItem(
            size=14,
            pen=pg.mkPen('white'),
            brush=pg.mkBrush((255, 255, 255, 128)),
            symbol='o',
            hoverable=False
        )
        self.stored_marker.setZValue(20)
        self.addItem(self.stored_marker, ignoreBounds=True)


    def x(self):
        return self.aspec[0]


    def y(self):
        return self.aspec[1]


    def z(self):
        return self.aspec[2] if len(self.aspec) > 2 else ''


    def add_item(self, item, is_data=False):
        if is_data:
            self.data_items.append(item)
            item.ax = self
        self.addItem(item)


    def range(self, axspec):
        return None, None, None

   
    def amplitudes(self, t0, t1):
        return None, None

    
    def get_marker_pos(self, x0, x1, y):
        return x0, y, None


    def set_stored_marker(self, x, y):
        self.stored_marker.setData((x, ), (y, ))
        self.stored_marker.setVisible(True)

        
    def update_plot(self):
        for item in self.data_items:
            if item.isVisible():
                item.update_plot()


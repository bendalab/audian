from PyQt5.QtCore import Signal
import pyqtgraph as pg
from .selectviewbox import SelectViewBox
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class SpectrumPlot(pg.PlotItem):

    
    sigSelectedRegion = Signal(object, object, object)


    def __init__(self, channel, xwidth):

        # view box:
        view = SelectViewBox(channel)
        
        # axis:
        bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
        bottom_axis.setLabel('Time', 's', color='black')
        bottom_axis.showLabel(False)
        bottom_axis.setStyle(showValues=False)
        bottom_axis.setPen('white')
        bottom_axis.setTextPen('black')
        top_axis = TimeAxisItem(orientation='top', showValues=False)
        left_axis = YAxisItem(orientation='left', showValues=True)
        left_axis.setLabel('Frequency', 'Hz', color='black')
        left_axis.setPen('white')
        left_axis.setTextPen('black')
        left_axis.setWidth(8*xwidth)
        right_axis = YAxisItem(orientation='right', showValues=False)

        # plot:
        pg.PlotItem.__init__(self,  viewBox=view,
                             axisItems={'bottom': bottom_axis,
                                        'top': top_axis,
                                        'left': left_axis,
                                        'right': right_axis})

        # design:
        self.getViewBox().setBackgroundColor('black')
        self.getViewBox().setDefaultPadding(padding=0.0)

        # ranges:
        self.setLimits(xMin=0, yMin=0.0)

        # functionality:
        self.enableAutoRange(False, False)
        self.hideButtons()
        self.setMenuEnabled(False)

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
        self.xline.setValue(-1)
        self.addItem(self.xline, ignoreBounds=True)
        
        self.yline = pg.InfiniteLine(angle=0, movable=False)
        self.yline.setPen(pg.mkPen('white', width=1))
        self.yline.setZValue(100)
        self.yline.setValue(-1)
        self.addItem(self.yline, ignoreBounds=True)

        # signals:
        view.sigSelectedRegion.connect(self.sigSelectedRegion)


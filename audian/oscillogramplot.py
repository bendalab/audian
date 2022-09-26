from PyQt5.QtCore import Signal
import pyqtgraph as pg
from .selectviewbox import SelectViewBox
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class OscillogramPlot(pg.PlotItem):

    
    sigSelectedRegion = Signal(object, object, object)

    
    def __init__(self, channel, xwidth):

        # view box:
        view = SelectViewBox(channel)
        
        # axis:
        bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
        bottom_axis.setLabel('Time', 's', color='black')
        bottom_axis.setPen('white')
        bottom_axis.setTextPen('black')
        top_axis = TimeAxisItem(orientation='top', showValues=False)
        left_axis = YAxisItem(orientation='left', showValues=True)
        left_axis.setLabel(f'channel {channel}', color='black')
        left_axis.setPen('white')
        left_axis.setTextPen('black')
        left_axis.setWidth(8*xwidth)
        right_axis = YAxisItem(orientation='right', showValues=False)

        # plot:
        pg.PlotItem.__init__(self, viewBox=view,
                             axisItems={'bottom': bottom_axis,
                                        'top': top_axis,
                                        'left': left_axis,
                                        'right': right_axis})

        # design:
        self.getViewBox().setBackgroundColor('black')
        self.getViewBox().setDefaultPadding(padding=0.0)

        # functionality:
        self.hideButtons()
        self.setMenuEnabled(False)
        self.enableAutoRange(False, False)

        # audio marker:
        self.vmarker = pg.InfiniteLine(angle=90, movable=False)
        self.vmarker.setPen(pg.mkPen('white', width=2))
        self.vmarker.setZValue(100)
        self.addItem(self.vmarker, ignoreBounds=True)

        # signals:
        view.sigSelectedRegion.connect(self.sigSelectedRegion)

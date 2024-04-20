try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
import pyqtgraph as pg
from .selectviewbox import SelectViewBox
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem


class SpectrumPlot(pg.PlotItem):

    
    sigSelectedRegion = Signal(object, object, object)
    sigUpdateFilter = Signal(object, object, object)


    def __init__(self, channel, xwidth, starttime, fmax):

        self.channel = channel

        # view box:
        view = SelectViewBox(channel)
        
        # axis:
        bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
        bottom_axis.setLabel('Time', 's', color='black')
        bottom_axis.showLabel(False)
        bottom_axis.setStyle(showValues=False)
        bottom_axis.setPen('white')
        bottom_axis.setTextPen('black')
        bottom_axis.setStartTime(starttime)
        top_axis = TimeAxisItem(orientation='top', showValues=False)
        top_axis.setStartTime(starttime)
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
        self.setLimits(xMin=0, yMin=0.0, yMax=fmax,
                       minYRange=0.1, maxYRange=fmax)

        # functionality:
        self.enableAutoRange(False, False)
        self.hideButtons()
        self.setMenuEnabled(False)

        # filter handles:
        self.highpass_cutoff = 0
        self.lowpass_cutoff = 0
        self.highpass_handle = pg.InfiniteLine(angle=0, movable=True)
        self.highpass_handle.setPen(pg.mkPen('white', width=2))
        self.highpass_handle.addMarker('o', position=0.75, size=6)
        self.highpass_handle.setZValue(100)
        self.highpass_handle.setBounds((0, fmax))
        self.highpass_handle.setValue(self.highpass_cutoff)
        self.highpass_handle.sigPositionChangeFinished.connect(self.highpass_changed)
        self.addItem(self.highpass_handle, ignoreBounds=True)
        self.lowpass_handle = pg.InfiniteLine(angle=0, movable=True)
        self.lowpass_handle.setPen(pg.mkPen('white', width=2))
        self.lowpass_handle.addMarker('o', position=0.75, size=6)
        self.lowpass_handle.setZValue(100)
        self.lowpass_handle.setBounds((0, fmax))
        self.lowpass_handle.setValue(self.lowpass_cutoff)
        self.lowpass_handle.sigPositionChangeFinished.connect(self.lowpass_changed)
        self.addItem(self.lowpass_handle, ignoreBounds=True)

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

        # signals:
        view.sigSelectedRegion.connect(self.sigSelectedRegion)


    def enableStartTime(self, enable):
        """ Enable addition of start time to tick labels.

        Parameters
        ----------
        enable: bool
            If True enable addition of start time to tick labels.
        """
        self.getAxis('bottom').enableStartTime(enable)
        self.getAxis('top').enableStartTime(enable)


    def set_filter(self, highpass_cutoff=None, lowpass_cutoff=None):
        if highpass_cutoff is not None:
            self.highpass_cutoff = highpass_cutoff
            self.highpass_handle.setValue(self.highpass_cutoff)
        if lowpass_cutoff is not None:
            self.lowpass_cutoff = lowpass_cutoff
            self.lowpass_handle.setValue(self.lowpass_cutoff)


    def highpass_changed(self):
        self.set_filter(highpass_cutoff=self.highpass_handle.value())
        self.sigUpdateFilter.emit(self.channel, self.highpass_cutoff,
                                  self.lowpass_cutoff)
        

    def lowpass_changed(self):
        self.set_filter(lowpass_cutoff=self.lowpass_handle.value())
        self.sigUpdateFilter.emit(self.channel, self.highpass_cutoff,
                                  self.lowpass_cutoff)


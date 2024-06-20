"""PlotItem for interactive display of spectrograms.
"""

import numpy as np
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
import pyqtgraph as pg
from thunderlab.powerspectrum import decibel
from .panels import Panel
from .rangeplot import RangePlot
from .timeplot import TimePlot
from .specitem import SpecItem


class PowerPlot(RangePlot):
    
    def __init__(self, aspec, channel, browser, *args, **kwargs):
        super().__init__(aspec, channel, browser, *args, **kwargs)
        self.getAxis('left').showLabel(False)
        self.getAxis('left').setStyle(showValues=False)
        self.getAxis('bottom').showLabel(False)
        self.getAxis('bottom').setStyle(showValues=False)
        for axis in ['left', 'right', 'bottom', 'top']:
            self.getAxis(axis).setVisible(False)
        #self.setLabel('bottom', 'Power (dB)')
        #self.getViewBox().setBackgroundColor('black')
        self.xline.setPen(0.7)
        self.yline.setPen(0.7)
        # data:
        self.power_item = pg.PlotCurveItem(connect='all',
                                           antialias=False,
                                           skipFiniteCheck=True)
        self.power_item.setPen(dict(color='#000099', width=2))
        self.add_item(self.power_item)
        self.zero_item = pg.PlotCurveItem(connect='all',
                                          antialias=False,
                                          skipFiniteCheck=True)
        self.zero_item.setPen(dict(color='#000099', width=2))
        self.add_item(self.zero_item)
        self.fill_item = pg.FillBetweenItem(self.zero_item,
                                            self.power_item, '#000099')
        self.add_item(self.fill_item)

        
    def range(self, axspec):
        if axspec == self.x():
            return -100, 20, 5
        elif axspec == self.y():
            return super().range(axspec)
        

    def get_marker_pos(self, x0, x1, y):
        xdata, ydata = self.power_item.getData()
        i = np.argmin(np.abs(ydata - y))
        x = xdata[i]
        return x, y, None


class SpectrogramPlot(TimePlot):

    
    sigUpdateFilter = Signal(object, object)

    def __init__(self, aspec, channel, browser, xwidth, color_map, show_cbars,
                 show_powers):
        super().__init__(aspec, channel, browser, xwidth)
        
        # axis:
        self.getAxis('bottom').showLabel(False)
        self.getAxis('bottom').setStyle(showValues=False)
        self.getAxis('left').setLabel('Frequency', 'Hz', color='black')
        
        # color bar:
        self.cbar = pg.ColorBarItem(colorMap=color_map,
                                    interactive=True,
                                    rounding=1, limits=(-200, 20))
        self.cbar.setLabel('right', 'Power (dB)')
        self.cbar.getAxis('right').setTextPen('black')
        self.cbar.getAxis('right').setWidth(6*xwidth)
        self.cbar.setVisible(show_cbars)

        # power spectrum:
        self.spec_data = None
        self.powerax = PowerPlot(self.z() + self.y(), channel, browser)
        self.powerax.setVisible(show_powers)

        # filter handles:
        self.highpass_handle = None        
        self.lowpass_handle = None        
        if 'filtered' in browser.data:
            self.highpass_cutoff = browser.data['filtered'].highpass_cutoff
            self.lowpass_cutoff = browser.data['filtered'].lowpass_cutoff
            self.highpass_handle = pg.InfiniteLine(angle=0, movable=True)
            self.highpass_handle.setPen(pg.mkPen('white', width=2))
            self.highpass_handle.addMarker('o', position=0.75, size=6)
            self.highpass_handle.setZValue(100)
            self.highpass_handle.setValue(self.highpass_cutoff)
            self.highpass_handle.sigPositionChangeFinished.connect(self.highpass_changed)
            self.addItem(self.highpass_handle, ignoreBounds=True)
            self.lowpass_handle = pg.InfiniteLine(angle=0, movable=True)
            self.lowpass_handle.setPen(pg.mkPen('white', width=2))
            self.lowpass_handle.addMarker('o', position=0.75, size=6)
            self.lowpass_handle.setZValue(100)
            self.lowpass_handle.setValue(self.lowpass_cutoff)
            self.lowpass_handle.sigPositionChangeFinished.connect(self.lowpass_changed)
            self.addItem(self.lowpass_handle, ignoreBounds=True)
            
        self.setVisible(browser.show_specs > 0)
        self.sigUpdateFilter.connect(browser.update_filter)
            

    def add_item(self, item, is_data=False):
        super().add_item(item, is_data)
        if is_data and isinstance(item, SpecItem):
            self.spec_data = item.data
            self.cbar.setImageItem(item)
            # TODO: this should go into the realm of PlotRanges:
            if self.highpass_handle is not None:
                self.highpass_handle.setBounds((item.data.ampl_min,
                                                item.data.ampl_max))
            if self.lowpass_handle is not None:
                self.lowpass_handle.setBounds((item.data.ampl_min,
                                               item.data.ampl_max))

                
    def update_plot(self):
        super().update_plot()
        if self.spec_data is None:
            return
        t0, t1 = self.getViewBox().viewRange()[0]
        i0 = int(t0*self.spec_data.rate)
        if i0 < 0:
            i0 = 0
        i1 = int(t1*self.spec_data.rate)
        if i1 > len(self.spec_data):
            i1 = len(self.spec_data)
        power = np.mean(self.spec_data[i0:i1, self.channel, :], axis=0)
        power = decibel(power)
        power[power < -200] = -200
        freqs = np.arange(len(power))*self.spec_data.fresolution
        zeros = np.zeros(len(freqs)) - 200
        self.powerax.power_item.setData(power, freqs)
        self.powerax.zero_item.setData(zeros, freqs)
        

    def range(self, axspec):
        if axspec == self.x():
            return super().range(axspec)
        elif axspec == self.y():
            return super().range(axspec)
        elif axspec == self.z():
            if self.y() == Panel.frequencies[1]:
                return -80, 0, 5
            else:
                return -200, 20, 5


    def amplitudes(self, t0, t1):
        amin, amax, astep = self.range(self.y())
        return amin, amax


    def setZRange(self, zmin, zmax):
        for item in self.data_items:
            if hasattr(item, 'setLevels'):
                item.setLevels((zmin, zmax), update=True)
        self.cbar.setLevels((zmin, zmax))


    def get_marker_pos(self, x0, x1, y):
        for item in reversed(self.data_items):
            if item.isVisible() and isinstance(item, SpecItem):
                z = item.get_power(x0, y)
                return x0, y, z
        return x0, y, None

            
    def set_filter_handles(self, highpass_cutoff=None, lowpass_cutoff=None):
        if highpass_cutoff is not None:
            self.highpass_cutoff = highpass_cutoff
            self.highpass_handle.setValue(self.highpass_cutoff)
        if lowpass_cutoff is not None:
            self.lowpass_cutoff = lowpass_cutoff
            self.lowpass_handle.setValue(self.lowpass_cutoff)


    def highpass_changed(self):
        self.highpass_cutoff = self.highpass_handle.value()
        self.sigUpdateFilter.emit(self.highpass_cutoff,
                                  self.lowpass_cutoff)
        

    def lowpass_changed(self):
        self.lowpass_cutoff = self.lowpass_handle.value()
        self.sigUpdateFilter.emit(self.highpass_cutoff,
                                  self.lowpass_cutoff)

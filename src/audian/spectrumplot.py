"""PlotItem for interactive display of spectrograms.
"""

try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
import pyqtgraph as pg
from .timeplot import TimePlot


class SpectrumPlot(TimePlot):

    
    sigUpdateFilter = Signal(object, object)


    def __init__(self, browser, channel, xwidth, cbar):
        super().__init__('f', '', channel, xwidth, browser)
        
        # axis:
        self.getAxis('bottom').showLabel(False)
        self.getAxis('bottom').setStyle(showValues=False)
        self.getAxis('left').setLabel('Frequency', 'Hz', color='black')

        # color bar:
        self.cbar = cbar

        # filter handles:
        self.highpass_handle = None        
        self.lowpass_handle = None        
        if browser.data.filtered is not None:
            self.highpass_cutoff = browser.data.filtered.highpass_cutoff
            self.lowpass_cutoff = browser.data.filtered.lowpass_cutoff
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
        self.sigYRangeChanged.connect(browser.update_frequencies)
        self.sigUpdateFilter.connect(browser.update_filter)
            

    def add_item(self, item, is_data):
        super().add_item(item, is_data)
        if is_data:
            item.set_cbar(self.cbar)
            if self.highpass_handle is not None:
                self.highpass_handle.setBounds((item.data.ampl_min,
                                                item.data.ampl_max))
            if self.lowpass_handle is not None:
                self.lowpass_handle.setBounds((item.data.ampl_min,
                                               item.data.ampl_max))

            
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

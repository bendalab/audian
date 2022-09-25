from math import ceil, floor, log
import numpy as np
from PyQt5.QtCore import Signal, QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGraphicsRectItem
import pyqtgraph as pg
from audioio import AudioLoader, available_formats, write_audio
from audioio import fade
from .version import __version__, __year__
from .timeaxisitem import TimeAxisItem
from .yaxisitem import YAxisItem
from .traceitem import TraceItem
from .specitem import SpecItem


class DataBrowser(QWidget):

    
    sigTimesChanged = Signal(object, object)
    sigAmplitudesChanged = Signal(object, object)
    sigFrequenciesChanged = Signal(object, object)
    sigResolutionChanged = Signal()
    sigPowerChanged = Signal()

    
    def __init__(self, file_path, channels, show_channels, audio,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        # data:
        self.file_path = file_path
        self.channels = channels
        self.data = None
        self.rate = None
        self.tmax = 0.0

        self.show_channels = show_channels
        self.current_channel = 0
        self.selected_channels = []

        self.trace_frac = 0.5
        
        # view:
        self.toffset = 0.0
        self.twindow = 2.0

        self.setting = False
        
        self.mouse_mode = pg.ViewBox.PanMode
        self.grids = 0
        self.show_traces = True
        self.show_specs = True
        self.show_cbars = True

        # audio:
        self.audio = audio
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.mark_audio)
        self.audio_time = 0.0
        self.audio_tmax = 0.0
        self.audio_markers = []

        # window:
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)
        self.setEnabled(False)


    def __del__(self):
        if not self.data is None:
            self.data.close()

        
    def open(self):
        if not self.data is None:
            self.data.close()
        self.data = AudioLoader(self.file_path, 60.0, 10.0)
        self.rate = self.data.samplerate

        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = np.round(2**(floor(log(self.tmax) / log(2.0)) + 1.0))

        self.nfft = 256
        self.fresolution = self.rate/self.nfft
        self.step_frac = 0.5

        if self.show_channels is None:
            if len(self.channels) == 0:
                self.show_channels = list(range(self.data.channels))
            else:
                self.show_channels = [c for c in self.channels if c < self.data.channels]
        else:
            self.show_channels = [c for c in self.show_channels if c < self.data.channels]
        if len(self.show_channels) == 0:
            self.show_channels = [0]
        
        self.current_channel = self.show_channels[0]
        self.selected_channels = list(self.show_channels)

        # load data:
        self.data[0,:]

        self.figs = []     # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        # nested lists (channel, panel):
        self.axs  = []      # all plots
        self.axts = []      # plots with time axis
        self.axys = []      # plots with amplitude axis
        self.axfxs = []     # plots with x-frequency axis
        self.axfys = []     # plots with y-frequency axis
        self.axgs = []      # plots with grids
        # lists with one plot per channel:
        self.axtraces = []  # trace plots
        self.axspacers = [] # spacer between trace and spectrogram
        self.axspecs = []   # spectrogram plots
        self.traces = []    # traces
        self.specs = []     # spectrograms
        self.cbars = []     # color bars
        self.audio_markers = [] # vertical line showing position while playing
        # font size:
        xwidth = self.fontMetrics().averageCharWidth()
        xwidth2 = xwidth/2
        for c in range(self.data.channels):
            self.axs.append([])
            self.axts.append([])
            self.axys.append([])
            self.axfxs.append([])
            self.axfys.append([])
            self.axgs.append([])
            self.audio_markers.append([])
            # one figure per channel:
            fig = pg.GraphicsLayoutWidget()
            fig.setBackground(None)
            fig.ci.layout.setContentsMargins(xwidth2, xwidth2, xwidth2, xwidth2)
            fig.ci.layout.setVerticalSpacing(0)
            fig.ci.layout.setHorizontalSpacing(xwidth)
            fig.setVisible(c in self.show_channels)
            self.vbox.addWidget(fig)
            self.figs.append(fig)
            # border:
            border = QGraphicsRectItem()
            border.setZValue(-1000)
            border.setPen(pg.mkPen('#aaaaaa', width=xwidth+1))
            fig.scene().addItem(border)
            fig.sigDeviceRangeChanged.connect(self.update_borders)
            self.borders.append(border)
            # spectrograms:
            spec = SpecItem(self.data, self.rate, c, self.nfft, self.step_frac)
            self.specs.append(spec)
            bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
            top_axis = TimeAxisItem(orientation='top', showValues=False)
            left_axis = YAxisItem(orientation='left', showValues=True)
            right_axis = YAxisItem(orientation='right', showValues=False)
            axs = fig.addPlot(row=0, col=0,
                              axisItems={'bottom': bottom_axis,
                                         'top': top_axis,
                                         'left': left_axis,
                                         'right': right_axis})
            axs.addItem(spec)
            vmarker = pg.InfiniteLine(angle=90, movable=False)
            vmarker.setPen(pg.mkPen('white', width=2))
            vmarker.setZValue(100)
            self.audio_markers[-1].append(vmarker)
            axs.addItem(vmarker, ignoreBounds=True)
            self.setup_spec_plot(axs, c)
            cbar = pg.ColorBarItem(colorMap='CET-R4', interactive=True,
                                   rounding=1, limits=(-200, 20))
            cbar.setLabel('right', 'Power (dB)')
            cbar.getAxis('right').setTextPen('black')
            cbar.getAxis('right').setWidth(6*xwidth)
            cbar.setLevels([spec.zmin, spec.zmax])
            cbar.setImageItem(spec)
            cbar.sigLevelsChanged.connect(self.update_power)
            cbar.setVisible(self.show_cbars)
            self.cbars.append(cbar)
            fig.addItem(cbar, row=0, col=1)
            spec.setCBar(cbar)
            self.axts[-1].append(axs)
            self.axfys[-1].append(axs)
            self.axgs[-1].append(axs)
            self.axs[-1].append(axs)
            self.axspecs.append(axs)
            # spacer:
            axsp = fig.addLayout(row=1, col=0)
            axsp.setContentsMargins(0, 0, 0, 0)
            self.axspacers.append(axsp)
            # trace plot:
            bottom_axis = TimeAxisItem(orientation='bottom', showValues=True)
            top_axis = TimeAxisItem(orientation='top', showValues=False)
            left_axis = YAxisItem(orientation='left', showValues=True)
            right_axis = YAxisItem(orientation='right', showValues=False)
            axt = fig.addPlot(row=2, col=0,
                              axisItems={'bottom': bottom_axis,
                                         'top': top_axis,
                                         'left': left_axis,
                                         'right': right_axis})
            trace = TraceItem(self.data, self.rate, c)
            self.traces.append(trace)
            self.setup_trace_plot(axt, c)
            axt.addItem(trace)
            vmarker = pg.InfiniteLine(angle=90, movable=False)
            vmarker.setPen(pg.mkPen('white', width=2))
            vmarker.setZValue(100)
            self.audio_markers[-1].append(vmarker)
            axt.addItem(vmarker, ignoreBounds=True)
            axt.setLabel('left', f'channel {c}', color='black')
            axt.setLabel('bottom', 'Time', 's', color='black')
            axt.getAxis('bottom').showLabel(c == self.show_channels[-1])
            axt.getAxis('bottom').setStyle(showValues=(c == self.show_channels[-1]))
            self.axts[-1].append(axt)
            self.axys[-1].append(axt)
            self.axgs[-1].append(axt)
            self.axs[-1].append(axt)
            self.axtraces.append(axt)
        self.set_times()
        self.setEnabled(True)
        self.adjust_layout(self.height())


    def update_borders(self, rect=None):
        for c in range(len(self.figs)):
            self.borders[c].setRect(0, 0, self.figs[c].size().width(),
                                    self.figs[c].size().height())
            self.borders[c].setVisible(c in self.selected_channels)


    def setup_trace_plot(self, ax, c):
        xwidth = self.fontMetrics().averageCharWidth()
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.setLimits(xMin=0, xMax=self.tmax,
                     yMin=self.traces[c].ymin, yMax=self.traces[c].ymax,
                     minXRange=10/self.rate, maxXRange=self.tmax,
                     minYRange=1/2**16,
                     maxYRange=self.traces[c].ymax - self.traces[c].ymin)
        ax.getAxis('bottom').setPen('white')
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setPen('white')
        ax.getAxis('left').setTextPen('black')
        ax.getAxis('left').setWidth(8*xwidth)
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.update_times)
        ax.setYRange(self.traces[c].ymin, self.traces[c].ymax)
        ax.sigYRangeChanged.connect(self.update_amplitudes)


    def setup_spec_plot(self, ax, c):
        xwidth = self.fontMetrics().averageCharWidth()
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.setLimits(xMin=0, xMax=self.tmax, yMin=0.0, yMax=self.specs[c].fmax,
                     minXRange=10/self.rate, maxXRange=self.tmax,
                     minYRange=0.1, maxYRange=self.specs[c].fmax)
        ax.setLabel('left', 'Frequency', 'Hz', color='black')
        ax.setLabel('bottom', 'Time', 's', color='black')
        ax.getAxis('bottom').showLabel(False)
        ax.getAxis('bottom').setStyle(showValues=False)
        ax.getAxis('left').setWidth(8*xwidth)
        ax.getAxis('bottom').setPen('white')
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setPen('white')
        ax.getAxis('left').setTextPen('black')
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.update_times)
        ax.setYRange(self.specs[c].f0, self.specs[c].f1)
        ax.sigYRangeChanged.connect(self.update_frequencies)


    def showEvent(self, event):
        if self.data is None:
            return
        self.setting = True
        for c in range(self.data.channels):
            # update time ranges:
            for ax in self.axts[c]:
                ax.setXRange(self.toffset, self.toffset + self.twindow)
            # update amplitude ranges:
            for ax in self.axys[c]:
                ax.setYRange(self.traces[c].ymin, self.traces[c].ymax)
            # update frequency ranges:
            for ax in self.axfys[c]:
                ax.setYRange(self.specs[c].f0, self.specs[c].f1)
            for ax in self.axfxs[c]:
                ax.setXRange(self.specs[c].f0, self.specs[c].f1)
            # update spectrograms:
            self.specs[c].updateSpec()
        self.setting = False

                
    def resizeEvent(self, event):
        if self.show_channels is None or len(self.show_channels) == 0:
            return
        self.adjust_layout(event.size().height())
        

    def adjust_layout(self, height):
        bottom_channel = self.show_channels[-1]
        xwidth = self.fontMetrics().averageCharWidth()
        #axis_height = None
        #if self.axtraces[bottom_channel].isVisible():
        #    axis_height = self.axtraces[bottom_channel].getAxis('bottom').height()
        #elif self.axspecs[bottom_channel].isVisible():
        #    axis_height = self.axspecs[bottom_channel].getAxis('bottom').height()
        axis_height = 5*xwidth
        ntraces = []
        nspecs = []
        for c in self.show_channels:
            nspecs.append(int(self.axspecs[c].isVisible()))
            ntraces.append(int(self.axtraces[c].isVisible()))
        spec_height = (height - axis_height)/(np.sum(nspecs) + self.trace_frac*np.sum(ntraces))
        for c, ns, nt in zip(self.show_channels, nspecs, ntraces):
            add_height = axis_height if c == bottom_channel else 0
            self.vbox.setStretch(c, int(ns*spec_height +
                                        nt*self.trace_frac*spec_height +
                                        add_height))
            t_height = max(0, int(nt*(self.trace_frac*spec_height + add_height) - xwidth))
            self.figs[c].ci.layout.setRowFixedHeight(2, t_height)
            self.figs[c].ci.layout.setRowFixedHeight(1, (nt+ns-1)*xwidth)
            s_height = max(0, int(ns*spec_height + (1-nt)*add_height - xwidth))
            self.figs[c].ci.layout.setRowFixedHeight(0, s_height)
        for c in self.show_channels:
            self.figs[c].update()
        
            
    def show_xticks(self, channel, show_ticks):
        if self.axtraces[channel].isVisible():
            self.axtraces[channel].getAxis('bottom').showLabel(show_ticks)
            self.axtraces[channel].getAxis('bottom').setStyle(showValues=show_ticks)
            self.axspecs[channel].getAxis('bottom').showLabel(False)
            self.axspecs[channel].getAxis('bottom').setStyle(showValues=False)
        elif self.axspecs[channel].isVisible():
            self.axspecs[channel].getAxis('bottom').showLabel(show_ticks)
            self.axspecs[channel].getAxis('bottom').setStyle(showValues=show_ticks)


    def set_times(self, toffset=None, twindow=None, dispatch=True):
        self.setting = True
        if not toffset is None:
            self.toffset = toffset
        if not twindow is None:
            self.twindow = twindow
        n2 = ceil(self.tmax / (0.5*self.twindow))
        ttmax = max(self.twindow, n2*0.5*self.twindow)
        for axs in self.axts:
            for ax in axs:
                ax.setLimits(xMax=ttmax, maxXRange=ttmax)
                if self.isVisible():
                    ax.setXRange(self.toffset, self.toffset + self.twindow)
        self.setting = False
        if dispatch:
            self.sigTimesChanged.emit(self.toffset, self.twindow)

            
    def update_times(self, viewbox, trange):
        if self.setting:
            return
        self.toffset = trange[0]
        self.twindow = trange[1] - trange[0]
        self.set_times()
        
        
    def zoom_time_in(self):
        if self.twindow * self.rate >= 20:
            self.twindow *= 0.5
            self.set_times()
        
        
    def zoom_time_out(self):
        if self.toffset + self.twindow < self.tmax:
            self.twindow *= 2.0
            self.set_times()

                
    def time_page_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            self.set_times()

            
    def time_page_up(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_times()

                
    def time_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            self.set_times()

                
    def time_up(self):
        if self.toffset > 0.0:
            self.toffset -= 0.05*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_times()

                
    def time_home(self):
        if self.toffset > 0.0:
            self.toffset = 0.0
            self.set_times()

                
    def time_end(self):
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            self.set_times()

                
    def snap_time(self):
        twindow = 10.0 * 2**np.round(log(self.twindow/10.0)/log(2.0))
        toffset = np.round(self.toffset / (0.5*twindow)) * (0.5*twindow)
        if twindow != self.twindow or toffset != self.toffset:
            self.set_times(toffset, twindow)


    def set_amplitudes(self, ymin=None, ymax=None):
        self.setting = True
        for c in self.selected_channels:
            if not ymin is None:
                self.traces[c].ymin = ymin
            if not ymax is None:
                self.traces[c].ymax = ymax
            if self.isVisible():
                for ax in self.axys[c]:
                    ax.setYRange(self.traces[c].ymin, self.traces[c].ymax)
        self.setting = False

            
    def update_amplitudes(self, viewbox, arange):
        if self.setting:
            return
        self.set_amplitudes(arange[0], arange[1])
        self.sigAmplitudesChanged.emit(arange[0], arange[1])
        

    def zoom_ampl_in(self):
        for c in self.selected_channels:
            self.traces[c].zoom_ampl_in()
        self.set_amplitudes()

        
    def zoom_ampl_out(self):
        for c in self.selected_channels:
            self.traces[c].zoom_ampl_out()
        self.set_amplitudes()
        
        
    def auto_ampl(self):
        for c in self.selected_channels:
            self.traces[c].auto_ampl(self.toffset, self.twindow)
        self.set_amplitudes()

        
    def reset_ampl(self):
        for c in self.selected_channels:
            self.traces[c].reset_ampl()
        self.set_amplitudes()


    def center_ampl(self):
        for c in self.selected_channels:
            self.traces[c].center_ampl()
        self.set_amplitudes()


    def set_frequencies(self, f0=None, f1=None):
        self.setting = True
        for c in self.selected_channels:
            if not f0 is None:
                self.specs[c].f0 = f0
            if not f1 is None:
                self.specs[c].f1 = f1
            if self.isVisible():
                for ax in self.axfys[c]:
                    ax.setYRange(self.specs[c].f0, self.specs[c].f1)
                for ax in self.axfxs[c]:
                    ax.setXRange(self.specs[c].f0, self.specs[c].f1)
        self.setting = False

            
    def update_frequencies(self, viewbox, frange):
        if self.setting:
            return
        self.set_frequencies(frange[0], frange[1])
        self.sigFrequenciesChanged.emit(frange[0], frange[1])
        
                
    def zoom_freq_in(self):
        for c in self.selected_channels:
            self.specs[c].zoom_freq_in()
        self.set_frequencies()
            
        
    def zoom_freq_out(self):
        for c in self.selected_channels:
            self.specs[c].zoom_freq_out()
        self.set_frequencies()
                
        
    def freq_down(self):
        for c in self.selected_channels:
            self.specs[c].freq_down()
        self.set_frequencies()

            
    def freq_up(self):
        for c in self.selected_channels:
            self.specs[c].freq_up()
        self.set_frequencies()


    def freq_home(self):
        for c in self.selected_channels:
            self.specs[c].freq_home()
        self.set_frequencies()

            
    def freq_end(self):
        for c in self.selected_channels:
            self.specs[c].freq_end()
        self.set_frequencies()


    def set_resolution(self, nfft=None, step_frac=None, dispatch=True):
        self.setting = True
        if not isinstance(nfft, list):
            nfft = [nfft] * (np.max(self.selected_channels) + 1)
        if not isinstance(step_frac, list):
            step_frac = [step_frac] * (np.max(self.selected_channels) + 1)
        for c in self.selected_channels:
            self.specs[c].set_resolution(nfft[c], step_frac[c],
                                         self.isVisible())
        self.setting = False
        if dispatch:
            self.sigResolutionChanged.emit()

        
    def freq_resolution_down(self):
        for c in self.selected_channels:
            self.specs[c].freq_resolution_down()
        self.set_resolution()

        
    def freq_resolution_up(self):
        for c in self.selected_channels:
            self.specs[c].freq_resolution_up()
        self.set_resolution()


    def step_frac_down(self):
        for c in self.selected_channels:
            self.specs[c].step_frac_down()
        self.set_resolution()


    def step_frac_up(self):
        for c in self.selected_channels:
            self.specs[c].step_frac_up()
        self.set_resolution()


    def set_power(self, zmin=None, zmax=None, dispatch=True):
        self.setting = True
        if not isinstance(zmin, list):
            zmin = [zmin] * (np.max(self.selected_channels) + 1)
        if not isinstance(zmax, list):
            zmax = [zmax] * (np.max(self.selected_channels) + 1)
        for c in self.selected_channels:
            self.specs[c].set_power(zmin[c], zmax[c])
        self.setting = False
        if dispatch:
            self.sigPowerChanged.emit()


    def update_power(self, cbar):
        if self.setting:
            return
        self.set_power(cbar.levels()[0], cbar.levels()[1])


    def power_up(self):
        for c in self.selected_channels:
            self.specs[c].zmax += 5.0
            self.specs[c].zmin += 5.0
        self.set_power()


    def power_down(self):
        for c in self.selected_channels:
            self.specs[c].zmax -= 5.0
            self.specs[c].zmin -= 5.0
        self.set_power()


    def max_power_up(self):
        for c in self.selected_channels:
            self.specs[c].zmax += 5.0
        self.set_power()


    def max_power_down(self):
        for c in self.selected_channels:
            self.specs[c].zmax -= 5.0
        self.set_power()


    def min_power_up(self):
        for c in self.selected_channels:
            self.specs[c].zmin += 5.0
        self.set_power()


    def min_power_down(self):
        for c in self.selected_channels:
            self.specs[c].zmin -= 5.0
        self.set_power()


    def all_channels(self):
        self.selected_channels = list(self.show_channels)
        self.update_borders()


    def next_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx + 1 < len(self.show_channels):
            self.current_channel = self.show_channels[idx + 1]
        self.selected_channels = [self.current_channel]
        self.update_borders()


    def previous_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx > 0:
            self.current_channel = self.show_channels[idx - 1]
        self.selected_channels = [self.current_channel]
        self.update_borders()


    def select_next_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx + 1 < len(self.show_channels):
            self.current_channel = self.show_channels[idx + 1]
        self.selected_channels.append(self.current_channel)
        self.update_borders()


    def select_previous_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx > 0:
            self.current_channel = self.show_channels[idx - 1]
        self.selected_channels.append(self.current_channel)
        self.update_borders()

            
    def select_channels(self, channels):
        self.selected_channels = [c for c in channels if c in self.show_channels]
        if not self.current_channel in self.selected_channels:
            for c in self.selected_channels:
                if c >= self.current_channel:
                    break
            self.current_channel = c
        self.update_borders()
        
            
    def set_channels(self, channels=None):
        if not channels is None:
            if self.data is None:
                self.channels = channels
                return
            self.show_channels = [c for c in channels if c < len(self.figs)]
            self.selected_channels = [c for c in self.selected_channels if c in self.show_channels]
        if not self.current_channel in self.selected_channels:
            for c in self.selected_channels:
                if c >= self.current_channel:
                    self.current_channel = c
                    break
                if not self.current_channel in self.selected_channels:
                    self.current_channel = self.selected_channels
        for c in range(len(self.figs)):
            self.figs[c].setVisible(c in self.show_channels)
            self.show_xticks(c, c == self.show_channels[-1])
        self.adjust_layout(self.height())
        self.update_borders()
            
            
    def toggle_channel(self, channel):
        if len(self.figs) > channel and \
           (len(self.show_channels) > 1 or channel != self.show_channels[0]):
            if channel in self.show_channels:
                self.show_channels.remove(channel)
                self.selected_channels.remove(channel)
            else:
                self.show_channels.append(channel)
                self.show_channels.sort()
                self.selected_channels.append(channel)
                self.selected_channels.sort()
            self.set_channels()


    def set_panels(self, traces=None, specs=None, cbars=None):
        if not traces is None:
            self.show_traces = traces
        if not specs is None:
            self.show_specs = specs
        if not cbars is None:
            self.show_cbars = cbars
        for axt, axs, cb in zip(self.axtraces, self.axspecs, self.cbars):
            axt.setVisible(self.show_traces)
            axs.setVisible(self.show_specs)
            cb.setVisible(self.show_specs and self.show_cbars)
            if axt is self.axtraces[self.show_channels[-1]]:
                axs.getAxis('bottom').showLabel(not self.show_traces)
                axs.getAxis('bottom').setStyle(showValues=not self.show_traces)
                axt.getAxis('bottom').showLabel(self.show_traces)
                axt.getAxis('bottom').setStyle(showValues=self.show_traces)
        self.adjust_layout(self.height())
            

    def toggle_traces(self):
        self.show_traces = not self.show_traces
        if not self.show_traces:
            self.show_specs = True
        self.set_panels()
            

    def toggle_spectrograms(self):
        self.show_specs = not self.show_specs
        if not self.show_specs:
            self.show_traces = True
        self.set_panels()

                
    def toggle_colorbars(self):
        self.show_cbars = not self.show_cbars
        for cb, axs in zip(self.cbars, self.axspecs):
            if axs.isVisible():
                cb.setVisible(self.show_cbars)
            

    def toggle_zoom_mode(self):
        if self.mouse_mode == pg.ViewBox.PanMode:
            self.mouse_mode = pg.ViewBox.RectMode
        else:
            self.mouse_mode = pg.ViewBox.PanMode
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().setMouseMode(self.mouse_mode)

            
    def toggle_grids(self):
        self.grids -= 1
        if self.grids < 0:
            self.grids = 3
        for c in self.selected_channels:
            for ax in self.axgs[c]:
                ax.showGrid(x=(self.grids & 1) > 0, y=(self.grids & 2) > 0,
                            alpha=0.8)
                # fix grid bug:
                ax.getAxis('bottom').setGrid(False)
                ax.getAxis('left').setGrid(False)
                for axis in ['right', 'top']:
                    ax.showAxis(axis)
                    ax.getAxis(axis).setStyle(showValues=False)


    def play_window(self):
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset + self.twindow)*self.rate))
        playdata = 1.0*self.data[t0:t1, self.selected_channels]
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        self.audio_time = self.toffset
        self.audio_tmax = self.toffset + self.twindow
        self.audio_timer.start(50)
        for c in range(self.data.channels):
            atime = self.audio_time if c in self.selected_channels else -1
            for vmarker in self.audio_markers[c]:
                vmarker.setValue(atime)

        
    def mark_audio(self):
        self.audio_time += 0.05
        for amarkers in self.audio_markers:
            for vmarker in amarkers:
                if vmarker.value() >= 0:
                    vmarker.setValue(self.audio_time)
        if self.audio_time > self.audio_tmax:
            self.audio_timer.stop()
            for amarkers in self.audio_markers:
                for vmarker in amarkers:
                    vmarker.setValue(-1)

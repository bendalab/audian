import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGraphicsRectItem
import pyqtgraph as pg
from audioio import AudioLoader, available_formats, write_audio
from audioio import fade
from .version import __version__, __year__
from .traceitem import TraceItem
from .specitem import SpecItem


class DataBrowser(QWidget):
    def __init__(self, file_path, channels, audio, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # data:
        self.file_path = file_path if file_path else None
        self.channels = channels
        self.data = None
        self.rate = None
        self.tmax = 0.0

        self.show_channels = []
        self.current_channel = 0
        self.selected_channels = []
        
        # view:
        self.toffset = 0.0
        self.twindow = 2.0

        self.f0 = 0.0
        self.f1 = 1000.0
        self.fmax = 1000.0
        self.fresolution = 500.0
        self.nfft = 256
        
        self.mouse_mode = pg.ViewBox.PanMode
        self.grids = 0
        self.show_traces = True
        self.show_specs = True
        self.show_cbars = True

        # audio:
        self.audio = audio

        # window:
        self.vbox = QVBoxLayout(self)
        self.vbox.setSpacing(0)

        self.open()


    def __del__(self):
        if not self.data is None:
            self.data.close()

        
    def open(self):
        if not self.file_path:
            return
        if not self.data is None:
            self.data.close()
        self.data = AudioLoader(self.file_path, 60.0, 10.0)
        self.rate = self.data.samplerate

        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = np.round(2**(np.floor(np.log(self.tmax) / np.log(2.0)) + 1.0))

        self.fmax = 0.5*self.rate
        self.f0 = 0.0
        self.f1 = self.fmax
        self.nfft = 256
        self.fresolution = self.rate/self.nfft
        
        if len(self.channels) == 0:
            self.show_channels = list(range(self.data.channels))
        else:
            self.show_channels = [c for c in self.channels if c < self.data.channels]
        self.current_channel = self.show_channels[0]
        self.selected_channels = [self.current_channel]

        # load data:
        self.data[0,:]

        self.figs = []     # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        self.axs  = []     # all plots
        self.axts = []     # plots with time axis
        self.axys = []     # plots with amplitude axis
        self.axfxs = []    # plots with x-frequency axis
        self.axfys = []    # plots with y-frequency axis
        self.axgs = []     # plots with grids
        self.axtraces = [] # all trace plots - one for each channel
        self.axspecs = []  # all spectrogram plots - one for each channel
        self.traces = []   # all traces - one for each channel
        self.specs = []    # all spectrograms - one for each channel
        self.cbars = []    # all color bars - one for each channel
        self.psds = []     # all power spectra - one for each channel
        for c in range(self.data.channels):
            # one figure per channel:
            fig = pg.GraphicsLayoutWidget()
            fig.setBackground(None)
            fig.setVisible(c in self.show_channels)
            self.vbox.addWidget(fig, 1)
            self.figs.append(fig)
            # border:
            border = QGraphicsRectItem()
            border.setZValue(-1000)
            border.setPen(pg.mkPen('#aaaaaa', width=10))
            fig.scene().addItem(border)
            fig.sigDeviceRangeChanged.connect(self.update_borders)
            self.borders.append(border)
            # spectrograms:
            spec = SpecItem(self.data, self.rate, c, self.nfft)
            self.fmax = spec.fmax
            self.f1 = self.fmax
            self.specs.append(spec)
            axs = fig.addPlot(row=0, col=0)
            axs.addItem(spec)
            self.setup_spec_plot(axs, c)
            cbar = pg.ColorBarItem(colorMap='CET-R4', interactive=True,
                                   rounding=1, limits=(-200, 20))
            cbar.setLabel('right', 'Power [dB]')
            cbar.getAxis('right').setTextPen('black')
            cbar.setLevels([spec.zmin, spec.zmax])
            cbar.setImageItem(spec)
            cbar.sigLevelsChanged.connect(self.set_cbar_levels)
            cbar.setVisible(self.show_cbars)
            self.cbars.append(cbar)
            fig.addItem(cbar, row=0, col=1)
            spec.setCBar(cbar)
            self.axts.append(axs)
            self.axfys.append(axs)
            self.axspecs.append(axs)
            self.axs.append(axs)
            # trace plot:
            axt = fig.addPlot(row=1, col=0)
            trace = TraceItem(self.data, self.rate, c)
            self.traces.append(trace)
            self.setup_trace_plot(axt, c)
            axt.addItem(trace)
            axt.setLabel('left', f'channel {c}', color='black')
            axt.setLabel('bottom', 'Time', 's', color='black')
            axt.getAxis('bottom').showLabel(c == self.show_channels[-1])
            axt.getAxis('bottom').setStyle(showValues=(c == self.show_channels[-1]))
            self.axts.append(axt)
            self.axys.append(axt)
            self.axgs.append(axt)
            self.axtraces.append(axt)
            self.axs.append(axt)


    def update_borders(self, rect=None):
        for c in range(len(self.figs)):
            self.borders[c].setRect(0, 0, self.figs[c].size().width(),
                                    self.figs[c].size().height())
            self.borders[c].setVisible(c in self.selected_channels)


    def setup_trace_plot(self, ax, c):
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.setLimits(xMin=0,
                     xMax=max(self.tmax, self.toffset + self.twindow),
                     yMin=self.traces[c].ymin, yMax=self.traces[c].ymax,
                     minXRange=10/self.rate, maxXRange=self.tmax,
                     minYRange=1/2**16,
                     maxYRange=self.traces[c].ymax - self.traces[c].ymin)
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setTextPen('black')
        ax.getAxis('left').setWidth(80)
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.set_xrange)
        ax.setYRange(self.traces[c].ymin, self.traces[c].ymax)


    def setup_spec_plot(self, ax, c):
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.setLimits(xMin=0, xMax=self.tmax, yMin=0.0, yMax=self.fmax)
        ax.setLabel('left', 'Frequency', 'Hz', color='black')
        ax.setLabel('bottom', 'Time', 's', color='black')
        ax.getAxis('bottom').showLabel(False)
        ax.getAxis('bottom').setStyle(showValues=False)
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setTextPen('black')
        ax.getAxis('left').setWidth(80)
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.set_xrange)
        ax.setYRange(self.f0, self.f1)
        ax.sigYRangeChanged.connect(self.set_frange)


    def show_xticks(self, channel, show_ticks):
        if self.axtraces[channel].isVisible():
            self.axtraces[channel].getAxis('bottom').showLabel(show_ticks)
            self.axtraces[channel].getAxis('bottom').setStyle(showValues=show_ticks)
            self.axspecs[channel].getAxis('bottom').showLabel(False)
            self.axspecs[channel].getAxis('bottom').setStyle(showValues=False)
        elif self.axspecs[channel].isVisible():
            self.axspecs[channel].getAxis('bottom').showLabel(show_ticks)
            self.axspecs[channel].getAxis('bottom').setStyle(showValues=show_ticks)

            
    def set_xrange(self, viewbox, xrange):
        self.toffset = xrange[0]
        self.twindow = xrange[1] - xrange[0]
        self.set_times()
        

    def set_times(self, toffset=None, twindow=None):
        if not toffset is None:
            self.toffset = toffset
        if not twindow is None:
            self.twindow = twindow
        for ax in self.axts:
            ax.getViewBox().setLimits(xMax=max(self.tmax,
                                               self.toffset + self.twindow))
            ax.setXRange(self.toffset, self.toffset + self.twindow)

        
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


    def set_amplitudes(self, ymin, ymax):
        for ax, trace in zip(self.axys, self.traces):
            trace.ymin = ymin
            trace.ymax = ymax
            ax.setYRange(trace.ymin, trace.ymax)


    def zoom_ampl_in(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.zoom_ampl_in()
            ax.setYRange(trace.ymin, trace.ymax)

        
    def zoom_ampl_out(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.zoom_ampl_out()
            ax.setYRange(trace.ymin, trace.ymax)
        
        
    def auto_ampl(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.auto_ampl(self.toffset, self.twindow)
            ax.setYRange(trace.ymin, trace.ymax)

        
    def reset_ampl(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.reset_ampl()
            ax.setYRange(trace.ymin, trace.ymax)


    def center_ampl(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.center_ampl()
            ax.setYRange(trace.ymin, trace.ymax)


    def set_frequencies(self, f0=None, f1=None):
        if not f0 is None:
            self.f0 = f0
        if not f1 is None:
            self.f1 = f1
        for ax in self.axfys:
            ax.setYRange(self.f0, self.f1)
        for ax in self.axfxs:
            ax.setXRange(self.f0, self.f1)

            
    def set_frange(self, viewbox, frange):
        self.f0 = frange[0]
        self.f1 = frange[1]
        self.set_frequencies()
        
            
    def zoom_freq_in(self):
        df = self.f1 - self.f0
        if df > 0.1:
            df *= 0.5
            self.f1 = self.f0 + df
            self.set_frequencies()
            
        
    def zoom_freq_out(self):
        if self.f1 - self.f0 < self.fmax:
            df = self.f1 - self.f0
            df *= 2.0
            if df > self.fmax:
                df = self.fmax
            self.f1 = self.f0 + df
            if self.f1 > self.fmax:
                self.f1 = self.fmax
                self.f0 = self.fmax - df
            if self.f0 < 0:
                self.f0 = 0
                self.f1 = df
            self.set_frequencies()
                
        
    def freq_down(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 -= 0.5*df
            self.f1 -= 0.5*df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df
            self.set_frequencies()

            
    def freq_up(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f0 += 0.5*df
            self.f1 += 0.5*df
            self.set_frequencies()


    def freq_home(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 = 0.0
            self.f1 = df
            self.set_frequencies()

            
    def freq_end(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f1 = np.ceil(self.fmax/(0.5*df))*(0.5*df)
            self.f0 = self.f1 - df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df
            self.set_frequencies()

        
    def freq_resolution_down(self):
        if self.fresolution < 10000.0 and self.nfft > 16:
            self.fresolution *= 2.0
            self.nfft = int(np.round(2**(np.floor(np.log(self.rate/self.fresolution) / np.log(2.0)))))
            for s in self.specs + self.psds:
                s.setNFFT(self.nfft)

        
    def freq_resolution_up(self):
        if self.nfft*2 < len(self.data):
            self.fresolution *= 0.5
            self.nfft = int(np.round(2**(np.floor(np.log(self.rate/self.fresolution) / np.log(2.0)))))
            for s in self.specs + self.psds:
                s.setNFFT(self.nfft)


    def power_up(self):
        self.specs[0].zmax += 5.0
        self.specs[0].zmin += 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def power_down(self):
        self.specs[0].zmax -= 5.0
        self.specs[0].zmin -= 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def max_power_up(self):
        self.specs[0].zmax += 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def max_power_down(self):
        self.specs[0].zmax -= 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def min_power_up(self):
        self.specs[0].zmin += 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def min_power_down(self):
        self.specs[0].zmin -= 5.0
        for s in self.specs:
            s.setCBarLevels(self.specs[0].zmin, self.specs[0].zmax)


    def set_cbar_levels(self, cbar):
        zmin = cbar.levels()[0]
        zmax = cbar.levels()[1]
        for s in self.specs:
            s.setCBarLevels(zmin, zmax)


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

            
    def set_channels(self, channels=None):
        if not channels is None:
            self.show_channels = [c for c in channels if c < len(self.figs)]
        for c in range(len(self.figs)):
            self.figs[c].setVisible(c in self.show_channels)
            self.show_xticks(c, c == self.show_channels[-1])
            
            
    def toggle_channel(self, channel):
        if len(self.figs) > channel and \
           (len(self.show_channels) > 1 or channel != self.show_channels[0]):
            if channel in self.show_channels:
                self.show_channels.remove(channel)
            else:
                self.show_channels.append(channel)
                self.show_channels.sort()
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
        for ax in self.axs:
            ax.getViewBox().setMouseMode(self.mouse_mode)

            
    def toggle_grids(self):
        self.grids -= 1
        if self.grids < 0:
            self.grids = 3
        for ax in self.axgs:
            ax.showGrid(x=(self.grids & 1) > 0, y=(self.grids & 2) > 0,
                        alpha=0.8)
            # fix grid bug:
            ax.getAxis('bottom').setGrid(False)
            ax.getAxis('left').setGrid(False)
            for axis in ['right', 'top']:
                ax.showAxis(axis)
                ax.getAxis(axis).setStyle(showValues=False)


    def play_segment(self):
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        playdata = 1.0*self.data[t0:t1,:]
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        

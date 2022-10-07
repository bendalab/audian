import os
from math import fabs, ceil, floor, log
import numpy as np
from PyQt5.QtCore import Qt, Signal, QTimer
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGraphicsRectItem
from PyQt5.QtWidgets import QMenu, QToolBar, QComboBox, QFileDialog
from PyQt5.QtWidgets import QLabel, QSizePolicy
import pyqtgraph as pg
from audioio import AudioLoader, available_formats, write_audio
from audioio import fade
from .version import __version__, __year__
from .fulltraceplot import FullTracePlot, secs_to_str
from .oscillogramplot import OscillogramPlot
from .spectrumplot import SpectrumPlot
from .traceitem import TraceItem
from .specitem import SpecItem


pg.setConfigOption('useNumba', True)


class DataBrowser(QWidget):

    zoom_region = 0
    play_region = 1
    save_region = 2
    ask_region = 3
    
    sigTimesChanged = Signal(object, object)
    sigAmplitudesChanged = Signal(object, object)
    sigFrequenciesChanged = Signal(object, object)
    sigResolutionChanged = Signal()
    sigPowerChanged = Signal()

    
    def __init__(self, file_path, channels, show_channels, audio, acts,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        # actions of main window:
        self.acts = acts

        # data:
        self.file_path = file_path
        self.channels = channels
        self.data = None
        self.rate = None
        self.tmax = 0.0

        self.show_channels = show_channels
        self.current_channel = 0
        self.selected_channels = []
        
        self.trace_fracs = {0: 1, 1: 1, 2: 0.5, 3: 0.25, 4: 0.15}

        self.region_mode = DataBrowser.ask_region
        
        # view:
        self.toffset = 0.0
        self.twindow = 2.0

        self.setting = False
        
        self.grids = 0
        self.show_traces = True
        self.show_specs = 2
        self.show_cbars = True
        self.show_fulldata = True
        
        # auto scroll:
        self.scroll_step = 0.0
        self.scroll_timer = QTimer(self)
        self.scroll_timer.timeout.connect(self.scroll_further)

        # audio:
        self.audio = audio
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.mark_audio)
        self.audio_time = 0.0
        self.audio_tmax = 0.0
        self.audio_markers = [] # vertical lines showing position while playing

        # window:
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)
        self.setEnabled(False)
        self.toolbar = None
        self.nfftw = None
        self.xpos_action = None
        self.ypos_action = None
        self.zpos_action = None
        self.prev_time = 0
        self.prev_ampl = 0
        self.prev_freq = 0
        self.prev_power = 0
        self.prev_channel = None
        
        # plots:
        self.figs = []      # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        self.sig_proxies = []
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


    def __del__(self):
        if not self.data is None:
            self.data.close()

        
    def open(self):
        if not self.data is None:
            self.data.close()
        try:
            self.data = AudioLoader(self.file_path, 60.0, 10.0)
        except IOError:
            self.data = None
            return
        self.rate = self.data.samplerate

        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = np.round(2**(floor(log(self.tmax) / log(2.0)) + 1.0))

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
        self.sig_proxies = []
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
            
            # spectrogram:
            spec = SpecItem(self.data, self.rate, c, 256, 0.5)
            self.specs.append(spec)
            axs = SpectrumPlot(c, xwidth)
            axs.addItem(spec)
            axs.setLimits(xMax=self.tmax, yMax=spec.fmax,
                         minXRange=10/self.rate, maxXRange=self.tmax,
                         minYRange=0.1, maxYRange=spec.fmax)
            axs.setXRange(self.toffset, self.toffset + self.twindow)
            axs.sigXRangeChanged.connect(self.update_times)
            axs.setYRange(self.specs[c].f0, self.specs[c].f1)
            axs.sigYRangeChanged.connect(self.update_frequencies)
            axs.sigSelectedRegion.connect(self.region_menu)
            axs.getViewBox().init_zoom_history()
            self.audio_markers[-1].append(axs.vmarker)
            fig.addItem(axs, row=0, col=0)
            
            # color bar:
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
            trace = TraceItem(self.data, self.rate, c)
            self.traces.append(trace)
            axt = OscillogramPlot(c, xwidth)
            axt.addItem(trace)
            axt.getAxis('bottom').showLabel(c == self.show_channels[-1])
            axt.getAxis('bottom').setStyle(showValues=(c == self.show_channels[-1]))
            axt.setLimits(xMin=0, xMax=self.tmax,
                          yMin=trace.ymin, yMax=trace.ymax,
                          minXRange=10/self.rate, maxXRange=self.tmax,
                          minYRange=1/2**16,
                          maxYRange=trace.ymax - trace.ymin)
        

            axt.setXRange(self.toffset, self.toffset + self.twindow)
            axt.sigXRangeChanged.connect(self.update_times)
            axt.setYRange(self.traces[c].ymin, self.traces[c].ymax)
            axt.sigYRangeChanged.connect(self.update_amplitudes)
            axt.sigSelectedRegion.connect(self.region_menu)
            axt.getViewBox().init_zoom_history()
            self.audio_markers[-1].append(axt.vmarker)
            fig.addItem(axt, row=2, col=0)
            self.axts[-1].append(axt)
            self.axys[-1].append(axt)
            self.axgs[-1].append(axt)
            self.axs[-1].append(axt)
            self.axtraces.append(axt)

            proxy = pg.SignalProxy(fig.scene().sigMouseMoved, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_moved(x, c))
            self.sig_proxies.append(proxy)
            proxy = pg.SignalProxy(fig.scene().sigMouseClicked, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_clicked(x, c))
            self.sig_proxies.append(proxy)
            
        self.set_times()
        
        # tool bar:
        self.toolbar = QToolBar()
        self.toolbar.addAction(self.acts.skip_backward)
        self.toolbar.addAction(self.acts.seek_backward)
        self.toolbar.addAction(self.acts.seek_forward)
        self.toolbar.addAction(self.acts.skip_forward)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.acts.play_window)
        self.toolbar.addSeparator()
        self.nfftw = QComboBox(self)
        self.nfftw.setToolTip('NFFT (R, Shift+R)')
        self.nfftw.addItems([f'{2**i}' for i in range(4, 16)])
        self.nfftw.setEditable(False)
        self.nfftw.setCurrentText(f'{self.specs[self.current_channel].nfft}')
        self.nfftw.currentTextChanged.connect(lambda s: self.set_resolution(nfft=int(s)))
        self.toolbar.addWidget(self.nfftw)
        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel('Channel:'))
        for act in self.acts.channels[:self.data.channels]:
            self.toolbar.addAction(act)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.xpos_action = self.toolbar.addAction('xpos')
        self.xpos_action.setVisible(False)
        self.ypos_action = self.toolbar.addAction('ypos')
        self.ypos_action.setVisible(False)
        self.zpos_action = self.toolbar.addAction('zpos')
        self.zpos_action.setVisible(False)
        self.vbox.addWidget(self.toolbar)
        self.toolbar.setVisible(self.data.channels > 1)
        
        # full data:
        self.datafig = FullTracePlot(self.data, self.rate, self.axtraces)
        self.vbox.addWidget(self.datafig)

        self.setEnabled(True)
        self.adjust_layout(self.width(), self.height())

        
    def mouse_moved(self, evt, channel, button=0, modifiers=0):
        clicked = (button & Qt.LeftButton) > 0 and modifiers == Qt.NoModifier
        store = (button & Qt.LeftButton) > 0 and (modifiers & Qt.ControlModifier) == Qt.ControlModifier
        pos = evt[0]  ## using signal proxy turns original arguments into a tuple
        time = None
        ampl = None
        freq = None
        power = None
        for ax in self.axs[channel]:
            if ax.sceneBoundingRect().contains(pos):
                if (button & Qt.RightButton) > 0:
                    ax.prev_marker.clear()
                    self.prev_channel = None
                pos = ax.getViewBox().mapSceneToView(pos)
                if hasattr(ax, 'xline'):
                    ax.xline.setPos(pos.x())
                    # is it time?
                    for axts in self.axts:
                        if ax in axts:
                            time = pos.x()
                            break
                if hasattr(ax, 'yline'):
                    ax.yline.setPos(pos.y())
                    # is it amplitude?
                    for axys in self.axys:
                        if ax in axys:
                            ampl = pos.y()
                            break
                    # is it trace amplitude?
                    if ax in self.axtraces:
                        data = self.traces[self.axtraces.index(ax)].data
                        if not time is None:
                            # TODO: do this only without downsampling!!!!
                            ampl = data[int(np.round(time*data.samplerate)), channel]
                            if clicked:
                                ax.prev_marker.setData((time,), (ampl,))
                    # is it frequency?
                    for axfys in self.axfys:
                        if ax in axfys:
                            freq = pos.y()
                            break
                    # is it spectrogram?
                    if time is not None and freq is not None and ax in self.axspecs:
                        spec = self.specs[self.axspecs.index(ax)]
                        fi = int(floor(freq/spec.fresolution))
                        ti = int(floor((time - spec.offset/spec.rate) / spec.tresolution))
                        power = spec.spectrum[fi, ti]
                break
        # set cross-hair positions:
        for axts in self.axts:
            for ax in axts:
                ax.xline.setPos(-1 if time is None else time)
        for axys in self.axys:
            for ax in axys:
                ax.yline.setPos(-1000 if ampl is None else ampl)
        for axfys in self.axfys:
            for ax in axfys:
                ax.yline.setPos(-1 if freq is None else freq)
        # remember:
        if clicked:
            self.prev_time = time
            self.prev_ampl = ampl
            self.prev_freq = freq
            self.prev_power = power
            self.prev_channel = channel
        # report positions on toolbar and store them:
        delta = self.prev_channel is not None and self.prev_channel == channel
        tds = ''
        ss = []
        if time is not None:
            if delta and self.prev_time is not None:
                time -= self.prev_time
                tds = '\u0394'
            s = f'{tds}t={secs_to_str(fabs(time))}'
            self.xpos_action.setText(s)
            ss.append(s)
        else:
            self.xpos_action.setText('')
        yds = ''
        if ampl is not None:
            if delta and self.prev_ampl is not None:
                ampl -= self.prev_ampl
                yds = '\u0394'
            s = f'{yds}y={ampl:6.3f}'
            self.ypos_action.setText(s)
            ss.append(s)
        elif freq is not None:
            if delta and self.prev_freq is not None:
                freq -= self.prev_freq
                yds = '\u0394'
            s = f'{yds}f={freq:4.0f}Hz'
            self.ypos_action.setText(s)
            ss.append(s)
        else:
            self.ypos_action.setText('')
        pds = ''
        if power is not None:
            if delta and self.prev_power is not None:
                power -= self.prev_power
                pds = '\u0394'
            s = f'{pds}p={power:6.1f}dB'
            self.zpos_action.setText(s)
            ss.append(s)
        else:
            self.zpos_action.setText('')
        self.xpos_action.setVisible(time is not None)
        self.ypos_action.setVisible(ampl is not None or freq is not None)
        self.zpos_action.setVisible(power is not None)
        if store:
            print(', '.join(ss))


    def mouse_clicked(self, evt, channel):
        self.mouse_moved((evt[0].scenePos(),), channel,
                         evt[0].button(), evt[0].modifiers())
            

    def update_borders(self, rect=None):
        for c in range(len(self.figs)):
            self.borders[c].setRect(0, 0, self.figs[c].size().width(),
                                    self.figs[c].size().height())
            self.borders[c].setVisible(c in self.selected_channels)


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
            self.specs[c].update_spectrum()
        self.setting = False

                
    def resizeEvent(self, event):
        if self.show_channels is None or len(self.show_channels) == 0:
            return
        self.adjust_layout(event.size().width(), event.size().height())
        

    def adjust_layout(self, width, height):
        xwidth = self.fontMetrics().averageCharWidth()
        xheight = self.fontMetrics().ascent()
        # subtract full data plot:
        data_height = 2.5*xheight if len(self.show_channels) <= 1 else 1.5*xheight
        if not self.show_fulldata:
            data_height = 0
        height -= len(self.show_channels)*data_height
        # subtract channel selector:
        if not self.toolbar is None and self.toolbar.isVisible():
            height -= 2*xheight
        bottom_channel = self.show_channels[-1]
        trace_frac = self.trace_fracs[self.show_specs]
        #axis_height = None
        #if self.axtraces[bottom_channel].isVisible():
        #    axis_height = self.axtraces[bottom_channel].getAxis('bottom').height()
        #elif self.axspecs[bottom_channel].isVisible():
        #    axis_height = self.axspecs[bottom_channel].getAxis('bottom').height()
        axis_height = 3.2*xheight
        ntraces = []
        nspecs = []
        nspacer = 0
        for c in self.show_channels:
            if c >= len(self.axspecs) or c >= len(self.axtraces):
                break
            nspecs.append(int(self.axspecs[c].isVisible()))
            ntraces.append(int(self.axtraces[c].isVisible()))
            if self.axspecs[c].isVisible() and self.axtraces[c].isVisible():
                nspacer += 1
        spec_height = (height - len(self.show_channels)*xwidth - nspacer*xwidth - axis_height)/(np.sum(nspecs) + trace_frac*np.sum(ntraces))
        for c, ns, nt in zip(self.show_channels, nspecs, ntraces):
            add_height = axis_height if c == bottom_channel else 0
            self.vbox.setStretch(c, int(ns*spec_height + (nt+ns)*xwidth +
                                        nt*trace_frac*spec_height + add_height))
            t_height = max(0, int(nt*(trace_frac*spec_height + add_height)))
            self.figs[c].ci.layout.setRowFixedHeight(2, t_height)
            self.figs[c].ci.layout.setRowFixedHeight(1, (nt+ns-1)*xwidth)
            s_height = max(0, int(ns*spec_height + (1-nt)*add_height))
            self.figs[c].ci.layout.setRowFixedHeight(0, s_height)
        # fix full data plot:
        self.datafig.update_layout(self.show_channels, data_height)
        self.datafig.setVisible(self.show_fulldata)
        # update:
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

                
    def time_seek_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            self.set_times()

            
    def time_seek_backward(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_times()

                
    def time_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            self.set_times()

                
    def time_backward(self):
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
        self.nfftw.setCurrentText(f'{self.specs[self.current_channel].nfft}')
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
        
            
    def set_channels(self, show_channels=None, selected_channels=None):
        if not show_channels is None:
            if self.data is None:
                self.channels = show_channels
                return
            self.show_channels = [c for c in show_channels if c < len(self.figs)]
            self.selected_channels = [c for c in selected_channels if c < len(self.figs)]
        if not self.current_channel in self.selected_channels:
            for c in self.selected_channels:
                if c >= self.current_channel:
                    self.current_channel = c
                    break
            if not self.current_channel in self.selected_channels:
                self.current_channel = self.selected_channels[-1]
        for c in range(len(self.figs)):
            self.figs[c].setVisible(c in self.show_channels)
            self.show_xticks(c, c == self.show_channels[-1])
            self.acts.channels[c].setChecked(not c in self.show_channels)
        self.adjust_layout(self.width(), self.height())
        self.update_borders()
            
        
    def toggle_channel(self, channel):
        if not self.acts.channels[channel].isChecked():
            if not channel in self.show_channels:
                if len(self.show_channels) == 1:
                    self.acts.channels[self.show_channels[0]].setCheckable(True)
                self.show_channels.append(channel)
                self.show_channels.sort()
                self.selected_channels.append(channel)
                self.selected_channels.sort()
                self.set_channels()
        else:
            if channel in self.show_channels:
                self.show_channels.remove(channel)
                if channel in self.selected_channels:
                    self.selected_channels.remove(channel)
                    if len(self.selected_channels) == 0:
                        for c in self.show_channels:
                            if c < channel:
                                self.current_channel = c
                            else:
                                break
                        self.selected_channels = [self.current_channel]
                if len(self.show_channels) == 1:
                    self.acts.channels[self.show_channels[0]].setCheckable(False)
                self.set_channels()
        self.setFocus()

        
    def set_panels(self, traces=None, specs=None, cbars=None):
        if not traces is None:
            self.show_traces = traces
        if not specs is None:
            self.show_specs = specs
        if not cbars is None:
            self.show_cbars = cbars
        for axt, axs, cb in zip(self.axtraces, self.axspecs, self.cbars):
            axt.setVisible(self.show_traces)
            axs.setVisible(self.show_specs > 0)
            cb.setVisible(self.show_specs > 0 and self.show_cbars)
            if axt is self.axtraces[self.show_channels[-1]]:
                axs.getAxis('bottom').showLabel(not self.show_traces)
                axs.getAxis('bottom').setStyle(showValues=not self.show_traces)
                axt.getAxis('bottom').showLabel(self.show_traces)
                axt.getAxis('bottom').setStyle(showValues=self.show_traces)
        self.adjust_layout(self.width(), self.height())
            

    def toggle_traces(self):
        self.show_traces = not self.show_traces
        if not self.show_traces:
            self.show_specs = 1
        self.set_panels()
            

    def toggle_spectrograms(self):
        self.show_specs += 1
        if self.show_specs > 4:
            self.show_specs = 0
        if self.show_specs == 0:
            self.show_traces = True
        self.set_panels()

                
    def toggle_colorbars(self):
        self.show_cbars = not self.show_cbars
        for cb, axs in zip(self.cbars, self.axspecs):
            if axs.isVisible():
                cb.setVisible(self.show_cbars)
            
                
    def set_fulldata(self, show):
        self.show_fulldata = show
        self.datafig.setVisible(self.show_fulldata)
        self.adjust_layout(self.width(), self.height())
            
                
    def toggle_fulldata(self):
        self.show_fulldata = not self.show_fulldata
        self.set_fulldata(self.show_fulldata)
            
            
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


    def set_zoom_mode(self, mode):
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().setMouseMode(mode)


    def zoom_back(self):
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().zoom_back()


    def zoom_forward(self):
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().zoom_forward()


    def zoom_reset(self):
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().zoom_reset()


    def set_region_mode(self, mode):
        self.region_mode = mode


    def region_menu(self, channel, vbox, rect):
        if self.region_mode == DataBrowser.zoom_region:
            vbox.zoom_region(rect)
        elif self.region_mode == DataBrowser.play_region:
            self.play_region(rect.left(), rect.right())
        elif self.region_mode == DataBrowser.save_region:
            self.save_region(rect.left(), rect.right())
        elif self.region_mode == DataBrowser.ask_region:
            menu = QMenu(self)
            zoom_act = menu.addAction('&Zoom')
            #analyze_act = menu.addAction('&Analyze')
            play_act = menu.addAction('&Play')
            save_act = menu.addAction('&Save as')
            #crop_act = menu.addAction('&Crop')
            act = menu.exec(QCursor.pos())
            if act is zoom_act:
                vbox.zoom_region(rect)
            elif act is play_act:
                self.play_region(rect.left(), rect.right())
            elif act is save_act:
                self.save_region(rect.left(), rect.right())
        vbox.hide_region()


    def play_scroll(self):
        if self.scroll_timer.isActive():
            self.scroll_timer.stop()
            self.scroll_step /= 2
        elif self.audio_timer.isActive():
            self.audio.stop()
            self.audio_timer.stop()
            for amarkers in self.audio_markers:
                for vmarker in amarkers:
                    vmarker.setValue(-1)
        else:
            self.play_window()
        

    def auto_scroll(self):
        if self.scroll_step == 0:
            self.scroll_step = 0.05
        elif self.scroll_step > 1.0:
            if self.scroll_timer.isActive():
                self.scroll_timer.stop()
            self.scroll_step = 0
            return
        else:
            self.scroll_step *= 2
        if not self.scroll_timer.isActive():
            self.scroll_timer.start(20)

        
    def scroll_further(self):
        if self.toffset + self.twindow > self.tmax:
            self.scroll_timer.stop()
            self.scroll_step /= 2
        else:
            self.set_times(self.toffset + self.scroll_step)


    def play_region(self, t0, t1):
        i0 = int(np.round(t0*self.rate))
        i1 = int(np.round(t1*self.rate))
        playdata = 1.0*self.data[i0:i1, self.selected_channels]
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        self.audio_time = t0
        self.audio_tmax = t1
        self.audio_timer.start(50)
        for c in range(self.data.channels):
            atime = self.audio_time if c in self.selected_channels else -1
            for vmarker in self.audio_markers[c]:
                vmarker.setValue(atime)


    def play_window(self):
        self.play_region(self.toffset, self.toffset + self.twindow)

        
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

                    
    def save_region(self, t0, t1):

        def secs_to_str(time):
            hours = time//3600
            time -= 3600*hours
            mins = time//60
            time -= 60*mins
            secs = int(np.floor(time))
            time -= secs
            msecs = f'{1000*time:03.0f}ms'
            if hours > 0:
                return f'{hours}h{mins}m{secs}s{msecs}'
            elif mins > 0:
                return f'{mins}m{secs}s{msecs}'
            elif secs > 0:
                return f'{secs}s{msecs}'
            else:
                return msecs

        i0 = int(np.round(t0*self.rate))
        i1 = int(np.round(t1*self.rate))
        name = os.path.splitext(os.path.basename(self.file_path))[0]
        #if self.channel > 0:
        #    filename = f'{name}-{channel:d}-{t0:.4g}s-{t1s:.4g}s.wav'
        t0s = secs_to_str(t0)
        t1s = secs_to_str(t1)
        filename = f'{name}-{t0s}-{t1s}.wav'
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if 'WAV' in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        file_path = os.path.join(os.path.dirname(self.file_path), filename)
        print(file_path)
        file_path = QFileDialog.getSaveFileName(self, 'Save region as',
                                                file_path,
                                                ';;'.join(filters))[0]
        if file_path:
            write_audio(file_path, self.data[i0:i1,:], self.rate)
            print('saved region to: ' , file_path)

        
    def save_window(self):
        self.save_region(self.toffset, self.toffset + self.twindow)

import os
from copy import deepcopy
from math import fabs, floor
import datetime as dt
import numpy as np
from scipy.signal import butter, sosfiltfilt
try:
    from PyQt5.QtCore import Signal
except ImportError:
    from PyQt5.QtCore import pyqtSignal as Signal
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QCursor, QKeySequence
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QScrollArea
from PyQt5.QtWidgets import QAction, QMenu, QToolBar, QComboBox, QCheckBox
from PyQt5.QtWidgets import QLabel, QSizePolicy, QTableView
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QFileDialog
from PyQt5.QtWidgets import QAbstractItemView, QGraphicsRectItem
import pyqtgraph as pg
from audioio import fade
from audioio import get_datetime, update_starttime
from audioio import bext_history_str, add_history
from thunderlab.datawriter import available_formats, write_data
from .version import __version__, __year__
from .data import Data
from .panel import Panel
from .plotrange import PlotRange
from .fulltraceplot import FullTracePlot, secs_to_str
from .timeplot import TimePlot
from .spectrumplot import SpectrumPlot
from .markerdata import colors, MarkerLabel, MarkerLabelsModel
from .markerdata import MarkerData, MarkerDataModel
from .analyzer import PlainAnalyzer
from .statisticsanalyzer import StatisticsAnalyzer


pg.setConfigOption('useNumba', True)


def marker_tip(x, y, data):
    s = ''
    if data:
        s += data + '\n'
    s += 'time=' + secs_to_str(x)
    return s


class DataBrowser(QWidget):

    color_maps = [
                  'CET-R4',   # jet
                  'CET-L8',   # blue-pink-yellow
                  'CET-L16',  # black-blue-green-white
                  'CET-CBL2', # black-blue-yellow-white
                  'CET-L1',   # black-white
                  #pg.colormap.get('CET-L1').reverse(),   # white-black
                  'CET-L3',   # inferno
                  ]
    # see https://colorcet.holoviz.org/
    # and pyqtgraph.colormap module for useful functions.

    zoom_region = 0
    play_region = 1
    analyze_region = 2
    save_region = 3
    ask_region = 4
    
    sigTimesChanged = Signal(object, object, object)
    sigAmplitudesChanged = Signal(object, object)
    sigFrequenciesChanged = Signal(object, object)
    sigResolutionChanged = Signal()
    sigColorMapChanged = Signal()
    sigFilterChanged = Signal()
    sigEnvelopeChanged = Signal()
    sigPowerChanged = Signal()
    sigAudioChanged = Signal(object, object, object)

    
    def __init__(self, file_path, load_kwargs, plugins, channels,
                 audio, acts, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # actions of main window:
        self.acts = acts

        # data:
        self.schannels = channels
        self.data = Data(file_path, **load_kwargs)
        self.plot_ranges = {}
        
        # panels:
        self.panels = {}
        self.add_panel('trace', 'xt', 0)
        self.add_panel('spectrogram', 'ft', 1)

        # plugins:
        self.plugins = plugins
        self.analysis_table = None
        self.analyzers = []
        self.plugins.setup_traces(self)
        self.data.setup_traces()

        # channel selection:
        self.show_channels = None
        self.current_channel = 0
        self.selected_channels = []
        
        # view:
        self.setting = False
        
        self.trace_fracs = {0: 1, 1: 1, 2: 0.5, 3: 0.25, 4: 0.15}

        self.region_mode = DataBrowser.ask_region
        
        self.grids = 0
        self.show_traces = True
        self.show_specs = 0
        self.show_cbars = False
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
        self.audio_use_heterodyne = False
        self.audio_heterodyne_freq = 40000.0
        self.audio_rate_fac = 1.0
        self.audio_tmax = 0.0
        self.audio_markers = [] # vertical lines showing position while playing

        # window:
        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(0, 0, 0, 0)
        self.vbox.setSpacing(0)
        self.setEnabled(False)
        self.toolbar = None
        self.audiofacw = None
        self.nfftw = None

        # cross hair:
        self.xpos_action = None
        self.ypos_action = None
        self.zpos_action = None
        self.cross_hair = False
        self.marker_ax = None
        self.marker_time = 0
        self.marker_ampl = 0
        self.marker_freq = 0
        self.marker_power = 0
        self.marker_channel = None
        self.prev_time = 0
        self.prev_ampl = 0
        self.prev_freq = 0
        self.prev_power = 0
        self.prev_channel = None
        self.delta_time = None
        self.delta_ampl = None
        self.delta_freq = None
        self.delta_power = None
        self.marker_data = MarkerData()
        self.marker_model = MarkerDataModel(self.marker_data)
        self.marker_labels = []
        self.marker_labels.append(MarkerLabel('start', 's', 'yellow'))
        self.marker_labels.append(MarkerLabel('end', 'e', 'blue'))
        self.marker_labels_model = MarkerLabelsModel(self.marker_labels,
                                                     self.acts)
        self.marker_orig_acts = []
        
        # plots:
        self.color_map = 0  # index into color_maps
        self.figs = []      # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        self.sig_proxies = []
        # nested lists (channel, panel):
        self.axs  = []      # all plots
        self.axts = []      # plots with time axis
        self.axgs = []      # plots with grids
        # lists with one plot item per channel:
        self.traces = []    # traces
        self.envelopes = [] # envelopes
        self.specs = []     # spectrograms
        self.cbars = []     # color bars
        # lists with marker labels and regions:
        self.trace_labels = [] # labels on traces
        self.trace_region_labels = [] # regions with labels on traces
        self.spec_labels = []  # labels on spectrograms
        self.spec_region_labels = [] # regions with labels on spectrograms
        # full traces:
        self.datafig = None

        # actions:
        if self.data.filtered is None:
            self.acts.link_filter.setEnabled(False)
            self.acts.highpass_up.setEnabled(False)
            self.acts.highpass_down.setEnabled(False)
            self.acts.lowpass_up.setEnabled(False)
            self.acts.lowpass_down.setEnabled(False)
        if self.data.envelope is None:
            self.acts.link_envelope.setEnabled(False)
            self.acts.show_envelope.setEnabled(False)
            self.acts.envelope_up.setEnabled(False)
            self.acts.envelope_down.setEnabled(False)


    def add_panel(self, name, axes, row=None):
        if row is None:
            row = len(self.panels)
        for panel in self.panels.values():
            if panel.row >= row:
                panel.row += 1
        self.panels[name] = Panel(name, axes, row)
        if len(self.panels) > 1:
            names = np.array(list(self.panels.keys()))
            rows = [self.panels[name].row for name in names]
            inx = np.argsort(rows)
            self.panels = {name: self.panels[name] for name in names[inx]}


    def remove_panel(self, name):
        del self.panels[name]


    def clear_panels(self):
        self.panels = {}


    def get_trace(self, name):
        return self.data[name]


    def add_trace(self, trace):
        self.data.add_trace(trace)


    def remove_trace(self, name):
        self.data.remove_trace(name)


    def clear_traces(self):
        self.data.clear_traces()


    def get_analyzer(self, name):
        for a in self.analyzers:
            if name.lower() == a.name.lower():
                return a
        return None


    def add_analyzer(self, analyzer):
        self.analyzers.append(analyzer)


    def remove_analyzer(self, name):
        for k, a in enumerate(self.analyzers):
            if name.lower() == a.name.lower():
                del self.analyzers[k]


    def clear_analyzer(self):
        self.analyzers = []


    def add_to_panel(self, trace_name, channel, plot_item):
        panel_name = self.data[trace_name].panel
        self.panels[panel_name].add_item(channel, plot_item, False)

        
    def open(self, gui, unwrap, unwrap_clip, highpass_cutoff, lowpass_cutoff):
        # load data:
        self.data.open(unwrap, unwrap_clip)
        if self.data.data is None:
            return
        self.marker_data.file_path = self.data.file_path

        # amplitude ranges:
        self.plot_ranges = {s: PlotRange(s, self.data.channels) for s in 'xyuf'}
        
        # requested filtering:
        filter_changed = False
        if self.data.filtered is not None and highpass_cutoff is not None:
            self.data.filtered.highpass_cutoff = highpass_cutoff
            filter_changed = True
        if self.data.filtered is not None and lowpass_cutoff is not None:
            self.data.filtered.lowpass_cutoff = lowpass_cutoff
            filter_changed = True
        if filter_changed:
            self.data.filtered.update()
                
        # setup channel selection:
        if self.show_channels is None:
            if len(self.schannels) == 0:
                self.show_channels = list(range(self.data.channels))
            else:
                self.show_channels = [c for c in self.schannels if c < self.data.channels]
        else:
            self.show_channels = [c for c in self.show_channels if c < self.data.channels]
        if len(self.show_channels) == 0:
            self.show_channels = [0]
        
        self.current_channel = self.show_channels[0]
        self.selected_channels = list(range(self.data.channels))

        # load marker data:
        locs, labels = self.data.data.markers()
        self.marker_data.set_markers(locs, labels, self.data.rate)
        if len(labels) > 0:
            lbls = np.unique(labels[:,0])
            for i, l in enumerate(lbls):
                self.marker_labels.append(MarkerLabel(l, l[0].lower(),
                                list(colors.keys())[i % len(colors.keys())]))

        # insert spacers:
        panels = {}
        row = 0
        spacer = 0
        for name in self.panels:
            if row > 0:
                panels[f'spacer{spacer}'] = Panel(f'spacer{spacer}',
                                                  'spacer', 0)
                spacer += 1
            panels[name] = self.panels[name]
            row += 1
        self.panels = panels
            
        # setup plots:
        self.figs = []     # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        self.sig_proxies = []
        # nested lists (channel, panel):
        self.axs  = []      # all plots
        self.axts = []      # plots with time axis
        self.axgs = []      # plots with grids
        # lists with one plot item per channel:
        self.traces = []    # traces
        self.envelopes = [] # envelopes
        self.specs = []     # spectrograms
        self.cbars = []     # color bars
        # lists with marker labels and regions:
        self.trace_labels = [] # labels on traces
        self.trace_region_labels = [] # regions with labels on traces
        self.spec_labels = []  # labels on spectrograms
        self.spec_region_labels = [] # regions with labels on spectrograms
        self.audio_markers = [] # vertical line showing position while playing
        # font size:
        xwidth = self.fontMetrics().averageCharWidth()
        xwidth2 = xwidth/2
        for c in range(self.data.channels):
            self.axs.append([])
            self.axts.append([])
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
                
            # setup plot panels:
            row = 0
            for name in reversed(self.panels):
                panel = self.panels[name]
                # spacer:
                if panel == 'spacer':
                    axsp = fig.addLayout(row=row, col=0)
                    axsp.setContentsMargins(0, 0, 0, 0)
                    panel.add_ax(axsp)
                    panel.row = row
                # trace plot:
                elif panel.ax_spec in ['xt', 'yt', 'ut']:
                    aspec = panel.ax_spec[0]
                    ylabel = panel.name if panel.name != 'trace' else ''
                    axt = TimePlot(aspec, ylabel, c, xwidth, self)
                    self.audio_markers[-1].append(axt.vmarker)
                    fig.addItem(axt, row=row, col=0)
                    self.axts[-1].append(axt)
                    self.axgs[-1].append(axt)
                    self.axs[-1].append(axt)
                    panel.add_ax(axt)
                    panel.row = row
                    panel.add_traces(c, self.data)
                    self.plot_ranges[aspec].add_yaxis(axt, c, True)
                    axt.sigYRangeChanged.connect(self.update_amplitudes)
                    # add marker labels:
                    labels = []
                    for l in self.marker_labels:
                        label = pg.ScatterPlotItem(size=10, hoverSize=20,
                                                   hoverable=True,
                                                   pen=pg.mkPen(None),
                                                   brush=pg.mkBrush(l.color))
                        axt.addItem(label)
                        labels.append(label)
                    self.trace_labels.append(labels)
                    self.trace_region_labels.append([])
                # spectrogram:
                elif panel == 'ft':
                    # color bar:
                    cbar = pg.ColorBarItem(colorMap=self.color_maps[self.color_map],
                                           interactive=True,
                                           rounding=1, limits=(-200, 20))
                    cbar.setLabel('right', 'Power (dB)')
                    cbar.getAxis('right').setTextPen('black')
                    cbar.getAxis('right').setWidth(6*xwidth)
                    cbar.sigLevelsChanged.connect(self.update_power)
                    cbar.setVisible(self.show_cbars)
                    self.cbars.append(cbar)
                    fig.addItem(cbar, row=row, col=1)

                    # spectrum:
                    axs = SpectrumPlot(self, c, xwidth, cbar)
                    self.audio_markers[-1].append(axs.vmarker)
                    fig.addItem(axs, row=row, col=0)
                    self.axts[-1].append(axs)
                    self.axgs[-1].append(axs)
                    self.axs[-1].append(axs)
                    panel.add_ax(axs)
                    panel.row = row
                    panel.add_traces(c, self.data)
                    self.plot_ranges['f'].add_yaxis(axs, c, True)
                    # add marker labels:
                    labels = []
                    for l in self.marker_labels:
                        label = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None),
                                                   brush=pg.mkBrush(l.color))
                        axs.addItem(label)
                        labels.append(label)
                    self.spec_labels.append(labels)
                    self.spec_region_labels.append([])

                row += 1
                
            # special trace items (TODO: eliminate those as soon as possible):
            for trace in self.data.traces:
                if trace.name == 'data': # or trace.name == 'filtered':
                    self.traces.append(trace.plot_item)
                elif trace.name == 'envelope':
                    self.envelopes.append(trace.plot_item)
                elif trace.name == 'spectrogram':
                    self.specs.append(trace.plot_item)

            proxy = pg.SignalProxy(fig.scene().sigMouseMoved, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_moved(x, c))
            self.sig_proxies.append(proxy)
            proxy = pg.SignalProxy(fig.scene().sigMouseClicked, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_clicked(x, c))
            self.sig_proxies.append(proxy)
            
        self.setting = True
        for r in self.plot_ranges.values():
            r.set_limits()
            r.set_ranges()
        if not self.plot_ranges['x'].is_used():
            self.acts.zoom_xamplitude_in.setEnabled(False)
            self.acts.zoom_xamplitude_out.setEnabled(False)
            self.acts.zoom_xamplitude_in.setVisible(False)
            self.acts.zoom_xamplitude_out.setVisible(False)
        if not self.plot_ranges['y'].is_used():
            self.acts.zoom_yamplitude_in.setEnabled(False)
            self.acts.zoom_yamplitude_out.setEnabled(False)
            self.acts.zoom_yamplitude_in.setVisible(False)
            self.acts.zoom_yamplitude_out.setVisible(False)
        if not self.plot_ranges['u'].is_used():
            self.acts.zoom_uamplitude_in.setEnabled(False)
            self.acts.zoom_uamplitude_out.setEnabled(False)
            self.acts.zoom_uamplitude_in.setVisible(False)
            self.acts.zoom_uamplitude_out.setVisible(False)
        self.setting = False
        self.data.set_need_update()
        self.set_times()
        
        # tool bar:
        self.toolbar = QToolBar()
        self.toolbar.addAction(self.acts.skip_backward)
        self.toolbar.addAction(self.acts.seek_backward)
        self.toolbar.addAction(self.acts.seek_forward)
        self.toolbar.addAction(self.acts.skip_forward)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.acts.play_window)
        self.audiofacw = QComboBox(self)
        self.audiofacw.setToolTip('Audio time expansion factor')
        self.audiofacw.addItems(['0.1', '0.2', '0.5', '1', '2', '5', '10', '20', '50', '100'])
        self.audiofacw.setEditable(False)
        self.audiofacw.setCurrentText(f'{self.audio_rate_fac:g}')
        self.audiofacw.currentTextChanged.connect(lambda s: self.set_audio(rate_fac=float(s)))
        self.toolbar.addWidget(self.audiofacw)
        self.audiohetfw = pg.SpinBox(self, self.audio_heterodyne_freq,
                                     bounds=(10000, 100000),
                                     suffix='Hz', siPrefix=True,
                                     step=0.1, dec=True, decimals=3,
                                     minStep=5000)
        self.audiohetfw.setToolTip('Audio heterodyne frequency')
        self.audiohetfw.sigValueChanged.connect(lambda s: self.set_audio(heterodyne_freq=s.value()))
        if self.data.rate > 50000:
            self.toolbar.addWidget(self.audiohetfw)
            self.toolbar.addAction(self.acts.use_heterodyne)
        else:
            self.audiohetfw.setVisible(False)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.acts.zoom_home)
        self.toolbar.addAction(self.acts.zoom_back)
        self.toolbar.addAction(self.acts.zoom_forward)
        self.toolbar.addSeparator()

        if self.data.spectrum is not None:
            self.toolbar.addWidget(QLabel('N:'))
            self.nfftw = QComboBox(self)
            self.nfftw.tooltip = 'NFFT (R, Shift+R)'
            self.nfftw.setToolTip(self.nfftw.tooltip)
            self.nfftw.addItems([f'{2**i}' for i in range(3, 20)])
            self.nfftw.setEditable(False)
            self.nfftw.setCurrentText(f'{self.data.spectrum.nfft}')
            self.nfftw.currentTextChanged.connect(lambda s: self.set_resolution(nfft=int(s)))
            self.toolbar.addWidget(self.nfftw)

            self.toolbar.addWidget(QLabel('O:'))
            self.ofracw = pg.SpinBox(self, 100*(1 - self.data.spectrum.hop_frac),
                                     bounds=(0, 99.8),
                                     suffix='%', siPrefix=False,
                                     step=0.5, dec=True, decimals=3,
                                     minStep=0.01)
            self.ofracw.setToolTip('Overlap of Fourier segments (O, Shift+O)')
            self.ofracw.valueChanged.connect(lambda v: self.set_resolution(hop_frac=1-0.01*v))
            self.toolbar.addWidget(self.ofracw)
            self.toolbar.addSeparator()

        if self.data.filtered is not None:
            self.toolbar.addWidget(QLabel('H:'))
            self.hpfw = pg.SpinBox(self, self.data.filtered.highpass_cutoff,
                                   bounds=(0, self.data.rate/2),
                                   suffix='Hz', siPrefix=True,
                                   step=0.5, dec=True, decimals=3,
                                   minStep=10**np.floor(np.log10(0.01*self.data.rate/2)))
            self.hpfw.setToolTip('High-pass filter cutoff frequency (H, Shift+H)')
            self.hpfw.sigValueChanged.connect(lambda s: self.update_filter(highpass_cutoff=s.value()))
            self.toolbar.addWidget(self.hpfw)        

            self.toolbar.addWidget(QLabel(' L:'))
            self.lpfw = pg.SpinBox(self, self.data.filtered.lowpass_cutoff,
                                   bounds=(0.01*self.data.rate/2, self.data.rate/2),
                                   suffix='Hz', siPrefix=True,
                                   step=0.5, dec=True, decimals=3,
                                   minStep=10**np.floor(np.log10(0.01*self.data.rate/2)))
            self.lpfw.setToolTip('Low-pass filter cutoff frequency (L, Shift+L)')
            self.lpfw.sigValueChanged.connect(lambda s: self.update_filter(lowpass_cutoff=s.value()))
            self.toolbar.addWidget(self.lpfw)        
        
        if self.data.envelope is not None:
            self.toolbar.addWidget(QLabel(' E:'))
            self.envfw = pg.SpinBox(self, self.data.envelope.envelope_cutoff,
                                    bounds=(0, 0.5*self.data.rate/2),
                                    suffix='Hz', siPrefix=True,
                                    step=0.5, dec=True, decimals=3,
                                    minStep=10**np.floor(np.log10(0.00001*self.data.rate/2)))
            self.envfw.setToolTip('Envelope low-pass filter cutoff frequency (E, Shift+E)')
            self.envfw.sigValueChanged.connect(lambda s: self.update_envelope(envelope_cutoff=s.value()))
            self.toolbar.addWidget(self.envfw)

        self.toolbar.addSeparator()
        self.toolbar.addWidget(QLabel('Channel:'))
        for c in range(max(self.data.channels, len(self.acts.channels))):
            gui.set_channel_action(c, self.data.channels,
                                   c in self.show_channels,
                                   gui.browser() is self)
            if c < self.data.channels:
                self.toolbar.addAction(self.acts.channels[c])
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.toolbar.addWidget(spacer)
        self.xpos_action = self.toolbar.addAction('xpos')
        self.xpos_action.setVisible(False)
        self.toolbar.widgetForAction(self.xpos_action).setFixedWidth(20*xwidth)
        self.ypos_action = self.toolbar.addAction('ypos')
        self.ypos_action.setVisible(False)
        self.toolbar.widgetForAction(self.ypos_action).setFixedWidth(10*xwidth)
        self.zpos_action = self.toolbar.addAction('zpos')
        self.zpos_action.setVisible(False)
        self.toolbar.widgetForAction(self.zpos_action).setFixedWidth(10*xwidth)
        self.vbox.addWidget(self.toolbar)
        
        # full data:
        self.datafig = FullTracePlot(self.data.data, self.panels['trace'].axs)
        self.vbox.addWidget(self.datafig)

        self.setEnabled(True)
        self.adjust_layout(self.width(), self.height())

        # setup analyzers:
        PlainAnalyzer(self)
        StatisticsAnalyzer(self)
        self.plugins.setup_analyzer(self)
        if len(self.analyzers) == 0:
            self.acts.analyze_region.setEnabled(False)            
            self.acts.analyze_region.setVisible(False)            

        # add marker data to plot:
        labels = [l.label for l in self.marker_labels]
        for t1, ddt, ls, ts in zip(self.marker_data.times,
                                  self.marker_data.delta_times,
                                  self.marker_data.labels,
                                  self.marker_data.texts):
            lidx = labels.index(ls)
            for c, tl in enumerate(self.trace_labels):
                ds = ts if ts else ls
                t0 = t1 - ddt
                idx0 = int(t0*self.data.rate)
                idx1 = int(t1*self.data.rate)
                if ddt > 0:
                    region = pg.LinearRegionItem((t0, t1),
                                                 orientation='vertical',
                                                 pen=pg.mkPen(self.marker_labels[lidx].color),
                                                 brush=pg.mkBrush(self.marker_labels[lidx].color),
                                                 movable=False,
                                                 span=(0.02, 0.05))
                    region.setZValue(-10)
                    self.panels['trace'].add_item(c, region, False)
                    #text = pg.TextItem(ds, color='green', anchor=(0, 0))
                    #text.setPos(t0, 0)
                    #self.panels['trace'].add_item(c, text, False)
                    self.trace_region_labels[c].append(region)
                else:
                    tl[lidx].addPoints((t1,), (self.data.data[idx1, c],), data=(ds,), tip=marker_tip)
            for c, sl in enumerate(self.spec_labels):
                if ddt > 0:
                    # TODO: self.spec_region_labels
                    sl[lidx].addPoints((t0, t1), (0.0, 0.0),
                                       data=(f'start: {ds}', f'end: {ds}'))
                else:
                    sl[lidx].addPoints((t1,), (0.0,), data=(ds,), tip=marker_tip)


    def show_metadata(self):
        
        def format_dict(md, level):
            mdtable = ''
            for k in md:
                pads = ''
                if level > 0:
                    pads = f' style="padding-left: {level*30:d}px;"'
                if isinstance(md[k], dict):
                    # new section:
                    if level == 0:
                        mdtable += f'<tr><td colspan=2><font size="+1"><b>{k}:</b></font></td></tr>'
                    else:
                        mdtable += f'<tr><td colspan=2{pads}><b>{k}:</b></td></tr>'
                    mdtable += format_dict(md[k], level+1)
                    if level == 0:
                        mdtable += '<tr><td colspan=2></td></tr>'
                else:
                    # key-value pair:
                    value = md[k]
                    if isinstance(value, (list, tuple)):
                        value = ', '.join([f'{v}' for v in value])
                    else:
                        value = f'{value}'
                    value = value.replace('\r\n', '\n')
                    value = value.replace('\r', '\n')
                    value = value.replace('\n', '<br>')
                    mdtable += f'<tr><td{pads}><b>{k}</b></td><td>{value}</td></tr>'
            return mdtable

        w = xwidth = self.fontMetrics().averageCharWidth()
        mdtable = f'<style>td {{padding: 0 {w}px 0 0; }}</style><table>'
        mdtable += format_dict(self.data.meta_data, 0)
        mdtable += '</table>'
        dialog = QDialog(self)
        dialog.setWindowTitle('Meta data')
        vbox = QVBoxLayout()
        dialog.setLayout(vbox)
        label = QLabel(mdtable)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse);
        scrollarea = QScrollArea()
        scrollarea.setWidget(label)
        vbox.addWidget(scrollarea)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        vbox.addWidget(buttons)
        dialog.show()


    def set_cross_hair(self, checked):
        self.cross_hair = checked
        if self.cross_hair:
            # disable existing key shortcuts:
            self.marker_orig_acts = []
            for l in self.marker_labels:
                ks = QKeySequence(l.key_shortcut)
                for a in dir(self.acts):
                    act = getattr(self.acts, a)
                    if isinstance(act, QAction) and act.shortcut() == ks:
                        self.marker_orig_acts.append((act.shortcut(), act))
                        act.setShortcut(QKeySequence())
                        break
            # setup marker actions:            
            for l in self.marker_labels:
                if l.action is None:
                    l.action = QAction(l.label, self)
                    l.action.triggered.connect(lambda x, label=l.label: self.store_marker(label))
                    self.addAction(l.action)
                l.action.setShortcut(l.key_shortcut)
                l.action.setEnabled(True)
            for r in self.plot_ranges.values():
                r.show_crosshair(True)
            # TODO: add to plot_ranges:
            for axts in self.axts:
                for ax in axts:
                    ax.xline.setVisible(True)
        else:
            self.xpos_action.setVisible(False)
            self.ypos_action.setVisible(False)
            self.zpos_action.setVisible(False)
            for r in self.plot_ranges.values():
                r.show_crosshair(False)
            # TODO: add to plot_ranges:
            for axts in self.axts:
                for ax in axts:
                    ax.xline.setVisible(False)
            self.clear_marker()
            # disable marker actions:
            for l in self.marker_labels:
                l.action.setEnabled(False)
            # restore key shortcuts:
            for key, act in self.marker_orig_acts:
                act.setShortcuts(key)
            self.marker_orig_acts = []


    def clear_marker(self):
        for axs in self.axs:
            for axp in axs:
                if hasattr(axp, 'prev_marker'):
                    axp.prev_marker.clear()
        self.prev_channel = None


    def set_marker(self):
        self.clear_marker()
        if not self.marker_ax is None and not self.marker_time is None:
            if not self.marker_ampl is None:
                self.marker_ax.prev_marker.setData((self.marker_time,),
                                                   (self.marker_ampl,))
            if not self.marker_freq is None:
                self.marker_ax.prev_marker.setData((self.marker_time,),
                                                   (self.marker_freq,))
            # remember:
            self.prev_time = self.marker_time
            self.prev_ampl = self.marker_ampl
            self.prev_freq = self.marker_freq
            self.prev_power = self.marker_power
            self.prev_channel = self.marker_channel

            
    def store_marker(self, label=''):
        self.marker_model.add_data(self.marker_channel,
                                   self.marker_time, self.marker_ampl,
                                   self.marker_freq,
                                   self.marker_power,self.delta_time,
                                   self.delta_ampl, self.delta_freq,
                                   self.delta_power, label)
        # add new label point to scatter plots:
        labels = [l.label for l in self.marker_labels]
        if len(label) > 0 and label in labels and \
           self.marker_time is not None:
            lidx = labels.index(label)
            for c, tl in enumerate(self.trace_labels):
                if c == self.marker_channel and self.marker_ampl is not None:
                    tl[lidx].addPoints((self.marker_time,),
                                      (self.marker_ampl,),
                                       tip=marker_tip)
                else:
                    tidx = int(self.marker_time*self.data.rate)
                    tl[lidx].addPoints((self.marker_time,),
                                       (self.data.data[tidx, c],),
                                       tip=marker_tip)
            for c, sl in enumerate(self.spec_labels):
                y = 0.0 if self.marker_freq is None else self.marker_freq
                sl[lidx].addPoints((self.marker_time,), (y,))
                
        
    def mouse_moved(self, evt, channel):
        if not self.cross_hair:
            return
            
        # find axes and position:
        pixel_pos = evt[0]
        self.marker_ax = None
        self.marker_time = None
        self.marker_ampl = None
        self.marker_freq = None
        self.marker_power = None
        self.marker_channel = channel
        for panel in self.panels.values():
            if not panel.is_used():
                continue
            ax = panel.axs[channel]
            if not ax.sceneBoundingRect().contains(pixel_pos):
                continue
            pos = ax.getViewBox().mapSceneToView(pixel_pos)
            pixel_pos.setX(pixel_pos.x() + 1)
            npos = ax.getViewBox().mapSceneToView(pixel_pos)
            if hasattr(ax, 'xline'):
                ax.xline.setPos(pos.x())
                if panel.is_time():
                    self.marker_ax = ax
                    self.marker_time = pos.x()
            if hasattr(ax, 'yline'):
                ax.yline.setPos(pos.y())
                if panel.is_amplitude():
                    self.marker_ampl = pos.y()
                    if not self.marker_time is None:
                        self.marker_time, self.marker_ampl = \
                            panel.get_amplitude(channel, self.marker_time,
                                                pos.y(), npos.x())
                        # TODO: marke amplitudes for types of amplitude plots!
                if panel.is_yfrequency():
                    self.marker_freq = pos.y()
                    if self.marker_time is not None:
                        self.marker_power = panel.get_power(channel,
                                                            self.marker_time,
                                                            self.marker_freq)
            break
        # set cross-hair positions:
        # TODO: add to plot_ranges:
        if self.marker_time:
            for axts in self.axts:
                for axt in axts:
                    axt.xline.setPos(self.marker_time)
                    axt.xline.setPos(self.marker_time)
        if self.marker_ampl:
            self.plot_ranges['x'].set_crosshair(self.marker_ampl)
        if self.marker_freq:
            self.plot_ranges['f'].set_crosshair(self.marker_freq)
        # compute deltas:
        self.delta_time = None
        self.delta_ampl = None
        self.delta_freq = None
        self.delta_power = None
        if self.marker_time is not None and \
           self.prev_channel is not None and self.prev_time is not None:
                self.delta_time = self.marker_time - self.prev_time
        if self.marker_ampl is not None and \
           self.prev_channel is not None and self.prev_ampl is not None:
                self.delta_ampl = self.marker_ampl - self.prev_ampl
        if self.marker_freq is not None and \
           self.prev_channel is not None and self.prev_freq is not None:
                self.delta_freq = self.marker_freq - self.prev_freq
        if self.marker_power is not None and \
           self.prev_channel is not None and self.prev_power is not None:
                self.delta_power = self.marker_power - self.prev_power
        
        # report time on toolbar:
        if self.delta_time is not None:
            sign = '-' if self.delta_time < 0 else ''
            s = f'\u0394t={sign}{secs_to_str(fabs(self.delta_time))}'
            if fabs(self.delta_time) > 1e-6:
                s += f': f={1/fabs(self.delta_time):.5g}Hz'
            self.xpos_action.setText(s)
        elif self.marker_time is not None:
            sign = '-' if self.marker_time < 0 else ''
            s = f't={sign}{secs_to_str(fabs(self.marker_time))}'
            self.xpos_action.setText(s)
        else:
            self.xpos_action.setText('')
        # report amplitude or frequency on toolbar:
        if self.delta_ampl is not None:
            s = f'\u0394a={self.delta_ampl:6.3f}'
            self.ypos_action.setText(s)
        elif self.marker_ampl is not None:
            s = f'a={self.marker_ampl:6.3f}'
            self.ypos_action.setText(s)
        elif self.delta_freq is not None:
            s = f'\u0394f={self.delta_freq:4.0f}Hz'
            self.ypos_action.setText(s)
        elif self.marker_freq is not None:
            s = f'f={self.marker_freq:4.0f}Hz'
            self.ypos_action.setText(s)
        else:
            self.ypos_action.setText('')
        # report power on toolbar:
        if self.delta_power is not None:
            s = f'\u0394p={self.delta_power:6.1f}dB'
            self.zpos_action.setText(s)
        elif self.marker_power is not None:
            s = f'p={self.marker_power:6.1f}dB'
            self.zpos_action.setText(s)
        else:
            self.zpos_action.setText('')
        self.xpos_action.setVisible(self.marker_time is not None)
        self.ypos_action.setVisible(self.marker_ampl is not None or
                                    self.marker_freq is not None)
        self.zpos_action.setVisible(self.marker_power is not None)


    def mouse_clicked(self, evt, channel):
        if not self.cross_hair:
            return
        
        # update position:
        self.mouse_moved((evt[0].scenePos(),), channel)

        # store marker positions:
        if (evt[0].button() & Qt.LeftButton) > 0 and \
           (evt[0].modifiers() == Qt.NoModifier or \
            (evt[0].modifiers() & Qt.ShiftModifier) == Qt.ShiftModifier):
            menu = QMenu(self)
            acts = [menu.addAction(self.marker_labels_model.icons[l.color], l.label) for l in self.marker_labels]
            act = menu.exec(QCursor.pos())
            if act in acts:
                idx = acts.index(act)
                self.store_marker(self.marker_labels[idx].label)

        # clear marker:
        if (evt[0].button() & Qt.RightButton) > 0:
            self.clear_marker()
            
        # set marker and remember position:
        if (evt[0].button() & Qt.LeftButton) > 0 and \
           (evt[0].modifiers() & Qt.ControlModifier) == Qt.ControlModifier:
            self.set_marker()

            
    def label_editor(self):
        self.marker_labels_model.set(self.marker_labels)
        self.marker_labels_model.edit(self)
        
        
    def marker_table(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Audian marker table')
        vbox = QVBoxLayout()
        dialog.setLayout(vbox)
        view = QTableView()
        view.setModel(self.marker_model)
        view.resizeColumnsToContents()
        width = view.verticalHeader().width() + 24
        for c in range(self.marker_model.columnCount()):
            width += view.columnWidth(c)
        dialog.setMaximumWidth(width)
        dialog.resize(width, 2*width//3)
        view.setSelectionMode(QAbstractItemView.ContiguousSelection)
        vbox.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.Close |
                                   QDialogButtonBox.Save |
                                   QDialogButtonBox.Reset)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self.marker_model.clear)
        buttons.button(QDialogButtonBox.Save).clicked.connect(lambda x: self.marker_model.save(self))
        vbox.addWidget(buttons)
        dialog.show()
            

    def update_borders(self, rect=None):
        for c in range(len(self.figs)):
            self.borders[c].setRect(0, 0, self.figs[c].size().width(),
                                    self.figs[c].size().height())
            self.borders[c].setVisible(c in self.selected_channels)


    def update_plots(self):
        for panel in self.panels.values():
            panel.update_plots()


    def showEvent(self, event):
        if self.data is None:
            return
        self.setting = True
        for c in range(self.data.channels):
            # update time ranges: TODO add to plot_ranges
            for ax in self.axts[c]:
                self.data.set_time_range(ax)
        # update ranges:
        for r in self.plot_ranges:
            r.set_ranges()
        self.data.set_need_update()
        self.update_plots()
        self.setting = False

                
    def resizeEvent(self, event):
        if self.show_channels is None or len(self.show_channels) == 0:
            return
        self.adjust_layout(event.size().width(), event.size().height())
        self.data.set_need_update()
        
            
    def show_xticks(self):
        for c in range(self.data.channels):
            first = True
            for panel in self.panels.values():
                if panel == 'spacer':
                    continue
                if first and c == self.show_channels[-1] and \
                   panel.is_visible(c):
                    panel.axs[c].getAxis('bottom').showLabel(True)
                    panel.axs[c].getAxis('bottom').setStyle(showValues=True)
                    first = False
                else:
                    panel.axs[c].getAxis('bottom').showLabel(False)
                    panel.axs[c].getAxis('bottom').setStyle(showValues=False)

            
    def show_spacers(self):
        first = True
        hide_spacers = []
        for panel in self.panels.values():
            if panel == 'spacer':
                panel.set_visible(not first)
                if not first:
                    hide_spacers.extend(panel.axs)
            elif panel.is_visible(self.show_channels[0]):
                first = False
                hide_spacers = []
        for spacer in hide_spacers:
            spacer.setVisible(False)


    def adjust_layout(self, width, height):
        if self.show_channels is None:
            return
        self.show_xticks()
        self.show_spacers()
        xwidth = self.fontMetrics().averageCharWidth()
        xheight = self.fontMetrics().ascent()
        # subtract full data plot:
        data_height = 5*xheight//2 if len(self.show_channels) <= 1 else 3*xheight//2
        if not self.show_fulldata:
            data_height = 0
        height -= len(self.show_channels)*data_height
        # subtract toolbar:
        height -= 2*xheight
        # subtract time axis:
        taxis_height = 2*xheight
        height -= taxis_height
        # what to plot:
        ntraces = 0
        nspecs = 0
        nspacers = 0
        c = self.show_channels[0]
        for panel in self.panels.values():
            if panel.is_visible(c):
                if panel == 'spacer':
                    nspacers += 1
                elif panel == 'ft':
                    nspecs += 1
                elif panel != 'spacer':
                    ntraces += 1
        nrows = len(self.show_channels)
        # subtract border height:
        border_height = 1.5*xwidth
        height -= nrows*border_height
        # subtract spacer height:
        spacer_height = 0*xheight
        height -= nspacers*spacer_height
        # set heights of panels and channels (figures):
        fig_height = height/nrows
        trace_frac = self.trace_fracs[self.show_specs]
        spec_height = fig_height/(nspecs + trace_frac*ntraces)
        trace_height = trace_frac*spec_height
        bottom_channel = self.show_channels[-1]
        for c in self.show_channels:
            add_height = taxis_height if c == bottom_channel else 0
            self.vbox.setStretch(c, int(10*(border_height +
                                            nspecs*spec_height +
                                            nspacers*spacer_height +
                                            ntraces*trace_height +
                                            add_height)))
            for panel in self.panels.values():
                if panel.is_visible(c):
                    if panel == 'spacer':
                        row_height = spacer_height
                    elif panel == 'ft':
                        row_height = spec_height + add_height
                    else:
                        row_height = trace_height + add_height
                    self.figs[c].ci.layout.setRowFixedHeight(panel.row,
                                                             row_height)
                    add_height = 0
                else:
                    self.figs[c].ci.layout.setRowFixedHeight(panel.row, 0)
        # fix full data plot:
        if self.datafig is not None:
            self.datafig.update_layout(self.show_channels, data_height)
            self.datafig.setVisible(self.show_fulldata)
        # update:
        for c in self.show_channels:
            self.figs[c].update()
        

    def set_times(self, toffset=None, twindow=None, enable_starttime=None,
                  dispatch=True):
        if self.setting:
            return
        self.setting = True
        if not toffset is None:
            self.data.toffset = toffset
        if not twindow is None:
            self.data.twindow = twindow
        self.data.update_times()
        for axs in self.axts:
            for ax in axs:
                if enable_starttime is not None:
                    ax.enable_start_time(enable_starttime)
                if self.isVisible():
                    self.data.set_time_range(ax)
        self.update_plots()
        self.setting = False
        if dispatch:
            self.sigTimesChanged.emit(self.data.toffset, self.data.twindow,
                                      enable_starttime)

            
    def update_times(self, viewbox, trange):
        if self.setting:
            return
        self.set_times(trange[0], trange[1] - trange[0])
        
        
    def zoom_time_in(self):
        if self.data.zoom_time_in():
            self.set_times()
        
        
    def zoom_time_out(self):
        if self.data.zoom_time_out():
            self.set_times()

                
    def time_seek_forward(self):
        if self.data.time_seek_forward():
            self.set_times()

            
    def time_seek_backward(self):
        if self.data.time_seek_backward():
            self.set_times()

                
    def time_forward(self):
        if self.data.time_forward():
            self.set_times()

                
    def time_backward(self):
        axt = None
        for axs in self.axts:
            if len(axs) > 0:
                axt = axs[0]
        if axt is None:
            return
        rect = axt.getViewBox().viewRect()
        toffs = self.data.toffset
        if toffs > rect.left():
            toffs = rect.left()
        if self.data.time_backward(toffs):
            self.set_times()

                
    def time_home(self):
        if self.data.time_home():
            self.set_times()

                
    def time_end(self):
        if self.data.time_end():
            self.set_times()

                
    def snap_time(self):
        if self.data.snap_time():
            self.set_times()


    def set_amplitudes(self, ymin=None, ymax=None):
        if self.setting:
            return
        self.setting = True
        self.plot_ranges['x'].set_ranges(ymin, ymax,
                                         self.selected_channels,
                                         self.isVisible())
        self.setting = False

            
    def update_amplitudes(self, viewbox, arange):
        if self.setting:
            return
        self.set_amplitudes(arange[0], arange[1])
        self.sigAmplitudesChanged.emit(arange[0], arange[1])
        

    def zoom_ampl_in(self, ax_spec='xyz'):
        self.setting = True
        for r in ax_spec:
            self.plot_ranges[r].zoom_in(self.selected_channels,
                                        self.isVisible())
        self.setting = False

        
    def zoom_ampl_out(self, ax_spec='xyz'):
        self.setting = True
        for r in ax_spec:
            self.plot_ranges[r].zoom_out(self.selected_channels,
                                         self.isVisible())
        self.setting = False
        
        
    def auto_ampl(self, ax_spec='xyz'):
        self.setting = True
        for r in ax_spec:
            self.plot_ranges[r].auto(self.data.toffset,
                                     self.data.toffset + self.data.twindow,
                                     self.selected_channels, self.isVisible())
        self.setting = False

        
    def reset_ampl(self, ax_spec='xyz'):
        self.setting = True
        for r in ax_spec:
            self.plot_ranges[r].reset(self.selected_channels, self.isVisible())
        self.setting = False


    def center_ampl(self, ax_spec='xyz'):
        self.setting = True
        for r in ax_spec:
            self.plot_ranges[r].center(self.selected_channels, self.isVisible())
        self.setting = False


    def set_frequencies(self, f0=None, f1=None):
        self.setting = True
        self.plot_ranges['x'].set_ranges(f0, f1,
                                         self.selected_channels,
                                         self.isVisible())
        self.setting = False

            
    def update_frequencies(self, viewbox, frange):
        if self.setting:
            return
        self.set_frequencies(frange[0], frange[1])
        self.sigFrequenciesChanged.emit(frange[0], frange[1])
        
                
    def zoom_freq_in(self):
        self.setting = True
        self.plot_ranges['f'].zoom_in(self.selected_channels, self.isVisible())
        self.setting = False
            
        
    def zoom_freq_out(self):
        self.setting = True
        self.plot_ranges['f'].zoom_out(self.selected_channels, self.isVisible())
        self.setting = False
                
        
    def freq_down(self):
        self.setting = True
        self.plot_ranges['f'].down(self.selected_channels, self.isVisible())
        self.setting = False

            
    def freq_up(self):
        self.setting = True
        self.plot_ranges['f'].up(self.selected_channels, self.isVisible())
        self.setting = False

        
    def freq_home(self):
        self.setting = True
        self.plot_ranges['f'].home(self.selected_channels, self.isVisible())
        self.setting = False

            
    def freq_end(self):
        self.setting = True
        self.plot_ranges['f'].end(self.selected_channels, self.isVisible())
        self.setting = False


    def set_resolution(self, nfft=None, hop_frac=None, dispatch=True):
        if self.setting:
            return
        self.setting = True
        if self.data.spectrum is None:
            return
        self.data.spectrum.update(nfft, hop_frac)
        self.update_plots()
        self.nfftw.setCurrentText(f'{self.data.spectrum.nfft}')
        T = self.data.spectrum.nfft/self.data.rate
        if T >= 1:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={self.data.spectrum.nfft}, ' +
                                  f'T={T:.1f}s, \u0394f={1/T:.2f}Hz')
        elif T >= 0.1:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={self.data.spectrum.nfft}, ' +
                                  f'T={1000*T:.0f}ms, \u0394f={1/T:.1f}Hz')
        elif T >= 0.01:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={self.data.spectrum.nfft}, ' +
                                  f'T={1000*T:.0f}ms, \u0394f={1/T:.0f}Hz')
        elif T >= 0.001:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={self.data.spectrum.nfft}, ' +
                                  f'T={1000*T:.1f}ms, \u0394f={1/T:.0f}Hz')
        else:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={self.data.spectrum.nfft}, ' +
                                  f'T={1000*T:.2f}ms, \u0394f={0.001/T:.1f}kHz')
        self.ofracw.setValue(100*(1 - self.data.spectrum.hop_frac))
        self.setting = False
        if dispatch:
            self.sigResolutionChanged.emit()

        
    def freq_resolution_down(self):
        if self.data.spectrum is not None:
            self.set_resolution(nfft=self.data.spectrum.nfft//2)

        
    def freq_resolution_up(self):
        if self.data.spectrum is not None:
            self.set_resolution(nfft=2*self.data.spectrum.nfft)


    def hop_frac_down(self):
        if self.data.spectrum is not None:
            self.set_resolution(hop_frac=self.data.spectrum.hop_frac/2)


    def hop_frac_up(self):
        if self.data.spectrum is not None:
            self.set_resolution(hop_frac=2*self.data.spectrum.hop_frac)

        
    def set_color_map(self, color_map=None, dispatch=True):
        if color_map is not None:
            self.color_map = color_map
        for cb in self.cbars:
            cb.setColorMap(self.color_maps[self.color_map])
        if dispatch:
            self.sigColorMapChanged.emit()

            
    def color_map_cycler(self):
        self.color_map += 1
        if self.color_map >= len(self.color_maps):
            self.color_map = 0
        self.set_color_map()


    def set_power(self, zmin=None, zmax=None, dispatch=True):
        self.setting = True
        if not isinstance(zmin, list):
            zmin = [zmin]*self.data.channels
        if not isinstance(zmax, list):
            zmax = [zmax]*self.data.channels
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


    def update_filter(self, highpass_cutoff=None, lowpass_cutoff=None):
        """Called when filter cutoffs were changed by key shortcuts or handles
        in spectrum plots and when dispatching.

        """
        if self.setting:
            return
        self.setting = True
        if self.data.filtered is None:
            return
        if highpass_cutoff is not None:
            self.data.filtered.highpass_cutoff = highpass_cutoff
        if lowpass_cutoff is not None:
            self.data.filtered.lowpass_cutoff = lowpass_cutoff
        for ax in self.panels['spectrogram'].axs:
            ax.set_filter_handles(self.data.filtered.highpass_cutoff,
                                  self.data.filtered.lowpass_cutoff)
        self.hpfw.setValue(self.data.filtered.highpass_cutoff)
        self.lpfw.setValue(self.data.filtered.lowpass_cutoff)
        self.data.filtered.update()
        self.update_plots()
        self.setting = False
        self.sigFilterChanged.emit()  # dispatch


    def update_envelope(self, envelope_cutoff=None, show_envelope=None):
        """Called when envelope cutoffs was changed by key shortcuts or widget.
        """
        if self.setting:
            return
        self.setting = True
        if self.data.envelope is None:
            return
        if envelope_cutoff is not None:
            self.data.envelope.envelope_cutoff = envelope_cutoff
        for c in range(self.data.channels):
            if show_envelope is not None:
                self.envelopes[c].setVisible(show_envelope)
        self.data.set_need_update()
        self.data.envelope.update()
        self.update_plots()
        self.envfw.setValue(self.data.envelope.envelope_cutoff)
        self.setting = False
        self.sigEnvelopeChanged.emit()  # dispatch


    def add_to_show_channels(self, channels):
        if isinstance(channels, int):
            channels = [channels]
        for channel in channels:
            if not channel in self.show_channels:
                self.show_channels.append(channel)
        self.show_channels.sort()


    def add_to_selected_channels(self, channels):
        if isinstance(channels, int):
            channels = [channels]
        for channel in channels:
            if not channel in self.selected_channels:
                self.selected_channels.append(channel)
        self.selected_channels.sort()

        
    def all_channels(self):
        if self.selected_channels == self.show_channels:
            self.selected_channels = list(range(self.data.channels))
        else:
            self.selected_channels = list(self.show_channels)
        self.update_borders()


    def next_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx + 1 < len(self.show_channels):
            self.current_channel = self.show_channels[idx + 1]
            self.selected_channels = [self.current_channel]
            self.update_borders()
        else:
            if self.show_channels[-1] < self.data.channels - 1:
                n = len(self.show_channels)
                if n > 1:
                    n -= 1
                if self.show_channels[-1] + n >= self.data.channels:
                    n = self.data.channels - 1 - self.show_channels[-1]
                self.add_to_show_channels(list(range(self.show_channels[-1] + 1,
                                                     self.show_channels[-1] + 1 + n)))
                del self.show_channels[:n]
                self.current_channel += 1
            self.selected_channels = [self.current_channel]
            self.set_channels()


    def previous_channel(self):
        idx = self.show_channels.index(self.current_channel)
        if idx > 0:
            self.current_channel = self.show_channels[idx - 1]
            self.selected_channels = [self.current_channel]
            self.update_borders()
        else:
            if self.show_channels[0] > 0:
                n = len(self.show_channels)
                if n > 1:
                    n -= 1
                if self.show_channels[0] < n:
                    n = self.show_channels[0]
                self.add_to_show_channels(list(range(self.show_channels[0] - n,
                                                 self.show_channels[0])))
                del self.show_channels[-n:]
                self.current_channel -= 1
            self.selected_channels = [self.current_channel]
            self.set_channels()


    def select_next_channel(self):
        show_selected_channels = [c for c in range(self.data.channels) if c in self.show_channels and c in self.selected_channels]
        if len(show_selected_channels) > 0:
            self.current_channel = show_selected_channels[-1]
        idx = self.show_channels.index(self.current_channel)
        if idx + 1 < len(self.show_channels):
            self.current_channel = self.show_channels[idx + 1]
            self.add_to_selected_channels(self.current_channel)
            self.update_borders()
        else:
            if self.show_channels[-1] < self.data.channels - 1:
                n = len(self.show_channels)
                if self.show_channels[-1] + n >= self.data.channels:
                    n = self.data.channels - 1 - self.show_channels[-1]
                self.add_to_show_channels(list(range(self.show_channels[-1] + 1,
                                                     self.show_channels[-1] + 1 + n)))
                del self.show_channels[:n]
            if self.current_channel < self.data.channels - 1:
                self.current_channel += 1
                self.add_to_selected_channels(self.current_channel)
            self.set_channels()


    def select_previous_channel(self):
        show_selected_channels = [c for c in range(self.data.channels) if c in self.show_channels and c in self.selected_channels]
        if len(show_selected_channels) > 0:
            self.current_channel = show_selected_channels[0]
        idx = self.show_channels.index(self.current_channel)
        if idx > 0:
            self.current_channel = self.show_channels[idx - 1]
            self.add_to_selected_channels(self.current_channel)
            self.update_borders()
        else:
            if self.show_channels[0] > 0:
                n = len(self.show_channels)
                if self.show_channels[0] < n:
                    n = self.show_channels[0]
                self.add_to_show_channels(list(range(self.show_channels[0] - n,
                                                     self.show_channels[0])))
                del self.show_channels[-n:]
            if self.current_channel > 0:
                self.current_channel -= 1
                self.add_to_selected_channels(self.current_channel)
            self.set_channels()

            
    def set_channels(self, show_channels=None, selected_channels=None,
                     current_channel=None):
        if self.setting:
            return
        self.setting = True
        if show_channels is not None:
            if self.data is None:
                self.schannels = show_channels
                self.setting = False
                return
            self.show_channels = [c for c in show_channels if c < self.data.channels]
        if selected_channels is not None:
            self.selected_channels = [c for c in selected_channels if c < self.data.channels]
        if current_channel is not None:
            self.current_channel = current_channel
        # current channel must be in shown and selected channels:
        show_selected_channels = [c for c in range(self.data.channels) if c in self.show_channels and c in self.selected_channels]
        if not self.current_channel in show_selected_channels:
            for c in show_selected_channels:
                if c >= self.current_channel:
                    self.current_channel = c
                    break
            if not self.current_channel in show_selected_channels:
                self.current_channel = show_selected_channels[-1]
        for c in range(self.data.channels):
            self.figs[c].setVisible(c in self.show_channels)
            self.acts.channels[c].setChecked(c in self.show_channels)
        self.adjust_layout(self.width(), self.height())
        self.update_borders()
        self.setting = False
            
        
    def toggle_channel(self, channel):
        if self.setting:
            return
        if channel < 0 or channel >= self.data.channels:
            return
        if self.acts.channels[channel].isChecked():
            self.add_to_show_channels(channel)
            self.add_to_selected_channels(channel)
            self.set_channels()
        else:
            if channel in self.show_channels:
                self.show_channels.remove(channel)
                if len(self.show_channels) == 0:
                    c = channel + 1
                    if c >= self.data.channels:
                        c = 0
                    self.show_channels = [c]
                    self.add_to_selected_channels(c)
                if channel in self.selected_channels:
                    self.selected_channels.remove(channel)
                    if len(self.selected_channels) == 0:
                        for c in self.show_channels:
                            if c < channel:
                                self.current_channel = c
                            else:
                                break
                        self.selected_channels = [self.current_channel]
                #if len(self.show_channels) == 1:
                #    self.acts.channels[self.show_channels[0]].setCheckable(False)
                self.set_channels()
        self.setFocus()

        
    def show_channel(self, channel):
        if channel < 0 or channel >= self.data.channels:
            return
        if self.current_channel == channel and \
           self.show_channels == [channel]:
            self.set_channels(list(range(self.data.channels)))
        else:
            self.current_channel = channel
            self.add_to_selected_channels(channel)
            self.set_channels([channel])

        
    def hide_deselected_channels(self):
        show_channels = [c for c in self.show_channels if c in self.selected_channels]
        if len(show_channels) == 0:
            show_channels = [self.show_channels[0]]
        self.set_channels(show_channels)
        
        
    def set_panels(self, traces=None, specs=None, cbars=None, fulldata=None):
        if not traces is None:
            self.show_traces = traces
        if not specs is None:
            self.show_specs = specs
        if not cbars is None:
            self.show_cbars = cbars
        if not fulldata is None:
            self.show_fulldata = fulldata
        for panel in self.panels.values():
            if panel == 'xt':
                panel.set_visible(self.show_traces)
            elif panel == 'ft':
                panel.set_visible(self.show_specs >  0)
                for c in range(len(panel)):
                    self.cbars[c].setVisible(self.show_cbars and
                                             self.show_specs > 0)
        if self.datafig is not None:
            self.datafig.setVisible(self.show_fulldata)
        self.adjust_layout(self.width(), self.height())
        self.data.set_need_update()
        self.data.update_times()
        self.update_plots()
            

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
        self.set_panels()
            
                
    def toggle_fulldata(self):
        self.show_fulldata = not self.show_fulldata
        self.set_panels()
            
            
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


    def zoom_home(self):
        for axs in self.axs:
            for ax in axs:
                ax.getViewBox().zoom_home()


    def set_region_mode(self, mode):
        self.region_mode = mode


    def region_menu(self, channel, vbox, rect):
        if self.region_mode == DataBrowser.zoom_region:
            vbox.zoom_region(rect)
        elif self.region_mode == DataBrowser.play_region:
            self.play_region(rect.left(), rect.right())
        elif self.region_mode == DataBrowser.analyze_region:
            self.analyze_region(rect.left(), rect.right(), channel)
        elif self.region_mode == DataBrowser.save_region:
            self.save_region(rect.left(), rect.right())
        elif self.region_mode == DataBrowser.ask_region:
            menu = QMenu(self)
            zoom_act = menu.addAction('&Zoom')
            play_act = menu.addAction('&Play')
            analyze_act = menu.addAction('&Analyze')
            analyze_act.setEnabled(self.acts.analyze_region.isEnabled())
            analyze_act.setVisible(self.acts.analyze_region.isVisible())
            save_act = menu.addAction('&Save as')
            #crop_act = menu.addAction('&Crop')
            act = menu.exec(QCursor.pos())
            if act is zoom_act:
                vbox.zoom_region(rect)
            elif act is play_act:
                self.play_region(rect.left(), rect.right())
            elif act is analyze_act:
                self.analyze_region(rect.left(), rect.right(), channel)
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
            self.scroll_step = 0.005
        elif self.scroll_step > 1.0:
            if self.scroll_timer.isActive():
                self.scroll_timer.stop()
            self.scroll_step = 0
            return
        else:
            self.scroll_step *= 2
        if not self.scroll_timer.isActive():
            self.scroll_timer.start(50)

        
    def scroll_further(self):
        if self.data.toffset + self.data.twindow > self.data.tmax:
            self.scroll_timer.stop()
            self.scroll_step /= 2
        else:
            self.set_times(self.data.toffset + self.data.twindow*self.scroll_step)


    def set_audio(self, rate_fac=None,
                  use_heterodyne=None, heterodyne_freq=None,
                  dispatch=True):
        if rate_fac is not None:
            self.audio_rate_fac = rate_fac
            if not dispatch:
                self.audiofacw.setCurrentText(f'{self.audio_rate_fac:g}')
        if use_heterodyne is not None:
            self.audio_use_heterodyne = use_heterodyne
        if heterodyne_freq is not None:
            self.audio_heterodyne_freq = float(heterodyne_freq)
            if not dispatch:
                self.audiohetfw.setValue(self.audio_heterodyne_freq)
        if dispatch:
            self.sigAudioChanged.emit(self.audio_rate_fac,
                                      self.audio_use_heterodyne,
                                      self.audio_heterodyne_freq)


    def play_region(self, t0, t1):
        data = self.data.data if self.data.filtered is None else self.data.filtered
        rate = data.rate
        i0 = int(np.round(t0*rate))
        i1 = int(np.round(t1*rate))
        if i1 > len(data):
            i1 = len(data)
            t1 = i1/rate
        n2 = (len(self.selected_channels)+1)//2
        playdata = np.zeros((i1-i0, min(2, len(self.selected_channels))))
        playdata[:,0] = np.mean(data[i0:i1, self.selected_channels[:n2]], 1)
        if len(self.selected_channels) > 1:
            playdata[:,1] = np.mean(data[i0:i1, self.selected_channels[n2:]], 1)
        if self.audio_use_heterodyne:
            # multiply with heterodyne frequency:
            heterodyne = np.sin(2*np.pi*self.audio_heterodyne_freq*np.arange(len(playdata))/rate)
            playdata = (playdata.T * heterodyne).T
            # low-pass filter and downsample:
            fcutoff = 20000.0
            sos = butter(2, 20000, 'low', output='sos', fs=rate)
            nstep = int(np.round(rate/(2*fcutoff)))
            if nstep < 1:
                nstep = 1
            playdata = sosfiltfilt(sos, playdata, 0)[::nstep]
            rate /= nstep
        fade(playdata, rate/self.audio_rate_fac, 0.1)
        self.audio.play(playdata, rate/self.audio_rate_fac, blocking=False)
        self.audio_time = t0
        self.audio_tmax = t1
        self.audio_timer.start(50)
        for c in range(data.channels):
            atime = self.audio_time if c in self.selected_channels else -1
            for vmarker in self.audio_markers[c]:
                vmarker.setValue(atime)


    def play_window(self):
        axt = None
        for axs in self.axts:
            if len(axs) > 0:
                axt = axs[0]
        if axt is None:
            return
        rect = axt.getViewBox().viewRect()
        self.play_region(rect.left(), rect.right())

        
    def mark_audio(self):
        self.audio_time += 0.05 / self.audio_rate_fac
        for amarkers in self.audio_markers:
            for vmarker in amarkers:
                if vmarker.value() >= 0:
                    vmarker.setValue(self.audio_time)
        if self.audio_time > self.audio_tmax:
            self.audio_timer.stop()
            for amarkers in self.audio_markers:
                for vmarker in amarkers:
                    vmarker.setValue(-1)

                    
    def analyze_region(self, t0, t1, channel):
        traces = self.data.get_region(t0, t1, channel)
        for a in self.analyzers:
            a.analyze(t0, t1, channel, traces)
        if self.analysis_table is None:
            self.analysis_results()
        else:
            self.analysis_table.setData(self.get_analysis_table())

            
    def get_analysis_table(self):
        table = []
        r = 0
        while True:
            row = {}
            for a in self.analyzers:
                if r < a.data.rows():
                    for c in range(len(a.data)):
                        us = f'/{a.data.unit(c)}' if a.data.unit(c) else ''
                        header = a.data.label(c) + us
                        row.update({header: a.data[r, c]})
            if len(row) == 0:
                break
            table.append(row)
            r += 1
        return table
    
            
    def analysis_results(self):
        if self.analysis_table is not None:
            return
        if len(self.analyzers) == 0:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle('Audian analyis table')
        vbox = QVBoxLayout()
        dialog.setLayout(vbox)
        self.analysis_table = pg.TableWidget()
        self.analysis_table.setMinimumHeight(250)
        self.analysis_table.setData(self.get_analysis_table())
        c = 0
        for a in self.analyzers:
            for i in range(len(a.data)):
                self.analysis_table.setFormat(a.data.format(i), c)
                c += 1
        vbox.addWidget(self.analysis_table)
        buttons = QDialogButtonBox(QDialogButtonBox.Close |
                                   QDialogButtonBox.Save |
                                   QDialogButtonBox.Reset)
        buttons.rejected.connect(dialog.reject)
        buttons.button(QDialogButtonBox.Reset).clicked.connect(self.clear_analysis)
        buttons.button(QDialogButtonBox.Save).clicked.connect(self.save_analysis)
        vbox.addWidget(buttons)
        dialog.finished.connect(lambda x: [None for self.analysis_table in [None]])
        dialog.show()


    def clear_analysis(self):
        if self.analysis_table is not None:
            self.analysis_table.clear()
        for a in self.analyzers:
            a.data = []

            
    def save_analysis(self):
        if len(self.analyzers) == 0 or len(self.analyzers[0].data) == 0:
            return
        file_name, _ = QFileDialog.getSaveFileName(
            self, 'Save analysis as',
            os.path.splitext(self.data.file_path)[0] + '-analysis.csv',
            'comma-separated values (*.csv)')
        if not file_name:
            return
        table = self.analyzers[0].data
        for a in self.analyzers[1:]:
            for c in range(len(a.data)):
                table.append(a.data.label(c), a.data.unit(c),
                             a.data.format(c), a.data.data[c])
        table.write(file_name, table_format='csv', delimiter=';',
                    unit_style='header', column_numbers=None, sections=0)
     
                    
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

        i0 = int(np.round(t0*self.data.rate))
        i1 = int(np.round(t1*self.data.rate))
        name = os.path.splitext(os.path.basename(self.data.file_path))[0]
        #if self.channel > 0:
        #    filename = f'{name}-{channel:d}-{t0:.4g}s-{t1s:.4g}s.wav'
        t0s = secs_to_str(t0)
        t1s = secs_to_str(t1)
        file_name = f'{name}-{t0s}-{t1s}.wav'
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if 'WAV' in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        file_path = os.path.join(os.path.dirname(self.data.file_path), file_name)
        file_path = QFileDialog.getSaveFileName(self, 'Save region as',
                                                file_path,
                                                ';;'.join(filters))[0]
        if file_path:
            md = deepcopy(self.data.data.metadata())
            update_starttime(md, t0, self.data.rate)
            hkey = 'CodingHistory'
            if 'BEXT' in md:
                hkey = 'BEXT.' + hkey
            bext_code = bext_history_str(self.data.data.encoding,
                                         self.data.rate, self.data.channels)
            add_history(md, bext_code + f',T=cut out {t0s}-{t1s}: {os.path.basename(file_path)}', hkey, bext_code + f',T={self.data.file_path}')
            locs, labels = self.marker_data.get_markers(self.data.rate)
            sel = (locs[:,0] + locs[:,1] >= i0) & (locs[:,0] <= i1)
            locs = locs[sel]
            labels = labels[sel]
            try:
                write_data(file_path,
                           self.data.data[i0:i1, self.selected_channels],
                           self.data.rate, self.data.data.ampl_max,
                           self.data.data.unit, md, locs, labels,
                           encoding=self.data.data.encoding)
                print(f'saved region to "{os.path.relpath(file_path)}"')
            except PermissionError as e:
                print(f'failed to save region to "{os.path.relpath(file_path)}": permission denied')

        
    def save_window(self):
        self.save_region(self.data.toffset, self.data.toffset +
                         self.data.twindow)

import os
from copy import deepcopy
from math import fabs, floor, log10
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
from .panels import Panel, Panels
from .plotranges import PlotRanges
from .bufferedspectrogram import BufferedSpectrogram
from .fulltraceplot import FullTracePlot, secs_to_str
from .timeplot import TimePlot
from .spectrogramplot import SpectrogramPlot
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
    
    sigRangesChanged = Signal(object, object)
    sigResolutionChanged = Signal()
    sigColorMapChanged = Signal()
    sigFilterChanged = Signal()
    sigEnvelopeChanged = Signal()
    sigTraceChanged = Signal(object, object, object)
    sigAudioChanged = Signal(object, object, object)

    
    def __init__(self, file_path, load_kwargs, plugins, channels,
                 audio, acts, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # actions of main window:
        self.acts = acts

        # data:
        self.schannels = channels
        self.data = Data(file_path, **load_kwargs)
        self.plot_ranges = PlotRanges()
        self.trace_acts = []
        self.spec_acts = []
        
        # panels:
        self.panels = Panels()
        self.panels.add_trace()
        self.panels.add_spectrogram()

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

        specs = self.data.get_trace_names(BufferedSpectrogram)
        self.spectrogram = specs[0] if len(specs) > 0 else ''
        self.spectrogram_power = ''
        
        self.grids = 0
        self.show_traces = True
        self.show_specs = 0
        self.show_powers = False
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
        self.axgs = []      # plots with grids
        # lists with marker labels and regions:
        self.trace_labels = [] # labels on traces
        self.trace_region_labels = [] # regions with labels on traces
        self.spec_labels = []  # labels on spectrograms
        self.spec_region_labels = [] # regions with labels on spectrograms
        # full traces:
        self.datafig = None


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


    def add_to_panel_trace(self, trace_name, channel, plot_item):
        panel_name = self.data[trace_name].panel
        self.panels[panel_name].add_item(plot_item, channel, False)


    def toggle_trace(self, checked, name):
        self.data.set_visible(name, checked)
        self.adjust_layout(self.width(), self.height())
        self.sigTraceChanged.emit(self, checked, name)

        
    def set_trace(self, checked, name):
        self.data.set_visible(name, checked)
        for act in self.trace_acts:
            if act.text() == name:
                act.blockSignals(True)
                act.setChecked(checked)
                act.blockSignals(False)
                
        
    def open(self, gui, unwrap, unwrap_clip, highpass_cutoff, lowpass_cutoff):
        # load data:
        self.data.open(unwrap, unwrap_clip)
        if self.data.data is None:
            return
        self.marker_data.file_path = self.data.file_path

        # add traces to menu:
        self.trace_acts = []
        for t in self.data.traces:
            act = QAction(t.name, self)
            act.setCheckable(True)
            act.setChecked(True)
            act.toggled.connect(lambda x, name=t.name: self.toggle_trace(x, name))
            self.trace_acts.append(act)
        # add spectrogram selection to menu:
        self.spec_acts = []
        for spec in self.data.get_trace_names(BufferedSpectrogram):
            act = QAction(spec, self)
            act.setCheckable(True)
            act.setChecked(False)
            act.toggled.connect(lambda x, name=spec: self.set_spectrogram(x, name))
            self.spec_acts.append(act)
            
        # ranges:
        self.plot_ranges.setup(self.data.channels)
        
        # requested filtering:
        if 'filtered' in self.data:
            filtered = self.data['filtered']
            filter_changed = False
            if highpass_cutoff is not None:
                filtered.highpass_cutoff = highpass_cutoff
                filter_changed = True
            if lowpass_cutoff is not None:
                filtered.lowpass_cutoff = lowpass_cutoff
                filter_changed = True
            if filter_changed:
                filtered.update()
                
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

        # make panels:
        self.panels.fill(self.data)
        self.panels.insert_spacers()
            
        # setup plots:
        self.figs = []     # all GraphicsLayoutWidgets - one for each channel
        self.borders = []
        self.sig_proxies = []
        # nested lists (channel, panel):
        self.axs  = []      # all plots
        self.axgs = []      # plots with grids
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
            self.axgs.append([])
            self.audio_markers.append([])
            
            # one figure per channel:
            fig = pg.GraphicsLayoutWidget()
            fig.setBackground(None)
            fig.ci.layout.setContentsMargins(xwidth2, xwidth2, xwidth2, xwidth2)
            fig.ci.layout.setVerticalSpacing(0)
            fig.ci.layout.setHorizontalSpacing(xwidth2)
            fig.ci.layout.setHorizontalSpacing(0)
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
                if panel.is_spacer():
                    axsp = fig.addLayout(row=row, col=0)
                    axsp.setContentsMargins(0, 0, 0, 0)
                    panel.add_ax(row, axsp)
                # trace plot:
                elif panel.is_trace():
                    ylabel = panel.name if panel.name != 'trace' else ''
                    axt = TimePlot(panel.ax_spec, c, self, xwidth, ylabel)
                    self.audio_markers[-1].append(axt.vmarker)
                    fig.addItem(axt, row=row, col=0)
                    self.axgs[-1].append(axt)
                    self.axs[-1].append(axt)
                    panel.add_ax(row, axt)
                    panel.add_traces(c, self.data)
                    self.plot_ranges.add_plot(axt)
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
                elif panel.is_spectrogram():
                    axs = SpectrogramPlot(panel.ax_spec, c, self, xwidth,
                                          self.color_maps[self.color_map],
                                          self.show_cbars, self.show_powers)
                    self.audio_markers[-1].append(axs.vmarker)
                    panel.add_ax(row, axs, axs.cbar)
                    panel.add_traces(c, self.data)
                    self.panels.add_power_ax(panel.name, row, axs.powerax)
                    self.plot_ranges.add_plot(axs)
                    self.plot_ranges.add_plot(axs.powerax)
                    fig.addItem(axs, row=row, col=0)
                    fig.addItem(axs.powerax, row=row, col=1)
                    fig.addItem(axs.cbar, row=row, col=2)
                    self.axgs[-1].append(axs)
                    self.axs[-1].append(axs)
                    # add marker labels:
                    labels = []
                    for l in self.marker_labels:
                        label = pg.ScatterPlotItem(size=10, pen=pg.mkPen(None),
                                                   brush=pg.mkBrush(l.color))
                        axs.addItem(label)
                        labels.append(label)
                    self.spec_labels.append(labels)
                    self.spec_region_labels.append([])
                # power:
                elif panel.is_power():
                    # was already set up with spectrogram
                    continue

                row += 1
                
            proxy = pg.SignalProxy(fig.scene().sigMouseMoved, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_moved(x, c))
            self.sig_proxies.append(proxy)
            proxy = pg.SignalProxy(fig.scene().sigMouseClicked, rateLimit=60,
                                   slot=lambda x, c=c: self.mouse_clicked(x, c))
            self.sig_proxies.append(proxy)
            
        self.setting = True
        self.plot_ranges.set_limits()
        self.plot_ranges.set_ranges()
        if not self.plot_ranges[Panel.amplitudes[0]].is_used():
            self.acts.zoom_xamplitude_in.setEnabled(False)
            self.acts.zoom_xamplitude_out.setEnabled(False)
            self.acts.zoom_xamplitude_in.setVisible(False)
            self.acts.zoom_xamplitude_out.setVisible(False)
        if not self.plot_ranges[Panel.amplitudes[1]].is_used():
            self.acts.zoom_yamplitude_in.setEnabled(False)
            self.acts.zoom_yamplitude_out.setEnabled(False)
            self.acts.zoom_yamplitude_in.setVisible(False)
            self.acts.zoom_yamplitude_out.setVisible(False)
        if not self.plot_ranges[Panel.amplitudes[2]].is_used():
            self.acts.zoom_uamplitude_in.setEnabled(False)
            self.acts.zoom_uamplitude_out.setEnabled(False)
            self.acts.zoom_uamplitude_in.setVisible(False)
            self.acts.zoom_uamplitude_out.setVisible(False)
        if not self.plot_ranges[Panel.frequencies[0]].is_used():
            self.acts.zoom_ffrequency_in.setEnabled(False)
            self.acts.zoom_ffrequency_out.setEnabled(False)
            self.acts.zoom_ffrequency_in.setVisible(False)
            self.acts.zoom_ffrequency_out.setVisible(False)
        if not self.plot_ranges[Panel.frequencies[1]].is_used():
            self.acts.zoom_wfrequency_in.setEnabled(False)
            self.acts.zoom_wfrequency_out.setEnabled(False)
            self.acts.zoom_wfrequency_in.setVisible(False)
            self.acts.zoom_wfrequency_out.setVisible(False)
        self.setting = False
        self.data.set_need_update()
        self.set_times()
        
        # tool bar:
        self.toolbar = QToolBar()
        self.toolbar.addAction(self.acts.time_home)
        self.toolbar.addAction(self.acts.time_up)
        self.toolbar.addAction(self.acts.time_down)
        self.toolbar.addAction(self.acts.time_end)
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

        if self.spectrogram:
            self.spectrogram_power = self.panels[self.data[self.spectrogram].panel].z()
        if 'spectrogram' in self.data:
            self.toolbar.addWidget(QLabel('N:'))
            self.nfftw = QComboBox(self)
            self.nfftw.tooltip = 'NFFT (R, Shift+R)'
            self.nfftw.setToolTip(self.nfftw.tooltip)
            self.nfftw.addItems([f'{2**i}' for i in range(3, 20)])
            self.nfftw.setEditable(False)
            self.nfftw.setCurrentText(f'{self.data["spectrogram"].nfft}')
            self.nfftw.currentTextChanged.connect(lambda s: self.set_resolution(nfft=int(s)))
            self.toolbar.addWidget(self.nfftw)

            self.toolbar.addWidget(QLabel('O:'))
            self.ofracw = pg.SpinBox(self, 100*(1 - self.data["spectrogram"].hop_frac),
                                     bounds=(0, 99.8),
                                     suffix='%', siPrefix=False,
                                     step=0.5, dec=True, decimals=3,
                                     minStep=0.01)
            self.ofracw.setToolTip('Overlap of Fourier segments (O, Shift+O)')
            self.ofracw.valueChanged.connect(lambda v: self.set_resolution(hop_frac=1-0.01*v))
            self.toolbar.addWidget(self.ofracw)
            self.toolbar.addSeparator()

        if 'filtered' in self.data:
            self.toolbar.addWidget(QLabel('H:'))
            self.hpfw = pg.SpinBox(self, self.data['filtered'].highpass_cutoff,
                                   bounds=(0, self.data.rate/2),
                                   suffix='Hz', siPrefix=True,
                                   step=0.5, dec=True, decimals=3,
                                   minStep=10**floor(log10(0.01*self.data.rate/2)))
            self.hpfw.setToolTip('High-pass filter cutoff frequency (H, Shift+H)')
            self.hpfw.sigValueChanged.connect(lambda s: self.update_filter(highpass_cutoff=s.value()))
            self.toolbar.addWidget(self.hpfw)        

            self.toolbar.addWidget(QLabel(' L:'))
            self.lpfw = pg.SpinBox(self, self.data['filtered'].lowpass_cutoff,
                                   bounds=(0.01*self.data.rate/2, self.data.rate/2),
                                   suffix='Hz', siPrefix=True,
                                   step=0.5, dec=True, decimals=3,
                                   minStep=10**floor(log10(0.01*self.data.rate/2)))
            self.lpfw.setToolTip('Low-pass filter cutoff frequency (L, Shift+L)')
            self.lpfw.sigValueChanged.connect(lambda s: self.update_filter(lowpass_cutoff=s.value()))
            self.toolbar.addWidget(self.lpfw)
        else:
            self.hpfw = None
            self.lpfw = None
            self.acts.link_filter.setEnabled(False)
            self.acts.highpass_up.setEnabled(False)
            self.acts.highpass_down.setEnabled(False)
            self.acts.lowpass_up.setEnabled(False)
            self.acts.lowpass_down.setEnabled(False)
        
        if 'envelope' in self.data:
            self.toolbar.addWidget(QLabel(' E:'))
            self.envfw = pg.SpinBox(self, self.data['envelope'].envelope_cutoff,
                                    bounds=(0, 0.5*self.data.rate/2),
                                    suffix='Hz', siPrefix=True,
                                    step=0.5, dec=True, decimals=3,
                                    minStep=10**np.floor(np.log10(0.00001*self.data.rate/2)))
            self.envfw.setToolTip('Envelope low-pass filter cutoff frequency (E, Shift+E)')
            self.envfw.sigValueChanged.connect(lambda s: self.update_envelope(envelope_cutoff=s.value()))
            self.toolbar.addWidget(self.envfw)
        else:
            self.envfw = None
            self.acts.link_envelope.setEnabled(False)
            self.acts.show_envelope.setEnabled(False)
            self.acts.envelope_up.setEnabled(False)
            self.acts.envelope_down.setEnabled(False)

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

        # update visibility of traces:
        for name in self.data.keys():
            for act in self.trace_acts:
                if act.text() == name:
                    act.blockSignals(True)
                    act.setChecked(self.data.is_visible(name))
                    act.blockSignals(False)

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
                    self.panels['trace'].add_item(region, c, False)
                    #text = pg.TextItem(ds, color='green', anchor=(0, 0))
                    #text.setPos(t0, 0)
                    #self.panels['trace'].add_item(text, c, False)
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
            self.plot_ranges.clear_marker()
            self.plot_ranges.clear_stored_marker()
        else:
            self.xpos_action.setVisible(False)
            self.ypos_action.setVisible(False)
            self.zpos_action.setVisible(False)
            self.plot_ranges.clear_marker()
            self.plot_ranges.clear_stored_marker()
            self.plot_ranges.update_crosshair()
            # disable marker actions:
            for l in self.marker_labels:
                l.action.setEnabled(False)
            # restore key shortcuts:
            for key, act in self.marker_orig_acts:
                act.setShortcuts(key)
            self.marker_orig_acts = []


    def set_marker(self):
        pass
        """
        if not self.marker_ax is None and not self.marker_time is None:
            if not self.marker_ampl is None:
                self.marker_ax.prev_marker.setData((self.marker_time,),
                                                   (self.marker_ampl,))
            if not self.marker_freq is None:
                self.marker_ax.prev_marker.setData((self.marker_time,),
                                                   (self.marker_freq,))
        """

            
    def store_marker(self, label=''):
        """
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
        """                
        
    def mouse_moved(self, evt, channel):
        if not self.cross_hair:
            return
            
        # find axes and position:
        pixel_pos = evt[0]
        self.plot_ranges.clear_marker()
        for panel in self.panels.values():
            if not panel.is_used() and not panel.is_visible(channel):
                continue
            ax = panel.axs[channel]
            if not ax.sceneBoundingRect().contains(pixel_pos):
                continue
            pos = ax.getViewBox().mapSceneToView(pixel_pos)
            pixel_pos.setX(pixel_pos.x() + 1)
            npos = ax.getViewBox().mapSceneToView(pixel_pos)
            x0 = pos.x()
            x1 = npos.x()
            y = pos.y()
            x, y, z = ax.get_marker_pos(x0, x1, y)
            self.plot_ranges[panel.x()].set_marker(channel, ax, x)
            self.plot_ranges[panel.y()].set_marker(channel, ax, y)
            if z is not None:
                self.plot_ranges[panel.z()].set_marker(channel, ax, z)
            """
            if not self.marker_time is None:
                self.marker_time, self.marker_ampl = \
                    panel.get_amplitude(channel, self.marker_time,
                                        pos.y(), npos.x())
            if panel.z():
                self.plot_ranges[panel.z()].set_marker(channel, ax, XXX)
            if self.marker_time is not None:
                self.marker_power = panel.get_power(channel,
                                                    self.marker_time,
                                                    self.marker_freq)
            """
            break
        # set cross-hair positions:
        self.plot_ranges.update_crosshair()
        
        # report time on toolbar:
        s = ''
        time, delta_time = self.plot_ranges.marker_delta_time()
        if delta_time is not None:
            sign = '-' if delta_time < 0 else ''
            s = f'\u0394{time}={sign}{secs_to_str(fabs(delta_time))}'
            if fabs(delta_time) > 1e-6:
                if 1/fabs(delta_time) > 1000:
                    s += f' ({0.001/fabs(delta_time):.4g}kHz)'
                elif 1/fabs(delta_time) < 1:
                    s += f' ({1000/fabs(delta_time):.4g}mHz)'
                else:
                    s += f' ({1/fabs(delta_time):.4g}Hz)'
        time, pos = self.plot_ranges.marker_time()
        if not s and pos is not None:
            sign = '-' if pos < 0 else ''
            s = f't={sign}{secs_to_str(fabs(pos))}'
        self.xpos_action.setText(s)
        self.xpos_action.setVisible(len(s) > 0)
        # report amplitude or frequency on toolbar:
        s = ''
        ampl, delta_ampl = self.plot_ranges.marker_delta_amplitude()
        freq, delta_freq = self.plot_ranges.marker_delta_frequency()
        if delta_ampl is not None:
            s = f'\u0394{ampl}={delta_ampl:6.3f}'
            self.ypos_action.setText(s)
        elif delta_freq is not None:
            if abs(delta_freq) > 1000:
                s = f'\u0394{freq}={delta_freq/1000:.4g}kHz'
            elif abs(delta_freq) < 1:
                s = f'\u0394{freq}={delta_freq*1000:.4g}mHz'
            else:
                s = f'\u0394{freq}={delta_freq:.4g}Hz'
        ampl, pos = self.plot_ranges.marker_amplitude()
        if not s and pos is not None:
            s = f'{ampl}={pos:.5g}'
        freq, pos = self.plot_ranges.marker_frequency()
        if not s and pos is not None:
            if pos > 1000:
                s = f'{freq}={pos/1000:.4g}kHz'
            elif pos < 1:
                s = f'{freq}={pos*1000:.4g}mHz'
            else:
                s = f'{freq}={pos:.4g}Hz'
        self.ypos_action.setText(s)
        self.ypos_action.setVisible(len(s) > 0)
        # report power on toolbar:
        s = ''
        pwr, delta_power = self.plot_ranges.marker_delta_power()
        if delta_power is not None:
            s = f'\u0394{pwr}={delta_power:6.1f}dB'
        pwr, pos = self.plot_ranges.marker_power()
        if not s and pos is not None:
            s = f'{pwr}={pos:6.1f}dB'
        self.zpos_action.setText(s)
        self.zpos_action.setVisible(len(s) > 0)

        
    def mouse_clicked(self, evt, channel):
        if not self.cross_hair:
            return
        
        # update position:
        self.mouse_moved((evt[0].scenePos(),), channel)

        """
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
        
        """
        # clear marker:
        if (evt[0].button() & Qt.RightButton) > 0:
            self.plot_ranges.clear_stored_marker()
            
        # store marker position:
        if (evt[0].button() & Qt.LeftButton) > 0: # and \
           #(evt[0].modifiers() & Qt.ControlModifier) == Qt.ControlModifier:
            self.plot_ranges.store_marker()

            
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


    def showEvent(self, event):
        if self.data is None:
            return
        self.setting = True
        self.plot_ranges.set_ranges()
        self.data.set_need_update()
        self.panels.update_plots()
        self.plot_ranges.set_powers()
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
                if panel.is_spacer() or panel.is_power():
                    continue
                if first and c == self.show_channels[-1] and \
                   panel.is_visible(c):
                    panel.axs[c].getAxis('bottom').showLabel(True)
                    panel.axs[c].getAxis('bottom').setStyle(showValues=True)
                    first = False
                else:
                    panel.axs[c].getAxis('bottom').showLabel(False)
                    panel.axs[c].getAxis('bottom').setStyle(showValues=False)


    def adjust_layout(self, width, height):
        if self.show_channels is None:
            return
        self.show_xticks()
        self.panels.show_spacers(self.show_channels[0])
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
            if panel.is_visible(c) and (panel.is_spacer() or
                                        panel.has_visible_traces(c)):
                if panel.is_spacer():
                    nspacers += 1
                elif panel.is_spectrogram():
                    nspecs += 1
                elif panel.is_trace():
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
            if self.show_specs > 0 and self.show_powers:
                self.figs[c].ci.layout.setColumnFixedWidth(1, 0.1*width)
            else:
                self.figs[c].ci.layout.setColumnFixedWidth(1, 0)
            add_height = taxis_height if c == bottom_channel else 0
            self.vbox.setStretch(c, int(10*(border_height +
                                            nspecs*spec_height +
                                            nspacers*spacer_height +
                                            ntraces*trace_height +
                                            add_height)))
            for panel in self.panels.values():
                if panel.is_power():
                    continue
                if panel.is_visible(c) and (panel.is_spacer() or
                                            panel.has_visible_traces(c)):
                    if panel.is_spacer():
                        row_height = spacer_height
                    elif panel.is_spectrogram():
                        row_height = spec_height + add_height
                    elif panel.is_trace():
                        row_height = trace_height + add_height
                    else:
                        continue
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

            
    def update_ranges(self, viewbox, arange):
        """
        TODO: a newer version of pyqtgraph might need:
        def update_ranges(self, viewbox, arange):
        """
        if self.setting:
            return
        panel = self.panels.get_panel(viewbox)
        if not panel:
            return
        axspec = panel.ax_spec
        for s in range(2):
            r0, r1 = arange[s]
            if axspec[s] in Panel.times:
                self.set_times(r0, r1 - r0)
            else:
                self.set_ranges(axspec[s], r0, r1)
        self.sigRangesChanged.emit(axspec, arange)


    def set_times(self, toffset=None, twindow=None):
        if self.setting:
            return
        self.setting = True
        trange = self.plot_ranges[Panel.times[0]]
        trange.set_ranges(toffset, None, twindow, None, True)
        self.data.update_times(trange.r0[0], trange.r1[0])
        self.panels.update_plots()
        self.plot_ranges.set_powers()
        self.setting = False
        

    def apply_time_ranges(self, timefunc):
        self.setting = True
        getattr(self.plot_ranges, timefunc)(Panel.times[0], None,
                                            self.isVisible())
        trange = self.plot_ranges[Panel.times[0]]
        self.data.update_times(trange.r0[0], trange.r1[0])
        # TODO: set time range here!
        self.panels.update_plots()
        self.plot_ranges.set_powers()
        self.setting = False
        

    def set_ranges(self, axspec, r0=None, r1=None):
        if self.setting:
            return
        self.setting = True
        self.plot_ranges[axspec].set_ranges(r0, r1, None,
                                            self.selected_channels,
                                            self.isVisible())
        self.setting = False


    def apply_ranges(self, amplitudefunc, axspec):
        self.setting = True
        getattr(self.plot_ranges, amplitudefunc)(axspec,
                                                 self.selected_channels,
                                                 self.isVisible())
        self.setting = False
        

    def auto_ampl(self, axspec=Panel.amplitudes):
        self.setting = True
        trange = self.plot_ranges[Panel.times[0]]
        t0 = trange.r0[0]
        t1 = trange.r1[0]
        self.plot_ranges.auto(axspec, t0, t1,
                              self.selected_channels, self.isVisible())
        self.setting = False


    def set_spectrogram(self, checked, spec):
        if checked:
            self.spectrogram = spec
            if self.spectrogram:
                self.spectrogram_power = self.panels[self.data[self.spectrogram].panel].z()
            self.set_resolution()

        
    def set_resolution(self, nfft=None, hop_frac=None, dispatch=True):
        if self.setting:
            return
        self.setting = True
        if not self.spectrogram and self.spectrogram not in self.data:
            return
        spectrogram = self.data[self.spectrogram]
        spectrogram.update(nfft, hop_frac)
        self.panels.update_plots()
        self.plot_ranges.set_powers()
        self.nfftw.setCurrentText(f'{spectrogram.nfft}')
        T = spectrogram.nfft/self.data.rate
        if T >= 1:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={spectrogram.nfft}, ' +
                                  f'T={T:.1f}s, \u0394f={1/T:.2f}Hz')
        elif T >= 0.1:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={spectrogram.nfft}, ' +
                                  f'T={1000*T:.0f}ms, \u0394f={1/T:.1f}Hz')
        elif T >= 0.01:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={spectrogram.nfft}, ' +
                                  f'T={1000*T:.0f}ms, \u0394f={1/T:.0f}Hz')
        elif T >= 0.001:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={spectrogram.nfft}, ' +
                                  f'T={1000*T:.1f}ms, \u0394f={1/T:.0f}Hz')
        else:
            self.nfftw.setToolTip(self.nfftw.tooltip +
                                  f'={spectrogram.nfft}, ' +
                                  f'T={1000*T:.2f}ms, \u0394f={0.001/T:.1f}kHz')
        self.ofracw.setValue(100*(1 - spectrogram.hop_frac))
        self.setting = False
        if dispatch:
            self.sigResolutionChanged.emit()

        
    def freq_resolution_down(self):
        if self.spectrogram in self.data:
            self.set_resolution(nfft=self.data[self.spectrogram].nfft//2)

        
    def freq_resolution_up(self):
        if self.spectrogram in self.data:
            self.set_resolution(nfft=2*self.data[self.spectrogram].nfft)


    def hop_frac_down(self):
        if self.spectrogram in self.data:
            self.set_resolution(hop_frac=self.data[self.spectrogram].hop_frac/2)


    def hop_frac_up(self):
        if self.spectrogram in self.data:
            self.set_resolution(hop_frac=2*self.data[self.spectrogram].hop_frac)

        
    def set_color_map(self, color_map=None, dispatch=True):
        if color_map is not None:
            self.color_map = color_map
        for panel in self.panels.values():
            if panel.is_spectrogram():
                panel.set_colormap(self.color_maps[self.color_map])
        if dispatch:
            self.sigColorMapChanged.emit()

            
    def color_map_cycler(self):
        self.color_map += 1
        if self.color_map >= len(self.color_maps):
            self.color_map = 0
        self.set_color_map()


    def update_filter(self, highpass_cutoff=None, lowpass_cutoff=None):
        """Called when filter cutoffs were changed by key shortcuts or handles
        in spectrum plots and when dispatching.

        """
        if self.setting:
            return
        self.setting = True
        if 'filtered' not in self.data:
            return
        filtered = self.data['filtered']
        if highpass_cutoff is not None:
            filtered.highpass_cutoff = highpass_cutoff
        if lowpass_cutoff is not None:
            filtered.lowpass_cutoff = lowpass_cutoff
        for ax in self.panels['spectrogram'].axs:
            ax.set_filter_handles(filtered.highpass_cutoff,
                                  filtered.lowpass_cutoff)
        self.hpfw.setValue(filtered.highpass_cutoff)
        self.lpfw.setValue(filtered.lowpass_cutoff)
        filtered.update()
        self.panels.update_plots()
        self.plot_ranges.set_powers()
        self.setting = False
        self.sigFilterChanged.emit()  # dispatch


    def update_envelope(self, envelope_cutoff=None, show_envelope=None,
                        dispatch=True):
        """Called when envelope cutoff was changed by key shortcuts or widget.
        """
        if self.setting:
            return
        self.setting = True
        if 'envelope' not in self.data:
            return
        if envelope_cutoff is not None:
            envelope = self.data['envelope']
            envelope.envelope_cutoff = envelope_cutoff
            envelope.update()
            self.data.set_need_update()
            self.panels.update_plots()
            self.envfw.setValue(envelope.envelope_cutoff)
        if show_envelope is not None:
            for name in self.data.keys():
                if name.startswith('env'):
                    self.set_trace(show_envelope, name)
            self.adjust_layout(self.width(), self.height())
        self.setting = False
        if dispatch:
            self.sigEnvelopeChanged.emit()


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
        
        
    def set_panels(self, traces=None, specs=None, powers=None,
                   cbars=None, fulldata=None):
        if not traces is None:
            self.show_traces = traces
        if not specs is None:
            self.show_specs = specs
        if not powers is None:
            self.show_powers = powers
        if not cbars is None:
            self.show_cbars = cbars
        if not fulldata is None:
            self.show_fulldata = fulldata
        for panel in self.panels.values():
            if panel.is_trace():
                panel.set_visible(self.show_traces)
            elif panel.is_spectrogram():
                panel.set_visible(self.show_specs >  0)
                panel.set_cbar_visible(self.show_specs >  0 and
                                       self.show_cbars)
            elif panel.is_power():
                panel.set_visible(self.show_specs >  0 and
                                  self.show_powers)
        if self.datafig is not None:
            self.datafig.setVisible(self.show_fulldata)
        self.adjust_layout(self.width(), self.height())
        self.data.set_need_update()
        trange = self.plot_ranges[Panel.times[0]]
        self.data.update_times(trange.r0[0], trange.r1[0])
        self.panels.update_plots()
        self.plot_ranges.set_powers()
            

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
            
                
    def toggle_powers(self):
        self.show_powers = not self.show_powers
        self.set_panels()
            
                
    def toggle_fulldata(self):
        self.show_fulldata = not self.show_fulldata
        self.set_panels()
            
            
    def toggle_grids(self):
        self.grids -= 1
        if self.grids < 0:
            self.grids = 3
        self.panels.show_grid(self.grids)


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
        panel = self.panels.get_panel(vbox)
        if self.region_mode == DataBrowser.zoom_region or not panel.is_time():
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
        trange = self.plot_ranges[Panel.times[0]]
        if trange.at_end():
            self.scroll_timer.stop()
            self.scroll_step /= 2
        else:
            twin = trange.r1[0] - trange.r0[0]
            self.set_times(trange.r0[0] + twin*self.scroll_step, twin)


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
        data = self.data['filtered'] if 'filtered' in self.data else self.data['data']
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
        trange = self.plot_ranges[Panel.times[0]]
        self.play_region(trange.r0[0], trange.r1[0])

        
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
        trange = self.plot_ranges[Panel.times[0]]
        self.save_region(trange.r0[0], trange.r1[0])

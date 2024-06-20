import os
import sys
import argparse
import numpy as np
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence, QIcon
from PyQt5.QtWidgets import QStyle, QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtWidgets import QAction, QActionGroup, QPushButton
from PyQt5.QtWidgets import QDialog, QDialogButtonBox, QScrollArea
from PyQt5.QtWidgets import QFileDialog, QMessageBox
import pyqtgraph as pg
from audioio import available_formats, PlayAudio
from .version import __version__, __year__
from .databrowser import DataBrowser
from .plugins import Plugins
from .panels import Panel


class Audian(QMainWindow):
    def __init__(self, file_paths, load_kwargs, plugins, channels,
                 highpass_cutoff, lowpass_cutoff,
                 unwrap, unwrap_clip):
        super().__init__()

        self.plugins = plugins
        if self.plugins is None:
            self.plugins = Plugins()

        class acts: pass
        self.acts = acts

        self.browsers = []
        self.prev_browser = None   # for load_data()

        self.channels = channels
        self.highpass_cutoff = highpass_cutoff
        self.lowpass_cutoff = lowpass_cutoff
        
        self.audio = PlayAudio()

        self.link_timezoom = True
        self.link_timescroll = False
        self.link_ranges = {}
        for s in Panel.amplitudes + Panel.frequencies + Panel.powers:
            self.link_ranges[s] = True
        self.link_filter = True
        self.link_envelope = True
        self.link_channels = True
        self.link_panels = True
        self.link_audio = True

        # window:
        rec = QApplication.desktop().screenGeometry()
        height = rec.height()
        width = rec.width()
        self.resize(int(0.7*width), int(0.7*height))
        self.setWindowTitle(f'Audian {__version__}')
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabBarAutoHide(False)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda index: self.close(index))
        self.tabs.currentChanged.connect(self.adapt_menu)
        self.setCentralWidget(self.tabs)

        # actions:
        self.toggle_menu = None
        self.show_menu = None
        self.data_menus = []
        file_menu = self.setup_file_actions(self.menuBar())
        region_menu = self.setup_region_actions(self.menuBar())
        spec_menu = self.setup_spectrogram_actions(self.menuBar())
        view_menu = self.setup_view_actions(self.menuBar())
        help_menu = self.setup_help_actions(self.menuBar())
        self.menus = [file_menu, region_menu, spec_menu, view_menu, help_menu]
        self.keys = []   # list of key shortcuts
        
        # default widget:
        self.setup_startup()
        self.startup_active = False
        
        # data:
        self.unwrap = unwrap
        self.unwrap_clip = unwrap_clip
        self.load_kwargs = load_kwargs
        self.load_files(file_paths)

        # init widgets to show:
        if len(self.browsers) > 0:
            self.tabs.setCurrentIndex(0)
            self.startup.setVisible(False)
            self.startup_active = False
            for menu in self.data_menus:
                menu.setEnabled(True)
        else:
            self.startup.setVisible(True)
            self.startup_active = True
            self.tabs.addTab(self.startup, 'Startup')
            for menu in self.data_menus:
                menu.setEnabled(False)


    def __del__(self):
        if self.audio is not None:
            self.audio.close()


    def setup_startup(self):
        self.startup = QWidget(self)
        hbox = QHBoxLayout(self.startup)
        hbox.addStretch(1)
        vbox = QVBoxLayout()
        hbox.addLayout(vbox, 1)
        vbox.addStretch(3)
        title = QLabel(f'Audian {__version__}', self.startup)
        font = title.font()
        font.setPointSize(72)
        font.setBold(True)
        title.setFont(font)
        vbox.addWidget(title)
        vbox.addStretch(1)
        open_button = QPushButton('&Open files')
        open_button.clicked.connect(self.open_files)
        vbox.addWidget(open_button)
        quit_button = QPushButton('&Quit')
        quit_button.clicked.connect(self.quit)
        vbox.addWidget(quit_button)
        vbox.addStretch(3)
        hbox.addStretch(2)


    def browser(self):
        return self.tabs.currentWidget()


    def menu_shortcuts(self, menu):
        for act in menu.actions():
            if act.menu():
                self.menu_shortcuts(act.menu())
        title = menu.title().replace('&', '')
        s = ''
        for act in menu.actions():
            if not act.menu() and act.isEnabled():
                name = act.text().replace('&', '')
                keys = ', '.join([key.toString() for key in act.shortcuts()])
                if name and keys:
                    s += f'<tr><td>{name:20s}</td><td>{keys}</td></tr>\n'
        if len(s) > 0:
            ks = f'<h2>{title}</h2>\n'
            ks += '<table>\n'
            ks += s
            ks += '</table>\n'
            self.keys.append(ks)

        
    def setup_file_actions(self, menu):
        self.acts.open_files = QAction('&Open', self)
        self.acts.open_files.setShortcuts(QKeySequence.Open)
        self.acts.open_files.triggered.connect(self.open_files)

        self.acts.save_window = QAction('&Save window as', self)
        self.acts.save_window.setShortcuts(QKeySequence.SaveAs)
        self.acts.save_window.triggered.connect(lambda x: self.browser().save_window())

        self.acts.meta_data = QAction('&Meta data', self)
        self.acts.meta_data.triggered.connect(lambda x: self.browser().show_metadata())

        self.acts.close = QAction('&Close', self)
        self.acts.close.setShortcuts(QKeySequence.Close)
        self.acts.close.triggered.connect(lambda x: self.close(None))

        self.acts.quit = QAction('&Quit', self)
        self.acts.quit.setShortcuts(QKeySequence.Quit)
        self.acts.quit.triggered.connect(self.quit)

        file_menu = menu.addMenu('&File')
        file_menu.addAction(self.acts.open_files)
        file_menu.addAction(self.acts.save_window)
        file_menu.addSeparator()
        file_menu.addAction(self.acts.meta_data)
        file_menu.addSeparator()
        file_menu.addAction(self.acts.close)
        file_menu.addAction(self.acts.quit)
        return file_menu


    def set_rect_mode(self):
        for b in self.browsers:
            b.set_zoom_mode(pg.ViewBox.RectMode)


    def set_pan_mode(self):
        for b in self.browsers:
            b.set_zoom_mode(pg.ViewBox.PanMode)


    def set_zoom(self):
        for b in self.browsers:
            b.set_region_mode(DataBrowser.zoom_region)


    def set_play(self):
        for b in self.browsers:
            b.set_region_mode(DataBrowser.play_region)


    def set_analyze(self):
        for b in self.browsers:
            b.set_region_mode(DataBrowser.analyze_region)


    def set_save(self):
        for b in self.browsers:
            b.set_region_mode(DataBrowser.save_region)


    def set_ask(self):
        for b in self.browsers:
            b.set_region_mode(DataBrowser.ask_region)


    def set_cross_hair(self, checked):
        for b in self.browsers:
            b.set_cross_hair(checked)

            
    def setup_region_actions(self, menu):
        self.acts.rect_zoom = QAction('&Rectangle zoom', self)
        self.acts.rect_zoom.setCheckable(True)
        self.acts.rect_zoom.setShortcut('Ctrl+R')
        self.acts.rect_zoom.toggled.connect(self.set_rect_mode)
        
        self.acts.pan_zoom = QAction('&Pan && zoom', self)
        self.acts.pan_zoom.setCheckable(True)
        self.acts.pan_zoom.setShortcut('Ctrl+Z')
        self.acts.pan_zoom.toggled.connect(self.set_pan_mode)
        
        self.acts.zoom_mode = QActionGroup(self)
        self.acts.zoom_mode.addAction(self.acts.rect_zoom)
        self.acts.zoom_mode.addAction(self.acts.pan_zoom)
        self.acts.rect_zoom.setChecked(True)
        
        self.acts.zoom_back = QAction('Zoom &back', self)
        self.acts.zoom_back.setIcon(self.style().standardIcon(QStyle.SP_ArrowBack))
        self.acts.zoom_back.setToolTip('Zoom back (Backspace)')
        self.acts.zoom_back.setShortcuts(['Backspace', 'Alt+Left'])
        self.acts.zoom_back.triggered.connect(lambda x=0: self.browser().zoom_back())
        
        self.acts.zoom_forward = QAction('Zoom &forward', self)
        self.acts.zoom_forward.setIcon(self.style().standardIcon(QStyle.SP_ArrowForward))
        self.acts.zoom_forward.setToolTip('Zoom forward (Shift+Backspace)')
        self.acts.zoom_forward.setShortcuts(['Shift+Backspace', 'Alt+Right'])
        self.acts.zoom_forward.triggered.connect(lambda x=0: self.browser().zoom_forward())
        
        self.acts.zoom_home = QAction('Zoom &home', self)
        self.acts.zoom_home.setIcon(self.style().standardIcon(QStyle.SP_DirHomeIcon))
        self.acts.zoom_home.setToolTip('Zoom home (Alt+Backspace)')
        self.acts.zoom_home.setShortcut('Alt+Backspace')
        self.acts.zoom_home.triggered.connect(lambda x=0: self.browser().zoom_home())
        
        self.acts.zoom_region = QAction('&Zoom', self)
        self.acts.zoom_region.setCheckable(True)
        self.acts.zoom_region.setShortcut('z')
        self.acts.zoom_region.toggled.connect(self.set_zoom)
        
        self.acts.play_region = QAction('&Play', self)
        self.acts.play_region.setCheckable(True)
        self.acts.play_region.setShortcut('P')
        self.acts.play_region.toggled.connect(self.set_play)
        
        self.acts.analyze_region = QAction('&Analyze', self)
        self.acts.analyze_region.setCheckable(True)
        self.acts.analyze_region.setShortcut('a')
        self.acts.analyze_region.toggled.connect(self.set_analyze)
        
        self.acts.save_region = QAction('&Save', self)
        self.acts.save_region.setCheckable(True)
        self.acts.save_region.setShortcut('s')
        self.acts.save_region.toggled.connect(self.set_save)
        
        self.acts.ask_region = QAction('Re&quest', self)
        self.acts.ask_region.setCheckable(True)
        self.acts.ask_region.setShortcut('q')
        self.acts.ask_region.toggled.connect(self.set_ask)
        
        self.acts.zoom_rect_mode = QActionGroup(self)
        self.acts.zoom_rect_mode.addAction(self.acts.zoom_region)
        self.acts.zoom_rect_mode.addAction(self.acts.play_region)
        self.acts.zoom_rect_mode.addAction(self.acts.analyze_region)
        self.acts.zoom_rect_mode.addAction(self.acts.save_region)
        self.acts.zoom_rect_mode.addAction(self.acts.ask_region)
        self.acts.ask_region.setChecked(True)
        
        self.acts.analysis_results = QAction('Analysis results', self)
        #self.acts.analysis_results.setShortcut('Alt+A')
        self.acts.analysis_results.triggered.connect(lambda x: self.browser().analysis_results())

        self.acts.play_window = QAction('&Play window', self)
        self.acts.play_window.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.acts.play_window.setToolTip('Play window (Space)')
        self.acts.play_window.setShortcut(' ')
        self.acts.play_window.triggered.connect(lambda x=0: self.browser().play_scroll())

        self.acts.use_heterodyne = QAction('&Use heterodyne frequency', self)
        self.acts.use_heterodyne.setIconText('h')
        self.acts.use_heterodyne.setCheckable(True)
        self.acts.use_heterodyne.setChecked(False)
        self.acts.use_heterodyne.toggled.connect(lambda v: self.browser().set_audio(use_heterodyne=bool(v)))
        
        self.acts.cross_hair = QAction('&Cross hair', self)
        self.acts.cross_hair.setCheckable(True)
        self.acts.cross_hair.setChecked(False)
        self.acts.cross_hair.setShortcut('Ctrl+c')
        self.acts.cross_hair.toggled.connect(self.set_cross_hair)

        """
        self.acts.label_editor = QAction('&Label editor', self)
        self.acts.label_editor.setShortcut('Ctrl+L')
        self.acts.label_editor.triggered.connect(lambda x: self.browser().label_editor())
        
        self.acts.marker_table = QAction('&Marker table', self)
        self.acts.marker_table.setShortcut('Ctrl+M')
        self.acts.marker_table.triggered.connect(lambda x: self.browser().marker_table())
        """

        region_menu = menu.addMenu('&Region')
        region_menu.addAction(self.acts.rect_zoom)
        region_menu.addAction(self.acts.pan_zoom)
        region_menu.addSeparator()
        region_menu.addAction(self.acts.zoom_back)
        region_menu.addAction(self.acts.zoom_forward)
        region_menu.addAction(self.acts.zoom_home)
        region_menu.addSeparator()
        region_menu.addAction(self.acts.zoom_region)
        region_menu.addAction(self.acts.play_region)
        region_menu.addAction(self.acts.analyze_region)
        region_menu.addAction(self.acts.save_region)
        region_menu.addAction(self.acts.ask_region)
        region_menu.addSeparator()
        region_menu.addAction(self.acts.analysis_results)
        region_menu.addAction(self.acts.cross_hair)
        region_menu.addSeparator()
        region_menu.addAction(self.acts.play_window)
        region_menu.addAction(self.acts.use_heterodyne)
        #region_menu.addSeparator()
        #region_menu.addAction(self.acts.label_editor)
        #region_menu.addAction(self.acts.marker_table)

        self.data_menus.append(region_menu)
        
        return region_menu

        
    def toggle_link_timezoom(self):
        self.link_timezoom = not self.link_timezoom

        
    def toggle_link_timescroll(self):
        self.link_timescroll = not self.link_timescroll


    def set_enable_starttime(self, enable):
        for b in self.browsers:
            b.plot_ranges[Panel.times[0]].enable_starttime(enable)


    def apply_time_ranges(self, timefunc, link):
        self.browser().apply_time_ranges(timefunc)
        if link:
            for b in self.browsers:
                if not b is self.browser():
                    b.apply_time_ranges(timefunc)


    def setup_time_actions(self, menu):
        self.acts.link_time_zoom = QAction('Link time &zoom', self)
        self.acts.link_time_zoom.setShortcut('Alt+Z')
        self.acts.link_time_zoom.setCheckable(True)
        self.acts.link_time_zoom.setChecked(self.link_timezoom)
        self.acts.link_time_zoom.toggled.connect(self.toggle_link_timezoom)

        self.acts.toggle_start_time = QAction('Toggle &start time', self)
        self.acts.toggle_start_time.setCheckable(True)
        self.acts.toggle_start_time.setShortcut('Ctrl+Shift+T')
        self.acts.toggle_start_time.setChecked(True)
        self.acts.toggle_start_time.toggled.connect(self.set_enable_starttime)

        self.acts.time_zoom_in = QAction('Zoom &in', self)
        self.acts.time_zoom_in.setShortcuts([QKeySequence.ZoomIn, '+', '=', 'Shift+T'])
        self.acts.time_zoom_in.triggered.connect(lambda x: self.apply_time_ranges('zoom_in', self.link_timezoom))
        
        self.acts.time_zoom_out = QAction('Zoom &out', self)
        self.acts.time_zoom_out.setShortcuts([QKeySequence.ZoomOut, '-', 'T'])
        self.acts.time_zoom_out.triggered.connect(lambda x: self.apply_time_ranges('zoom_out', self.link_timezoom))
        
        self.acts.link_time_scroll = QAction('Link &time scroll', self)
        self.acts.link_time_scroll.setShortcut('Alt+T')
        self.acts.link_time_scroll.setCheckable(True)
        self.acts.link_time_scroll.setChecked(self.link_timescroll)
        self.acts.link_time_scroll.toggled.connect(self.toggle_link_timescroll)

        self.acts.time_down = QAction('Seek &forward', self)
        self.acts.time_down.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self.acts.time_down.setToolTip('Seek forward (Page down)')
        self.acts.time_down.setShortcuts(QKeySequence.MoveToNextPage)
        self.acts.time_down.triggered.connect(lambda x: self.apply_time_ranges('up', self.link_timescroll))

        self.acts.time_up = QAction('Seek &backward', self)
        self.acts.time_up.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self.acts.time_up.setToolTip('Seek backward (Page up)')
        self.acts.time_up.setShortcuts(QKeySequence.MoveToPreviousPage)
        self.acts.time_up.triggered.connect(lambda x: self.apply_time_ranges('down', self.link_timescroll))

        self.acts.time_small_down = QAction('Forward', self)
        self.acts.time_small_down.setShortcuts(QKeySequence.MoveToNextLine)
        self.acts.time_small_down.triggered.connect(lambda x: self.apply_time_ranges('small_up', self.link_timescroll))

        self.acts.time_small_up = QAction('Backward', self)
        self.acts.time_small_up.setShortcuts(QKeySequence.MoveToPreviousLine)
        self.acts.time_small_up.triggered.connect(lambda x: self.apply_time_ranges('small_down', self.link_timescroll))

        self.acts.time_end = QAction('&End', self)
        self.acts.time_end.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.acts.time_end.setToolTip('Skip to end of data (End)')
        self.acts.time_end.setShortcuts([QKeySequence.MoveToEndOfLine, QKeySequence.MoveToEndOfDocument])
        self.acts.time_end.triggered.connect(lambda x: self.apply_time_ranges('end', self.link_timescroll))

        self.acts.time_home = QAction('&Home', self)
        self.acts.time_home.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.acts.time_home.setToolTip('Skip to beginning of data (Home)')
        self.acts.time_home.setShortcuts([QKeySequence.MoveToStartOfLine, QKeySequence.MoveToStartOfDocument])
        self.acts.time_home.triggered.connect(lambda x: self.apply_time_ranges('home', self.link_timescroll))

        self.acts.time_snap = QAction('&Snap', self)
        self.acts.time_snap.setShortcut('.')
        self.acts.time_snap.triggered.connect(lambda x: self.apply_time_ranges('snap', self.link_timescroll))

        self.acts.auto_scroll = QAction('&Auto scroll', self)
        self.acts.auto_scroll.setShortcut('!')
        self.acts.auto_scroll.triggered.connect(lambda x=0: self.browser().auto_scroll())

        time_menu = menu.addMenu('Time')
        time_menu.addAction(self.acts.link_time_zoom)
        time_menu.addAction(self.acts.toggle_start_time)
        time_menu.addAction(self.acts.time_zoom_in)
        time_menu.addAction(self.acts.time_zoom_out)
        time_menu.addAction(self.acts.link_time_scroll)
        time_menu.addAction(self.acts.time_down)
        time_menu.addAction(self.acts.time_up)
        time_menu.addAction(self.acts.time_small_down)
        time_menu.addAction(self.acts.time_small_up)
        time_menu.addAction(self.acts.time_end)
        time_menu.addAction(self.acts.time_home)
        time_menu.addAction(self.acts.time_snap)
        time_menu.addAction(self.acts.auto_scroll)

        self.data_menus.append(time_menu)
        
        return time_menu


    def apply_ranges(self, amplitudefunc, axspec):
        if not axspec:
            return
        self.browser().apply_ranges(amplitudefunc, axspec)
        for s in axspec:
            if self.link_ranges[s]:
                for b in self.browsers:
                    if not b is self.browser():
                        b.apply_ranges(amplitudefunc, s)


    def dispatch_ranges(self, axspec, arange):
        for s in range(2):
            if axspec[s] in Panel.times:
                toffs = None
                if self.link_timescroll:
                    toffs = arange[s]
                twin = None
                if self.link_timezoom:
                    twin = arange[s][1] - arange[s][0]
                for b in self.browsers:
                    if not b is self.browser():
                        b.set_times(toffs, twin)
            elif self.link_ranges[axspec[s]]:
                for b in self.browsers:
                    if not b is self.browser():
                        b.set_ranges(axspec[s], *arange[s])                     

        
    def toggle_link_amplitude(self):
        for s in Panel.amplitudes:
            self.link_ranges[s] = not self.link_ranges[s]


    def auto_amplitude(self):
        self.browser().auto_ampl()
        for s in Panel.amplitudes:
            if self.link_ranges[s]:
                for b in self.browsers:
                    if not b is self.browser():
                        b.auto_ampl([s])

        
    def setup_amplitude_actions(self, menu):
        self.acts.link_amplitude = QAction('Link &amplitude', self)
        self.acts.link_amplitude.setShortcut('Alt+A')
        self.acts.link_amplitude.setCheckable(True)
        self.acts.link_amplitude.setChecked(self.link_ranges[Panel.amplitudes[0]])
        self.acts.link_amplitude.toggled.connect(self.toggle_link_amplitude)
        
        self.acts.zoom_xamplitude_in = QAction('Zoom &in', self)
        self.acts.zoom_xamplitude_in.setShortcut('Shift+X')
        self.acts.zoom_xamplitude_in.triggered.connect(lambda x: self.apply_ranges('zoom_in', Panel.amplitudes[0]))

        self.acts.zoom_xamplitude_out = QAction('Zoom &out', self)
        self.acts.zoom_xamplitude_out.setShortcut('X')
        self.acts.zoom_xamplitude_out.triggered.connect(lambda x: self.apply_ranges('zoom_out', Panel.amplitudes[0]))
        
        self.acts.zoom_yamplitude_in = QAction('Zoom y in', self)
        self.acts.zoom_yamplitude_in.setShortcut('Shift+Y')
        self.acts.zoom_yamplitude_in.triggered.connect(lambda x: self.apply_ranges('zoom_in', Panel.amplitudes[1]))

        self.acts.zoom_yamplitude_out = QAction('Zoom y out', self)
        self.acts.zoom_yamplitude_out.setShortcut('Y')
        self.acts.zoom_yamplitude_out.triggered.connect(lambda x: self.apply_ranges('zoom_out', Panel.amplitudes[1]))
        
        self.acts.zoom_uamplitude_in = QAction('Zoom u in', self)
        self.acts.zoom_uamplitude_in.setShortcut('Shift+U')
        self.acts.zoom_uamplitude_in.triggered.connect(lambda x: self.apply_ranges('zoom_in', Panel.amplitudes[2]))

        self.acts.zoom_uamplitude_out = QAction('Zoom u out', self)
        self.acts.zoom_uamplitude_out.setShortcut('U')
        self.acts.zoom_uamplitude_out.triggered.connect(lambda x: self.apply_ranges('zoom_out', Panel.amplitudes[2]))

        self.acts.auto_zoom_amplitude = QAction('&Auto scale', self)
        self.acts.auto_zoom_amplitude.setShortcut('v')
        self.acts.auto_zoom_amplitude.triggered.connect(self.auto_amplitude)

        self.acts.reset_amplitude = QAction('&Reset', self)
        self.acts.reset_amplitude.setShortcut('Shift+V')
        self.acts.reset_amplitude.triggered.connect(lambda x: self.apply_ranges('reset', Panel.amplitudes))

        self.acts.center_amplitude = QAction('&Center', self)
        self.acts.center_amplitude.setShortcut('C')
        self.acts.center_amplitude.triggered.connect(lambda x: self.apply_ranges('center', Panel.amplitudes))

        ampl_menu = menu.addMenu('&Amplitude')
        ampl_menu.addAction(self.acts.link_amplitude)
        ampl_menu.addAction(self.acts.zoom_xamplitude_in)
        ampl_menu.addAction(self.acts.zoom_xamplitude_out)
        ampl_menu.addAction(self.acts.zoom_yamplitude_in)
        ampl_menu.addAction(self.acts.zoom_yamplitude_out)
        ampl_menu.addAction(self.acts.zoom_uamplitude_in)
        ampl_menu.addAction(self.acts.zoom_uamplitude_out)
        ampl_menu.addAction(self.acts.auto_zoom_amplitude)
        ampl_menu.addAction(self.acts.reset_amplitude)
        ampl_menu.addAction(self.acts.center_amplitude)

        self.data_menus.append(ampl_menu)
        
        return ampl_menu

        
    def toggle_link_frequency(self):
        for s in Panel.frequencies:
            self.link_ranges[s] = not self.link_ranges[s]


    def setup_frequency_actions(self, menu):
        self.acts.link_frequency = QAction('Link &frequency', self)
        #self.acts.link_frequency.setShortcut('Alt+F')
        self.acts.link_frequency.setCheckable(True)
        self.acts.link_frequency.setChecked(self.link_ranges[Panel.frequencies[0]])
        self.acts.link_frequency.toggled.connect(self.toggle_link_frequency)
        
        self.acts.zoom_ffrequency_in = QAction('Zoom &in', self)
        self.acts.zoom_ffrequency_in.setShortcut('Shift+F')
        self.acts.zoom_ffrequency_in.triggered.connect(lambda x: self.apply_ranges('zoom_in', Panel.frequencies[0]))

        self.acts.zoom_ffrequency_out = QAction('Zoom &out', self)
        self.acts.zoom_ffrequency_out.setShortcut('F')
        self.acts.zoom_ffrequency_out.triggered.connect(lambda x: self.apply_ranges('zoom_out', Panel.frequencies[0]))
        
        self.acts.zoom_wfrequency_in = QAction('Zoom w &in', self)
        self.acts.zoom_wfrequency_in.setShortcut('Shift+W')
        self.acts.zoom_wfrequency_in.triggered.connect(lambda x: self.apply_ranges('zoom_in', Panel.frequencies[1]))

        self.acts.zoom_wfrequency_out = QAction('Zoom w &out', self)
        self.acts.zoom_wfrequency_out.setShortcut('W')
        self.acts.zoom_wfrequency_out.triggered.connect(lambda x: self.apply_ranges('zoom_out', Panel.frequencies[1]))

        self.acts.frequency_up = QAction('Move &up', self)
        self.acts.frequency_up.setShortcuts(QKeySequence.MoveToNextChar)
        self.acts.frequency_up.triggered.connect(lambda x: self.apply_ranges('up', Panel.frequencies[0]))

        self.acts.frequency_down = QAction('Move &down', self)
        self.acts.frequency_down.setShortcuts(QKeySequence.MoveToPreviousChar)
        self.acts.frequency_down.triggered.connect(lambda x: self.apply_ranges('down', Panel.frequencies[0]))

        self.acts.frequency_home = QAction('&Home', self)
        self.acts.frequency_home.setShortcuts(QKeySequence.MoveToPreviousWord)
        self.acts.frequency_home.triggered.connect(lambda x: self.apply_ranges('home', Panel.frequencies[0]))

        self.acts.frequency_end = QAction('&End', self)
        self.acts.frequency_end.setShortcuts(QKeySequence.MoveToNextWord)
        self.acts.frequency_end.triggered.connect(lambda x: self.apply_ranges('end', Panel.frequencies[0]))
        
        freq_menu = menu.addMenu('Frequenc&y')
        freq_menu.addAction(self.acts.link_frequency)
        freq_menu.addAction(self.acts.zoom_ffrequency_in)
        freq_menu.addAction(self.acts.zoom_ffrequency_out)
        freq_menu.addAction(self.acts.zoom_wfrequency_in)
        freq_menu.addAction(self.acts.zoom_wfrequency_out)
        freq_menu.addAction(self.acts.frequency_up)
        freq_menu.addAction(self.acts.frequency_down)
        freq_menu.addAction(self.acts.frequency_home)
        freq_menu.addAction(self.acts.frequency_end)

        self.data_menus.append(freq_menu)
        
        return freq_menu


    def set_spectrogram(self, spec):
        for b in self.browsers:
            b.set_spectrogram(False, spec)

        
    def dispatch_resolution(self):
        pass
        """
        TODO: should set nfft and hop for all spectrograms!!!
        if self.link_ranges[Panel.frequencies[0]]:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_resolution(self.browser().data.nfft,
                                     self.browser().data.hop_frac,
                                     False)
        """

        
    def dispatch_colormap(self):
        cm = self.browser().color_map
        for b in self.browsers:
            if not b is self.browser():
                b.set_color_map(cm, False)

        
    def toggle_link_power(self):
        for s in Panel.powers:
            self.link_ranges[s] = not self.link_ranges[s]


    def apply_power_ranges(self, amplitudefunc):
        self.apply_ranges(amplitudefunc, self.browser().spectrogram_power)

        
    def toggle_link_filter(self):
        self.link_filter = not self.link_filter

        
    def dispatch_filter(self):
        if self.link_filter and 'filtered' in self.browser().data:
            highpass_cutoff = self.browser().data['filtered'].highpass_cutoff
            lowpass_cutoff = self.browser().data['filtered'].lowpass_cutoff
            for b in self.browsers:
                if not b is self.browser():
                    bs = b.blockSignals(True)
                    b.update_filter(highpass_cutoff, lowpass_cutoff)
                    b.blockSignals(bs)


    def setup_spectrogram_actions(self, menu):
        self.acts.frequency_resolution_up = QAction('Increase &resolution', self)
        self.acts.frequency_resolution_up.setShortcut('Shift+R')
        self.acts.frequency_resolution_up.triggered.connect(lambda x: self.browser().freq_resolution_up())

        self.acts.frequency_resolution_down = QAction('De&crease resolution', self)
        self.acts.frequency_resolution_down.setShortcut('R')
        self.acts.frequency_resolution_down.triggered.connect(lambda x: self.browser().freq_resolution_down())

        self.acts.overlap_up = QAction('Increase overlap', self)
        self.acts.overlap_up.setShortcut('Shift+O')
        self.acts.overlap_up.triggered.connect(lambda x: self.browser().hop_frac_down())

        self.acts.overlap_down = QAction('Decrease &overlap', self)
        self.acts.overlap_down.setShortcut('O')
        self.acts.overlap_down.triggered.connect(lambda x: self.browser().hop_frac_up())
        
        self.acts.color_map_cycler = QAction('&Color map', self)
        self.acts.color_map_cycler.setShortcut('Shift+C')
        self.acts.color_map_cycler.triggered.connect(lambda x: self.browser().color_map_cycler())

        self.acts.link_power = QAction('Link &power', self)
        self.acts.link_power.setShortcut('Alt+P')
        self.acts.link_power.setCheckable(True)
        self.acts.link_power.setChecked(self.link_ranges[Panel.powers[0]])
        self.acts.link_power.toggled.connect(self.toggle_link_power)
        
        self.acts.power_up = QAction('Power &up', self)
        self.acts.power_up.setShortcut('Shift+D')
        self.acts.power_up.triggered.connect(lambda x: self.apply_power_ranges('step_up'))

        self.acts.power_down = QAction('Power &down', self)
        self.acts.power_down.setShortcut('D')
        self.acts.power_down.triggered.connect(lambda x: self.apply_power_ranges('step_down'))

        self.acts.max_power_up = QAction('Max up', self)
        self.acts.max_power_up.setShortcut('Shift+K')
        self.acts.max_power_up.triggered.connect(lambda x: self.apply_power_ranges('max_up'))

        self.acts.max_power_down = QAction('Max down', self)
        self.acts.max_power_down.setShortcut('K')
        self.acts.max_power_down.triggered.connect(lambda x: self.apply_power_ranges('max_down'))

        self.acts.min_power_up = QAction('Min up', self)
        self.acts.min_power_up.setShortcut('Shift+J')
        self.acts.min_power_up.triggered.connect(lambda x: self.apply_power_ranges('min_up'))

        self.acts.min_power_down = QAction('Min down', self)
        self.acts.min_power_down.setShortcut('J')
        self.acts.min_power_down.triggered.connect(lambda x: self.apply_power_ranges('min_down'))

        self.acts.link_filter = QAction('Link &filter', self)
        #self.acts.link_filter.setShortcut('Alt+F')
        self.acts.link_filter.setCheckable(True)
        self.acts.link_filter.setChecked(self.link_filter)
        self.acts.link_filter.toggled.connect(self.toggle_link_filter)

        self.acts.highpass_up = QAction('Increase &highpass cutoff', self)
        self.acts.highpass_up.setShortcut('Shift+H')
        self.acts.highpass_up.triggered.connect(lambda x: self.browser().hpfw.stepUp())

        self.acts.highpass_down = QAction('Decrease highpass cutoff', self)
        self.acts.highpass_down.setShortcut('H')
        self.acts.highpass_down.triggered.connect(lambda x: self.browser().hpfw.stepDown())

        self.acts.lowpass_up = QAction('Increase &lowpass cutoff', self)
        self.acts.lowpass_up.setShortcut('Shift+L')
        self.acts.lowpass_up.triggered.connect(lambda x: self.browser().lpfw.stepUp())

        self.acts.lowpass_down = QAction('Decrease lowpass cutoff', self)
        self.acts.lowpass_down.setShortcut('L')
        self.acts.lowpass_down.triggered.connect(lambda x: self.browser().lpfw.stepDown())
        
        spec_menu = menu.addMenu('&Spectrogram')
        self.spectrogram_group = QActionGroup(self)
        self.spectrogram_menu = spec_menu.addMenu('&Active')
        self.data_menus.append(self.spectrogram_menu)
        spec_menu.addAction(self.acts.frequency_resolution_up)
        spec_menu.addAction(self.acts.frequency_resolution_down)
        spec_menu.addAction(self.acts.overlap_up)
        spec_menu.addAction(self.acts.overlap_down)
        spec_menu.addAction(self.acts.color_map_cycler)
        spec_menu.addSeparator()
        spec_menu.addAction(self.acts.link_power)
        spec_menu.addAction(self.acts.power_up)
        spec_menu.addAction(self.acts.power_down)
        spec_menu.addAction(self.acts.max_power_up)
        spec_menu.addAction(self.acts.max_power_down)
        spec_menu.addAction(self.acts.min_power_up)
        spec_menu.addAction(self.acts.min_power_down)
        spec_menu.addSeparator()
        spec_menu.addAction(self.acts.link_filter)
        spec_menu.addAction(self.acts.highpass_up)
        spec_menu.addAction(self.acts.highpass_down)
        spec_menu.addAction(self.acts.lowpass_up)
        spec_menu.addAction(self.acts.lowpass_down)

        self.data_menus.append(spec_menu)
        
        return spec_menu

        
    def toggle_link_envelope(self):
        self.link_envelope = not self.link_envelope

        
    def toggle_show_envelope(self):
        self.browser().update_envelope(show_envelope=not self.browser().data.is_visible('envelope'))


    def dispatch_envelope(self):
        if self.link_envelope and 'envelope' in self.browser().data:
            envelope_cutoff = self.browser().data['envelope'].envelope_cutoff
            show_envelope = self.browser().data.is_visible('envelope')
            for b in self.browsers:
                if b is not self.browser():
                    b.update_envelope(envelope_cutoff=envelope_cutoff,
                                      show_envelope=show_envelope,
                                      dispatch=False)


    def setup_envelope_actions(self, menu):
        self.acts.link_envelope = QAction('Link &envelope', self)
        self.acts.link_envelope.setShortcut('Alt+E')
        self.acts.link_envelope.setCheckable(True)
        self.acts.link_envelope.setChecked(self.link_envelope)
        self.acts.link_envelope.toggled.connect(self.toggle_link_envelope)
        
        self.acts.show_envelope = QAction('&Show envelope', self)
        self.acts.show_envelope.setShortcut('Ctrl+E')
        self.acts.show_envelope.setCheckable(True)
        self.acts.show_envelope.setChecked(True)
        self.acts.show_envelope.toggled.connect(self.toggle_show_envelope)
        
        self.acts.envelope_up = QAction('Envelope cutoff &up', self)
        self.acts.envelope_up.setShortcut('Shift+E')
        self.acts.envelope_up.triggered.connect(lambda x: self.browser().envfw.stepUp())

        self.acts.envelope_down = QAction('Envelope cutoff &down', self)
        self.acts.envelope_down.setShortcut('E')
        self.acts.envelope_down.triggered.connect(lambda x: self.browser().envfw.stepDown())
        
        envelope_menu = menu.addMenu('&Envelope')
        envelope_menu.addAction(self.acts.link_envelope)
        envelope_menu.addAction(self.acts.show_envelope)
        envelope_menu.addAction(self.acts.envelope_up)
        envelope_menu.addAction(self.acts.envelope_down)

        self.data_menus.append(envelope_menu)
        
        return envelope_menu

    
    def toggle_link_channels(self):
        self.link_channels = not self.link_channels

        
    def toggle_channel(self, channel):
        self.browser().toggle_channel(channel)
        if self.link_channels and not self.browser().setting:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_channels(self.browser().show_channels,
                                   self.browser().selected_channels,
                                   self.browser().current_channel)

        
    def show_channel(self, channel):
        self.browser().show_channel(channel)
        if self.link_channels and not self.browser().setting:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_channels(self.browser().show_channels,
                                   self.browser().selected_channels,
                                   self.browser().current_channel)

        
    def select_channels(self, selectfunc):
        getattr(self.browser(), selectfunc)()
        if self.link_channels and not self.browser().setting:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_channels(self.browser().show_channels,
                                   self.browser().selected_channels,
                                   self.browser().current_channel)

        
    def hide_deselected_channels(self):
        self.browser().hide_deselected_channels()
        if self.link_channels and not self.browser().setting:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_channels(self.browser().show_channels,
                                   self.browser().selected_channels,
                                   self.browser().current_channel)


    def set_channel_action(self, c, n, checked=True, active=True):
        if c >= len(self.acts.channels):
            cact = QAction(f'Channel &{c}', self)
            cact.setIconText(f'{c}')
            cact.setCheckable(True)
            cact.setChecked(checked)
            cact.toggled.connect(lambda x, channel=c: self.toggle_channel(channel))
            if self.toggle_menu:
                self.toggle_menu.addAction(cact)
            self.acts.channels.append(cact)
            sact = QAction(f'Show channel {c}', self)
            sact.triggered.connect(lambda x, channel=c: self.show_channel(channel))
            setattr(self.acts, f'select_channel{c}', sact)
            if self.show_menu:
                self.show_menu.addAction(sact)
            self.acts.show_channels.append(sact)
        else:
            cact = self.acts.channels[c]
            sact = self.acts.show_channels[c]
        if active:
            cact.toggled.disconnect()
            cact.setChecked(checked)
            cact.toggled.connect(lambda x, channel=c: self.toggle_channel(channel))
            cact.setEnabled(c < n)
            cact.setVisible(c < n)
            sact.setEnabled(c < n)
            sact.setVisible(c < n)
            if c < n:
                if n < 10:
                    cact.setShortcut(f'{c}')
                    sact.setShortcut(f'Ctrl+{c}')
                elif n < 100:
                    cact.setShortcut(f'{c//10}, {c%10}')
                    sact.setShortcut(f'Ctrl+{c//10}, Ctrl+{c%10}')
                else:
                    nt = c//1000
                    rc = c - 1000*nt
                    cact.setShortcut(f'{nt}, {rc//10}, {rc%10}')
                    sact.setShortcut(f'Ctrl+{nt}, Ctrl+{rc//10}, Ctrl+{rc%10}')
                keys = ', '.join([key.toString() for key in cact.shortcuts()])
                cact.setToolTip(f'Toggle channel {c} ({keys})')


    def setup_channel_actions(self, menu):
        self.acts.link_channels = QAction('Link &channels', self)
        self.acts.link_channels.setShortcut('Alt+C')
        self.acts.link_channels.setCheckable(True)
        self.acts.link_channels.setChecked(self.link_channels)
        self.acts.link_channels.toggled.connect(self.toggle_link_channels)

        self.acts.channels = []
        self.acts.show_channels = []

        self.acts.select_all_channels = QAction('Select &all channels', self)
        self.acts.select_all_channels.setShortcuts(QKeySequence.SelectAll)
        self.acts.select_all_channels.triggered.connect(lambda x: self.select_channels('all_channels'))

        self.acts.next_channel = QAction('&Next channel', self)
        self.acts.next_channel.setShortcuts(QKeySequence.SelectNextLine)
        self.acts.next_channel.triggered.connect(lambda x: self.select_channels('next_channel'))

        self.acts.previous_channel = QAction('&Previous channel', self)
        self.acts.previous_channel.setShortcuts(QKeySequence.SelectPreviousLine)
        self.acts.previous_channel.triggered.connect(lambda x: self.select_channels('previous_channel'))

        self.acts.select_next_channel = QAction('Select next channel', self)
        self.acts.select_next_channel.setShortcuts(QKeySequence.SelectNextPage)
        self.acts.select_next_channel.triggered.connect(lambda x: self.select_channels('select_next_channel'))

        self.acts.select_previous_channel = QAction('Select previous channel', self)
        self.acts.select_previous_channel.setShortcuts(QKeySequence.SelectPreviousPage)
        self.acts.select_previous_channel.triggered.connect(lambda x: self.select_channels('select_previous_channel'))

        self.acts.hide_deselected_channels = QAction('Hide deselected channels', self)
        self.acts.hide_deselected_channels.setShortcuts(QKeySequence.Delete)
        self.acts.hide_deselected_channels.triggered.connect(self.hide_deselected_channels)

        channel_menu = menu.addMenu('&Channels')
        channel_menu.addAction(self.acts.link_channels)
        channel_menu.addAction(self.acts.select_all_channels)
        channel_menu.addAction(self.acts.next_channel)
        channel_menu.addAction(self.acts.previous_channel)
        channel_menu.addAction(self.acts.select_next_channel)
        channel_menu.addAction(self.acts.select_previous_channel)
        channel_menu.addAction(self.acts.hide_deselected_channels)
        self.toggle_menu = channel_menu.addMenu('&Toggle channels')
        for act in self.acts.channels:
            self.toggle_menu.addAction(act)
        self.show_menu = channel_menu.addMenu('&Show channels')
        for act in self.acts.show_channels:
            self.show_menu.addAction(act)

        self.data_menus.append(channel_menu)
        self.data_menus.append(self.toggle_menu)
        self.data_menus.append(self.show_menu)
        
        return channel_menu


    def dispatch_trace(self, browser, checked, name):
        for b in self.browsers:
            if b is not browser:
                b.set_trace(checked, name)
                
        
    def toggle_link_panels(self):
        self.link_panels = not self.link_panels

        
    def toggle_traces(self):
        self.browser().toggle_traces()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_powers,
                                 self.browser().show_cbars,
                                 self.browser().show_fulldata)

        
    def toggle_spectrograms(self):
        self.browser().toggle_spectrograms()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_powers,
                                 self.browser().show_cbars,
                                 self.browser().show_fulldata)

        
    def toggle_powers(self):
        self.browser().toggle_powers()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_powers,
                                 self.browser().show_cbars,
                                 self.browser().show_fulldata)

        
    def toggle_colorbars(self):
        self.browser().toggle_colorbars()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_powers,
                                 self.browser().show_cbars,
                                 self.browser().show_fulldata)

        
    def toggle_fulldata(self):
        self.browser().toggle_fulldata()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_powers,
                                 self.browser().show_cbars,
                                 self.browser().show_fulldata)

                    
    def setup_panel_actions(self, menu):
        self.acts.link_panels = QAction('Link &panels', self)
        #self.acts.link_panels.setShortcut('Alt+P')
        self.acts.link_panels.setCheckable(True)
        self.acts.link_panels.setChecked(self.link_panels)
        self.acts.link_panels.toggled.connect(self.toggle_link_panels)

        self.acts.toggle_traces = QAction('Toggle &traces', self)
        self.acts.toggle_traces.setShortcut('Ctrl+T')
        self.acts.toggle_traces.triggered.connect(self.toggle_traces)

        self.acts.toggle_spectrograms = QAction('Toggle &spectrograms', self)
        self.acts.toggle_spectrograms.setShortcut('Ctrl+S')
        self.acts.toggle_spectrograms.triggered.connect(self.toggle_spectrograms)
        
        self.acts.toggle_power = QAction('Toggle power', self)
        self.acts.toggle_power.setShortcut('Ctrl+P')
        self.acts.toggle_power.triggered.connect(self.toggle_powers)

        self.acts.toggle_cbars = QAction('Toggle color bars', self)
        self.acts.toggle_cbars.setShortcut('Ctrl+B')
        self.acts.toggle_cbars.triggered.connect(self.toggle_colorbars)

        self.acts.toggle_fulldata = QAction('Toggle full data', self)
        self.acts.toggle_fulldata.setShortcut('Ctrl+F')
        self.acts.toggle_fulldata.triggered.connect(self.toggle_fulldata)
            
        panel_menu = menu.addMenu('&Panels')
        panel_menu.addAction(self.acts.link_panels)
        panel_menu.addAction(self.acts.toggle_traces)
        panel_menu.addAction(self.acts.toggle_spectrograms)
        panel_menu.addAction(self.acts.toggle_power)
        panel_menu.addAction(self.acts.toggle_cbars)
        panel_menu.addAction(self.acts.toggle_fulldata)

        self.data_menus.append(panel_menu)
        
        return panel_menu


    def dispatch_audio(self, rate_fac, use_heterodyne, heterodyne_freq):
        if self.link_audio:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_audio(rate_fac, use_heterodyne, heterodyne_freq,
                                False)

    
    def next_tab(self):
        idx = self.tabs.currentIndex()
        if idx + 1 < self.tabs.count():
            self.tabs.setCurrentIndex(idx + 1)


    def previous_tab(self):
        idx = self.tabs.currentIndex()
        if idx > 0:
            self.tabs.setCurrentIndex(idx - 1)


    def setup_view_actions(self, menu):
        self.acts.toggle_grid = QAction('Toggle &grid', self)
        self.acts.toggle_grid.setShortcut('g')
        self.acts.toggle_grid.triggered.connect(lambda x: self.browser().toggle_grids())

        self.acts.next_file = QAction('Next tab', self)
        self.acts.next_file.setShortcut('Ctrl+PgDown')
        self.acts.next_file.triggered.connect(self.next_tab)

        self.acts.previous_file = QAction('Previous tab', self)
        self.acts.previous_file.setShortcut('Ctrl+PgUp')
        self.acts.previous_file.triggered.connect(self.previous_tab)

        self.acts.maximize_window = QAction('Toggle &maximize', self)
        self.acts.maximize_window.setShortcut('Ctrl+Shift+M')
        self.acts.maximize_window.triggered.connect(self.toggle_maximize)

        view_menu = menu.addMenu('&View')
        self.setup_time_actions(view_menu)
        self.setup_amplitude_actions(view_menu)
        self.setup_frequency_actions(view_menu)
        self.setup_envelope_actions(view_menu)
        self.setup_channel_actions(view_menu)
        self.setup_panel_actions(view_menu)
        self.traces_menu = view_menu.addMenu('&Traces')
        self.data_menus.append(self.traces_menu)
        view_menu.addAction(self.acts.toggle_grid)
        view_menu.addAction(self.acts.maximize_window)
        self.addAction(self.acts.next_file)
        self.addAction(self.acts.previous_file)

        self.data_menus.append(view_menu)
        
        return view_menu


    def setup_help_actions(self, menu):
        self.acts.key_shortcuts = QAction('&Key shortcuts', self)
        self.acts.key_shortcuts.setShortcut('Ctrl+K')
        self.acts.key_shortcuts.triggered.connect(self.shortcuts)
        
        self.acts.about = QAction('&About Audian', self)
        self.acts.about.triggered.connect(self.about)
        
        help_menu = menu.addMenu('&Help')
        help_menu.addAction(self.acts.key_shortcuts)
        help_menu.addAction(self.acts.about)
        return help_menu
        

    def adapt_menu(self, index):
        browser = self.tabs.widget(index)
        if isinstance(browser, DataBrowser) and not browser.data is None:
            for c in range(len(self.acts.channels)):
                checked = browser.show_channels is None or c in browser.show_channels
                self.set_channel_action(c, browser.data.channels,
                                        checked, True)
            self.traces_menu.clear()
            for act in browser.trace_acts:
                self.traces_menu.addAction(act)
            for act in self.spectrogram_group.actions():
                self.spectrogram_group.removeAction(act)
            self.spectrogram_menu.clear()
            for act in browser.spec_acts:
                self.spectrogram_menu.addAction(act)
                self.spectrogram_group.addAction(act)
            if len(browser.spec_acts) > 0:
                browser.spec_acts[0].setChecked(True)
            self.spectrogram_menu.menuAction().setVisible(len(browser.spec_acts) > 1)
            browser.update()

        
    def open_files(self):
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if f in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        path = '.' if self.startup_active else os.path.dirname(self.browser().data.file_path)
        if len(path) == 0:
            path = '.'
        file_paths = QFileDialog.getOpenFileNames(self, directory=path, filter=';;'.join(filters))[0]

        self.load_files(file_paths)
            
        # disable startup widget:
        if self.startup_active and self.tabs.count() > 1:
            self.tabs.removeTab(0)
            self.startup.setVisible(False)
            self.startup_active = False
            for menu in self.data_menus:
                menu.setEnabled(True)


    def load_files(self, file_paths):
        if len(self.browsers) > 0:
            self.prev_browser = self.browser()
        # prepare open files:
        first = True
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                continue
            browser = DataBrowser(file_path, self.load_kwargs, self.plugins,
                                  self.channels, self.audio, self.acts)
            self.tabs.addTab(browser, os.path.basename(file_path))
            self.browsers.append(browser)
            if first:
                self.tabs.setCurrentWidget(browser)
                first = False
        QTimer.singleShot(100, self.load_data)

            
    def load_data(self):
        for browser in self.browsers:
            if browser.data.data is None:
                browser.open(self, self.unwrap, self.unwrap_clip,
                             self.highpass_cutoff, self.lowpass_cutoff)
                if browser.data is None:
                    self.tabs.removeTab(self.tabs.indexOf(browser))
                    self.browsers.remove(browser)
                    QMessageBox.critical(self, 'Error', f'''
Can not open file <b>{browser.file_path}</b>!''')
                    break
                self.tabs.setTabText(self.tabs.indexOf(browser),
                                     os.path.basename(browser.data.file_path))
                for b in self.browsers:
                    if not b.data.data is None and \
                       b.data.channels != browser.data.channels:
                        self.link_channels = False
                        self.acts.link_channels.setChecked(self.link_channels)
                if browser is self.browser():
                    self.adapt_menu(self.tabs.currentIndex())
                browser.sigRangesChanged.connect(self.dispatch_ranges)
                browser.sigResolutionChanged.connect(self.dispatch_resolution)
                browser.sigColorMapChanged.connect(self.dispatch_colormap)
                browser.sigFilterChanged.connect(self.dispatch_filter)
                browser.sigEnvelopeChanged.connect(self.dispatch_envelope)
                browser.sigTraceChanged.connect(self.dispatch_trace)
                browser.sigAudioChanged.connect(self.dispatch_audio)
                browser.plot_ranges[Panel.times[0]].enable_starttime(self.acts.toggle_start_time.isChecked())
                pb = self.browser() if self.prev_browser is None else self.prev_browser
                if self.link_panels:
                    browser.set_panels(pb.show_traces, pb.show_specs,
                                       pb.show_powers, pb.show_cbars,
                                       pb.show_fulldata)
                else:
                    browser.set_panels()
                if self.link_channels:
                    browser.set_channels(pb.show_channels,
                                         pb.selected_channels,
                                         pb.current_channel)
                else:
                    browser.set_channels()
                QTimer.singleShot(100, self.load_data)
                break


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


    def shortcuts(self):
        self.keys = ['<h1>Audian key shortcuts</h1>']
        for menu in self.menus:
            self.menu_shortcuts(menu)
        dialog = QDialog(self)
        dialog.setWindowTitle('Audian Key Shortcuts')
        dvbox = QVBoxLayout(dialog)
        scrollarea = QScrollArea()
        dvbox.addWidget(scrollarea)
        widget = QWidget()
        mvbox = QVBoxLayout(widget)
        mvbox.addWidget(QLabel(self.keys[0]))
        for ks in self.keys[1:]:
            mvbox.addWidget(QLabel(ks), 1, Qt.AlignLeft)
        scrollarea.setWidget(widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(dialog.reject)
        dvbox.addWidget(buttons)
        dialog.setMinimumWidth(widget.width() + 70)
        dialog.show()


    def about(self):
        QMessageBox.about(self, 'About Audian', f'''
<b>Audian</b>, version {__version__}<br>(c) {__year__}''')

            
    def close(self, index=None):
        if self.tabs.count() > 0:
            if index is None:
                index = self.tabs.currentIndex()
            if not self.startup_active:
                self.browsers.remove(self.tabs.widget(index))
                self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.tabs.addTab(self.startup, 'Startup')
            self.startup.setVisible(True)
            self.startup_active = True
            for menu in self.data_menus:
                menu.setEnabled(False)

            
    def quit(self):
        QApplication.quit()


def audian_cli(cargs=[], plugins=None):
    # command line arguments:
    parser = argparse.ArgumentParser(description='Browse and analyze recordings of animal vocalizations..', epilog=f'version {__version__} by Jan Benda (2015-{__year__})')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-v', action='count', dest='verbose',
                        help='Print debug information')
    parser.add_argument('-c', dest='channels', default='',
                        type=str, metavar='CHANNELS',
                        help='Comma separated list of channels to be displayed (first channel is 0).')
    parser.add_argument('-f', dest='highpass_cutoff', type=float,
                        metavar='FREQ', default=None,
                        help='Cutoff frequency of highpass filter in Hz')
    parser.add_argument('-l', dest='lowpass_cutoff', type=float,
                        metavar='FREQ', default=None,
                        help='Cutoff frequency of lowpass filter in Hz')
    parser.add_argument('-i', dest='load_kwargs', default=[],
                        action='append', metavar='KWARGS',
                        help='key-word arguments for the data loader function')
    parser.add_argument('-u', dest='unwrap', default=0, type=float,
                        metavar='UNWRAP', const=1.5, nargs='?',
                        help='unwrap clipped data with threshold relative to maximum input range and divide by two using unwrap() from audioio package')
    parser.add_argument('-U', dest='unwrap_clip', default=0, type=float,
                        metavar='UNWRAP', const=1.5, nargs='?',
                        help='unwrap clipped data with threshold relative to maximum input range and clip using unwrap() from audioio package')
    parser.add_argument('files', nargs='*', default=[], type=str,
                        help='name of files with the time series data')
    args, qt_args = parser.parse_known_args(cargs)

    cs = [s.strip() for s in args.channels.split(',')]
    channels = []
    for c in cs:
        if len(c) == 0:
            continue
        css = [s.strip() for s in c.split('-')]
        if len(css) == 2:
            channels.extend(list(range(int(css[0]), int(css[1])+1)))
        else:
            channels.append(int(c))

    if args.unwrap_clip > 1e-3:
        args.unwrap = args.unwrap_clip
        args.unwrap_clip = True
    else:
        args.unwrap_clip = False

    # kwargs for data loader:
    load_kwargs = {}
    for s in args.load_kwargs:
        for kw in s.split(','):
            kws = kw.split(':')
            if len(kws) == 2:
                load_kwargs[kws[0].strip()] = kws[1].strip()
    
    app = QApplication(sys.argv[:1] + qt_args)
    main = Audian(args.files, load_kwargs, plugins, channels,
                  args.highpass_cutoff, args.lowpass_cutoff,
                  args.unwrap, args.unwrap_clip)
    main.show()
    app.exec_()


def main(cargs):
    plugins = Plugins()
    plugins.load_plugins()
    audian_cli(cargs, plugins)
    

def run():
    main(sys.argv[1:])

    
if __name__ == '__main__':
    run()

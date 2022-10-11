import os
import sys
import argparse
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QStyle, QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtWidgets import QAction, QActionGroup, QPushButton
from PyQt5.QtWidgets import QDialog, QFileDialog, QMessageBox
import pyqtgraph as pg
from audioio import available_formats, PlayAudio
from .version import __version__, __year__
from .databrowser import DataBrowser


class Audian(QMainWindow):
    def __init__(self, file_paths, channels):
        super().__init__()

        class acts: pass
        self.acts = acts

        self.browsers = []

        self.channels = channels
        self.audio = PlayAudio()

        self.link_timezoom = True
        self.link_timescroll = False
        self.link_amplitude = True
        self.link_frequency = True
        self.link_power = True
        self.link_channels = True
        self.link_panels = True

        # window:
        rec = QApplication.desktop().screenGeometry()
        height = rec.height()
        width = rec.width()
        self.resize(int(0.7*width), int(0.7*height))
        self.setWindowTitle(f'Audian {__version__}')
        self.tabs = QTabWidget(self)
        self.tabs.setDocumentMode(True)
        self.tabs.setMovable(True)
        self.tabs.setTabBarAutoHide(True)
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(lambda index: self.close(index))
        self.tabs.currentChanged.connect(self.adapt_menu)
        self.setCentralWidget(self.tabs)

        # actions:
        self.data_menus = []
        file_menu = self.setup_file_actions(self.menuBar())
        region_menu = self.setup_region_actions(self.menuBar())
        spec_menu = self.setup_spectrogram_actions(self.menuBar())
        view_menu = self.setup_view_actions(self.menuBar())
        help_menu = self.setup_help_actions(self.menuBar())
        self.keys = ['<h1>Audian key shortcuts</h1>']
        for menu in [file_menu, region_menu, spec_menu, view_menu, help_menu]:
            self.menu_shortcuts(menu)
        
        # default widget:
        self.setup_startup()
        self.startup_active = False
        
        # data:
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
            if not act.menu():
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
        self.acts.pan_zoom.setShortcut('Ctrl+P')
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
        
        self.acts.save_region = QAction('&Save', self)
        self.acts.save_region.setCheckable(True)
        self.acts.save_region.setShortcut('s')
        self.acts.save_region.toggled.connect(self.set_save)
        
        self.acts.ask_region = QAction('&Ask', self)
        self.acts.ask_region.setCheckable(True)
        self.acts.ask_region.setShortcut('a')
        self.acts.ask_region.toggled.connect(self.set_ask)
        
        self.acts.zoom_rect_mode = QActionGroup(self)
        self.acts.zoom_rect_mode.addAction(self.acts.zoom_region)
        self.acts.zoom_rect_mode.addAction(self.acts.play_region)
        self.acts.zoom_rect_mode.addAction(self.acts.save_region)
        self.acts.zoom_rect_mode.addAction(self.acts.ask_region)
        self.acts.ask_region.setChecked(True)
        
        self.acts.cross_hair = QAction('&Cross hair', self)
        self.acts.cross_hair.setCheckable(True)
        self.acts.cross_hair.setChecked(False)
        self.acts.cross_hair.setShortcut('Ctrl+c')
        self.acts.cross_hair.toggled.connect(self.set_cross_hair)
        
        self.acts.marker_table = QAction('&Marker table', self)
        self.acts.marker_table.setShortcut('M')
        self.acts.marker_table.triggered.connect(lambda x: self.browser().marker_table())

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
        region_menu.addAction(self.acts.save_region)
        region_menu.addAction(self.acts.ask_region)
        region_menu.addSeparator()
        region_menu.addAction(self.acts.cross_hair)
        region_menu.addAction(self.acts.marker_table)

        self.data_menus.append(region_menu)
        
        return region_menu

        
    def toggle_link_timezoom(self):
        self.link_timezoom = not self.link_timezoom

        
    def toggle_link_timescroll(self):
        self.link_timescroll = not self.link_timescroll


    def dispatch_times(self, toffset, twindow):
        if not self.link_timescroll:
            toffset = None
        if not self.link_timezoom:
            twindow = None
        for b in self.browsers:
            if not b is self.browser():
                b.set_times(toffset, twindow, False)


    def setup_time_actions(self, menu):
        self.acts.play_window = QAction('&Play window', self)
        self.acts.play_window.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.acts.play_window.setToolTip('Play window (space)')
        self.acts.play_window.setShortcut(' ')
        self.acts.play_window.triggered.connect(lambda x=0: self.browser().play_scroll())
        
        self.acts.link_time_zoom = QAction('Link time &zoom', self)
        self.acts.link_time_zoom.setShortcut('Alt+Z')
        self.acts.link_time_zoom.setCheckable(True)
        self.acts.link_time_zoom.setChecked(self.link_timezoom)
        self.acts.link_time_zoom.toggled.connect(self.toggle_link_timezoom)

        self.acts.zoom_time_in = QAction('Zoom &in', self)
        self.acts.zoom_time_in.setShortcuts([QKeySequence.ZoomIn, '+', '=', 'Shift+X'])
        self.acts.zoom_time_in.triggered.connect(lambda x: self.browser().zoom_time_in())
        
        self.acts.zoom_time_out = QAction('Zoom &out', self)
        self.acts.zoom_time_out.setShortcuts([QKeySequence.ZoomOut, '-', 'x'])
        self.acts.zoom_time_out.triggered.connect(lambda x: self.browser().zoom_time_out())
        
        self.acts.link_time_scroll = QAction('Link &time scroll', self)
        self.acts.link_time_scroll.setShortcut('Alt+T')
        self.acts.link_time_scroll.setCheckable(True)
        self.acts.link_time_scroll.setChecked(self.link_timescroll)
        self.acts.link_time_scroll.toggled.connect(self.toggle_link_timescroll)

        self.acts.seek_forward = QAction('Seek &forward', self)
        self.acts.seek_forward.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekForward))
        self.acts.seek_forward.setToolTip('Seek forward (Page down)')
        self.acts.seek_forward.setShortcuts(QKeySequence.MoveToNextPage)
        self.acts.seek_forward.triggered.connect(lambda x=0: self.browser().time_seek_forward())

        self.acts.seek_backward = QAction('Seek &backward', self)
        self.acts.seek_backward.setIcon(self.style().standardIcon(QStyle.SP_MediaSeekBackward))
        self.acts.seek_backward.setToolTip('Seek backward (Page up)')
        self.acts.seek_backward.setShortcuts(QKeySequence.MoveToPreviousPage)
        self.acts.seek_backward.triggered.connect(lambda x=0: self.browser().time_seek_backward())

        self.acts.time_forward = QAction('Forward', self)
        self.acts.time_forward.setShortcuts(QKeySequence.MoveToNextLine)
        self.acts.time_forward.triggered.connect(lambda x=0: self.browser().time_forward())

        self.acts.time_backward = QAction('Backward', self)
        self.acts.time_backward.setShortcuts(QKeySequence.MoveToPreviousLine)
        self.acts.time_backward.triggered.connect(lambda x=0: self.browser().time_backward())

        self.acts.skip_forward = QAction('&End', self)
        self.acts.skip_forward.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipForward))
        self.acts.skip_forward.setToolTip('Skip to end of data (End)')
        self.acts.skip_forward.setShortcuts([QKeySequence.MoveToEndOfLine, QKeySequence.MoveToEndOfDocument])
        self.acts.skip_forward.triggered.connect(lambda x=0: self.browser().time_end())

        self.acts.skip_backward = QAction('&Home', self)
        self.acts.skip_backward.setIcon(self.style().standardIcon(QStyle.SP_MediaSkipBackward))
        self.acts.skip_backward.setToolTip('Skip to beginning of data (Home)')
        self.acts.skip_backward.setShortcuts([QKeySequence.MoveToStartOfLine, QKeySequence.MoveToStartOfDocument])
        self.acts.skip_backward.triggered.connect(lambda x=0: self.browser().time_home())

        self.acts.snap_time = QAction('&Snap', self)
        self.acts.snap_time.setShortcut('.')
        self.acts.snap_time.triggered.connect(lambda x=0: self.browser().snap_time())

        self.acts.auto_scroll = QAction('&Auto scroll', self)
        self.acts.auto_scroll.setShortcut('!')
        self.acts.auto_scroll.triggered.connect(lambda x=0: self.browser().auto_scroll())

        time_menu = menu.addMenu('&Time')
        time_menu.addAction(self.acts.play_window)
        time_menu.addAction(self.acts.link_time_zoom)
        time_menu.addAction(self.acts.zoom_time_in)
        time_menu.addAction(self.acts.zoom_time_out)
        time_menu.addAction(self.acts.link_time_scroll)
        time_menu.addAction(self.acts.seek_forward)
        time_menu.addAction(self.acts.seek_backward)
        time_menu.addAction(self.acts.time_forward)
        time_menu.addAction(self.acts.time_backward)
        time_menu.addAction(self.acts.skip_forward)
        time_menu.addAction(self.acts.skip_backward)
        time_menu.addAction(self.acts.snap_time)
        time_menu.addAction(self.acts.auto_scroll)

        self.data_menus.append(time_menu)
        
        return time_menu

        
    def toggle_link_amplitude(self):
        self.link_amplitude = not self.link_amplitude


    def apply_amplitude(self, amplitudefunc):
        getattr(self.browser(), amplitudefunc)()
        if self.link_amplitude:
            for b in self.browsers:
                if not b is self.browser():
                    getattr(b, amplitudefunc)()


    def dispatch_amplitudes(self, ymin, ymax):
        if self.link_amplitude:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_amplitudes(ymin, ymax)

        
    def setup_amplitude_actions(self, menu):
        self.acts.link_amplitude = QAction('Link &amplitude', self)
        self.acts.link_amplitude.setShortcut('Alt+A')
        self.acts.link_amplitude.setCheckable(True)
        self.acts.link_amplitude.setChecked(self.link_amplitude)
        self.acts.link_amplitude.toggled.connect(self.toggle_link_amplitude)
        
        self.acts.zoom_amplitude_in = QAction('Zoom &in', self)
        self.acts.zoom_amplitude_in.setShortcut('Shift+Y')
        self.acts.zoom_amplitude_in.triggered.connect(lambda x: self.apply_amplitude('zoom_ampl_in'))

        self.acts.zoom_amplitude_out = QAction('Zoom &out', self)
        self.acts.zoom_amplitude_out.setShortcut('Y')
        self.acts.zoom_amplitude_out.triggered.connect(lambda x: self.apply_amplitude('zoom_ampl_out'))

        self.acts.auto_zoom_amplitude = QAction('&Auto scale', self)
        self.acts.auto_zoom_amplitude.setShortcut('v')
        self.acts.auto_zoom_amplitude.triggered.connect(lambda x: self.apply_amplitude('auto_ampl'))

        self.acts.reset_amplitude = QAction('&Reset', self)
        self.acts.reset_amplitude.setShortcut('Shift+V')
        self.acts.reset_amplitude.triggered.connect(lambda x: self.apply_amplitude('reset_ampl'))

        self.acts.center_amplitude = QAction('&Center', self)
        self.acts.center_amplitude.setShortcut('C')
        self.acts.center_amplitude.triggered.connect(lambda x: self.apply_amplitude('center_ampl'))

        ampl_menu = menu.addMenu('&Amplitude')
        ampl_menu.addAction(self.acts.link_amplitude)
        ampl_menu.addAction(self.acts.zoom_amplitude_in)
        ampl_menu.addAction(self.acts.zoom_amplitude_out)
        ampl_menu.addAction(self.acts.auto_zoom_amplitude)
        ampl_menu.addAction(self.acts.reset_amplitude)
        ampl_menu.addAction(self.acts.center_amplitude)

        self.data_menus.append(ampl_menu)
        
        return ampl_menu

        
    def toggle_link_frequency(self):
        self.link_frequency = not self.link_frequency


    def apply_frequencies(self, frequencyfunc):
        getattr(self.browser(), frequencyfunc)()
        if self.link_frequency:
            for b in self.browsers:
                if not b is self.browser():
                    getattr(b, frequencyfunc)()


    def dispatch_frequencies(self, f0, f1):
        if self.link_frequency:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_frequencies(f0, f1)


    def setup_frequency_actions(self, menu):
        self.acts.link_frequency = QAction('Link &frequency', self)
        #self.acts.link_frequency.setShortcut('Alt+F')
        self.acts.link_frequency.setCheckable(True)
        self.acts.link_frequency.setChecked(self.link_frequency)
        self.acts.link_frequency.toggled.connect(self.toggle_link_frequency)
        
        self.acts.zoom_frequency_in = QAction('Zoom &in', self)
        self.acts.zoom_frequency_in.setShortcut('Shift+F')
        self.acts.zoom_frequency_in.triggered.connect(lambda x: self.apply_frequencies('zoom_freq_in'))

        self.acts.zoom_frequency_out = QAction('Zoom &out', self)
        self.acts.zoom_frequency_out.setShortcut('F')
        self.acts.zoom_frequency_out.triggered.connect(lambda x: self.apply_frequencies('zoom_freq_out'))

        self.acts.frequency_up = QAction('Move &up', self)
        self.acts.frequency_up.setShortcuts(QKeySequence.MoveToNextChar)
        self.acts.frequency_up.triggered.connect(lambda x: self.apply_frequencies('freq_up'))

        self.acts.frequency_down = QAction('Move &down', self)
        self.acts.frequency_down.setShortcuts(QKeySequence.MoveToPreviousChar)
        self.acts.frequency_down.triggered.connect(lambda x: self.apply_frequencies('freq_down'))

        self.acts.frequency_home = QAction('&Home', self)
        self.acts.frequency_home.setShortcuts(QKeySequence.MoveToPreviousWord)
        self.acts.frequency_home.triggered.connect(lambda x: self.apply_frequencies('freq_home'))

        self.acts.frequency_end = QAction('&End', self)
        self.acts.frequency_end.setShortcuts(QKeySequence.MoveToNextWord)
        self.acts.frequency_end.triggered.connect(lambda x: self.apply_frequencies('freq_end'))
        
        freq_menu = menu.addMenu('Frequenc&y')
        freq_menu.addAction(self.acts.link_frequency)
        freq_menu.addAction(self.acts.zoom_frequency_in)
        freq_menu.addAction(self.acts.zoom_frequency_out)
        freq_menu.addAction(self.acts.frequency_up)
        freq_menu.addAction(self.acts.frequency_down)
        freq_menu.addAction(self.acts.frequency_home)
        freq_menu.addAction(self.acts.frequency_end)

        self.data_menus.append(freq_menu)
        
        return freq_menu

        
    def dispatch_resolution(self):
        if self.link_frequency:
            nfft = [s.nfft for s in self.browser().specs]
            sfrac = [s.step_frac for s in self.browser().specs]
            for b in self.browsers:
                if not b is self.browser():
                    b.set_resolution(nfft, sfrac, False)


    def setup_spectrogram_actions(self, menu):
        self.acts.frequency_resolution_up = QAction('Increase &resolution', self)
        self.acts.frequency_resolution_up.setShortcut('Shift+R')
        self.acts.frequency_resolution_up.triggered.connect(lambda x: self.browser().freq_resolution_up())

        self.acts.frequency_resolution_down = QAction('De&crease resolution', self)
        self.acts.frequency_resolution_down.setShortcut('R')
        self.acts.frequency_resolution_down.triggered.connect(lambda x: self.browser().freq_resolution_down())

        self.acts.overlap_up = QAction('Increase overlap', self)
        self.acts.overlap_up.setShortcut('Shift+O')
        self.acts.overlap_up.triggered.connect(lambda x: self.browser().step_frac_down())

        self.acts.overlap_down = QAction('Decrease &overlap', self)
        self.acts.overlap_down.setShortcut('O')
        self.acts.overlap_down.triggered.connect(lambda x: self.browser().step_frac_up())
        
        spec_menu = menu.addMenu('&Spectrogram')
        spec_menu.addAction(self.acts.frequency_resolution_up)
        spec_menu.addAction(self.acts.frequency_resolution_down)
        spec_menu.addAction(self.acts.overlap_up)
        spec_menu.addAction(self.acts.overlap_down)

        self.data_menus.append(spec_menu)
        
        return spec_menu

        
    def toggle_link_power(self):
        self.link_power = not self.link_power


    def dispatch_power(self):
        if self.link_power:
            zmin = [s.zmin for s in self.browser().specs]
            zmax = [s.zmax for s in self.browser().specs]
            for b in self.browsers:
                if not b is self.browser():
                    b.set_power(zmin, zmax, False)


    def setup_power_actions(self, menu):
        self.acts.link_power = QAction('Link &power', self)
        self.acts.link_power.setShortcut('Alt+P')
        self.acts.link_power.setCheckable(True)
        self.acts.link_power.setChecked(self.link_power)
        self.acts.link_power.toggled.connect(self.toggle_link_power)
        
        self.acts.power_up = QAction('Power &up', self)
        self.acts.power_up.setShortcut('Shift+D')
        self.acts.power_up.triggered.connect(lambda x: self.browser().power_up())

        self.acts.power_down = QAction('Power &down', self)
        self.acts.power_down.setShortcut('D')
        self.acts.power_down.triggered.connect(lambda x: self.browser().power_down())

        self.acts.max_power_up = QAction('Max up', self)
        self.acts.max_power_up.setShortcut('Shift+K')
        self.acts.max_power_up.triggered.connect(lambda x: self.browser().max_power_up())

        self.acts.max_power_down = QAction('Max down', self)
        self.acts.max_power_down.setShortcut('K')
        self.acts.max_power_down.triggered.connect(lambda x: self.browser().max_power_down())

        self.acts.min_power_up = QAction('Min up', self)
        self.acts.min_power_up.setShortcut('Shift+J')
        self.acts.min_power_up.triggered.connect(lambda x: self.browser().min_power_up())

        self.acts.min_power_down = QAction('Min down', self)
        self.acts.min_power_down.setShortcut('J')
        self.acts.min_power_down.triggered.connect(lambda x: self.browser().min_power_down())
        
        power_menu = menu.addMenu('&Power')
        power_menu.addAction(self.acts.link_power)
        power_menu.addAction(self.acts.power_up)
        power_menu.addAction(self.acts.power_down)
        power_menu.addAction(self.acts.max_power_up)
        power_menu.addAction(self.acts.max_power_down)
        power_menu.addAction(self.acts.min_power_up)
        power_menu.addAction(self.acts.min_power_down)

        self.data_menus.append(power_menu)
        
        return power_menu

        
    def toggle_link_channels(self):
        self.link_channels = not self.link_channels

        
    def toggle_channel(self, channel):
        self.browser().toggle_channel(channel)
        if self.link_channels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_channels(self.browser().show_channels,
                                   self.browser().selected_channels)

        
    def select_channels(self, selectfunc):
        getattr(self.browser(), selectfunc)()
        if self.link_channels:
            for b in self.browsers:
                if not b is self.browser():
                    b.select_channels(self.browser().selected_channels)

        
    def toggle_link_panels(self):
        self.link_panels = not self.link_panels

        
    def toggle_traces(self):
        self.browser().toggle_traces()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)

        
    def toggle_spectrograms(self):
        self.browser().toggle_spectrograms()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)

        
    def toggle_colorbars(self):
        self.browser().toggle_colorbars()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)

        
    def toggle_fulldata(self):
        self.browser().toggle_fulldata()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.browser():
                    b.set_fulldata(self.browser().show_fulldata)


    def next_tab(self):
        idx = self.tabs.currentIndex()
        if idx + 1 < self.tabs.count():
            self.tabs.setCurrentIndex(idx + 1)


    def previous_tab(self):
        idx = self.tabs.currentIndex()
        if idx > 0:
            self.tabs.setCurrentIndex(idx - 1)


    def setup_view_actions(self, menu):
        self.acts.link_channels = QAction('Link &channels', self)
        self.acts.link_channels.setShortcut('Alt+C')
        self.acts.link_channels.setCheckable(True)
        self.acts.link_channels.setChecked(self.link_channels)
        self.acts.link_channels.toggled.connect(self.toggle_link_channels)

        self.acts.channels = []
        for c in range(10):
            channel = QAction(f'Channel &{c}', self)
            channel.setToolTip(f'Toggle channel {c} ({c})')
            channel.setIconText(f'{c}')
            channel.setShortcut(f'{c}')
            channel.setCheckable(True)
            channel.setChecked(True)
            channel.toggled.connect(lambda x, channel=c: self.toggle_channel(channel))
            self.acts.channels.append(channel)

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

        self.acts.link_panels = QAction('Link &panels', self)
        self.acts.link_panels.setShortcut('Alt+P')
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
        self.acts.toggle_power.triggered.connect(self.toggle_colorbars)

        self.acts.toggle_fulldata = QAction('Toggle full data', self)
        self.acts.toggle_fulldata.setShortcut('Ctrl+F')
        self.acts.toggle_fulldata.triggered.connect(self.toggle_fulldata)
            
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
        self.acts.maximize_window.setShortcut('Ctrl+M')
        self.acts.maximize_window.triggered.connect(self.toggle_maximize)

        view_menu = menu.addMenu('&View')
        self.setup_time_actions(view_menu)
        self.setup_amplitude_actions(view_menu)
        self.setup_frequency_actions(view_menu)
        self.setup_power_actions(view_menu)
        view_menu.addAction(self.acts.link_channels)
        channel_menu = view_menu.addMenu('&Channels')
        for act in self.acts.channels:
            channel_menu.addAction(act)
        view_menu.addAction(self.acts.select_all_channels)
        view_menu.addAction(self.acts.next_channel)
        view_menu.addAction(self.acts.previous_channel)
        view_menu.addAction(self.acts.select_next_channel)
        view_menu.addAction(self.acts.select_previous_channel)
        view_menu.addAction(self.acts.link_panels)
        view_menu.addAction(self.acts.toggle_traces)
        view_menu.addAction(self.acts.toggle_spectrograms)
        view_menu.addAction(self.acts.toggle_power)
        view_menu.addAction(self.acts.toggle_fulldata)
        view_menu.addSeparator()
        view_menu.addAction(self.acts.toggle_grid)
        view_menu.addAction(self.acts.maximize_window)
        self.addAction(self.acts.next_file)
        self.addAction(self.acts.previous_file)

        self.data_menus.append(view_menu)
        
        return view_menu


    def setup_help_actions(self, menu):
        self.acts.key_shortcuts = QAction('&Key shortcuts', self)
        self.acts.key_shortcuts.setShortcut('H')
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
            for i, act in enumerate(self.acts.channels):
                act.setVisible(i < browser.data.channels)
            browser.update()

        
    def open_files(self):
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if 'WAV' in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        path = '.' if self.startup_active else os.path.dirname(self.browser().file_path)
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
        # prepare open files:
        show_channels = None
        if self.link_channels and len(self.browsers) > 0:
            show_channels = self.browser().show_channels
        first = True
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                continue
            browser = DataBrowser(file_path, self.channels,
                                  show_channels, self.audio,
                                  self.acts)
            self.tabs.addTab(browser, os.path.basename(file_path))
            self.browsers.append(browser)
            if first:
                self.tabs.setCurrentWidget(browser)
                first = False
        QTimer.singleShot(100, self.load_data)

            
    def load_data(self):
        for browser in self.browsers:
            if browser.data is None:
                browser.open()
                if browser.data is None:
                    self.tabs.removeTab(self.tabs.indexOf(browser))
                    self.browsers.remove(browser)
                    QMessageBox.critical(self, 'Error', f'''
Can not open file <b>{browser.file_path}</b>!''')
                    break
                if browser is self.browser():
                    self.adapt_menu(self.tabs.currentIndex())
                browser.sigTimesChanged.connect(self.dispatch_times)
                browser.sigAmplitudesChanged.connect(self.dispatch_amplitudes)
                browser.sigFrequenciesChanged.connect(self.dispatch_frequencies)
                browser.sigResolutionChanged.connect(self.dispatch_resolution)
                browser.sigPowerChanged.connect(self.dispatch_power)
                QTimer.singleShot(100, self.load_data)
                break


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


    def shortcuts(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Audian Key Shortcuts')
        vbox = QVBoxLayout(dialog)
        vbox.addWidget(QLabel(self.keys[0]))
        hbox = QHBoxLayout()
        hbox.setSpacing(4*self.fontMetrics().averageCharWidth())
        vbox.addLayout(hbox)
        n = 2
        for ks in self.keys[1:]:
            if n == 2:
                vbox = QVBoxLayout()
                hbox.addLayout(vbox)
                n = 0
            valign = Qt.AlignTop if n == 0 else Qt.AlignBottom
            vbox.addWidget(QLabel(ks), 1, Qt.AlignLeft | valign)
            n += 1
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()


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


def main(cargs):
    # config file name:
    cfgfile = __package__ + '.cfg'
    
    # command line arguments:
    parser = argparse.ArgumentParser(description='Browse and analyze recordings of animal vocalizations..', epilog=f'version {__version__} by Jan Benda (2015-{__year__})')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-v', action='count', dest='verbose',
                        help='Print debug information')
    parser.add_argument('--config', nargs='?', default='', const=cfgfile, type=str, metavar='CFGFILE',
                        help='Save configuration to file cfgfile (defaults to {0})'.format(cfgfile))
    parser.add_argument('-c', dest='channels', default='',
                        type=str, metavar='CHANNELS',
                        help='Comma separated list of channels to be displayed (first channel is 0).')
    parser.add_argument('-f', dest='high_pass', type=float, metavar='FREQ', default=None,
                        help='Cutoff frequency of highpass filter in Hz')
    parser.add_argument('-l', dest='low_pass', type=float, metavar='FREQ', default=None,
                        help='Cutoff frequency of lowpass filter in Hz')
    parser.add_argument('files', nargs='*', default=[], type=str, help='name of the file with the time series data')
    args, qt_args = parser.parse_known_args(cargs)

    cs = [s.strip() for s in args.channels.split(',')]
    channels = [int(c) for c in cs if len(c)>0]
    
    app = QApplication(sys.argv[:1] + qt_args)
    main = Audian(args.files, channels)
    main.show()
    app.exec_()


def run():
    main(sys.argv[1:])

    
if __name__ == '__main__':
    run()

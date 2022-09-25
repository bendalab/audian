import os
import sys
import argparse
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtWidgets import QAction, QPushButton
from PyQt5.QtWidgets import QDialog, QFileDialog
from audioio import available_formats, PlayAudio
from .version import __version__, __year__
from .databrowser import DataBrowser


class Audian(QMainWindow):
    def __init__(self, file_paths, channels):
        super().__init__()

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
        height = rec.height();
        width = rec.width();
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
        file_menu = self.setup_file_actions(self.menuBar())
        view_menu = self.setup_view_actions(self.menuBar())
        help_menu = self.setup_help_actions(self.menuBar())
        self.keys = ['<h1>Audian key shortcuts</h1>']
        for menu in [file_menu, view_menu, help_menu]:
            self.menu_shortcuts(menu)
        
        # default widget:
        self.setup_startup()
        self.startup_active = False
        
        # data:
        self.browsers = []
        self.load_files(file_paths)

        # init widgets to show:
        if len(self.browsers) > 0:
            self.tabs.setCurrentIndex(0)
            self.startup.setVisible(False)
            self.startup_active = False
            self.view_menu.setEnabled(True)
        else:
            self.startup.setVisible(True)
            self.startup_active = True
            self.tabs.addTab(self.startup, 'Startup')
            self.view_menu.setEnabled(False)


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
        open_act = QAction('&Open', self)
        open_act.setShortcuts(QKeySequence.Open)
        open_act.triggered.connect(self.open_files)

        close_act = QAction('&Close', self)
        close_act.setShortcuts([QKeySequence.Close, 'Q'])
        close_act.triggered.connect(lambda x: self.close(None))

        quit_act = QAction('&Quit', self)
        quit_act.setShortcuts(QKeySequence.Quit)
        quit_act.triggered.connect(self.quit)
        
        file_menu = menu.addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        file_menu.addAction(close_act)
        file_menu.addAction(quit_act)
        return file_menu

        
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
            if not b is self.tabs.currentWidget():
                b.set_times(toffset, twindow, False)


    def setup_time_actions(self, menu):
        play_act = QAction('&Play', self)
        play_act.setShortcut('P')
        play_act.triggered.connect(lambda x=0: self.browser().play_window())
        
        linktimezoom_act = QAction('Link time &zoom', self)
        linktimezoom_act.setShortcut('Alt+Z')
        linktimezoom_act.setCheckable(True)
        linktimezoom_act.setChecked(self.link_timezoom)
        linktimezoom_act.toggled.connect(self.toggle_link_timezoom)

        zoomxin_act = QAction('Zoom &in', self)
        zoomxin_act.setShortcuts([QKeySequence.ZoomIn, '+', '=', 'Shift+X'])
        zoomxin_act.triggered.connect(lambda x: self.browser().zoom_time_in())
        
        zoomxout_act = QAction('Zoom &out', self)
        zoomxout_act.setShortcuts([QKeySequence.ZoomOut, '-', 'x'])
        zoomxout_act.triggered.connect(lambda x: self.browser().zoom_time_out())
        
        linktimescroll_act = QAction('Link &time scroll', self)
        linktimescroll_act.setShortcut('Alt+T')
        linktimescroll_act.setCheckable(True)
        linktimescroll_act.setChecked(self.link_timescroll)
        linktimescroll_act.toggled.connect(self.toggle_link_timescroll)

        pagedown_act = QAction('Page &down', self)
        pagedown_act.setShortcuts(QKeySequence.MoveToNextPage)
        pagedown_act.triggered.connect(lambda x=0: self.browser().time_page_down())

        pageup_act = QAction('Page &up', self)
        pageup_act.setShortcuts(QKeySequence.MoveToPreviousPage)
        pageup_act.triggered.connect(lambda x=0: self.browser().time_page_up())

        datadown_act = QAction('Trace down', self)
        datadown_act.setShortcuts(QKeySequence.MoveToNextLine)
        datadown_act.triggered.connect(lambda x=0: self.browser().time_down())

        dataup_act = QAction('Trace up', self)
        dataup_act.setShortcuts(QKeySequence.MoveToPreviousLine)
        dataup_act.triggered.connect(lambda x=0: self.browser().time_up())

        dataend_act = QAction('&End', self)
        dataend_act.setShortcuts([QKeySequence.MoveToEndOfLine, QKeySequence.MoveToEndOfDocument])
        dataend_act.triggered.connect(lambda x=0: self.browser().time_end())

        datahome_act = QAction('&Home', self)
        datahome_act.setShortcuts([QKeySequence.MoveToStartOfLine, QKeySequence.MoveToStartOfDocument])
        datahome_act.triggered.connect(lambda x=0: self.browser().time_home())

        snaptime_act = QAction('&Snap', self)
        snaptime_act.setShortcut('.')
        snaptime_act.triggered.connect(lambda x=0: self.browser().snap_time())

        time_menu = menu.addMenu('&Time')
        time_menu.addAction(play_act)
        time_menu.addAction(linktimezoom_act)
        time_menu.addAction(zoomxin_act)
        time_menu.addAction(zoomxout_act)
        time_menu.addAction(linktimescroll_act)
        time_menu.addAction(pagedown_act)
        time_menu.addAction(pageup_act)
        time_menu.addAction(datadown_act)
        time_menu.addAction(dataup_act)
        time_menu.addAction(dataend_act)
        time_menu.addAction(datahome_act)
        time_menu.addAction(snaptime_act)
        return time_menu

        
    def toggle_link_amplitude(self):
        self.link_amplitude = not self.link_amplitude


    def apply_amplitude(self, amplitudefunc):
        getattr(self.browser(), amplitudefunc)()
        if self.link_amplitude:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    getattr(b, amplitudefunc)()


    def dispatch_amplitudes(self, ymin, ymax):
        if self.link_amplitude:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_amplitudes(ymin, ymax)

        
    def setup_amplitude_actions(self, menu):
        linkamplitude_act = QAction('Link &amplitude', self)
        linkamplitude_act.setShortcut('Alt+A')
        linkamplitude_act.setCheckable(True)
        linkamplitude_act.setChecked(self.link_amplitude)
        linkamplitude_act.toggled.connect(self.toggle_link_amplitude)
        
        zoomyin_act = QAction('Zoom &in', self)
        zoomyin_act.setShortcut('Shift+Y')
        zoomyin_act.triggered.connect(lambda x: self.apply_amplitude('zoom_ampl_in'))

        zoomyout_act = QAction('Zoom &out', self)
        zoomyout_act.setShortcut('Y')
        zoomyout_act.triggered.connect(lambda x: self.apply_amplitude('zoom_ampl_out'))

        autoy_act = QAction('&Auto scale', self)
        autoy_act.setShortcut('v')
        autoy_act.triggered.connect(lambda x: self.apply_amplitude('auto_ampl'))

        resety_act = QAction('&Reset', self)
        resety_act.setShortcut('Shift+V')
        resety_act.triggered.connect(lambda x: self.apply_amplitude('reset_ampl'))

        centery_act = QAction('&Center', self)
        centery_act.setShortcut('C')
        centery_act.triggered.connect(lambda x: self.apply_amplitude('center_ampl'))

        ampl_menu = menu.addMenu('&Amplitude')
        ampl_menu.addAction(linkamplitude_act)
        ampl_menu.addAction(zoomyin_act)
        ampl_menu.addAction(zoomyout_act)
        ampl_menu.addAction(autoy_act)
        ampl_menu.addAction(resety_act)
        ampl_menu.addAction(centery_act)
        return ampl_menu

        
    def toggle_link_frequency(self):
        self.link_frequency = not self.link_frequency


    def dispatch_frequencies(self, f0, f1):
        if self.link_frequency:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_frequencies(f0, f1, False)

        
    def dispatch_resolution(self, nfft, fresolution, step_frac):
        if self.link_frequency:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_resolution(nfft, fresolution, step_frac, False)


    def setup_frequency_actions(self, menu):
        linkfrequency_act = QAction('Link &frequency', self)
        #linkfrequency_act.setShortcut('Alt+F')
        linkfrequency_act.setCheckable(True)
        linkfrequency_act.setChecked(self.link_frequency)
        linkfrequency_act.toggled.connect(self.toggle_link_frequency)
        
        zoomfin_act = QAction('Zoom &in', self)
        zoomfin_act.setShortcut('Shift+F')
        zoomfin_act.triggered.connect(lambda x: self.browser().zoom_freq_in())

        zoomfout_act = QAction('Zoom &out', self)
        zoomfout_act.setShortcut('F')
        zoomfout_act.triggered.connect(lambda x: self.browser().zoom_freq_out())

        frequp_act = QAction('Move &up', self)
        frequp_act.setShortcuts(QKeySequence.MoveToNextChar)
        frequp_act.triggered.connect(lambda x: self.browser().freq_up())

        freqdown_act = QAction('Move &down', self)
        freqdown_act.setShortcuts(QKeySequence.MoveToPreviousChar)
        freqdown_act.triggered.connect(lambda x: self.browser().freq_down())

        freqhome_act = QAction('&Home', self)
        freqhome_act.setShortcuts(QKeySequence.MoveToPreviousWord)
        freqhome_act.triggered.connect(lambda x: self.browser().freq_home())

        freqend_act = QAction('&End', self)
        freqend_act.setShortcuts(QKeySequence.MoveToNextWord)
        freqend_act.triggered.connect(lambda x: self.browser().freq_end())

        fresup_act = QAction('Increase &resolution', self)
        fresup_act.setShortcut('Shift+R')
        fresup_act.triggered.connect(lambda x: self.browser().freq_resolution_up())

        fresdown_act = QAction('De&crease resolution', self)
        fresdown_act.setShortcut('R')
        fresdown_act.triggered.connect(lambda x: self.browser().freq_resolution_down())

        stepdown_act = QAction('Increase overlap', self)
        stepdown_act.setShortcut('Shift+O')
        stepdown_act.triggered.connect(lambda x: self.browser().step_frac_down())

        stepup_act = QAction('Decrease &overlap', self)
        stepup_act.setShortcut('O')
        stepup_act.triggered.connect(lambda x: self.browser().step_frac_up())
        
        freq_menu = menu.addMenu('Frequenc&y')
        freq_menu.addAction(linkfrequency_act)
        freq_menu.addAction(zoomfin_act)
        freq_menu.addAction(zoomfout_act)
        freq_menu.addAction(frequp_act)
        freq_menu.addAction(freqdown_act)
        freq_menu.addAction(freqhome_act)
        freq_menu.addAction(freqend_act)
        freq_menu.addAction(fresup_act)
        freq_menu.addAction(fresdown_act)
        freq_menu.addAction(stepdown_act)
        freq_menu.addAction(stepup_act)
        return freq_menu

        
    def toggle_link_power(self):
        self.link_power = not self.link_power


    def dispatch_power(self):
        if self.link_power:
            zmin = [s.zmin for s in self.browser().specs]
            zmax = [s.zmax for s in self.browser().specs]
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_power(zmin, zmax, False)


    def setup_power_actions(self, menu):
        linkpower_act = QAction('Link &power', self)
        linkpower_act.setShortcut('Alt+P')
        linkpower_act.setCheckable(True)
        linkpower_act.setChecked(self.link_power)
        linkpower_act.toggled.connect(self.toggle_link_power)
        
        powerup_act = QAction('Power &up', self)
        powerup_act.setShortcut('Shift+Z')
        powerup_act.triggered.connect(lambda x: self.browser().power_up())

        powerdown_act = QAction('Power &down', self)
        powerdown_act.setShortcut('Z')
        powerdown_act.triggered.connect(lambda x: self.browser().power_down())

        maxpowerup_act = QAction('Max up', self)
        maxpowerup_act.setShortcut('Shift+K')
        maxpowerup_act.triggered.connect(lambda x: self.browser().max_power_up())

        maxpowerdown_act = QAction('Max down', self)
        maxpowerdown_act.setShortcut('K')
        maxpowerdown_act.triggered.connect(lambda x: self.browser().max_power_down())

        minpowerup_act = QAction('Min up', self)
        minpowerup_act.setShortcut('Shift+J')
        minpowerup_act.triggered.connect(lambda x: self.browser().min_power_up())

        minpowerdown_act = QAction('Min down', self)
        minpowerdown_act.setShortcut('J')
        minpowerdown_act.triggered.connect(lambda x: self.browser().min_power_down())
        
        power_menu = menu.addMenu('&Power')
        power_menu.addAction(linkpower_act)
        power_menu.addAction(powerup_act)
        power_menu.addAction(powerdown_act)
        power_menu.addAction(maxpowerup_act)
        power_menu.addAction(maxpowerdown_act)
        power_menu.addAction(minpowerup_act)
        power_menu.addAction(minpowerdown_act)
        return power_menu

        
    def toggle_link_channels(self):
        self.link_channels = not self.link_channels

        
    def toggle_channel(self, channel):
        self.browser().toggle_channel(channel)
        if self.link_channels:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_channels(self.browser().show_channels)

        
    def select_channels(self, selectfunc):
        getattr(self.browser(), selectfunc)()
        if self.link_channels:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.select_channels(self.browser().selected_channels)

        
    def toggle_link_panels(self):
        self.link_panels = not self.link_panels

        
    def toggle_traces(self):
        self.browser().toggle_traces()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)

        
    def toggle_spectrograms(self):
        self.browser().toggle_spectrograms()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)

        
    def toggle_colorbars(self):
        self.browser().toggle_colorbars()
        if self.link_panels:
            for b in self.browsers:
                if not b is self.tabs.currentWidget():
                    b.set_panels(self.browser().show_traces,
                                 self.browser().show_specs,
                                 self.browser().show_cbars)


    def next_tab(self):
        idx = self.tabs.currentIndex()
        if idx + 1 < self.tabs.count():
            self.tabs.setCurrentIndex(idx + 1)


    def previous_tab(self):
        idx = self.tabs.currentIndex()
        if idx > 0:
            self.tabs.setCurrentIndex(idx - 1)


    def setup_view_actions(self, menu):
        linkchannels_act = QAction('Link &channels', self)
        linkchannels_act.setShortcut('Alt+C')
        linkchannels_act.setCheckable(True)
        linkchannels_act.setChecked(self.link_channels)
        linkchannels_act.toggled.connect(self.toggle_link_channels)

        self.toggle_channel_acts = []
        for c in range(10):
            togglechannel_act = QAction(f'Toggle channel &{c}', self)
            togglechannel_act.setShortcut(f'{c}')
            togglechannel_act.triggered.connect(lambda x, channel=c: self.toggle_channel(channel))
            self.toggle_channel_acts.append(togglechannel_act)

        allchannel_act = QAction('Select &all channels', self)
        allchannel_act.setShortcuts(QKeySequence.SelectAll)
        allchannel_act.triggered.connect(lambda x: self.select_channels('all_channels'))

        nextchannel_act = QAction('&Next channel', self)
        nextchannel_act.setShortcuts(QKeySequence.SelectNextLine)
        nextchannel_act.triggered.connect(lambda x: self.select_channels('next_channel'))

        previouschannel_act = QAction('&Previous channel', self)
        previouschannel_act.setShortcuts(QKeySequence.SelectPreviousLine)
        previouschannel_act.triggered.connect(lambda x: self.select_channels('previous_channel'))

        selectnextchannel_act = QAction('Select next channel', self)
        selectnextchannel_act.setShortcuts(QKeySequence.SelectNextPage)
        selectnextchannel_act.triggered.connect(lambda x: self.select_channels('select_next_channel'))

        selectpreviouschannel_act = QAction('Select previous channel', self)
        selectpreviouschannel_act.setShortcuts(QKeySequence.SelectPreviousPage)
        selectpreviouschannel_act.triggered.connect(lambda x: self.select_channels('select_previous_channel'))

        linkpanels_act = QAction('Link &panels', self)
        linkpanels_act.setShortcut('Alt+P')
        linkpanels_act.setCheckable(True)
        linkpanels_act.setChecked(self.link_panels)
        linkpanels_act.toggled.connect(self.toggle_link_panels)

        toggletraces_act = QAction('Toggle &traces', self)
        toggletraces_act.setShortcut('Ctrl+T')
        toggletraces_act.triggered.connect(self.toggle_traces)

        togglespectros_act = QAction('Toggle &spectrograms', self)
        togglespectros_act.setShortcut('Ctrl+S')
        togglespectros_act.triggered.connect(self.toggle_spectrograms)

        togglecbars_act = QAction('Toggle color bars', self)
        togglecbars_act.setShortcut('Ctrl+C')
        togglecbars_act.triggered.connect(self.toggle_colorbars)
            
        grid_act = QAction('Toggle &grid', self)
        grid_act.setShortcut('g')
        grid_act.triggered.connect(lambda x: self.browser().toggle_grids())

        mouse_act = QAction('Toggle &zoom mode', self)
        mouse_act.setShortcut('Ctrl+z')
        mouse_act.triggered.connect(lambda x: self.browser().toggle_zoom_mode())

        nexttab_act = QAction('Next tab', self)
        nexttab_act.setShortcut('Ctrl+PgDown')
        nexttab_act.triggered.connect(self.next_tab)

        previoustab_act = QAction('Previous tab', self)
        previoustab_act.setShortcut('Ctrl+PgUp')
        previoustab_act.triggered.connect(self.previous_tab)

        maximize_act = QAction('Toggle &maximize', self)
        maximize_act.setShortcut('Ctrl+M')
        maximize_act.triggered.connect(self.toggle_maximize)

        self.view_menu = menu.addMenu('&View')
        self.setup_time_actions(self.view_menu)
        self.setup_amplitude_actions(self.view_menu)
        self.setup_frequency_actions(self.view_menu)
        self.setup_power_actions(self.view_menu)
        self.view_menu.addAction(linkchannels_act)
        channel_menu = self.view_menu.addMenu('&Channels')
        for act in self.toggle_channel_acts:
            channel_menu.addAction(act)
        self.view_menu.addAction(allchannel_act)
        self.view_menu.addAction(nextchannel_act)
        self.view_menu.addAction(previouschannel_act)
        self.view_menu.addAction(selectnextchannel_act)
        self.view_menu.addAction(selectpreviouschannel_act)
        self.view_menu.addAction(linkpanels_act)
        self.view_menu.addAction(toggletraces_act)
        self.view_menu.addAction(togglespectros_act)
        self.view_menu.addAction(togglecbars_act)
        self.view_menu.addSeparator()
        self.view_menu.addAction(mouse_act)
        self.view_menu.addAction(grid_act)
        self.view_menu.addAction(maximize_act)
        self.addAction(nexttab_act)
        self.addAction(previoustab_act)
        return self.view_menu


    def setup_help_actions(self, menu):
        shortcuts_act = QAction('&Key shortcuts', self)
        shortcuts_act.triggered.connect(self.shortcuts)
        
        about_act = QAction('&About Audian', self)
        about_act.triggered.connect(self.about)
        
        help_menu = menu.addMenu('&Help')
        help_menu.addAction(shortcuts_act)
        help_menu.addAction(about_act)
        return help_menu
        

    def adapt_menu(self, index):
        browser = self.tabs.widget(index)
        if isinstance(browser, DataBrowser) and not browser.data is None:
            for i, act in enumerate(self.toggle_channel_acts):
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
            self.view_menu.setEnabled(True)


    def load_files(self, file_paths):
        # prepare open files:
        show_channels = None
        if self.link_channels and len(self.browsers) > 0:
            show_channels = self.browser().show_channels
        first = True
        for file_path in file_paths:
            browser = DataBrowser(file_path, self.channels,
                                  show_channels, self.audio)
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
                if self.tabs.currentWidget() is browser:
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
            self.browsers.remove(self.tabs.widget(index))
            self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.tabs.addTab(self.startup, 'Startup')
            self.startup.setVisible(True)
            self.startup_active = True
            self.view_menu.setEnabled(False)

            
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

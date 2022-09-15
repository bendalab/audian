import os
import sys
import argparse
from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel
from PyQt5.QtWidgets import QAction, QPushButton, QFileDialog
from PyQt5.QtGui import QKeySequence
from audioio import available_formats, PlayAudio
from .version import __version__, __year__
from .databrowser import DataBrowser


class Audian(QMainWindow):
    def __init__(self, file_paths, channels):
        super().__init__()

        self.channels = channels
        self.audio = PlayAudio()

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
        self.setup_file_actions(self.menuBar())
        self.setup_view_actions(self.menuBar())
        
        # default widget:
        self.setup_startup()

        # data:
        for file_path in file_paths:
            browser = DataBrowser(file_path, self.channels, self.audio)
            self.tabs.addTab(browser, os.path.basename(file_path))
        if self.tabs.count() > 0:
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

        
    def setup_file_actions(self, menu):
        open_act = QAction('&Open', self)
        open_act.setShortcuts(QKeySequence.Open)
        open_act.triggered.connect(self.open_files)

        close_act = QAction('&Close', self)
        close_act.setShortcut(QKeySequence.Close)
        close_act.triggered.connect(lambda x: self.close(None))

        quit_act = QAction('&Quit', self)
        quit_act.setShortcuts(QKeySequence.Quit)
        quit_act.triggered.connect(self.quit)
        
        file_menu = menu.addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        file_menu.addAction(close_act)
        file_menu.addAction(quit_act)


    def setup_time_actions(self, menu):
        play_act = QAction('&Play', self)
        play_act.setShortcut('P')
        play_act.triggered.connect(lambda x=0: self.browser().play_segment())
        
        zoomxin_act = QAction('Zoom &in', self)
        zoomxin_act.setShortcuts(['+', '=', 'Shift+X']) # + QKeySequence.ZoomIn
        zoomxin_act.triggered.connect(lambda x=0: self.browser().zoom_time_in())
        
        zoomxout_act = QAction('Zoom &out', self)
        zoomxout_act.setShortcuts(['-', 'x']) # + QKeySequence.ZoomOut
        zoomxout_act.triggered.connect(lambda x=0: self.browser().zoom_time_out())

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

        time_menu = menu.addMenu('&Time')
        time_menu.addAction(play_act)
        time_menu.addAction(zoomxin_act)
        time_menu.addAction(zoomxout_act)
        time_menu.addAction(pagedown_act)
        time_menu.addAction(pageup_act)
        time_menu.addAction(datadown_act)
        time_menu.addAction(dataup_act)
        time_menu.addAction(dataend_act)
        time_menu.addAction(datahome_act)

        
    def setup_amplitude_actions(self, menu):
        zoomyin_act = QAction('Zoom &in', self)
        zoomyin_act.setShortcut('Shift+Y')
        zoomyin_act.triggered.connect(lambda x=0: self.browser().zoom_ampl_in())

        zoomyout_act = QAction('Zoom &out', self)
        zoomyout_act.setShortcut('Y')
        zoomyout_act.triggered.connect(lambda x=0: self.browser().zoom_ampl_out())

        autoy_act = QAction('&Auto scale', self)
        autoy_act.setShortcut('v')
        autoy_act.triggered.connect(lambda x=0: self.browser().auto_ampl())

        resety_act = QAction('&Reset', self)
        resety_act.setShortcut('Shift+V')
        resety_act.triggered.connect(lambda x=0: self.browser().reset_ampl())

        centery_act = QAction('&Center', self)
        centery_act.setShortcut('C')
        centery_act.triggered.connect(lambda x=0: self.browser().center_ampl())

        ampl_menu = menu.addMenu('&Amplitude')
        ampl_menu.addAction(zoomyin_act)
        ampl_menu.addAction(zoomyout_act)
        ampl_menu.addAction(autoy_act)
        ampl_menu.addAction(resety_act)
        ampl_menu.addAction(centery_act)


    def setup_frequency_actions(self, menu):
        zoomfin_act = QAction('Zoom &in', self)
        zoomfin_act.setShortcut('Shift+F')
        zoomfin_act.triggered.connect(lambda x=0: self.browser().zoom_freq_in())

        zoomfout_act = QAction('Zoom &out', self)
        zoomfout_act.setShortcut('F')
        zoomfout_act.triggered.connect(lambda x=0: self.browser().zoom_freq_out())

        frequp_act = QAction('Move &up', self)
        frequp_act.setShortcuts(QKeySequence.MoveToNextChar)
        frequp_act.triggered.connect(lambda x=0: self.browser().freq_up())

        freqdown_act = QAction('Move &down', self)
        freqdown_act.setShortcuts(QKeySequence.MoveToPreviousChar)
        freqdown_act.triggered.connect(lambda x=0: self.browser().freq_down())

        freqhome_act = QAction('&Home', self)
        freqhome_act.setShortcuts(QKeySequence.MoveToPreviousWord)
        freqhome_act.triggered.connect(lambda x=0: self.browser().freq_home())

        freqend_act = QAction('&End', self)
        freqend_act.setShortcuts(QKeySequence.MoveToNextWord)
        freqend_act.triggered.connect(lambda x=0: self.browser().freq_end())

        fresup_act = QAction('Increase &resolution', self)
        fresup_act.setShortcut('Shift+R')
        fresup_act.triggered.connect(lambda x=0: self.browser().freq_resolution_up())

        fresdown_act = QAction('De&crease resolution', self)
        fresdown_act.setShortcut('R')
        fresdown_act.triggered.connect(lambda x=0: self.browser().freq_resolution_down())
        
        freq_menu = menu.addMenu('Frequenc&y')
        freq_menu.addAction(zoomfin_act)
        freq_menu.addAction(zoomfout_act)
        freq_menu.addAction(frequp_act)
        freq_menu.addAction(freqdown_act)
        freq_menu.addAction(freqhome_act)
        freq_menu.addAction(freqend_act)
        freq_menu.addAction(fresup_act)
        freq_menu.addAction(fresdown_act)


    def setup_power_actions(self, menu):
        powerup_act = QAction('Power &up', self)
        powerup_act.setShortcut('Shift+Z')
        powerup_act.triggered.connect(lambda x=0: self.browser().power_up())

        powerdown_act = QAction('Power &down', self)
        powerdown_act.setShortcut('Z')
        powerdown_act.triggered.connect(lambda x=0: self.browser().power_down())

        maxpowerup_act = QAction('Max up', self)
        maxpowerup_act.setShortcut('Shift+K')
        maxpowerup_act.triggered.connect(lambda x=0: self.browser().max_power_up())

        maxpowerdown_act = QAction('Max down', self)
        maxpowerdown_act.setShortcut('K')
        maxpowerdown_act.triggered.connect(lambda x=0: self.browser().max_power_down())

        minpowerup_act = QAction('Min up', self)
        minpowerup_act.setShortcut('Shift+J')
        minpowerup_act.triggered.connect(lambda x=0: self.browser().min_power_up())

        minpowerdown_act = QAction('Min down', self)
        minpowerdown_act.setShortcut('J')
        minpowerdown_act.triggered.connect(lambda x=0: self.browser().min_power_down())
        
        power_menu = menu.addMenu('&Power')
        power_menu.addAction(powerup_act)
        power_menu.addAction(powerdown_act)
        power_menu.addAction(maxpowerup_act)
        power_menu.addAction(maxpowerdown_act)
        power_menu.addAction(minpowerup_act)
        power_menu.addAction(minpowerdown_act)


    def setup_view_actions(self, menu):
        toggletraces_act = QAction('Toggle &traces', self)
        toggletraces_act.setShortcut('Ctrl+T')
        toggletraces_act.triggered.connect(lambda x=0: self.browser().toggle_traces())

        togglespectros_act = QAction('Toggle &spectrograms', self)
        togglespectros_act.setShortcut('Ctrl+S')
        togglespectros_act.triggered.connect(lambda x=0: self.browser().toggle_spectrograms())

        togglecbars_act = QAction('Toggle &color bars', self)
        togglecbars_act.setShortcut('Ctrl+C')
        togglecbars_act.triggered.connect(lambda x=0: self.browser().toggle_colorbars())
        self.toggle_channel_acts = []
        for c in range(10):
            togglechannel_act = QAction(f'Toggle channel &{c}', self)
            togglechannel_act.setShortcut(f'{c}')
            togglechannel_act.triggered.connect(lambda x, channel=c: self.browser().toggle_channel(channel))
            self.toggle_channel_acts.append(togglechannel_act)
        grid_act = QAction('Toggle &grid', self)
        grid_act.setShortcut('g')
        grid_act.triggered.connect(lambda x=0: self.browser().toggle_grids())

        mouse_act = QAction('Toggle &zoom mode', self)
        mouse_act.setShortcut('o')
        mouse_act.triggered.connect(lambda x=0: self.browser().toggle_zoom_mode())

        maximize_act = QAction('Toggle &maximize', self)
        maximize_act.setShortcut('Ctrl+M')
        maximize_act.triggered.connect(self.toggle_maximize)

        self.view_menu = menu.addMenu('&View')
        self.setup_time_actions(self.view_menu)
        self.setup_amplitude_actions(self.view_menu)
        self.setup_frequency_actions(self.view_menu)
        self.setup_power_actions(self.view_menu)
        channel_menu = self.view_menu.addMenu('&Channels')
        for act in self.toggle_channel_acts:
            channel_menu.addAction(act)
        self.view_menu.addAction(toggletraces_act)
        self.view_menu.addAction(togglespectros_act)
        self.view_menu.addAction(togglecbars_act)
        self.view_menu.addSeparator()
        self.view_menu.addAction(mouse_act)
        self.view_menu.addAction(grid_act)
        self.view_menu.addAction(maximize_act)


    def adapt_menu(self, index):
        browser = self.tabs.widget(index)
        if isinstance(browser, DataBrowser):
            for i, act in enumerate(self.toggle_channel_acts):
                act.setVisible(i < browser.data.channels)

        
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
        for file_path in file_paths:
            browser = DataBrowser(file_path, self.channels, self.audio)
            self.tabs.addTab(browser, os.path.basename(file_path))
        if self.startup_active and self.tabs.count() > 1:
            self.tabs.removeTab(0)
            self.startup.setVisible(False)
            self.startup_active = False
            self.view_menu.setEnabled(True)


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()

            
    def close(self, index=None):
        if self.tabs.count() > 0:
            if index is None:
                index = self.tabs.currentIndex()
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

import os
import sys
import argparse
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QAction, QPushButton, QFileDialog
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QKeySequence
import pyqtgraph as pg
from audioio import AudioLoader, available_formats, write_audio
from audioio import PlayAudio, fade
from .version import __version__, __year__
from .traceitem import TraceItem
from .specitem import SpecItem
from IPython import embed


# list of all open data files:
main_wins = []


class MenuWindow(QMainWindow):
    def __init__(self, channels):
        super().__init__()
        self.channels = channels
        self.setWindowTitle(f'AUDIoANalyzer {__version__}')
        self.setup_file_actions()

        # button:
        open_button = QPushButton('&Open files')
        open_button.clicked.connect(self.open_files)
        self.setCentralWidget(open_button)


    def setup_file_actions(self):
        open_act = QAction('&Open', self)
        open_act.setShortcuts(QKeySequence.Open)
        open_act.triggered.connect(self.open_files)

        quit_act = QAction('&Quit', self)
        quit_act.setShortcuts(QKeySequence.Quit)
        quit_act.triggered.connect(self.quit)
        
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addAction(quit_act)
        
        
    def open_files(self):
        global main_wins
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if 'WAV' in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        file_paths = QFileDialog.getOpenFileNames(self, directory='.', filter=';;'.join(filters))[0]
        for file_path in reversed(file_paths):
            main = MainWindow(file_path, self.channels)
            main.show()
            main_wins.append(main)
        if len(main_wins) > 0:
            self.close()

            
    def quit(self):
        QApplication.quit()



class MainWindow(QMainWindow):
    def __init__(self, file_path, channels):
        super().__init__()

        # data:
        self.file_path = file_path if file_path else None
        self.channels = channels
        self.data = None
        self.rate = None
        self.tmax = 0.0

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
        self.show_cbars = True

        # audio:
        self.audio = PlayAudio()

        # window:
        self.setWindowTitle(f'AUDIoANalyzer {__version__}')
        vbox_widget = QWidget(self)
        self.vbox = QVBoxLayout(vbox_widget)
        self.vbox.setSpacing(0)
        self.setCentralWidget(vbox_widget)

        self.open()

        # actions:
        self.setup_file_actions()
        self.setup_time_actions()
        self.setup_amplitude_actions()
        self.setup_frequency_actions()
        self.setup_power_actions()
        self.setup_view_actions()


    def __del__(self):
        if not self.data is None:
            self.data.close()
        if self.audio is not None:
            self.audio.close()

        
    def setup_file_actions(self):
        open_act = QAction('&Open', self)
        open_act.setShortcuts(QKeySequence.Open)
        open_act.triggered.connect(self.open_files)

        close_act = QAction('&Close', self)
        close_act.setShortcut('q')  # QKeySequence.Close
        close_act.triggered.connect(self.close)

        quit_act = QAction('&Quit', self)
        quit_act.setShortcuts(QKeySequence.Quit)
        quit_act.triggered.connect(self.quit)
        
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        file_menu.addAction(close_act)
        file_menu.addAction(quit_act)


    def setup_time_actions(self):
        play_act = QAction('&Play', self)
        play_act.setShortcut('P')
        play_act.triggered.connect(self.play_segment)
        
        zoomxin_act = QAction('Zoom &in', self)
        zoomxin_act.setShortcuts(['+', '=', 'Shift+X']) # + QKeySequence.ZoomIn
        zoomxin_act.triggered.connect(self.zoom_time_in)

        zoomxout_act = QAction('Zoom &out', self)
        zoomxout_act.setShortcuts(['-', 'x']) # + QKeySequence.ZoomOut
        zoomxout_act.triggered.connect(self.zoom_time_out)

        pagedown_act = QAction('Page &down', self)
        pagedown_act.setShortcuts(QKeySequence.MoveToNextPage)
        pagedown_act.triggered.connect(self.time_page_down)

        pageup_act = QAction('Page &up', self)
        pageup_act.setShortcuts(QKeySequence.MoveToPreviousPage)
        pageup_act.triggered.connect(self.time_page_up)

        largedown_act = QAction('Block down', self)
        largedown_act.setShortcut('Ctrl+PgDown')
        largedown_act.triggered.connect(self.time_block_down)

        largeup_act = QAction('Block up', self)
        largeup_act.setShortcut('Ctrl+PgUp')
        largeup_act.triggered.connect(self.time_block_up)

        datadown_act = QAction('Data down', self)
        datadown_act.setShortcuts(QKeySequence.MoveToNextLine)
        datadown_act.triggered.connect(self.time_down)

        dataup_act = QAction('Data up', self)
        dataup_act.setShortcuts(QKeySequence.MoveToPreviousLine)
        dataup_act.triggered.connect(self.time_up)

        dataend_act = QAction('&End', self)
        dataend_act.setShortcuts([QKeySequence.MoveToEndOfLine, QKeySequence.MoveToEndOfDocument])
        dataend_act.triggered.connect(self.time_end)

        datahome_act = QAction('&Home', self)
        datahome_act.setShortcuts([QKeySequence.MoveToStartOfLine, QKeySequence.MoveToStartOfDocument])
        datahome_act.triggered.connect(self.time_home)

        time_menu = self.menuBar().addMenu('&Time')
        time_menu.addAction(play_act)
        time_menu.addAction(zoomxin_act)
        time_menu.addAction(zoomxout_act)
        time_menu.addAction(pagedown_act)
        time_menu.addAction(pageup_act)
        self.addAction(largedown_act)
        self.addAction(largeup_act)
        time_menu.addAction(datadown_act)
        time_menu.addAction(dataup_act)
        time_menu.addAction(dataend_act)
        time_menu.addAction(datahome_act)

        
    def setup_amplitude_actions(self):
        zoomyin_act = QAction('Zoom &in', self)
        zoomyin_act.setShortcut('Shift+Y')
        zoomyin_act.triggered.connect(self.zoom_ampl_in)

        zoomyout_act = QAction('Zoom &out', self)
        zoomyout_act.setShortcut('Y')
        zoomyout_act.triggered.connect(self.zoom_ampl_out)

        autoy_act = QAction('&Auto scale', self)
        autoy_act.setShortcut('v')
        autoy_act.triggered.connect(self.auto_ampl)

        resety_act = QAction('&Reset', self)
        resety_act.setShortcut('Shift+V')
        resety_act.triggered.connect(self.reset_ampl)

        centery_act = QAction('&Center', self)
        centery_act.setShortcut('C')
        centery_act.triggered.connect(self.center_ampl)

        ampl_menu = self.menuBar().addMenu('&Amplitude')
        ampl_menu.addAction(zoomyin_act)
        ampl_menu.addAction(zoomyout_act)
        ampl_menu.addAction(autoy_act)
        ampl_menu.addAction(resety_act)
        ampl_menu.addAction(centery_act)


    def setup_frequency_actions(self):
        zoomfin_act = QAction('Zoom &in', self)
        zoomfin_act.setShortcut('Shift+F')
        zoomfin_act.triggered.connect(self.zoom_freq_in)

        zoomfout_act = QAction('Zoom &out', self)
        zoomfout_act.setShortcut('F')
        zoomfout_act.triggered.connect(self.zoom_freq_out)

        frequp_act = QAction('Move &up', self)
        frequp_act.setShortcuts(QKeySequence.MoveToNextChar)
        frequp_act.triggered.connect(self.freq_up)

        freqdown_act = QAction('Move &down', self)
        freqdown_act.setShortcuts(QKeySequence.MoveToPreviousChar)
        freqdown_act.triggered.connect(self.freq_down)

        freqhome_act = QAction('&Home', self)
        freqhome_act.setShortcuts(QKeySequence.MoveToPreviousWord)
        freqhome_act.triggered.connect(self.freq_home)

        freqend_act = QAction('&End', self)
        freqend_act.setShortcuts(QKeySequence.MoveToNextWord)
        freqend_act.triggered.connect(self.freq_end)

        fresup_act = QAction('Increase &resolution', self)
        fresup_act.setShortcut('Shift+R')
        fresup_act.triggered.connect(self.freq_resolution_up)

        fresdown_act = QAction('De&crease resolution', self)
        fresdown_act.setShortcut('R')
        fresdown_act.triggered.connect(self.freq_resolution_down)
        
        freq_menu = self.menuBar().addMenu('Frequenc&y')
        freq_menu.addAction(zoomfin_act)
        freq_menu.addAction(zoomfout_act)
        freq_menu.addAction(frequp_act)
        freq_menu.addAction(freqdown_act)
        freq_menu.addAction(freqhome_act)
        freq_menu.addAction(freqend_act)
        freq_menu.addAction(fresup_act)
        freq_menu.addAction(fresdown_act)


    def setup_power_actions(self):
        powerup_act = QAction('Power &up', self)
        powerup_act.setShortcut('Shift+Z')
        powerup_act.triggered.connect(self.power_up)

        powerdown_act = QAction('Power &down', self)
        powerdown_act.setShortcut('Z')
        powerdown_act.triggered.connect(self.power_down)

        maxpowerup_act = QAction('Max up', self)
        maxpowerup_act.setShortcut('Shift+K')
        maxpowerup_act.triggered.connect(self.max_power_up)

        maxpowerdown_act = QAction('Max down', self)
        maxpowerdown_act.setShortcut('K')
        maxpowerdown_act.triggered.connect(self.max_power_down)

        minpowerup_act = QAction('Min up', self)
        minpowerup_act.setShortcut('Shift+J')
        minpowerup_act.triggered.connect(self.min_power_up)

        minpowerdown_act = QAction('Min down', self)
        minpowerdown_act.setShortcut('J')
        minpowerdown_act.triggered.connect(self.min_power_down)
        
        power_menu = self.menuBar().addMenu('&Power')
        power_menu.addAction(powerup_act)
        power_menu.addAction(powerdown_act)
        power_menu.addAction(maxpowerup_act)
        power_menu.addAction(maxpowerdown_act)
        power_menu.addAction(minpowerup_act)
        power_menu.addAction(minpowerdown_act)


    def setup_view_actions(self):
        toggletraces_act = QAction('Toggle &traces', self)
        toggletraces_act.setShortcut('Ctrl+T')
        toggletraces_act.triggered.connect(self.toggle_traces)

        togglespectros_act = QAction('Toggle &spectrograms', self)
        togglespectros_act.setShortcut('Ctrl+S')
        togglespectros_act.triggered.connect(self.toggle_spectrograms)

        togglecbars_act = QAction('Toggle &color bars', self)
        togglecbars_act.setShortcut('Ctrl+C')
        togglecbars_act.triggered.connect(self.toggle_colorbars)

        toggle_channel_acts = []
        if self.data.channels > 1:
            for c in range(min(10, self.data.channels)):
                togglechannel_act = QAction(f'Toggle channel &{c}', self)
                togglechannel_act.setShortcut(f'{c}')
                togglechannel_act.triggered.connect(lambda x, c=c: self.toggle_channel(c))
                toggle_channel_acts.append(togglechannel_act)

        grid_act = QAction('Toggle &grid', self)
        grid_act.setShortcut('g')
        grid_act.triggered.connect(self.toggle_grids)

        mouse_act = QAction('Toggle &zoom mode', self)
        mouse_act.setShortcut('o')
        mouse_act.triggered.connect(self.toggle_zoom_mode)

        maximize_act = QAction('Toggle &maximize', self)
        maximize_act.setShortcut('Ctrl+M')
        maximize_act.triggered.connect(self.toggle_maximize)

        view_menu = self.menuBar().addMenu('&View')
        view_menu.addAction(toggletraces_act)
        view_menu.addAction(togglespectros_act)
        view_menu.addAction(togglecbars_act)
        for act in toggle_channel_acts:
            view_menu.addAction(act)
        view_menu.addSeparator()
        view_menu.addAction(mouse_act)
        view_menu.addAction(grid_act)
        view_menu.addAction(maximize_act)

        
    def open(self):
        if not self.file_path:
            return
        if not self.data is None:
            self.data.close()
        self.data = AudioLoader(self.file_path, 60.0, 10.0)
        self.rate = self.data.samplerate
        self.setWindowTitle(f'AUDIoANalyzer {__version__}: {os.path.basename(self.file_path)}')

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
            self.show_channels = np.arange(self.data.channels)
        else:
            self.show_channels = np.array([c for c in self.channels if c < self.data.channels])

        # load data:
        self.data[0,:]

        self.figs = []     # all GraphicsLayoutWidgets - one for each channel
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
            self.vbox.addWidget(fig, 1)
            self.figs.append(fig)
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
            axt.getAxis('bottom').showLabel(c == self.data.channels-1)
            axt.getAxis('bottom').setStyle(showValues=(c == self.data.channels-1))
            self.axts.append(axt)
            self.axys.append(axt)
            self.axgs.append(axt)
            self.axtraces.append(axt)
            self.axs.append(axt)

        
    def open_files(self):
        global main_wins
        formats = available_formats()
        for f in ['MP3', 'OGG', 'WAV']:
            if 'WAV' in formats:
                formats.remove(f)
                formats.insert(0, f)
        filters = ['All files (*)'] + [f'{f} files (*.{f}, *.{f.lower()})' for f in formats]
        path = '.' if self.file_path is None else os.path.dirname(self.file_path)
        if len(path) == 0:
            path = '.'
        file_paths = QFileDialog.getOpenFileNames(self, directory=path, filter=';;'.join(filters))[0]
        for file_path in reversed(file_paths):
            main = MainWindow(file_path, self.channels)
            main.show()
            main_wins.append(main)


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

            
    def set_xrange(self, viewbox, xrange):
        self.toffset = xrange[0]
        self.twindow = xrange[1] - xrange[0]
        self.set_traces_xrange()
        

    def set_traces_xrange(self):
        for ax in self.axts:
            ax.getViewBox().setLimits(xMax=max(self.tmax,
                                               self.toffset + self.twindow))
            ax.setXRange(self.toffset, self.toffset + self.twindow)

        
    def zoom_time_in(self):
        if self.twindow * self.rate >= 20:
            self.twindow *= 0.5
            self.set_traces_xrange()
        
        
    def zoom_time_out(self):
        if self.toffset + self.twindow < self.tmax:
            self.twindow *= 2.0
            self.set_traces_xrange()

                
    def time_page_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            self.set_traces_xrange()

            
    def time_page_up(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def time_block_down(self):
        if self.toffset + self.twindow < self.tmax:
            for k in range(5):
                self.toffset += self.twindow
                if self.toffset + self.twindow >= self.tmax:
                    break
            self.set_traces_xrange()

                
    def time_block_up(self):
        if self.toffset > 0:
            self.toffset -= 5.0*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def time_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            self.set_traces_xrange()

                
    def time_up(self):
        if self.toffset > 0.0:
            self.toffset -= 0.05*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def time_home(self):
        if self.toffset > 0.0:
            self.toffset = 0.0
            self.set_traces_xrange()

                
    def time_end(self):
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            self.set_traces_xrange()


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


    def set_freq_ranges(self):
        for ax in self.axfys:
            ax.setYRange(self.f0, self.f1)
        for ax in self.axfxs:
            ax.setXRange(self.f0, self.f1)

            
    def set_frange(self, viewbox, frange):
        self.f0 = frange[0]
        self.f1 = frange[1]
        self.set_freq_ranges()
        
            
    def zoom_freq_in(self):
        df = self.f1 - self.f0
        if df > 0.1:
            df *= 0.5
            self.f1 = self.f0 + df
            self.set_freq_ranges()
            
        
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
            self.set_freq_ranges()
                
        
    def freq_down(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 -= 0.5*df
            self.f1 -= 0.5*df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df
            self.set_freq_ranges()

            
    def freq_up(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f0 += 0.5*df
            self.f1 += 0.5*df
            self.set_freq_ranges()


    def freq_home(self):
        if self.f0 > 0.0:
            df = self.f1 - self.f0
            self.f0 = 0.0
            self.f1 = df
            self.set_freq_ranges()

            
    def freq_end(self):
        if self.f1 < self.fmax:
            df = self.f1 - self.f0
            self.f1 = np.ceil(self.fmax/(0.5*df))*(0.5*df)
            self.f0 = self.f1 - df
            if self.f0 < 0.0:
                self.f0 = 0.0
                self.f1 = df
            self.set_freq_ranges()

        
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

            
    def toggle_channel(self, channel):
        if len(self.figs) > channel:
            self.figs[channel].setVisible(not self.figs[channel].isVisible())
            

    def toggle_traces(self):
        for axt, axs, cb in zip(self.axtraces, self.axspecs, self.cbars):
            if axt.isVisible():
                axs.setVisible(True)
                cb.setVisible(self.show_cbars)
            axt.setVisible(not axt.isVisible())
            

    def toggle_spectrograms(self):
        for axt, axs, cb in zip(self.axtraces, self.axspecs, self.cbars):
            if axs.isVisible():
                axt.setVisible(True)
            axs.setVisible(not axs.isVisible())
            if axs.isVisible():
                cb.setVisible(self.show_cbars)
            else:
                cb.setVisible(False)

                
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


    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()


    def play_segment(self):
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        playdata = 1.0*self.data[t0:t1,:]
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        
            
    def close(self):
        global main_wins
        QMainWindow.close(self)
        main_wins.remove(self)

            
    def quit(self):
        global main_wins
        for win in reversed(main_wins):
            win.close()
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
    if len(args.files) == 0:
        main = MenuWindow(channels)
        main.show()
    else:
        for file_path in reversed(args.files):
            main = MainWindow(file_path, channels)
            main.show()
            main_wins.append(main)
    app.exec_()


def run():
    main(sys.argv[1:])

    
if __name__ == '__main__':
    run()

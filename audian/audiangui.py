import os
import sys
import argparse
import numpy as np
from scipy.signal import spectrogram
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QAction, QPushButton, QFileDialog
from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtGui import QKeySequence
import pyqtgraph as pg
from audioio import AudioLoader
from .version import __version__, __year__
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
        file_paths = QFileDialog.getOpenFileNames(self, directory='.', filter='All files (*);;Wave files (*.wav *.WAV);;MP3 files (*.mp3)')[0]
        for file_path in reversed(file_paths):
            main = MainWindow(file_path, self.channels)
            main.show()
            main_wins.append(main)
        if len(main_wins) > 0:
            self.close()

            
    def quit(self):
        QApplication.quit()



class TraceItem(pg.PlotDataItem):
    
    def __init__(self, data, rate, channel, *args, **kwargs):
        self.data = data
        self.rate = rate
        self.channel = channel
        self.ymin = -1.0
        self.ymax = +1.0
        
        pg.PlotDataItem.__init__(self, *args, connect='all',
                                 antialias=False, skipFiniteCheck=True,
                                 **kwargs)
        self.setPen(dict(color='#00ff00', width=2))
        self.setSymbolSize(8)
        self.setSymbolBrush(color='#00ff00')
        self.setSymbolPen(color='#00ff00')
        self.setSymbol(None)

        
    def viewRangeChanged(self):
        self.update()
    

    def update(self):
        vb = self.getViewBox()
        if not isinstance(vb, pg.ViewBox):
            return

        trange = vb.viewRange()[0]
        start = max(0, int(trange[0]*self.rate))
        stop = min(len(self.data), int(trange[1]*self.rate+1))
        step = max(1, (stop - start)//10000)
        if step > 1:
            # min - max: (good but a bit slow - let numba do it!)
            step2 = step//2
            step = step2*2
            n = (stop-start)//step
            data = np.array([(np.min(self.data[start+k*step:start+(k+1)*step, self.channel]), np.max(self.data[start+k*step:start+(k+1)*step, self.channel])) for k in range(n)]).reshape((-1))
            self.setData(np.arange(start, start + len(data)*step2, step2)/self.rate, data)
            self.setPen(dict(color='#00ff00', width=1.1))
        elif step > 1:  # TODO: not used
            # subsample:
            self.setData(np.arange(start, stop, step)/self.rate,
                         self.data[start:stop:step, self.channel])
            self.setPen(dict(color='#00ff00', width=1.1))
        else:
            # all data:
            self.setData(np.arange(start, stop)/self.rate,
                         self.data[start:stop, self.channel])
            self.setPen(dict(color='#00ff00', width=2))
            if stop - start <= 50:
                self.setSymbol('o')
            else:
                self.setSymbol(None)


    def zoom_y_in(self):
        h = 0.25*(self.ymax - self.ymin)
        c = 0.5*(self.ymax + self.ymin)
        self.ymin = c - h
        self.ymax = c + h

        
    def zoom_y_out(self):
        h = self.ymax - self.ymin
        c = 0.5*(self.ymax + self.ymin)
        self.ymin = c - h
        self.ymax = c + h
        
        
    def auto_y(self, toffset, twindow):
        t0 = int(np.round(toffset * self.rate))
        t1 = int(np.round((toffset + twindow) * self.rate))
        ymin = np.min(self.data[t0:t1, self.channel])
        ymax = np.max(self.data[t0:t1, self.channel])
        h = 0.5*(ymax - ymin)
        c = 0.5*(ymax + ymin)
        self.ymin = c - h
        self.ymax = c + h

        
    def reset_y(self):
        self.ymin = -1.0
        self.ymax = +1.0


    def center_y(self):
        dy = self.ymax - self.ymin
        self.ymin = -dy/2
        self.ymax = +dy/2
        

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
        
        self.mouse_mode = pg.ViewBox.PanMode
        self.grids = 0

        # window:
        self.setWindowTitle(f'AUDIoANalyzer {__version__}')
        vbox_widget = QWidget(self)
        self.vbox = QVBoxLayout(vbox_widget)
        self.vbox.setSpacing(0)
        self.setCentralWidget(vbox_widget)

        self.open()

        # actions:
        self.setup_file_actions()
        self.setup_view_actions()

        
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


    def setup_view_actions(self):
        zoomxin_act = QAction('Zoom &in', self)
        zoomxin_act.setShortcuts(['+', '=', 'Shift+X']) # + QKeySequence.ZoomIn
        zoomxin_act.triggered.connect(self.zoom_x_in)

        zoomxout_act = QAction('Zoom &out', self)
        zoomxout_act.setShortcuts(['-', 'x']) # + QKeySequence.ZoomOut
        zoomxout_act.triggered.connect(self.zoom_x_out)

        pagedown_act = QAction('Page &down', self)
        pagedown_act.setShortcuts(QKeySequence.MoveToNextPage)
        pagedown_act.triggered.connect(self.page_down)

        pageup_act = QAction('Page &up', self)
        pageup_act.setShortcuts(QKeySequence.MoveToPreviousPage)
        pageup_act.triggered.connect(self.page_up)

        largedown_act = QAction('Block down', self)
        largedown_act.setShortcut('Ctrl+PgDown')
        largedown_act.triggered.connect(self.large_down)

        largeup_act = QAction('Block up', self)
        largeup_act.setShortcut('Ctrl+PgUp')
        largeup_act.triggered.connect(self.large_up)

        datadown_act = QAction('Data down', self)
        datadown_act.setShortcuts(QKeySequence.MoveToNextLine)
        datadown_act.triggered.connect(self.data_down)

        dataup_act = QAction('Data up', self)
        dataup_act.setShortcuts(QKeySequence.MoveToPreviousLine)
        dataup_act.triggered.connect(self.data_up)

        dataend_act = QAction('&End', self)
        dataend_act.setShortcuts([QKeySequence.MoveToEndOfLine, QKeySequence.MoveToEndOfDocument])
        dataend_act.triggered.connect(self.data_end)

        datahome_act = QAction('&Home', self)
        datahome_act.setShortcuts([QKeySequence.MoveToStartOfLine, QKeySequence.MoveToStartOfDocument])
        datahome_act.triggered.connect(self.data_home)

        zoomyin_act = QAction('Zoom y in', self)
        zoomyin_act.setShortcut('Shift+Y')
        zoomyin_act.triggered.connect(self.zoom_y_in)

        zoomyout_act = QAction('Zoom y out', self)
        zoomyout_act.setShortcut('Y')
        zoomyout_act.triggered.connect(self.zoom_y_out)

        autoy_act = QAction('Auto set y', self)
        autoy_act.setShortcut('v')
        autoy_act.triggered.connect(self.auto_y)

        resety_act = QAction('Reset y range', self)
        resety_act.setShortcut('Shift+V')
        resety_act.triggered.connect(self.reset_y)

        centery_act = QAction('Center y range', self)
        centery_act.setShortcut('C')
        centery_act.triggered.connect(self.center_y)

        toggletraces_act = QAction('Toggle traces', self)
        toggletraces_act.setShortcut('Ctrl+T')
        toggletraces_act.triggered.connect(self.toggle_traces)

        togglespectros_act = QAction('Toggle spectrograms', self)
        togglespectros_act.setShortcut('Ctrl+S')
        togglespectros_act.triggered.connect(self.toggle_spectrograms)

        togglecbars_act = QAction('Toggle color bars', self)
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
        maximize_act.setShortcut('m')
        maximize_act.triggered.connect(self.toggle_maximize)

        view_menu = self.menuBar().addMenu('&View')
        view_menu.addAction(zoomxin_act)
        view_menu.addAction(zoomxout_act)
        view_menu.addAction(pagedown_act)
        view_menu.addAction(pageup_act)
        self.addAction(largedown_act)
        self.addAction(largeup_act)
        view_menu.addAction(datadown_act)
        view_menu.addAction(dataup_act)
        view_menu.addAction(dataend_act)
        view_menu.addAction(datahome_act)
        view_menu.addSeparator()
        view_menu.addAction(zoomyin_act)
        view_menu.addAction(zoomyout_act)
        view_menu.addAction(autoy_act)
        view_menu.addAction(resety_act)
        view_menu.addAction(centery_act)
        view_menu.addSeparator()
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
        self.data = AudioLoader(self.file_path, 60.0)
        self.rate = self.data.samplerate
        self.setWindowTitle(f'AUDIoANalyzer {__version__}: {os.path.basename(self.file_path)}')

        self.toffset = 0.0
        self.twindow = 2.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = np.round(2**(np.floor(np.log(self.tmax) / np.log(2.0)) + 1.0))
        
        if len(self.channels) == 0:
            self.show_channels = np.arange(self.data.channels)
        else:
            self.show_channels = np.array([c for c in self.channels if c < self.data.channels])
        channel = self.show_channels[0]  # TODO: remove

        self.figs = []
        self.axs  = []     # all plots
        self.axts = []     # plots with time axis
        self.axys = []     # plots with amplitude axis
        self.axfs = []     # plots with frequency axis
        self.axgs = []     # plots with grids
        self.axtraces = [] # all traces
        self.axspecs = []  # all spectrogams
        self.cbars = []    # all color bars
        self.traces = []
        self.specs = []
        for c in range(self.data.channels):
            # one figure per channel:
            fig = pg.GraphicsLayoutWidget()
            fig.setBackground(None)
            self.vbox.addWidget(fig, 1)
            self.figs.append(fig)
            # spectrograms:
            nfft = 2048//4
            freq, time, Sxx = spectrogram(self.data[:, c], self.rate, nperseg=nfft, noverlap=nfft/2)
            Sxx = 10*np.log10(Sxx)
            print(np.max(Sxx))
            zmax = np.percentile(Sxx, 99.9) + 5.0
            #zmin = np.percentile(Sxx, 50.0)
            #zmax = -20
            zmin = zmax - 60
            pg.setConfigOptions(imageAxisOrder='row-major')
            axs = fig.addPlot(row=0, col=0)
            spec = pg.ImageItem(Sxx) # self.data, self.rate, c)
            spec.scale(time[-1]/len(time), freq[-1]/len(freq))
            axs.setLimits(xMin=0, xMax=time[-1], yMin=0, yMax=freq[-1])
            self.specs.append(spec)
            self.setup_spec_plot(axs, c)
            axs.addItem(spec)
            axs.setLabel('left', 'Frequency', 'Hz', color='black')
            axs.setLabel('bottom', 'Time', 's', color='black')
            axs.getAxis('bottom').showLabel(False)
            axs.getAxis('bottom').setStyle(showValues=False)
            cbar = pg.ColorBarItem(colorMap='CET-R4', interactive=True,
                                   rounding=1, limits=(-200, 20))
            cbar.setLabel('right', 'Power [dB]')
            cbar.getAxis('right').setTextPen('black')
            cbar.setLevels([zmin, zmax])
            cbar.setImageItem(spec)
            self.cbars.append(cbar)
            fig.addItem(cbar, row=0, col=1)
            self.axts.append(axs)
            self.axfs.append(axs)
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
        file_paths = QFileDialog.getOpenFileNames(self, directory='.', filter='All files (*);;Wave files (*.wav *.WAV);;MP3 files (*.mp3)')[0]
        for file_path in reversed(file_paths):
            main = MainWindow(file_path, self.channels)
            main.show()
            main_wins.append(main)


    def setup_trace_plot(self, ax, c):
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.getViewBox().setLimits(xMin=0,
                                  xMax=max(self.tmax,
                                           self.toffset + self.twindow),
                                  yMin=self.traces[c].ymin,
                                  yMax=self.traces[c].ymax,
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
        """
        ax.getViewBox().setLimits(xMin=0,
                                  xMax=max(self.tmax,
                                           self.toffset + self.twindow),
                                  yMin=self.traces[c].ymin,
                                  yMax=self.traces[c].ymax,
                                  minXRange=10/self.rate, maxXRange=self.tmax,
                                  minYRange=1/2**16,
                                  maxYRange=self.traces[c].ymax - self.traces[c].ymin)
        """
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setTextPen('black')
        ax.getAxis('left').setWidth(80)
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.set_xrange)
        #ax.setYRange(self.traces[c].ymin, self.traces[c].ymax)

            
    def set_xrange(self, viewbox, xrange):
        self.toffset = xrange[0]
        self.twindow = xrange[1] - xrange[0]
        self.set_traces_xrange()
        

    def set_traces_xrange(self):
        for ax in self.axts:
            ax.getViewBox().setLimits(xMax=max(self.tmax,
                                               self.toffset + self.twindow))
            ax.setXRange(self.toffset, self.toffset + self.twindow)

        
    def zoom_x_in(self):
        if self.twindow * self.rate >= 20:
            self.twindow *= 0.5
            self.set_traces_xrange()
        
        
    def zoom_x_out(self):
        if self.toffset + self.twindow < self.tmax:
            self.twindow *= 2.0
            self.set_traces_xrange()

                
    def page_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            self.set_traces_xrange()

            
    def page_up(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def large_down(self):
        if self.toffset + self.twindow < self.tmax:
            for k in range(5):
                self.toffset += self.twindow
                if self.toffset + self.twindow >= self.tmax:
                    break
            self.set_traces_xrange()

                
    def large_up(self):
        if self.toffset > 0:
            self.toffset -= 5.0*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def data_down(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            self.set_traces_xrange()

                
    def data_up(self):
        if self.toffset > 0.0:
            self.toffset -= 0.05*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def data_home(self):
        if self.toffset > 0.0:
            self.toffset = 0.0
            self.set_traces_xrange()

                
    def data_end(self):
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            self.set_traces_xrange()


    def zoom_y_in(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.zoom_y_in()
            ax.setYRange(trace.ymin, trace.ymax)

        
    def zoom_y_out(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.zoom_y_out()
            ax.setYRange(trace.ymin, trace.ymax)
        
        
    def auto_y(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.auto_y(self.toffset, self.twindow)
            ax.setYRange(trace.ymin, trace.ymax)

        
    def reset_y(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.reset_y()
            ax.setYRange(trace.ymin, trace.ymax)


    def center_y(self):
        for ax, trace in zip(self.axys, self.traces):
            trace.center_y()
            ax.setYRange(trace.ymin, trace.ymax)


    def toggle_channel(self, channel):
        if len(self.figs) > channel:
            self.figs[channel].setVisible(not self.figs[channel].isVisible())
            

    def toggle_traces(self):
        for axt, axs in zip(self.axtraces, self.axspecs):
            if axt.isVisible():
                axs.setVisible(True)
            axt.setVisible(not axt.isVisible())
            

    def toggle_spectrograms(self):
        self.toggle_colorbars()
        for axt, axs in zip(self.axtraces, self.axspecs):
            if axs.isVisible():
                axt.setVisible(True)
            axs.setVisible(not axs.isVisible())
            

    def toggle_colorbars(self):
        for cb in self.cbars:
            cb.setVisible(not cb.isVisible())
            

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

import os
import sys
import argparse
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow
from PyQt5.QtWidgets import QAction, QPushButton, QFileDialog
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



class DataItem(pg.PlotDataItem):
    
    def __init__(self, data, rate, channel, *args, **kwargs):
        self.data = data
        self.rate = rate
        self.channel = channel
        pg.PlotDataItem.__init__(self, *args, connect='all',
                                 antialias=False, skipFiniteCheck=True,
                                 **kwargs)
        self.setPen(dict(color='#00ff00', width=2))
        self.setSymbolSize(8)
        self.setSymbolBrush(color='#00ff00')
        self.setSymbolPen(color='#00ff00')
        self.setSymbol(None)

        
    def viewRangeChanged(self):
        self.updateDataPlot()
    

    def updateDataPlot(self):
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
        self.ymin = -1.0
        self.ymax = +1.0
        
        self.mouse_mode = pg.ViewBox.PanMode
        self.grids = 0

        # window:
        self.setWindowTitle(f'AUDIoANalyzer {__version__}')
        self.setup_file_actions()
        self.setup_view_actions()

        # main plots:
        self.axts = []
        self.fig = pg.GraphicsLayoutWidget()
        self.setCentralWidget(self.fig)
        self.fig.setBackground(None)

        self.ax = self.fig.addPlot(row=0, col=0)
        self.trace = None

        self.open()


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
        if len(self.channels) == 0:
            self.show_channels = np.arange(self.data.channels)
        else:
            self.show_channels = np.array(self.channels)
        self.channel = self.show_channels[0]

        self.toffset = 0.0
        self.twindow = 2.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = np.round(2**(np.floor(np.log(self.tmax) / np.log(2.0)) + 1.0))
        self.ymin = -1.0
        self.ymax = +1.0

        if not self.trace is None:
            self.ax.removeItem(self.trace)
            del self.trace
        self.trace_plot(self.ax, len(self.data), self.rate)
        self.trace = DataItem(self.data, self.rate, self.channel)
        self.ax.addItem(self.trace)
        self.ax.setLabel('left', 'Sound', 'V', color='black')
        self.ax.setLabel('bottom', 'Time', 's', color='black')
        self.setWindowTitle(f'AUDIoANalyzer {__version__}: {os.path.basename(self.file_path)} {self.channel}')

        
    def open_files(self):
        global main_wins
        file_paths = QFileDialog.getOpenFileNames(self, directory='.', filter='All files (*);;Wave files (*.wav *.WAV);;MP3 files (*.mp3)')[0]
        for file_path in reversed(file_paths):
            main = MainWindow(file_path, self.channels)
            main.show()
            main_wins.append(main)


    def trace_plot(self, ax, n, rate):
        tmax = n/rate
        if self.twindow > tmax:
            self.twindow = tmax
        ax.getViewBox().setBackgroundColor('black')
        ax.getViewBox().setDefaultPadding(padding=0.0)
        ax.getViewBox().setLimits(xMin=0,
                                  xMax=max(tmax, self.toffset + self.twindow),
                                  yMin=-1, yMax=1,
                                  minXRange=10/rate, maxXRange=tmax,
                                  minYRange=1/2**16, maxYRange=2)
        ax.getAxis('bottom').setTextPen('black')
        ax.getAxis('left').setTextPen('black')
        ax.getAxis('left').setWidth(60)
        ax.enableAutoRange(False, False)
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        ax.sigXRangeChanged.connect(self.set_xrange)
        ax.setYRange(-1, 1)
        self.axts.append(ax)

            
    def set_xrange(self, viewbox, xrange):
        self.toffset = xrange[0]
        self.twindow = xrange[1] - xrange[0]
        self.set_traces_xrange()
        

    def set_traces_xrange(self):
        for ax in self.axts:
            ax.getViewBox().setLimits(xMax=max(self.tmax,
                                               self.toffset + self.twindow))
            ax.setXRange(self.toffset, self.toffset + self.twindow)


    def set_traces_yrange(self):
        for ax in self.axts:
            ax.setYRange(self.ymin, self.ymax)

        
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
        h = 0.25*(self.ymax - self.ymin)
        c = 0.5*(self.ymax + self.ymin)
        self.ymin = c - h
        self.ymax = c + h
        self.set_traces_yrange()

        
    def zoom_y_out(self):
        h = self.ymax - self.ymin
        c = 0.5*(self.ymax + self.ymin)
        self.ymin = c - h
        self.ymax = c + h
        self.set_traces_yrange()
        
        
    def auto_y(self):
        t0 = int(np.round(self.toffset * self.rate))
        t1 = int(np.round((self.toffset + self.twindow) * self.rate))
        ymin = np.min(self.data[t0:t1, self.channel])
        ymax = np.max(self.data[t0:t1, self.channel])
        h = 0.5*(ymax - ymin)
        c = 0.5*(ymax + ymin)
        self.ymin = c - h
        self.ymax = c + h
        self.set_traces_yrange()

        
    def reset_y(self):
        self.ymin = -1.0
        self.ymax = +1.0
        self.set_traces_yrange()


    def center_y(self):
        dy = self.ymax - self.ymin
        self.ymin = -dy/2
        self.ymax = +dy/2
        self.set_traces_yrange()
            

    def toggle_zoom_mode(self):
        if self.mouse_mode == pg.ViewBox.PanMode:
            self.mouse_mode = pg.ViewBox.RectMode
        else:
            self.mouse_mode = pg.ViewBox.PanMode
        for ax in self.axts:
            ax.getViewBox().setMouseMode(self.mouse_mode)

            
    def toggle_grids(self):
        self.grids -= 1
        if self.grids < 0:
            self.grids = 3
        for ax in self.axts:
            ax.showGrid(x=(self.grids & 1) > 0, y=(self.grids & 2) > 0,
                        alpha=0.8)


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
        print(main_wins)
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

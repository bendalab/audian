import sys
import argparse
import numpy as np
from PyQt5.QtWidgets import QApplication, QMainWindow, QAction, QLabel
from PyQt5.QtGui import QKeySequence
import pyqtgraph as pg
from audioio import AudioLoader
from .version import __version__, __year__
from IPython import embed


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
        if step > 10:
            # min - max: (good but a bit slow - let numba do it!)
            step2 = step//2
            step = step2*2
            n = (stop-start)//step
            data = np.array([(np.min(self.data[start+k*step:start+(k+1)*step, self.channel]), np.max(self.data[start+k*step:start+(k+1)*step, self.channel])) for k in range(n)]).reshape((-1))
            self.setData(np.arange(start, start + len(data)*step2, step2)/self.rate, data)
            self.setPen(dict(color='#00ff00', width=1.1))
        elif step > 1:
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
    def __init__(self, data, channel, rate):
        super().__init__()

        # data:
        self.data = data
        self.channel = channel
        self.rate = rate

        # view:
        self.toffset = 0.0
        self.twindow = 2.0
        tmax = len(self.data)/rate
        if self.twindow > tmax:
            self.twindow = np.round(2**(np.floor(np.log(tmax) / np.log(2.0)) + 1.0))
        self.ymin = -1.0
        self.ymax = +1.0
        
        self.mouse_mode = pg.ViewBox.PanMode
        self.grids = 0
        
        # file menu:
        open_act = QAction('&Open', self)
        #act.setShortcut('F')
        open_act.setShortcuts(QKeySequence.Open)
        open_act.triggered.connect(self.open_file)

        quit_act = QAction('&Quit', self)
        quit_act.setShortcut('q')
        quit_act.triggered.connect(self.quit)
        
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(open_act)
        file_menu.addSeparator()
        file_menu.addAction(quit_act)

        # view menu:
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

        mouse_act = QAction('Toggle &mouse', self)
        mouse_act.setShortcut('o')
        mouse_act.triggered.connect(self.toggle_mouse)

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

        # main plots:
        self.axts = []
        fig = pg.GraphicsLayoutWidget()
        self.setCentralWidget(fig)
        fig.setBackground(None)

        #trace1 = DataItem(self.data, self.rate, self.channel)
        trace2 = DataItem(self.data, self.rate, self.channel)
        #ax1 = fig.addPlot(row=0, col=0)
        ax2 = fig.addPlot(row=0, col=0)
        #self.trace_plot(ax1, len(data), rate)
        self.trace_plot(ax2, len(data), rate)
        #ax1.addItem(trace1)
        ax2.addItem(trace2)
        #ax1.setLabel('left', 'Sound', 'V', color='black')
        ax2.setLabel('left', 'Sound', 'V', color='black')
        ax2.setLabel('bottom', 'Time', 's', color='black')



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


    def set_traces_xrange(self):
        for ax in self.axts:
            ax.getViewBox().setLimits(xMax=max(len(self.data)/self.rate,
                                               self.toffset + self.twindow))
            ax.setXRange(self.toffset, self.toffset + self.twindow)


    def set_traces_yrange(self):
        for ax in self.axts:
            ax.setYRange(self.ymin, self.ymax)

        
    def open_file(self):
        print('open file')

        
    def zoom_x_in(self):
        if self.twindow*self.rate >= 20:
            self.twindow *= 0.5
            self.set_traces_xrange()
        
        
    def zoom_x_out(self):
        if self.toffset + self.twindow < len(self.data)/self.rate:
            self.twindow *= 2.0
            self.set_traces_xrange()

                
    def page_down(self):
        if self.toffset + self.twindow < len(self.data)/self.rate:
            self.toffset += 0.5*self.twindow
            self.set_traces_xrange()

            
    def page_up(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def large_down(self):
        if self.toffset + self.twindow < len(self.data)/self.rate:
            for k in range(5):
                self.toffset += self.twindow
                if self.toffset + self.twindow >= len(self.data)/self.rate:
                    break
            self.set_traces_xrange()

                
    def large_up(self):
        if self.toffset > 0:
            self.toffset -= 5.0*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            self.set_traces_xrange()

                
    def data_down(self):
        if self.toffset + self.twindow < len(self.data)/self.rate:
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
        n2 = np.floor(len(self.data)/self.rate / (0.5*self.twindow))
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
        t1 = int(np.round((self.toffset + self.twindow)*self.rate))
        ymin = np.min(self.data[t0:t1])
        ymax = np.max(self.data[t0:t1])
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
            
            
    def set_xrange(self, viewbox, xrange):
        self.toffset = xrange[0]
        self.twindow = xrange[1] - xrange[0]
        self.set_traces_xrange()
        

    def toggle_mouse(self):
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

            
    def quit(self):
        QApplication.quit()


def main(cargs):
    # config file name:
    #cfgfile = __package__ + '.cfg'
    cfgfile = 'audian.cfg'
    
    # command line arguments:
    parser = argparse.ArgumentParser(description='Display waveform, spectrogram, power spectrum, envelope, and envelope spectrum of time series data.', epilog=f'version {__version__} by Jan Benda (2015-{__year__})')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-v', action='count', dest='verbose',
                        help='print debug information')
    parser.add_argument('-c', '--save-config', nargs='?', default='', const=cfgfile, type=str, metavar='cfgfile',
                        help='save configuration to file cfgfile (defaults to {0})'.format(cfgfile))
    parser.add_argument('-f', dest='high_pass', type=float, metavar='FREQ', default=None,
                        help='cutoff frequency of highpass filter in Hz')
    parser.add_argument('-l', dest='low_pass', type=float, metavar='FREQ', default=None,
                        help='cutoff frequency of lowpass filter in Hz')
    parser.add_argument('file', nargs='?', default='', type=str, help='name of the file with the time series data')
    parser.add_argument('channel', nargs='?', default=0, type=int, help='channel to be displayed')
    args, qt_args = parser.parse_known_args(cargs)
    
    with AudioLoader(args.file, 60.0) as data:
        app = QApplication(sys.argv[:1] + qt_args)
        main = MainWindow(data, 0, data.samplerate)
        main.show()
        app.exec_()


def run():
    main(sys.argv[1:])

    
if __name__ == '__main__':
    run()

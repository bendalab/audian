"""Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

"""

import numpy as np
from audioio import get_datetime
from thunderlab.dataloader import DataLoader
from .bufferedfilter import BufferedFilter
from .bufferedenvelope import BufferedEnvelope
from .bufferedspectrogram import BufferedSpectrogram


class Data(object):

    def __init__(self, file_path):
        self.buffer_time = 60
        self.back_time = 20
        self.follow_time = 0
        self.file_path = file_path
        self.data = None
        self.rate = None
        self.channels = 0
        self.tmax = 0.0
        self.toffset = 0.0
        self.twindow = 10.0
        self.start_time = None
        self.meta_data = {}
        self.tbefore = 0
        self.tafter = 0
        self.filtered = BufferedFilter()
        self.envelope = BufferedEnvelope()
        self.spectrum = BufferedSpectrogram()
        self.traces = [self.filtered, self.envelope, self.spectrum]
        self.order_plugins()

        
    def __del__(self):
        if not self.data is None:
            self.data.close()


    def __len__(self):
        return len(self.traces)

            
    def __getitem__(self, key):
        for trace in self.traces:
            if trace.name.lower() == key.lower():
                return trace
        return None


    def keys(self):
        return [trace.name for trace in self.traces]

        
    def order_plugins(self):
        traces = []
        self.sources = []
        i = -1
        while i < len(traces):
            sname = traces[i].name if i >= 0 else 'data'
            dtraces = []
            for k in range(len(self.traces)):
                if self.traces[k] is not None and \
                   self.traces[k].source_name is sname:
                    dtraces.append(self.traces[k])
                    self.traces[k] = None
            for t in reversed(dtraces):
                traces.insert(i + 1, t)
                self.sources.insert(i + 1, i)
            i += 1
        if len(traces) < len(self.traces):
            for trace in self.traces:
                if trace is not None:
                    print(f'! ERROR: source "{trace.source_name}" for trace "{trace.name}" not found!')
            print('! the following sources are available:')
            print('  data')
            for source in traces:
                print(f'  {source.name}')
        self.traces = traces

        
    def open(self, unwrap, unwrap_clip):
        if not self.data is None:
            self.data.close()
        # expand buffer times:
        self.tbefore = 0
        self.tafter = 0
        tbefore = [0] * len(self.traces)
        tafter = [0] * len(self.traces)
        for k in reversed(range(len(self.traces))):
            tb, ta = self.traces[k].expand_times(tbefore[k], tafter[k])
            i = self.sources[k]
            if i < 0:
                self.tbefore = max(self.tbefore, tb)
                self.tafter = max(self.tafter, ta)
            else:
                tbefore[i] = max(tbefore[i], tb)
                tafter[i] = max(tafter[i], ta)
        # raw data:        
        tbuffer = self.buffer_time + self.tbefore + self.tafter
        tback = self.back_time + self.tbefore
        try:
            self.data = DataLoader(self.file_path, tbuffer, tback)
        except IOError:
            self.data = None
            return
        self.data.set_unwrap(unwrap, unwrap_clip, False, self.data.unit)
        self.data.follow = int(self.follow_time*self.data.rate)
        self.data.name = 'data'
        self.data.dests = []
        self.traces.insert(0, self.data)
        self.sources = [None] + [i + 1 for i in self.sources]
        self.file_path = self.data.filepath
        self.rate = self.data.rate
        self.channels = self.data.channels
        self.toffset = 0.0
        self.twindow = 10.0
        self.tmax = len(self.data)/self.rate
        if self.twindow > self.tmax:
            self.twindow = self.tmax
        # metadata:
        self.meta_data = dict(Format=self.data.format_dict())
        self.meta_data.update(self.data.metadata())
        self.start_time = get_datetime(self.meta_data)
        # derived data:
        for trace, source in zip(self.traces[1:], self.sources[1:]):
            trace.open(self.traces[source])


    def update_times(self):
        self.data.update_time(self.toffset - self.tbefore,
                              self.toffset + self.twindow + self.tafter)
        for trace in self.traces[1:]:
            trace.align_buffer()
        
        
    def set_time_limits(self, ax):
        ax.setLimits(xMin=0, xMax=self.tmax,
                     minXRange=10/self.rate, maxXRange=self.tmax)
        # TODO: limit maxXRange to 60s or so!

        
    def set_time_range(self, ax):
        ax.setXRange(self.toffset, self.toffset + self.twindow)
        
        
    def zoom_time_in(self):
        if self.twindow * self.rate >= 20:
            self.twindow *= 0.5
            return True
        return False
        
        
    def zoom_time_out(self):
        if self.toffset + self.twindow < self.tmax:
            self.twindow *= 2.0
            return True
        return False

                
    def time_seek_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.5*self.twindow
            return True
        return False

            
    def time_seek_backward(self):
        if self.toffset > 0:
            self.toffset -= 0.5*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            return True
        return False

                
    def time_forward(self):
        if self.toffset + self.twindow < self.tmax:
            self.toffset += 0.05*self.twindow
            return True
        return False

                
    def time_backward(self, toffs):
        if toffs > 0.0:
            self.toffset = toffs - 0.05*self.twindow
            if self.toffset < 0.0:
                self.toffset = 0.0
            return True
        return False

                
    def time_home(self):
        if self.toffset > 0.0:
            self.toffset = 0.0
            return True
        return False

                
    def time_end(self):
        n2 = np.floor(self.tmax / (0.5*self.twindow))
        toffs = max(0, n2-1)  * 0.5*self.twindow
        if self.toffset < toffs:
            self.toffset = toffs
            return True
        return False

                
    def snap_time(self):
        twindow = 10.0 * 2**np.round(log(self.twindow/10.0)/log(2.0))
        toffset = np.round(self.toffset / (0.5*twindow)) * (0.5*twindow)
        if twindow != self.twindow or toffset != self.toffset:
            self.toffset = toffset
            self.twindow = twindow
            return True
        return False


    def set_amplitude_limits(self, ax):
        if np.isfinite(self.data.ampl_min) and np.isfinite(self.data.ampl_max):
            ax.setLimits(yMin=self.data.ampl_min, yMax=self.data.ampl_max,
                         minYRange=1/2**16,
                         maxYRange=self.data.ampl_max - self.data.ampl_min)


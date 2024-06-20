"""Class managing all raw data, spectrograms, filtered and derived data
and the time window shown.

"""

import numpy as np
from audioio import get_datetime
from thunderlab.dataloader import DataLoader
from .bufferedspectrogram import BufferedSpectrogram


class Data(object):

    def __init__(self, file_path, **kwargs):
        self.buffer_time = 60
        self.back_time = 20
        self.follow_time = 0
        self.file_path = file_path
        self.load_kwargs = kwargs
        self.data = None
        self.rate = None
        self.channels = 0
        self.start_time = None
        self.meta_data = {}
        self.tbefore = 0
        self.tafter = 0
        self.traces = []
        self.sources = []


    def add_trace(self, trace):
        self.traces.append(trace)


    def remove_trace(self, name):
        t = self[name]
        if t is not None:
            i = self.traces.index(t)
            del self.traces[i]


    def clear_traces(self):
        self.traces = []

        
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

            
    def __contains__(self, key):
        for trace in self.traces:
            if trace.name.lower() == key.lower():
                return True
        return False


    def keys(self):
        return [trace.name for trace in self.traces]


    def get_trace_names(self, class_name):
        traces = []
        for trace in self.traces:
            if isinstance(trace, class_name):
                traces.append(trace.name)
        return traces


    def is_visible(self, name):
        if name in self:
            for pi in self[name].plot_items:
                if pi is not None and pi.isVisible():
                    return True
        return False


    def set_visible(self, name, show):
        changed = False
        if name in self:
            for pi in self[name].plot_items:
                if pi is not None:
                    if pi.isVisible() != show:
                        changed = True
                    pi.setVisible(show)
        return changed

    
    def get_region(self, t0, t1, channel):
        traces = {}
        for t in self.traces:
            i0 = int(t0*t.rate)
            if i0 < 0:
                i0 = 0
            i1 = int(t1*t.rate) + 1
            if i1 > len(t):
                i1 = len(t)
            time = np.arange(i0, i1)/t.rate
            data = t[i0:i1, channel]
            if isinstance(t, BufferedSpectrogram):
                freqs = t.frequencies
                traces[t.name] = (time, freqs, data)
            else:
                traces[t.name] = (time, data)
        return traces
    
        
    def setup_traces(self):
        """ order trace sequence.
        """
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
            self.data = DataLoader(self.file_path, tbuffer, tback,
                                   **self.load_kwargs)
        except IOError:
            self.data = None
            return
        self.data.set_unwrap(unwrap, unwrap_clip, False, self.data.unit)
        self.data.follow = int(self.follow_time*self.data.rate)
        self.data.name = 'data'
        self.data.panel = 'trace'
        self.data.panel_type =  'trace'
        self.data.plot_items = [None]*self.data.channels
        self.data.color = '#0000ee'
        self.data.lw_thin = 1.1
        self.data.lw_thick = 2
        self.data.dests = []
        self.data.need_update = False
        self.traces.insert(0, self.data)
        self.sources = [None] + [i + 1 for i in self.sources]
        self.file_path = self.data.filepath
        self.rate = self.data.rate
        self.channels = self.data.channels
        # metadata:
        self.meta_data = dict(Format=self.data.format_dict())
        self.meta_data.update(self.data.metadata())
        self.start_time = get_datetime(self.meta_data)
        # derived data:
        for trace, source in zip(self.traces[1:], self.sources[1:]):
            trace.open(self.traces[source])
        self.set_need_update()

            
    def set_need_update(self):
        if self.data is None:
            return
        self.data.need_update = False
        for pi in self.data.plot_items:
            if pi is not None and pi.isVisible():
                self.data.need_update = True
                break
        for d in self.data.dests:
            d.set_need_update()

            
    def update_times(self, t0, t1):
        if self.data.need_update:
            self.data.update_time(t0 - self.tbefore,
                                  t1 + self.tafter)
        for trace in self.traces[1:]:
            if trace.need_update:
                trace.align_buffer()
        

"""Base class for computed data.
"""

from audioio import BufferedArray


class BufferedData(BufferedArray):

    def __init__(self, name, tbefore=0, tafter=0, verbose=0):
        self.name = name
        self.tbuffer = 0
        self.tbefore = 0
        self.tafter = 0
        self.source = None
        self.source_tbefore = tbefore
        self.source_tafter = tafter
        self.verbose = verbose


    def expand_times(self, tbefore, tafter):
        self.tbefore += tbefore
        self.tafter += tafter
        return self.source_tbefore + tbefore, self.source_tafter + tafter


    def update_step(self, buffer_time, back_time, step=1, more_shape=None):
        if step < 1:
            step = 1
        self.rate = self.source.rate/step
        self.frames = (self.source.frames + step - 1)//step
        if more_shape is None:
            self.shape = (self.frames, self.channels)
        else:
            self.shape = (self.frames, self.channels) + more_shape
        self.size = self.frames * self.channels
        if self.source.bufferframes == self.source.frames:
            self.bufferframes = self.frames
            self.backframes = 0
        else:
            self.bufferframes = int((buffer_time + self.tbefore + self.tafter)*self.rate)
            self.backframes = int((back_time + self.tbefore)*self.rate)
            print(f'setup {self.name}: buffer={self.bufferframes/self.rate:.3f}s,  source={self.source.bufferframes/self.source.rate:.3f}s')
        self.offset = self.source.offset//step

        
    def open(self, source, buffer_time, back_time, step=1, more_shape=None):
        self.source = source
        self.channels = self.source.channels
        self.update_step(buffer_time, back_time, step, more_shape)
        self.init_buffer()
        print(f'init {self.name}: {self.bufferframes/self.rate:.3f}s')

        
    def update_time(self, tstart, tstop):
        t0 = tstart - self.tbefore
        t1 = tstop + self.tafter
        print(f'update {self.name} {t0:.3f}s - {t1:.3f}s, buffer holds {self.offset/self.rate:.3f}s - {(self.offset + len(self.buffer))/self.rate:.3f}s')
        super().update_time(t0, t1)


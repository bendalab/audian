"""Base class for computed data.
"""

from audioio import BufferedArray


class BufferedData(BufferedArray):

    def __init__(self, name, tbefore=0, tafter=0, verbose=0):
        self.name = name
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


    def update_hop(self, hop=1, more_shape=None):
        self.rate = self.source.rate/hop
        self.frames = self.source.frames//hop
        if more_shape is None:
            self.shape = (self.frames, self.channels)
        else:
            self.shape = (self.frames, self.channels) + more_shape
        self.size = self.frames * self.channels
        if self.source.bufferframes == self.source.frames:
            self.bufferframes = self.source.bufferframes//hop
            self.backframes = self.source.backframes//hop
        else:
            self.bufferframes = (self.source.bufferframes -
                                 int((self.source_tbefore + self.source_tafter)*self.source.rate))//hop
            self.backframes = (self.source.backframes -
                           int(self.source_tbefore*self.source.rate))//hop
        self.offset = self.source.offset//hop

        
    def open(self, source, hop=1, more_shape=None):
        self.source = source
        self.channels = self.source.channels
        self.update_hop(hop, more_shape)
        self.init_buffer()

        
    def update_time(self, tstart, tstop):
        t0 = tstart - self.tbefore
        t1 = tstop + self.tafter
        super().update_time(t0, t1)


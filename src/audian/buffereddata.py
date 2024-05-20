"""Base class for computed data.
"""

import numpy as np
from audioio import BufferedArray


class BufferedData(BufferedArray):

    def __init__(self, name, tbefore=0, tafter=0):
        self.name = name
        self.tbefore = 0
        self.tafter = 0
        self.source = None
        self.source_tbefore = tbefore
        self.source_tafter = tafter
        self.verbose = 0


    def expand_times(self, tbefore, tafter):
        self.tbefore += tbefore
        self.tafter += tafter
        return self.source_tbefore + tbefore, self.source_tafter + tafter


    def update_step(self, step=1, more_shape=None):
        tbuffer = self.bufferframes/self.rate
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
        else:
            self.bufferframes = int(tbuffer*self.rate)
        self.offset = (self.source.offset + step - 1)//step

        
    def open(self, source, step=1, more_shape=None):
        self.source = source
        self.bufferframes = 0
        self.backframes = 0
        self.channels = self.source.channels
        self.rate = self.source.rate
        self.update_step(step, more_shape)
        self.init_buffer()

        
    def align_buffer(self):
        offset = self.source.offset
        nframes = len(self.source.buffer)
        if offset > 0:
            n = int(self.source_tbefore*self.source.rate)
            offset += n
            nframes -= n
        if self.source.offset + len(self.source.buffer) < self.source.frames:
            n = int(self.source_tafter*self.source.rate)
            nframes -= n
        offset = int(np.ceil(offset*self.rate/self.source.rate))
        nframes = int(np.floor(nframes*self.rate/self.source.rate))
        self.move_buffer(offset, nframes)
        self.bufferframes = len(self.buffer)


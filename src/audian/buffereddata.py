"""Base class for computed data.
"""

import numpy as np
from audioio import BufferedArray


class BufferedData(BufferedArray):

    def __init__(self, name, tbefore=0, tafter=0, verbose=0):
        self.name = name
        self.buffer_time = 0
        self.back_time = 0
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


    def update_step(self, step=1, more_shape=None):
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
            self.bufferframes = int((self.buffer_time + self.tbefore + self.tafter)*self.rate)
            self.backframes = int((self.back_time + self.tbefore)*self.rate)
        self.offset = (self.source.offset + step - 1)//step

        
    def open(self, source, buffer_time, back_time=0, step=1, more_shape=None):
        self.source = source
        self.buffer_time = buffer_time
        self.back_time = back_time
        self.channels = self.source.channels
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


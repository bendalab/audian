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
        self.ndim = len(self.shape)
        self.size = self.frames * self.channels
        if self.source.bufferframes == self.source.frames:
            self.bufferframes = self.frames
        else:
            self.bufferframes = int(tbuffer*self.rate)
        self.offset = (self.source.offset + step - 1)//step
        self.follow = 0

        
    def open(self, source, step=1, more_shape=None):
        self.source = source
        self.bufferframes = 0
        self.backframes = 0
        self.channels = self.source.channels
        self.rate = self.source.rate
        self.buffer_changed = np.zeros(self.channels, dtype=bool)
        self.buffer = np.zeros((0, self.channels))
        self.update_step(step, more_shape)

        
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


    def load_buffer(self, offset, nframes, buffer):
        print(f'load {self.name} {offset/self.rate:.3f} - {(offset + nframes)/self.rate:.3f}')
        # transform to rate of source buffer:
        soffset = int(offset*self.source.rate/self.rate)
        snframes = int(nframes*self.source.rate/self.rate)
        nbefore = int(self.source_tbefore/self.source.rate)
        soffset -= nbefore
        snframes += nbefore
        soffset -= self.source.offset
        if soffset < 0:
            snbefore += soffset
            snframes += soffset
            soffset = 0
        if soffset + snframes > len(self.source.buffer):
            snframes = len(self.source.buffer) - soffset
        source = self.source.buffer[soffset:soffset + snframes]
        self.process(source, buffer, nbefore)


    def recompute(self):
        if len(self.source.buffer) > 0:
            self.allocate_buffer()
        self.reload_buffer()
        
        


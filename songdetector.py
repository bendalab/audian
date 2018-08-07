#!/usr/bin/python

import sys
import os
import platform
import argparse
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.mlab as ml
import matplotlib.colors as mc
import matplotlib.widgets as widgets
import scipy.signal as sig
from audioio import PlayAudio, fade
from thunderfish.dataloader import load_data
from thunderfish.configfile import ConfigFile


###############################################################################
## filter and envelope:

def highpass_filter( rate, data, cutoff ) :
    nyq = 0.5*rate
    high = cutoff/nyq
    b, a = sig.butter( 4, high, btype='highpass' )
    ## w, h = sig.freqz(b, a)
    ## plt.semilogx(w, 20 * np.log10(abs(h)))
    ## plt.show()
    fdata = sig.lfilter( b, a, data )
    return fdata


def bandpass_filter(data, rate, lowf=5500.0, highf=7500.0):
    """
    Bandpass filter the signal.
    """
    nyq = 0.5*rate
    low = lowf/nyq
    high = highf/nyq
    b, a = sig.butter(1, [low, high], btype='bandpass')
    #fdata = sig.lfilter(b, a, data, axis=0)
    fdata = sig.filtfilt(b, a, data, axis=0)
    return fdata


def lowpass_filter(data, rate, freq=100.0):
    nyq = 0.5*rate
    low = freq/nyq
    b, a = sig.butter(1, low, btype='lowpass')
    fdata = sig.filtfilt(b, a, data, axis=0)
    return fdata


def envelope(data, rate, freq=100.0):
    nyq = 0.5*rate
    low = freq/nyq
    b, a = sig.butter(1, low, btype='lowpass')
    edata = 2.0*sig.filtfilt(b, a, data*data, axis=0)
    edata[edata<0.0] = 0.0
    envelope = np.sqrt(edata)*np.sqrt(2.0)
    #envelope = np.sqrt(data*data)*np.sqrt(2.0) # this is actually not bad for finding power!
    return envelope

# def running_std( rate, data ):
#def envelope( rate, data, freq=100.0 ):
#    #from scipy.signal import gaussian
#
#    # width
#    rstd_window_size_time = 1.0/freq  # s
#    rstd_window_size = int(rstd_window_size_time * rate)
#    # w = 1.0 * gaussian(rstd_window_size, std=rstd_window_size/7)
#    w = 1.0 * np.ones(rstd_window_size)
#    w /= np.sum(w)
#    rstd = (np.sqrt((np.correlate(data ** 2, w, mode='same') -
#                     np.correlate(data, w, mode='same') ** 2)).ravel()) * np.sqrt(2.)
#    return rstd

## histogram based threshold:
## def threshold_estimates(envelopes, fac=10.0):
##     maxe = np.max(envelopes)
##     threshs = []
##     for c in range(envelopes.shape[1]):
##         h, b = np.histogram(envelopes[:,c], bins=np.linspace(0.0, maxe, 1000))
##         ## if c == 0:
##         ##     plt.bar(b[:-1], h, width=np.diff(b))
##         ##     plt.show()
##         maxi = 2*(np.argmax(h)+1)
##         if maxi >= len(b):
##             maxi = len(b)
##         mean = np.mean(envelopes[envelopes[:,c]<b[maxi],c])
##         std = np.std(envelopes[envelopes[:,c]<b[maxi],c])
##         threshs.append(mean + fac*std)
##     return threshs

# std based threshold:
def threshold_estimates(envelopes, fac=1.0):
    threshs = np.mean(envelopes, axis=0) + fac*np.std(envelopes, axis=0)
    max_thresh = np.max(threshs)
    threshs = np.ones(len(threshs))*max_thresh
    return threshs

def detect_power(envelope, rate, threshold, min_duration):
    onsets = np.nonzero((envelope[1:]>threshold) & (envelope[:-1]<=threshold))[0]
    offsets = np.nonzero((envelope[1:]<=threshold) & (envelope[:-1]>threshold))[0]
    if len(onsets) == 0 or len(offsets) == 0:
        return np.array([]), np.array([])
    else:
        if offsets[0] < onsets[0] :
            offsets = offsets[1:]
        if len(onsets) != len(offsets):
            minlen = min(len(onsets), len(offsets))
            onsets = onsets[:minlen]
            offsets = offsets[:minlen]
        if len(onsets) == 0 or len(offsets) == 0:
            return np.array([]), np.array([])
        # merge songs:
        diff = (onsets[1:] - offsets[:-1])/rate
        indices = diff > min_duration
        onsets = onsets[np.hstack([True, indices])]
        offsets = offsets[np.hstack([indices, True])]
        # skip songs that are too short:
        diff = (offsets - onsets)/rate
        indices = diff > min_duration
        onsets = onsets[indices]
        offsets = offsets[indices]
    return np.array(onsets), np.array(offsets)


def detect_songs(envelopes, rate, thresholds, min_duration=0.1, thresh_fac=10.0, envelope_use_freq=True):
    songonsets = []
    songoffsets = []
    for c in range(envelopes.shape[1]):
        # corse detection of songs:
        onsets, offsets = detect_power(envelopes[:,c], rate, thresholds[c], min_duration)
        
        # refine detections:
        new_onsets = []
        new_offsets = []
        for k in range(len(onsets)):
            i0 = onsets[k]
            i1 = offsets[k]
            # enlarge song:
            w = (i1 - i0)//2
            ii0 = i0 - w if i0 >= w else 0
            if k > 0 and ii0 <= offsets[k-1]:
                ii0 = offsets[k-1]
            ii1 = i1 + w if i1 + w < len(envelopes[:,c]) else len(envelopes[:,c])
            if k < len(onsets)-1 and ii1 >= onsets[k+1]:
                ii1 = onsets[k+1]
            # window before song:
            m0 = ii0 - 2*w
            m1 = ii0
            if k > 0 and m0 < offsets[k-1] :
                m0 = offsets[k-1]
            if m0 < 0:
                m0 = 0
            if m1 - m0 < w:
                m1 = i0
            # window after song:
            n0 = ii1
            n1 = ii1 + 2*w
            if k < len(onsets)-1 and n1 > onsets[k+1]:
                n1 = onsets[k+1]
            if n1 > len(envelopes[:,c]):
                n1 = len(envelopes[:,c])
            if n1 - n0 < w:
                n0 = i1
            if envelope_use_freq:
                # spectrum of envelope:
                freq_resolution = 2.0
                min_nfft = 16
                n = rate / freq_resolution
                nfft = int(2 ** np.floor(np.log(n) / np.log(2.0) + 1.0-1e-8))
                if nfft < min_nfft:
                    nfft = min_nfft
                if nfft > ii1 - ii0 :
                    n = (ii1 - ii0)/2
                    nfft = int(2 ** np.floor(np.log(n) / np.log(2.0) + 1.0-1e-8))
                f, Pxx = sig.welch(envelopes[ii0:ii1,c], fs=rate, nperseg=nfft, noverlap=nfft//2, nfft=None)
                ipeak = np.argmax(Pxx)
                fpeak = f[np.argmax(Pxx)]
                ## Pdecibel = 10.0*np.log10(Pxx)
                ## plt.plot(f, Pdecibel)
                ## plt.scatter([fpeak], Pdecibel[ipeak])
                ## plt.xlim(0.0, 100.0)
                ## plt.ylim(np.min(Pdecibel[f<100.0]), np.max(Pdecibel[f<100.0])*0.95)
                ## plt.show()
                # lowpass filter on envelope:
                fcutoff = 4*fpeak
                envelopes[m0:n1,c] = lowpass_filter(envelopes[m0:n1,c], rate, fcutoff)
            # set threshold:
            thresh0 = np.mean(envelopes[m0:m1,c]) + thresh_fac*np.std(envelopes[m0:m1,c])
            thresh1 = np.mean(envelopes[n0:n1,c]) + thresh_fac*np.std(envelopes[n0:n1,c])
            thresh = max(thresh0, thresh1)
            if thresh > thresholds[c]:
                thresh = thresholds[c]
            # detect song:
            on, off = detect_power(envelopes[ii0:ii1,c], rate, thresh, min_duration)
            if len(on[on<=i0-ii0]) == 0 or len(off[off>=i1-ii0]) == 0:
                new_onsets.append(i0/rate)
                new_offsets.append(i1/rate)
            else:
                new_onsets.append((ii0+on[on<=i0-ii0][-1])/rate)
                new_offsets.append((ii0+off[off>=i1-ii0][0])/rate)
        songonsets.append(np.array(new_onsets))
        songoffsets.append(np.array(new_offsets))
    return songonsets, songoffsets

    
###############################################################################
## plotting etc.
    
class SignalPlot :
    def __init__(self, samplingrate, data, fdata, env, threshs, onsets, offsets, unit, filename, path, cfg) :
        self.filepath = ''
        if platform.system() == 'Windows' :
            self.filepath = path
        self.filename = filename
        self.rate = samplingrate
        self.data = data
        self.unit = unit
        self.time = np.arange( 0.0, self.data.shape[0] )/self.rate
        self.toffset = 0.0
        self.twindow = 60.0
        if self.twindow > self.time[-1] :
            self.twindow = np.round( 2**(np.floor(np.log(self.time[-1]) / np.log(2.0)) + 1.0) )
        self.lowpassfreq = cfg.value('lowpassfreq')
        self.highpassfreq = cfg.value('highpassfreq')
        self.fdata = fdata
        self.channels = data.shape[1]
        self.envelopecutofffreq = cfg.value('envelopecutofffreq')
        self.envelopeusefreq = cfg.value('envelopeusefreq')
        self.envelope = env
        self.thresholdfac = cfg.value('thresholdfactor')
        self.thresholds = threshs
        self.min_duration = cfg.value('minduration')
        self.noisethresholdfac = cfg.value('noisethresholdfactor')
        self.songonsets = onsets
        self.songoffsets = offsets
        self.trace_artists = []
        self.filtered_trace_artists = []
        self.envelope_artists = []
        self.threshold_artists = []
        self.songonset_artists = []
        self.songoffset_artists = []
        self.highpass_label = None
        self.lowpass_label = None
        self.envelope_label = None
        self.max_pixel = cfg.value('maxpixel')
        self.show_traces = cfg.value('displayTraces')
        self.show_filtered_traces = cfg.value('displayFilteredTraces')
        self.show_envelope = cfg.value('displayEnvelope')
        self.show_thresholds = True
        self.show_songonsets = True
        self.show_songoffsets = True
        self.help = cfg.value('displayHelp')
        self.helptext = []
        self.analysis_file = None

        # audio output:
        self.audio = PlayAudio()

        # set key bindings:
        #plt.rcParams['keymap.fullscreen'] = 'ctrl+f'
        plt.rcParams['keymap.fullscreen'] = ''
        plt.rcParams['keymap.pan'] = 'ctrl+m'
        plt.rcParams['keymap.quit'] = 'ctrl+w, alt+q, q'
        plt.rcParams['keymap.save'] = 'alt+s'
        plt.rcParams['keymap.yscale'] = ''
        plt.rcParams['keymap.xscale'] = ''
        plt.rcParams['keymap.grid'] = ''
        plt.rcParams['keymap.all_axes'] = ''
        
        # the figure:
        self.fig = plt.figure( figsize=( 15, 9 ) )
        self.fig.canvas.set_window_title( 'SongDetector: ' + self.filename )
        self.fig.canvas.mpl_connect( 'key_press_event', self.keypress )
        
        # trace plots:
        ph = 0.9/self.channels
        self.axt = []
        self.ymin = []
        self.ymax = []
        for c in range(self.channels):
            self.ymin.append( -1.0 )
            self.ymax.append( +1.0 )
            if np.min(self.data[:, c]) < -1.0 or np.max(self.data[:, c]) > +1.0 :
                self.ymin[c] = -10.0
                self.ymax[c] = +10.0
            if c == 0 :
                self.axt.append( self.fig.add_axes( [ 0.08, 0.06+(self.channels-c-1)*ph, 0.89, ph ] ) )
                self.highpass_label = self.axt[0].text( 0.05, 0.9, 'highpass=%.1fkHz' % (0.001*self.highpassfreq), transform=self.axt[0].transAxes )
                self.lowpass_label = self.axt[0].text( 0.2, 0.9, 'lowpass=%.1fkHz' % (0.001*self.lowpassfreq), transform=self.axt[0].transAxes )
                self.envelope_label = self.axt[0].text( 0.35, 0.9, 'envelope=%.0fHz' % self.envelopecutofffreq, transform=self.axt[0].transAxes )
            else:
                self.axt.append( self.fig.add_axes( [ 0.08, 0.08+(self.channels-c-1)*ph, 0.89, ph ], sharex=self.axt[0] ) )
            self.axt[-1].set_ylabel( 'Amplitude [{:s}]'.format( self.unit ) )
        self.axt[-1].set_xlabel( 'Time [s]' )
        """
        ht = self.axt.text( 0.98, 0.05, '(ctrl+) page and arrow up, down, home, end: scroll', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.15, '+, -, X, x: zoom in/out', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.25, 'y,Y,v,V: zoom amplitudes', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.35, 'p,P: play audio (display,all)', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.45, 'ctrl-f: full screen', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.65, 's: save figure', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.75, 'q: quit', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        ht = self.axt.text( 0.98, 0.85, 'h: toggle this help', ha='right', transform=self.axt.transAxes )
        self.helptext.append( ht )
        # plot:
        for ht in self.helptext :
            ht.set_visible( self.help )
        """
        self.update_plots( False )
        plt.show()

    def __del( self ) :
        if self.analysis_file != None :
            self.analysis_file.close()
        if self.audio is not None:
            self.audio.close()
            
    def update_plots( self, draw=True ) :
        # trace:
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        tstep = 1
        if self.max_pixel > 0 :
            tstep = int((t1-t0)//self.max_pixel)
            if tstep < 1 :
                tstep = 1
        for c in range(self.channels) :
            self.axt[c].set_xlim( self.toffset, self.toffset+self.twindow )
            self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
        if self.show_traces :
            append = len(self.trace_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.data[t0:t1:tstep, c], 'b', zorder=0 )
                    self.trace_artists.append( ta )
                else :
                    self.trace_artists[c].set_data( self.time[t0:t1:tstep], self.data[t0:t1:tstep, c] )
                self.trace_artists[c].set_visible(True)
        else :
            for c in range(len(self.trace_artists)) :
                self.trace_artists[c].set_visible(False)
        if self.show_filtered_traces :
            append = len(self.filtered_trace_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.fdata[t0:t1:tstep, c], 'g', zorder=1 )
                    self.filtered_trace_artists.append( ta )
                else :
                    self.filtered_trace_artists[c].set_data( self.time[t0:t1:tstep], self.fdata[t0:t1:tstep, c] )
                self.filtered_trace_artists[c].set_visible(True)
        else :
            for c in range(len(self.filtered_trace_artists)) :
                self.filtered_trace_artists[c].set_visible(False)
        if self.show_envelope :
            append = len(self.envelope_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.envelope[t0:t1:tstep, c], 'r', lw=2, zorder=2 )
                    self.envelope_artists.append( ta )
                else :
                    self.envelope_artists[c].set_data( self.time[t0:t1:tstep], self.envelope[t0:t1:tstep, c] )
                self.envelope_artists[c].set_visible(True)
        else :
            for c in range(len(self.envelope_artists)) :
                self.envelope_artists[c].set_visible(False)
        if self.show_thresholds :
            append = len(self.threshold_artists) == 0
            for c in range(self.channels) :
                tm = t1
                if tm >= len(self.time):
                    tm = len(self.time)-1
                if append :
                    ta, = self.axt[c].plot( [self.time[t0], self.time[tm]], [self.thresholds[c], self.thresholds[c]], 'k', zorder=3 )
                    self.threshold_artists.append( ta )
                else :
                    self.threshold_artists[c].set_data( [self.time[t0], self.time[tm]], [self.thresholds[c], self.thresholds[c]] )
                self.threshold_artists[c].set_visible(True)
        else :
            for c in range(len(self.threshold_artists)) :
                self.threshold_artists[c].set_visible(False)
        if self.show_songonsets :
            append = len(self.songonset_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.songonsets[c], self.thresholds[c]*np.ones(len(self.songonsets[c])), '.b', ms=10, zorder=4 )
                    self.songonset_artists.append( ta )
                else :
                    self.songonset_artists[c].set_data( self.songonsets[c], self.thresholds[c]*np.ones(len(self.songonsets[c])) )
                self.songonset_artists[c].set_visible(True)
        else :
            for c in range(len(self.songonset_artists)) :
                self.songonset_artists[c].set_visible(False)
        if self.show_songoffsets :
            append = len(self.songoffset_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.songoffsets[c], self.thresholds[c]*np.ones(len(self.songoffsets[c])), '.b', ms=10, zorder=5 )
                    self.songoffset_artists.append( ta )
                else :
                    self.songoffset_artists[c].set_data( self.songoffsets[c], self.thresholds[c]*np.ones(len(self.songoffsets[c])) )
                self.songoffset_artists[c].set_visible(True)
        else :
            for c in range(len(self.songoffset_artists)) :
                self.songoffset_artists[c].set_visible(False)
        
        if draw :
            self.fig.canvas.draw()
                 
    def keypress( self, event ) :
        if event.key in '+=X' :
            if self.twindow*self.rate > 20 :
                self.twindow *= 0.5
                self.update_plots()
        elif event.key in '-x' :
            if self.twindow < len( self.data )/self.rate :
                self.twindow *= 2.0
                self.update_plots()
        elif event.key == 'pagedown' :
            if self.toffset + 0.5*self.twindow < len( self.data )/self.rate :
                self.toffset += 0.5*self.twindow
                self.update_plots()
        elif event.key == 'pageup' :
            if self.toffset > 0 :
                self.toffset -= 0.5*self.twindow
                if self.toffset < 0.0 :
                    self.toffset = 0.0
                self.update_plots()
        elif event.key == 'ctrl+pagedown' :
            if self.toffset + 5.0*self.twindow < len( self.data )/self.rate :
                self.toffset += 5.0*self.twindow
                self.update_plots()
        elif event.key == 'ctrl+pageup' :
            if self.toffset > 0 :
                self.toffset -= 5.0*self.twindow
                if self.toffset < 0.0 :
                    self.toffset = 0.0
                self.update_plots()
        elif event.key == 'down' :
            if self.toffset + self.twindow < len( self.data )/self.rate :
                self.toffset += 0.05*self.twindow
                self.update_plots()
        elif event.key == 'up' :
            if self.toffset > 0.0 :
                self.toffset -= 0.05*self.twindow
                if self.toffset < 0.0 :
                    self.toffset = 0.0
                self.update_plots()
        elif event.key == 'home':
            if self.toffset > 0.0 :
                self.toffset = 0.0
                self.update_plots()
        elif event.key == 'end':
            toffs = np.floor( len( self.data )/self.rate / self.twindow ) * self.twindow
            if self.toffset < toffs :
                self.toffset = toffs
                self.update_plots()
        elif event.key == 'y':
            for c in range(self.channels):
                h = self.ymax[c] - self.ymin[c]
                v = 0.5*(self.ymax[c] + self.ymin[c])
                self.ymin[c] = v-h
                self.ymax[c] = v+h
                self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
            self.fig.canvas.draw()
        elif event.key == 'Y':
            for c in range(self.channels):
                h = 0.25*(self.ymax[c] - self.ymin[c])
                v = 0.5*(self.ymax[c] + self.ymin[c])
                self.ymin[c] = v-h
                self.ymax[c] = v+h
                self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
            self.fig.canvas.draw()
        elif event.key == 'v':
            for c in range(self.channels):
                min = np.min( self.fdata[:, c] )
                max = np.max( self.fdata[:, c] )
                h = 0.5*(max - min)
                v = 0.5*(max + min)
                self.ymin[c] = v-h
                self.ymax[c] = v+h
                self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
            self.fig.canvas.draw()
        elif event.key == 'V':
            for c in range(self.channels):
                self.ymin[c] = -1.0
                self.ymax[c] = +1.0
                self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
            self.fig.canvas.draw()
        elif event.key == 'ctrl+t' :
            self.show_traces = not self.show_traces
            if len(self.trace_artists) > 0 :
                for c in range(self.channels) :
                    self.trace_artists[c].set_visible( self.show_traces )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'ctrl+f' :
            self.show_filtered_traces = not self.show_filtered_traces
            if len(self.filtered_trace_artists) > 0 :
                for c in range(self.channels) :
                    self.filtered_trace_artists[c].set_visible( self.show_filtered_traces )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'ctrl+e' :
            self.show_envelope = not self.show_envelope
            if len(self.envelope_artists) > 0 :
                for c in range(self.channels) :
                    self.envelope_artists[c].set_visible( self.show_envelope )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'h' :
            self.highpassfreq /= 1.5
            self.highpass_label.set_text('highpass=%.1fkHz' % (0.001*self.highpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'H' :
            self.highpassfreq * 1.5
            self.highpass_label.set_text('highpass=%.1fkHz' % (0.001*self.highpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'l' :
            self.lowpassfreq /= 1.5
            self.lowpass_label.set_text('lowpass=%.1fkHz' % (0.001*self.lowpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'L' :
            self.lowpassfreq * 1.5
            self.lowpass_label.set_text('lowpass=%.1fkHz' % (0.001*self.lowpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'e' :
            self.envelopecutofffreq /= 1.5
            self.envelope_label.set_text('envelope=%.0fHz' % self.envelopecutofffreq)
            self.envelope = envelope(self.fdata, self.rate, self.envelopecutofffreq )
            self.songonsets, self.songoffsets = detect_songs(self.envelope, self.rate, self.thresholds, envelope_use_freq=self.envelopeusefreq)
            self.update_plots()
        elif event.key == 'E' :
            self.envelopecutofffreq *= 1.5
            self.envelope_label.set_text('envelope=%.0fHz' % self.envelopecutofffreq)
            self.envelope = envelope(self.fdata, self.rate, self.envelopecutofffreq )
            self.songonsets, self.songoffsets = detect_songs(self.envelope, self.rate, self.thresholds, envelope_use_freq=self.envelopeusefreq)
            self.update_plots()
#        elif event.key in 'h' :
#            self.help = not self.help
#            for ht in self.helptext :
#                ht.set_visible( self.help )
#            self.fig.canvas.draw()
        elif event.key in 'w' :
            self.plot_waveform()
        elif event.key in 'p' :
            self.play_segment()
        elif event.key in 'P' :
            self.play_all()

    def plot_waveform( self ) :
        fig = plt.figure()
        ax = fig.add_subplot( 1, 1, 1 )
        name = os.path.splitext( self.filename )[0]
        ax.set_title( self.filename )
        figfile = '{name}-{time:.4g}s-waveform.png'.format( name=name, time=self.toffset )
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        if self.twindow < 1.0 :
            ax.set_xlabel( 'Time [ms]' )
            ax.set_xlim( 1000.0*self.toffset,
                         1000.0*(self.toffset+self.twindow) )
            ax.plot( 1000.0*self.time[t0:t1], self.data[t0:t1], 'b' )
            if self.show_envelope :
                ax.plot( 1000.0*self.time[t0:t1], self.envelope[t0:t1], 'r' )
        else :
            ax.set_xlabel( 'Time [s]' )
            ax.set_xlim( self.toffset, self.toffset+self.twindow )
            ax.plot( self.time[t0:t1], self.data[t0:t1], 'b' )
            if self.show_envelope :
                ax.plot( self.time[t0:t1], self.envelope[t0:t1], 'r' )
        ax.set_ylabel( 'Amplitude [{:s}]'.format( self.unit ) )
        fig.tight_layout()
        # on linux the following is not what you want! You want to save this into the current working directory!!!
        fig.savefig( os.path.join( self.filepath, figfile ) )
        fig.clear()
        plt.close( fig )
        print('saved waveform figure to %s' % figfile)

    def play_segment( self ) :
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        playdata = 1.0*np.mean(self.fdata[t0:t1,:], axis=1)
        playdata -= np.mean(playdata)
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        
    def play_all( self ) :
        playdata = np.mean(self.fdata, axis=1)
        playdata -= np.mean(playdata)
        self.audio.play(np.mean(self.data, axis=1), self.rate, blocking=False)
                    

def main():
    # config file name:
    prog, ext = os.path.splitext( sys.argv[0] )
    cfgfile = prog + '.cfg'

    # command line arguments:
    parser = argparse.ArgumentParser(description='Detect songs in multitrace time series data.', epilog='by Jan Benda (2018)')
    parser.add_argument('--version', action='version', version='1.0')
    parser.add_argument('-v', action='count', dest='verbose', help='print debug information' )
    parser.add_argument('-c', '--save-config', nargs='?', default='', const=cfgfile, type=str, metavar='cfgfile', help='save configuration to file cfgfile (defaults to {0})'.format(cfgfile))
    parser.add_argument('file', nargs='?', default='', type=str, help='name of the files with the time series data')
    args = parser.parse_args()

    # set configuration from command line:
    verbose = 0
    if args.verbose != None:
        verbose = args.verbose
    
    # configuration options:
    cfg = ConfigFile()

    cfg.add_section('Plotting:')
    cfg.add('maxpixel', 50000, '', 'Either maximum number of data points to be plotted or zero for plotting all data points.')

    cfg.add_section('Filter:')
    cfg.add('highpassfreq', 1000.0, 'Hz', 'Cutoff frequency of the high-pass filter applied to the signal.')
    cfg.add('lowpassfreq', 10000.0, 'Hz', 'Cutoff frequency of the low-pass filter applied to the signal.')

    cfg.add_section('Envelope:')
    cfg.add('envelopecutofffreq', 500.0, 'Hz', 'Cutoff frequency of the low-pass filter used for computing the envelope from the squared signal.')
    cfg.add('envelopeusefreq', True, '', 'Apply lowpass filter to song envelope with cutoff determined from main peak in envelope spectrum.')

    cfg.add_section('Thresholds:')
    cfg.add('thresholdfactor', 1.0, '', 'Factor that multiplies the standard deviation of the whole envelope.')
    cfg.add('noisethresholdfactor', 12.0, '', 'Factor that multiplies the standard deviation of the noise envelope.')

    cfg.add_section('Detection:')
    cfg.add('minduration', 0.4, 's', 'Minimum duration of an detected song.')

    cfg.add_section('Items to display:')
    cfg.add('displayHelp', False, '', 'Display help on key bindings' )
    cfg.add('displayTraces', False, '', 'Display the raw data traces' )
    cfg.add('displayFilteredTraces', True, '', 'Display the filtered data traces' )
    cfg.add('displayEnvelope', True, '', 'Display the envelope' )

    # load configuration from working directory and data directories:
    filepath = args.file
    cfg.load_files(cfgfile, filepath, 3, verbose)

    # save configuration:
    if len(args.save_config) > 0:
        ext = os.path.splitext(args.save_config)[1]
        if ext != os.extsep + 'cfg':
            print('configuration file name must have .cfg as extension!')
        else:
            print('write configuration to %s ...' % args.save_config)
            cfg.dump(args.save_config)
        return

    # load data:
    data, rate, unit = load_data(filepath)

    # process data:
    fdata = bandpass_filter(data, rate, cfg.value('highpassfreq'), cfg.value('lowpassfreq'))
    env = envelope(fdata, rate, cfg.value('envelopecutofffreq'))
    threshs = threshold_estimates(env, cfg.value('thresholdfactor'))
    onsets, offsets = detect_songs(env, rate, threshs, cfg.value('minduration'), cfg.value('noisethresholdfactor'), cfg.value('envelopeusefreq'))
    
    # plot:
    sp = SignalPlot(rate, data, fdata, env, threshs, onsets, offsets, unit, filepath, os.path.dirname(filepath), cfg)

if __name__ == '__main__':
    main()

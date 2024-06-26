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
import scipy.stats as stats
from audioio import PlayAudio, fade
from thunderlab.dataloader import load_data
from thunderlab.configfile import ConfigFile
from thunderlab.eventdetection import threshold_crossings, merge_events
from thunderlab.eventdetection import remove_events, widen_events
from thunderlab.powerspectrum import peak_freqs


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
    envrate = freq*10
    if envrate > rate:
        envrate = rate
    step = int(np.round(rate / envrate))
    envelope = np.sqrt(edata[::step])*np.sqrt(2.0)
    #envelope = np.sqrt(data*data)*np.sqrt(2.0) # this is actually not bad for finding power!
    return envelope, rate/step

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

# histogram based threshold:
def threshold_estimates(envelopes, fac=10.0):
    maxe = np.max(envelopes)
    threshs = []
    for c in range(envelopes.shape[1]):
        h, b = np.histogram(envelopes[:,c], bins=np.linspace(0.0, maxe, 50))
        mini = np.nonzero(h>0)[0][0]
        maxi = np.argmax(h)+1
        w = maxi - mini
        maxi = maxi + w
        if maxi >= len(b):
            maxi = len(b)-1
        lower = envelopes[envelopes[:,c]<b[maxi],c]
        mean = np.mean(lower)
        std = np.std(lower)
        #threshs.append(mean + fac*std)

        # XXX improve (and proof) this:
        upper = envelopes[envelopes[:,c]>mean+3.0*std,c]
        uppermean = np.mean(upper)
        if uppermean > mean + 6.0*std:
            threshs.append(0.5*(mean + uppermean))
        else:
            threshs.append(maxe + std)

        ## peaks = sig.find_peaks(envelopes[:,c])[0]  # scipy 1.1
        ## h, b = np.histogram(envelopes[peaks,c], bins=np.linspace(0.0, np.max(envelopes[:,c]), 100))
        ## plt.bar(b[:-1], h, width=np.diff(b))
        ## plt.plot([mean, mean], [0, np.max(h)], 'k', lw=2)
        ## plt.plot([mean+std, mean+std], [0, np.max(h)], 'g', lw=2)
        ## plt.plot([threshs[-1], threshs[-1]], [0, np.max(h)], 'r', lw=2)
        ## plt.show()
    return threshs

## # std based threshold:
## def threshold_estimates(envelopes, fac=1.0):
##     # CV < 0.5: no songs!
##     for k in range(envelopes.shape[1]):
##         print('cv: %g' % (np.std(envelopes[:,k])/np.mean(envelopes[:,k])))
##     threshs = np.mean(envelopes, axis=0) + fac*np.std(envelopes, axis=0)
##     max_thresh = np.max(threshs)
##     threshs = np.ones(len(threshs))*max_thresh
##     return threshs


def detect_songs(envelopes, rate, thresholds, min_duration=0.1):
    """Detect crossings of the envelope over a threshold."""
    songonsets = []
    songoffsets = []
    for c in range(envelopes.shape[1]):
        onsets, offsets = threshold_crossings(envelopes[:,c], thresholds[c])
        # merge songs (because envelope could wiggle around threshold):
        onsets, offsets = merge_events(onsets, offsets, int(min_duration*rate))
        # skip songs that are too short:
        onsets, offsets = remove_events(onsets, offsets, int(min_duration*rate))
        # store:
        songonsets.append(onsets)
        songoffsets.append(offsets)
    return songonsets, songoffsets


def env_freqs(onsets, offsets, envelopes, rate, freq_resolution=1.0, min_nfft=16, thresh=10.0):
    """Return list of peak frequencies of the data snippets"""
    freqs = []
    # for all traces:
    for c in range(envelopes.shape[1]):
        freqs.append(peak_freqs(onsets[c], offsets[c], envelopes[:,c], rate, freq_resolution, min_nfft, thresh))
    return freqs


def clean_env_freqs(onsets, offsets, freqs, fac=6.0):
    """remove songs with undefined or outlier envelope frequencies."""
    # check for outliers:
    ffreqs = np.concatenate(freqs)
    if len(ffreqs) == 0:
        return onsets, offsets, freqs
    lq, uq = np.percentile(ffreqs, [25.0, 75.0])
    cfreqs = ffreqs[(~np.isnan(ffreqs))&(ffreqs>=lq)&(ffreqs<=uq)]
    m = np.mean(cfreqs)
    s = np.std(cfreqs)
    for c in range(len(freqs)):
        freqs[c][(~np.isnan(freqs[c]))&((freqs[c]<m-fac*s)|(freqs[c]>m+fac*s))] = float('NaN')
    # remove songs:
    new_onsets = []
    new_offsets = []
    new_freqs = []
    for c in range(len(onsets)):
        new_onsets.append(onsets[c][~np.isnan(freqs[c])])
        new_offsets.append(offsets[c][~np.isnan(freqs[c])])
        new_freqs.append(freqs[c][~np.isnan(freqs[c])])
    return new_onsets, new_offsets, new_freqs


def filter_envelopes(onsets, offsets, freqs, envelopes, rate, min_duration=0.1, mode='apply'):
    if mode == 'apply':
        for c in range(envelopes.shape[1]):
            on_indices, off_indices = widen_events(onsets[c], offsets[c],
                                                   len(envelopes[:,c]), 2.0*min_duration*rate)
            for on_idx, off_idx, fcutoff in zip(on_indices, off_indices, freqs[c]):
                if not np.isnan(fcutoff):
                    # lowpass filter on envelope:
                    envelopes[on_idx:off_idx,c] = lowpass_filter(envelopes[on_idx:off_idx,c],
                                                                 rate, 4.0*fcutoff)
    elif mode == 'average':
        if (~np.isnan(freqs)).sum() > 0:
            # lowpass filter on envelope:
            fcutoff = np.nanmean(freqs)
            envelopes[:,:] = lowpass_filter(envelopes[:,:], rate, 4.0*fcutoff)
        

def analyse_songs(onsets, offsets, envelopes, rate, envfreqs, thresholds, min_duration=0.1, min_thresh_fac=1.0):
    songonsets = []
    songoffsets = []
    w = int(min_duration*rate)
    for c in range(envelopes.shape[1]):
        wide_onsets, wide_offsets = widen_events(onsets[c], offsets[c],
                                                 len(envelopes[:,c]), w)
        noise_onsets, noise_offsets = widen_events(onsets[c], offsets[c],
                                                   len(envelopes[:,c]), 2*w)
        prev_wideoff = 0
        thresh0 = thresholds[c]
        thresh1 = thresholds[c]
        new_onsets = []
        new_offsets = []
        for noiseon, wideon, songon, songoff, wideoff, noiseoff, next_wideon, fcutoff in zip(noise_onsets, wide_onsets, onsets[c], offsets[c], wide_offsets, noise_offsets, np.hstack((wide_onsets[1:], len(envelopes[c]))), envfreqs[c]):
            # if no peak frequency, then remove this song:
            if np.isnan(fcutoff):
                print('removed channel %d time %g because of missing envelope frequency' % (c, songon/rate))
                prev_wideoff = wideoff
                continue
            # adjust window before song:
            if wideon-noiseon < w:
                noiseon = wideon-w
                if noiseon < prev_wideoff:
                    noiseon = prev_wideoff
            # adjust window after song:
            if noiseoff-wideoff < w:
                noiseoff = wideoff+w
                if noiseoff > next_wideon:
                    noiseoff = next_wideon
            # set threshold:
            if wideon - noiseon > w/2:
                thresh0 = np.max(envelopes[noiseon:wideon,c])*1.2
            if noiseoff - wideoff > w/2:
                thresh1 = np.max(envelopes[wideoff:noiseoff,c])*1.2
            thresh = max(thresh0, thresh1)
            if thresh < min_thresh_fac*thresholds[c]:
                thresh = min_thresh_fac*thresholds[c]
            # redetect song on fast envelope:
            on, off = threshold_crossings(envelopes[wideon:wideoff,c], thresh)
            # store song:
            if len(on) > 0 and len(off) > 0:
                new_onsets.append(wideon+on[0])
                new_offsets.append(wideon+off[-1])
            # analyse song:
            # ...
            prev_wideoff = wideoff
        songonsets.append(np.array(new_onsets))
        songoffsets.append(np.array(new_offsets))
    return songonsets, songoffsets

    
###############################################################################
## plotting etc.
    
class SignalPlot :
    def __init__(self, samplingrate, data, fdata, env, slowenv, envrate, threshs, onsets, offsets, unit, filename, path, cfg) :
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
        self.envelopefilter = cfg.value('envelopefilter')
        self.envelope = env
        self.slowenvelope = slowenv
        self.envrate = envrate
        self.thresholdfac = cfg.value('thresholdfactor')
        self.thresholds = threshs
        self.min_duration = cfg.value('minduration')
        self.songonsets = onsets
        self.songoffsets = offsets
        self.trace_artists = []
        self.filtered_trace_artists = []
        self.envelope_artists = []
        self.slowenvelope_artists = []
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
        self.show_slowenvelope = cfg.value('displaySlowEnvelope')
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

    def __del__( self ) :
        if self.analysis_file != None :
            self.analysis_file.close()
        if self.audio is not None:
            self.audio.close()
            
    def update_plots( self, draw=True ) :
        # time window:
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
        # raw trace:
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
        # filtered trace:
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
        # fast envelope:
        if self.show_envelope :
            et0 = int(np.round(self.toffset*self.envrate))
            et1 = int(np.round((self.toffset+self.twindow)*self.envrate))
            etstep = int(np.round(tstep*self.rate/self.envrate))
            etime = self.time[t0:t1+etstep:etstep][:len(self.envelope[et0:et1:tstep, c])]
            append = len(self.envelope_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( etime, self.envelope[et0:et1:tstep, c], 'r', lw=2, zorder=2 )
                    self.envelope_artists.append( ta )
                else :
                    self.envelope_artists[c].set_data( etime, self.envelope[et0:et1:tstep, c] )
                self.envelope_artists[c].set_visible(True)
        else :
            for c in range(len(self.envelope_artists)) :
                self.envelope_artists[c].set_visible(False)
        # slow envelope:
        if self.show_slowenvelope :
            et0 = int(np.round(self.toffset*self.envrate))
            et1 = int(np.round((self.toffset+self.twindow)*self.envrate))
            etstep = int(np.round(tstep*self.rate/self.envrate))
            etime = self.time[t0:t1+etstep:etstep][:len(self.slowenvelope[et0:et1:tstep, c])]
            append = len(self.slowenvelope_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( etime, self.slowenvelope[et0:et1:tstep, c], 'c', lw=2, zorder=3 )
                    self.slowenvelope_artists.append( ta )
                else :
                    self.slowenvelope_artists[c].set_data( etime, self.slowenvelope[et0:et1:tstep, c] )
                self.slowenvelope_artists[c].set_visible(True)
        else :
            for c in range(len(self.slowenvelope_artists)) :
                self.slowenvelope_artists[c].set_visible(False)
        # thresholds:
        if self.show_thresholds :
            append = len(self.threshold_artists) == 0
            for c in range(self.channels) :
                tm = t1
                if tm >= len(self.time):
                    tm = len(self.time)-1
                if append :
                    ta, = self.axt[c].plot( [self.time[t0], self.time[tm]], [self.thresholds[c], self.thresholds[c]], 'k', zorder=4 )
                    self.threshold_artists.append( ta )
                else :
                    self.threshold_artists[c].set_data( [self.time[t0], self.time[tm]], [self.thresholds[c], self.thresholds[c]] )
                self.threshold_artists[c].set_visible(True)
        else :
            for c in range(len(self.threshold_artists)) :
                self.threshold_artists[c].set_visible(False)
        # song onsets:
        if self.show_songonsets :
            append = len(self.songonset_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot(self.songonsets[c]/self.envrate, self.thresholds[c]*np.ones(len(self.songonsets[c])), '.b', ms=10, zorder=5)
                    self.songonset_artists.append(ta)
                else :
                    self.songonset_artists[c].set_data(self.songonsets[c]/self.envrate, self.thresholds[c]*np.ones(len(self.songonsets[c])))
                self.songonset_artists[c].set_visible(True)
        else :
            for c in range(len(self.songonset_artists)) :
                self.songonset_artists[c].set_visible(False)
        # song offsets:
        if self.show_songoffsets :
            append = len(self.songoffset_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot(self.songoffsets[c]/self.envrate, self.thresholds[c]*np.ones(len(self.songoffsets[c])), '.b', ms=10, zorder=6)
                    self.songoffset_artists.append(ta)
                else :
                    self.songoffset_artists[c].set_data(self.songoffsets[c]/self.envrate, self.thresholds[c]*np.ones(len(self.songoffsets[c])))
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
                fdmin = np.min( self.fdata[:, c] )
                fdmax = np.max( self.fdata[:, c] )
                #h = 0.5*(fdmax - fdmin)
                #v = 0.5*(fdmax + fdmin)
                #self.ymin[c] = v-h
                #self.ymax[c] = v+h
                m = max(-fdmin, fdmax)
                self.ymin[c] = -m
                self.ymax[c] = m
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
            self.envelope, self.envrate = envelope(self.fdata, self.rate, self.envelopecutofffreq)
            self.songonsets, self.songoffsets = detect_songs(self.slowenvelope, self.envrate, self.thresholds, min_duration=self.min_duration)
            self.songonsets, self.songoffsets = refine_detection(self.songonsets, self.songoffsets, self.envelope, self.envrate, self.thresholds, min_duration=self.min_duration, envelope_use_freq=self.envelopeusefreq)
            self.update_plots()
        elif event.key == 'E' :
            self.envelopecutofffreq *= 1.5
            self.envelope_label.set_text('envelope=%.0fHz' % self.envelopecutofffreq)
            self.envelope, self.envrate = envelope(self.fdata, self.rate, self.envelopecutofffreq)
            self.songonsets, self.songoffsets = detect_songs(self.slowenvelope, self.envrate, self.thresholds)
            self.songonsets, self.songoffsets = refine_detection(self.songonsets, self.songoffsets, self.envelope, self.envrate, self.thresholds, min_duration=self.min_duration, envelope_use_freq=self.envelopeusefreq)
            self.update_plots()
#        elif event.key in 'h' :
#            self.help = not self.help
#            for ht in self.helptext :
#                ht.set_visible( self.help )
#            self.fig.canvas.draw()
        elif event.key in 'w' :
            self.plot_waveform()
        elif event.key in 'p' :
            self.play_segment(self.fdata)
        elif event.key in 'P' :
            self.play_segment(self.data)
            #self.play_all()

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

    def play_segment(self, data) :
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        playdata = 1.0*np.mean(data[t0:t1,:], axis=1)
        playdata -= np.mean(playdata)
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        
    def play_all(self) :
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
    cfg.add('envelopepeakthresh', 10.0, 'dB', 'Minimum required height of peak in envelope.')
    cfg.add('envelopefilter', 'apply', '', 'Apply lowpass filter to envelope with cutoff determined from main peak in envelope spectrum for each event (apply), filter envelopes with the average peak frequency (average), or do not filter envelope (none).')

    cfg.add_section('Thresholds:')
    cfg.add('thresholdfactor', 8.0, '', 'Factor that multiplies the standard deviation of the whole envelope.')
    cfg.add('minthreshfac', 1.0, '', 'In the final analysis the local threshold must be larger than this factor times the global threshold.')

    cfg.add_section('Detection:')
    cfg.add('minduration', 0.5, 's', 'Minimum duration of an detected song.')

    cfg.add_section('Items to display:')
    cfg.add('displayHelp', False, '', 'Display help on key bindings' )
    cfg.add('displayTraces', False, '', 'Display the raw data traces' )
    cfg.add('displayFilteredTraces', True, '', 'Display the filtered data traces' )
    cfg.add('displayEnvelope', True, '', 'Display the envelope' )
    cfg.add('displaySlowEnvelope', True, '', 'Display slow envelope' )

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
    if verbose > 0: print('load data ...')
    data, rate, unit = load_data(filepath)

    # process data:
    if verbose > 0: print('apply bandpass filter ...')
    fdata = bandpass_filter(data, rate, cfg.value('highpassfreq'), cfg.value('lowpassfreq'))
    if verbose > 0: print('compute envelope ...')
    env, envrate = envelope(fdata, rate, cfg.value('envelopecutofffreq'))
    if verbose > 0: print('apply low-pass filter to envelope ...')
    slowenv = lowpass_filter(env, envrate, 1.0/cfg.value('minduration'))
    if verbose > 0: print('estimate thresholds ...')
    threshs = threshold_estimates(slowenv, cfg.value('thresholdfactor'))
    if verbose > 0: print('detect songs ...')
    onsets, offsets = detect_songs(slowenv, envrate, threshs, cfg.value('minduration'))
    if verbose > 0: print('compute envelope frequencies ...')
    envfreqs = env_freqs(onsets, offsets, env, envrate, thresh=cfg.value('envelopepeakthresh'))
    if verbose > 0: print('clean envelope frequencies ...')
    onsets, offsets, envfreqs = clean_env_freqs(onsets, offsets, envfreqs)
    if verbose > 0: print('filter envelope (%s) ...' % cfg.value('envelopefilter'))
    filter_envelopes(onsets, offsets, envfreqs, env, envrate, cfg.value('minduration'), cfg.value('envelopefilter'))
    if verbose > 0: print('analyse songs ...')
    onsets, offsets = analyse_songs(onsets, offsets, env, envrate, envfreqs, threshs, cfg.value('minduration'), cfg.value('minthreshfac'))
    if verbose > 0: print('plot ...')
    
    # plot:
    sp = SignalPlot(rate, data, fdata, env, slowenv, envrate, threshs, onsets, offsets, unit, filepath, os.path.dirname(filepath), cfg)

if __name__ == '__main__':
    main()

# python ~/prj/audian/songdetector.py -v 2017-08-05-ad/info.dat # data/slovenia/2017/distance-cages
# crosstalk in front of songs in trace 0: 142.5 251.5

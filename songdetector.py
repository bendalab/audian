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
from collections import OrderedDict
from audioio import PlayAudio, fade
from thunderfish.dataloader import load_data
    
cfg = OrderedDict()
cfgsec = dict()

cfgsec['maxpixel'] = 'Plotting:'
cfg['maxpixel'] = [ 0, '', 'Either maximum number of data points to be plotted or zero for plotting all data points.' ]

cfgsec['highpassfreq'] = 'Filter:'
cfg['highpassfreq'] = [ 1000.0, 'Hz', 'Cutoff frequency of the high-pass filter applied to the signal.' ]
cfg['lowpassfreq'] = [ 10000.0, 'Hz', 'Cutoff frequency of the low-pass filter applied to the signal.' ]

cfgsec['envfastcutofffreq'] = 'Envelope:'
cfg['envfastcutofffreq'] = [ 100.0, 'Hz', 'Cutoff frequency of the low-pass filter used for computing the fast envelope from the squared signal.' ]
cfg['envslowcutofffreq'] = [ 5.0, 'Hz', 'Cutoff frequency of the low-pass filter used for computing the slow envelope from the squared signal.' ]

cfgsec['verboseLevel'] = 'Debugging:'
cfg['verboseLevel'] = [ 0, '', '0=off upto 4 very detailed' ]

cfgsec['displayHelp'] = 'Items to display:'
cfg['displayTraces'] = [ False, '', 'Display the raw data traces' ] 
cfg['displayFilteredTraces'] = [ True, '', 'Display the filtered data traces' ] 
cfg['displayFastEnvelope'] = [ True, '', 'Display the fast envelope' ] 
cfg['displaySlowEnvelope'] = [ True, '', 'Display the slow envelope' ] 
cfg['displayHelp'] = [ False, '', 'Display help on key bindings' ] 


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
    b, a = sig.butter(2, [low, high], btype='bandpass')
    #fdata = sig.lfilter(b, a, data, axis=0)
    fdata = sig.filtfilt(b, a, data, axis=0)
    return fdata


def envelope( data, rate, freq=100.0 ):
    nyq = 0.5*rate
    low = freq/nyq
    b, a = sig.butter( 2, low, btype='lowpass' )
    edata = 2.0*sig.filtfilt( b, a, data*data, axis=0 )
    edata[edata<0.0] = 0.0
    envelope = np.sqrt( edata )*np.sqrt(2.0)
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

###############################################################################
## configuration file writing and loading:

def dump_config( filename, cfg, sections=None, header=None, maxline=60 ) :
    """
    Pretty print non-nested dicionary cfg into file.

    The keys of the dictionary are strings.
    
    The values of the dictionary can be single variables or lists:
    [value, unit, comment]
    Both unit and comment are optional.

    value can be any type of variable.

    unit is a string (that can be empty).
    
    Comments comment are printed out right before the key-value pair.
    Comments are single strings. Newline characters are intepreted as new paragraphs.
    Lines are folded if the character count exceeds maxline.

    Section comments can be added by the sections dictionary.
    It contains comment strings as values that are inserted right
    before the key-value pair with the same key. Section comments
    are formatted in the same way as comments for key-value pairs,
    but get two comment characters prependend ('##').

    A header can be printed initially. This is a simple string that is formatted
    like the section comments.

    Args:
        filename: The name of the file for writing the configuration.
        cfg (dict): Configuration keys, values, units, and comments.
        sections (dict): Comments describing secions of the configuration file.
        header (string): A string that is written as an introductory comment into the file.
        maxline (int): Maximum number of characters that fit into a line.
    """

    def write_comment( f, comment, maxline=60, cs='#' ) :
        # format comment:
        if len( comment ) > 0 :
            for line in comment.split( '\n' ) :
                f.write( cs + ' ' )
                cc = len( cs ) + 1  # character count
                for w in line.strip().split( ' ' ) :
                    # line too long?
                    if cc + len( w ) > maxline :
                        f.write( '\n' + cs + ' ' )
                        cc = len( cs ) + 1
                    f.write( w + ' ' )
                    cc += len( w ) + 1
                f.write( '\n' )
    
    with open( filename, 'w' ) as f :
        if header != None :
            write_comment( f, header, maxline, '##' )
        maxkey = 0
        for key in cfg.keys() :
            if maxkey < len( key ) :
                maxkey = len( key )
        for key, v in cfg.items() :
            # possible section entry:
            if sections != None and key in sections :
                f.write( '\n\n' )
                write_comment( f, sections[key], maxline, '##' )

            # get value, unit, and comment from v:
            val = None
            unit = ''
            comment = ''
            if hasattr(v, '__len__') and (not isinstance(v, str)) :
                val = v[0]
                if len( v ) > 1 :
                    unit = ' ' + v[1]
                if len( v ) > 2 :
                    comment = v[2]
            else :
                val = v

            # next key-value pair:
            f.write( '\n' )
            write_comment( f, comment, maxline, '#' )
            f.write( '{key:<{width}s}: {val}{unit:s}\n'.format( key=key, width=maxkey, val=val, unit=unit ) )


def load_config( filename, cfg ) :
    """
    Set values of dictionary cfg to values from key-value pairs read in from file.
    
    Args:
        filename: The name of the file from which to read in the configuration.
        cfg (dict): Configuration keys, values, units, and comments.
    """
    with open( filename, 'r' ) as f :
        for line in f :
            # do not process empty lines and comments:
            if len( line.strip() ) == 0 or line[0] == '#' or not ':' in line :
                continue
            key, val = line.split(':', 1)
            key = key.strip()
            if not key in cfg :
                continue
            cv = cfg[key]
            vals = val.strip().split( ' ' )
            if hasattr(cv, '__len__') and (not isinstance(cv, str)) :
                unit = ''
                if len( vals ) > 1 :
                    unit = vals[1]
                if unit != cv[1] :
                    print('unit for %s is %s but should be %s' % (key, unit, cv[1]))
                cv[0] = type(cv[0])(vals[0])
            else :
                cfg[key] = type(cv)(vals[0])
            

###############################################################################
## peak detection:

def detect_peaks( time, data, threshold, check_func=None, check_conditions=None ):

    if not check_conditions:
        check_conditions = dict()
        
    event_list = list()

    # initialize:
    dir = 0
    min_inx = 0
    max_inx = 0
    min_value = data[0]
    max_value = min_value
    trough_inx = 0

    # loop through the new read data
    for index, value in enumerate(data):

        # rising?
        if dir > 0:
            # if the new value is bigger than the old maximum: set it as new maximum
            if max_value < value:
                max_inx = index  # maximum element
                max_value = value

            # otherwise, if the maximum value is bigger than the new value plus the threshold:
            # this is a local maximum!
            elif max_value >= value + threshold:
                # there was a peak:
                event_inx = max_inx

                # check and update event with this magic function
                if check_func:
                    r = check_func( time, data, event_inx, index, trough_inx, min_inx, threshold, check_conditions )
                    if len( r ) > 0 :
                        # this really is an event:
                        event_list.append( r )
                else:
                    # this really is an event:
                    event_list.append( time[event_inx] )

                # change direction:
                min_inx = index  # minimum element
                min_value = value
                dir = -1

        # falling?
        elif dir < 0:
            if value < min_value:
                min_inx = index  # minimum element
                min_value = value
                trough_inx = index

            elif value >= min_value + threshold:
                # there was a trough:
                # change direction:
                max_inx = index  # maximum element
                max_value = value
                dir = 1

        # don't know!
        else:
            if max_value >= value + threshold:
                dir = -1  # falling
            elif value >= min_value + threshold:
                dir = 1  # rising

            if max_value < value:
                max_inx = index  # maximum element
                max_value = value

            elif value < min_value:
                min_inx = index  # minimum element
                min_value = value
                trough_inx = index

    return np.array( event_list )


def threshold_estimate( data, noise_factor ) :
    """
    Estimate noise standard deviation from histogram
    for usefull peak-detection thresholds.

    The standard deviation of the noise floor without peaks is estimated from
    the histogram of the data at 1/sqrt(e) relative height.

    Args:
        data: the data from which to estimate the thresholds
        noise_factor (float): multiplies the estimate of the standard deviation
                              of the noise to result in the threshold

    Returns:
        threshold (float): the threshold above the noise floor
        center: (float): estimate of the median of the data without peaks
    """
    
    # estimate noise standard deviation:
    # XXX what about the number of bins for small data sets?
    hist, bins = np.histogram( data, 100, density=True )
    inx = hist > np.max( hist ) / np.sqrt( np.e )
    lower = bins[inx][0]
    upper = bins[inx][-1] # needs to return the next bin
    center = 0.5*(lower+upper)
    noisestd = 0.5*(upper-lower)
    
    # threshold:
    threshold = noise_factor*noisestd

    return threshold, center


def accept_psd_peaks( freqs, data, peak_inx, index, trough_inx, min_inx, threshold, check_conditions ) :
    """
    Accept each detected peak and compute its size and width.

    Args:
        freqs (array): frequencies of the power spectrum
        data (array): the power spectrum
        peak_inx: index of the current peak
        index: current index (first minimum after peak at threshold below)
        trough_inx: index of the previous trough
        min_inx: index of previous minimum
        threshold: threshold value
        check_conditions: not used
    
    Returns: 
        freq (float): frequency of the peak
        power (float): power of the peak (value of data at the peak)
        size (float): size of the peak (peak minus previous trough)
        width (float): width of the peak at 0.75*size
        count (float): zero
    """
    size = data[peak_inx] - data[trough_inx]
    wthresh = data[trough_inx] + 0.75*size
    width = 0.0
    for k in range( peak_inx, trough_inx, -1 ) :
        if data[k] < wthresh :
            width = freqs[peak_inx] - freqs[k]
            break
    for k in range( peak_inx, index ) :
        if data[k] < wthresh :
            width += freqs[k] - freqs[peak_inx]
            break
    return [ freqs[peak_inx], data[peak_inx], size, width, 0.0 ]


def psd_peaks( psd_freqs, psd, cfg ) :
    """
    Detect peaks in power spectrum.

    Args:
        psd_freqs (array): frequencies of the power spectrum
        psd (array): power spectrum
        cfg (dict): configuration parameter

    Returns:
        all_freqs (2-d array): peaks in the power spectrum
                  detected with low threshold
                  [frequency, power, size, width, double use count]
        threshold (float): the relative threshold for detecting all peaks in the decibel spectrum
        center (float): the baseline level of the power spectrum
    """
    
    verbose = cfg['verboseLevel'][0]

    if verbose > 0 :
        print()
        print(70*'#')
        print('##### psd_peaks', 48*'#')
    
    # decibel power spectrum:
    log_psd = 10.0*np.log10( psd )

    # thresholds:
    threshold = cfg['threshold'][0]
    center = 0.0
    if cfg['threshold'][0] <= 0.0 :
        n = len( log_psd )
        threshold, center = threshold_estimate( log_psd[2*n/3:n*9/10],
                                                cfg['noiseFactor'][0] )
        if verbose > 1 :
            print()
            print('threshold=', threshold, center+threshold)
            print('center=', center)
    
    # detect peaks in decibel power spectrum:
    all_freqs = detect_peaks( psd_freqs, log_psd, threshold, accept_psd_peaks )

    # convert peak sizes back to power:
    if len( all_freqs ) > 0 :
        all_freqs[:,1] = 10.0**(0.1*all_freqs[:,1])
    
    return all_freqs, threshold, center

    
###############################################################################
## plotting etc.
    
class SignalPlot :
    def __init__( self, samplingrate, data, unit, filename, path ) :
        self.filepath = ''
        if platform.system() == 'Windows' :
            self.filepath = path
        self.filename = filename
        self.rate = samplingrate
        self.data = data
        self.lowpassfreq = cfg['lowpassfreq'][0]
        self.highpassfreq = cfg['highpassfreq'][0]
        self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
        self.channels = data.shape[1]
        self.envslowcutofffreq = cfg['envslowcutofffreq'][0]
        self.envfastcutofffreq = cfg['envfastcutofffreq'][0]
        self.slowenvelope = envelope(self.fdata, self.rate, self.envslowcutofffreq )
        self.fastenvelope = envelope(self.fdata, self.rate, self.envfastcutofffreq )
        self.unit = unit
        self.time = np.arange( 0.0, self.data.shape[0] )/self.rate
        self.toffset = 0.0
        self.twindow = 60.0
        if self.twindow > self.time[-1] :
            self.twindow = np.round( 2**(np.floor(np.log(self.time[-1]) / np.log(2.0)) + 1.0) )
        self.trace_artists = []
        self.filtered_trace_artists = []
        self.slowenvelope_artists = []
        self.fastenvelope_artists = []
        self.highpass_artist = None
        self.lowpass_artist = None
        self.fastenvelope_artist = None
        self.slowenvelope_artist = None
        self.show_traces = cfg['displayTraces'][0]
        self.show_filtered_traces = cfg['displayFilteredTraces'][0]
        self.show_fastenvelope = cfg['displayFastEnvelope'][0]
        self.show_slowenvelope = cfg['displaySlowEnvelope'][0]
        self.help = cfg['displayHelp'][0]
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
                self.highpass_artist = self.axt[0].text( 0.05, 0.9, 'highpass=%.2fkHz' % (0.001*self.highpassfreq), transform=self.axt[0].transAxes )
                self.lowpass_artist = self.axt[0].text( 0.2, 0.9, 'lowpass=%.2fkHz' % (0.001*self.lowpassfreq), transform=self.axt[0].transAxes )
                self.fastenvelope_artist = self.axt[0].text( 0.35, 0.9, 'fast envelope=%.2fkHz' % (0.001*self.envfastcutofffreq), transform=self.axt[0].transAxes )
                self.slowenvelope_artist = self.axt[0].text( 0.5, 0.9, 'slow envelope=%.2fkHz' % (0.001*self.envslowcutofffreq), transform=self.axt[0].transAxes )

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
        if cfg['maxpixel'][0] > 0 :
            tstep = int((t1-t0)//cfg['maxpixel'][0])
            if tstep < 1 :
                tstep = 1
        for c in range(self.channels) :
            self.axt[c].set_xlim( self.toffset, self.toffset+self.twindow )
            self.axt[c].set_ylim( self.ymin[c], self.ymax[c] )
        if self.show_traces :
            append = len(self.trace_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.data[t0:t1:tstep, c], 'b' )
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
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.fdata[t0:t1:tstep, c], 'g' )
                    self.filtered_trace_artists.append( ta )
                else :
                    self.filtered_trace_artists[c].set_data( self.time[t0:t1:tstep], self.fdata[t0:t1:tstep, c] )
                self.filtered_trace_artists[c].set_visible(True)
        else :
            for c in range(len(self.filtered_trace_artists)) :
                self.filtered_trace_artists[c].set_visible(False)
        if self.show_fastenvelope :
            append = len(self.fastenvelope_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.fastenvelope[t0:t1:tstep, c], 'r', lw=2 )
                    self.fastenvelope_artists.append( ta )
                else :
                    self.fastenvelope_artists[c].set_data( self.time[t0:t1:tstep], self.fastenvelope[t0:t1:tstep, c] )
                self.fastenvelope_artists[c].set_visible(True)
        else :
            for c in range(len(self.fastenvelope_artists)) :
                self.fastenvelope_artists[c].set_visible(False)
        if self.show_slowenvelope :
            append = len(self.slowenvelope_artists) == 0
            for c in range(self.channels) :
                if append :
                    ta, = self.axt[c].plot( self.time[t0:t1:tstep], self.slowenvelope[t0:t1:tstep, c], 'c', lw=2 )
                    self.slowenvelope_artists.append( ta )
                else :
                    self.slowenvelope_artists[c].set_data( self.time[t0:t1:tstep], self.slowenvelope[t0:t1:tstep, c] )
                self.slowenvelope_artists[c].set_visible(True)
        else :
            for c in range(len(self.slowenvelope_artists)) :
                self.slowenvelope_artists[c].set_visible(False)
        
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
            if len(self.trace_artists) > 0 :
                for c in range(self.channels) :
                    self.filtered_trace_artists[c].set_visible( self.show_filtered_traces )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'ctrl+e' :
            self.show_fastenvelope = not self.show_fastenvelope
            if len(self.trace_artists) > 0 :
                for c in range(self.channels) :
                    self.fastenelvope_artists[c].set_visible( self.show_fastenvelope )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'ctrl+s' :
            self.show_slowenvelope = not self.show_slowenvelope
            if len(self.trace_artists) > 0 :
                for c in range(self.channels) :
                    self.slowenelvope_artists[c].set_visible( self.show_slowenvelope )
                self.fig.canvas.draw()
            else:
                self.update_plots()
        elif event.key == 'h' :
            self.highpassfreq /= 1.5
            self.highpass_artist.set_text('highpass=%.2fkHz' % (0.001*self.highpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'H' :
            self.highpassfreq * 1.5
            self.highpass_artist.set_text('highpass=%.2fkHz' % (0.001*self.highpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'l' :
            self.lowpassfreq /= 1.5
            self.lowpass_artist.set_text('lowpass=%.2fkHz' % (0.001*self.lowpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 'L' :
            self.lowpassfreq * 1.5
            self.lowpass_artist.set_text('lowpass=%.2fkHz' % (0.001*self.lowpassfreq))
            self.fdata = bandpass_filter(self.data, self.rate, self.highpassfreq, self.lowpassfreq)
            self.update_plots()
        elif event.key == 's' :
            self.envslowcutofffreq /= 1.5
            self.slowenvelope_artist.set_text('slow envelope=%.2fkHz' % (0.001*self.envslowcutofffreq))
            self.slowenvelope = envelope(self.fdata, self.rate, self.envslowcutofffreq )
            self.update_plots()
        elif event.key == 'S' :
            self.envslowcutofffreq *= 1.5
            self.slowenvelope_artist.set_text('slow envelope=%.2fkHz' % (0.001*self.envslowcutofffreq))
            self.slowenvelope = envelope(self.fdata, self.rate, self.envslowcutofffreq )
            self.update_plots()
        elif event.key == 'f' :
            self.envfastcutofffreq /= 1.5
            self.fastenvelope_artist.set_text('fast envelope=%.2fkHz' % (0.001*self.envfastcutofffreq))
            self.fastenvelope = envelope(self.fdata, self.rate, self.envfastcutofffreq )
            self.update_plots()
        elif event.key == 'F' :
            self.envfastcutofffreq *= 1.5
            self.fastenvelope_artist.set_text('fast envelope=%.2fkHz' % (0.001*self.envfastcutofffreq))
            self.fastenvelope = envelope(self.fdata, self.rate, self.envfastcutofffreq )
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
        playdata = 1.0*np.mean(self.data[t0:t1,:], axis=1)
        playdata -= np.mean(playdata)
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        
    def play_all( self ) :
        playdata = np.mean(self.data, axis=1)
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
    parser.add_argument('-c', '--save-config', nargs='?', default='', const=cfgfile, type=str, metavar='cfgfile', help='save configuration to file cfgfile (defaults to {0})'.format( cfgfile ))
    parser.add_argument('file', nargs='?', default='', type=str, help='name of the files with the time series data')
    args = parser.parse_args()

    # load configuration from the current directory:
    if os.path.isfile( cfgfile ) :
        print('load configuration file %s' % cfgfile)
        load_config( cfgfile, cfg )

    # set configuration from command line:
    if args.verbose != None :
        cfg['verboseLevel'][0] = args.verbose
    
    # save configuration:
    if len( args.save_config ) > 0 :
        ext = os.path.splitext( args.save_config )[1]
        if ext != '.cfg' :
            print('configuration file name must have .cfg as extension!')
        else :
            print('write configuration to %s ...' % args.save_config)
            dump_config( args.save_config, cfg, cfgsec )
        quit()

    # load data:
    filepath = args.file
    data, freq, unit = load_data( filepath )
    
    #highpass_cutoff = 400.0
    #data = highpass_filter( freq, data, highpass_cutoff )
    #data = bandpass_filter(data, freq)

    # plot:
    sp = SignalPlot( freq, data, unit, filepath, os.path.dirname( filepath ) )

if __name__ == '__main__':
    main()

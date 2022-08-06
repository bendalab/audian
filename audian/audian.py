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
from .version import __version__, __year__
from audioio import load_audio, write_audio, PlayAudio, fade
try:
    from audioio import load_audio, write_audio, PlayAudio, fade
    have_audioio = True
except ImportError:
    have_audioio = False

    
cfg = OrderedDict()
cfgsec = dict()

cfgsec['maxpixel'] = 'Plotting:'
cfg['maxpixel'] = [ 50000, '', 'Either maximum number of data points to be plotted or zero for plotting all data points.' ]

cfgsec['envthreshfac'] = 'Envelope:'
cfg['envcutofffreq'] = [ 100.0, 'Hz', 'Cutoff frequency of the low-pass filter used for computing the envelope from the squared signal.' ]
cfg['envthreshfac'] = [ 2.0, '', 'Threshold for peak detection in envelope is this factor time the standard deviation of the envelope.' ]

cfgsec['minPSDAverages'] = 'Power spectrum estimation:'
cfg['minPSDAverages'] = [ 3, '', 'Minimum number of fft averages for estimating the power spectrum.' ]

cfgsec['threshold'] = 'Thresholds for peak detection in power spectra:'
cfg['threshold'] = [ 2.0, 'dB', 'Threshold for all peaks.\n If set to 0.0, estimate threshold from histogram.' ]

cfgsec['noiseFactor'] = 'Threshold estimation:\nIf no thresholds are specified, they are estimated from the histogram of the decibel power spectrum.'
cfg['noiseFactor'] = [ 12.0, '', 'Factor for multiplying std of noise floor for lower threshold.' ]

cfgsec['displayHelp'] = 'Items to display:'
cfg['displayHelp'] = [ False, '', 'Display help on key bindings' ] 
cfg['labelFrequency'] = [ True, '', 'Display the frequency of the peak' ] 
cfg['labelPower'] = [ True, '', 'Display the power of the peak' ]
cfg['labelWidth'] = [ True, '', 'Display the width of the peak' ]

cfgsec['verboseLevel'] = 'Debugging:'
cfg['verboseLevel'] = [ 0, '', '0=off upto 4 very detailed' ]


###############################################################################
## load data:
    
def load_audioio(filename, trace=0) :
    """
    load audio file using audioio
    """
    data, rate = load_audio(filename)
    if len(data.shape) == 1 :
        if trace >= 1 :
            print('number of traces in file is %d' % 1)
            quit()
        return rate, data
    else :
        tracen = data.shape[1]
        if trace >= tracen :
            print('number of traces in file is %d' % tracen)
            quit()
        return rate, data[:,trace]

    
def load_wavfile(filename, trace=0):
    """
    load wav file using scipy io.wavfile
    """
    from scipy.io import wavfile
    rate, data = wavfile.read(filename)
    if len(data.shape) == 1 :
        if trace >= 1 :
            print('number of traces in file is %d' % 1)
            quit()
        return rate, data/2.0**15, 'a.u.'
    else :
        tracen = data.shape[1]
        if trace >= tracen :
            print('number of traces in file is %d' % tracen)
            quit()
        return rate, data[:,trace]/2.0**15, 'a.u.'

    
def load_wave(filename, trace=0) :
    """
    load wav file using wave module
    """
    try:
        import wave
    except ImportError:
        print('python module "wave" is not installed.')
        return load_wavfile(filename, trace)

    wf = wave.open(filename, 'r')
    (nchannels, sampwidth, rate, nframes, comptype, compname) = wf.getparams()
    #print nchannels, sampwidth, rate, nframes, comptype, compname
    buffer = wf.readframes(nframes)
    format = 'i%d' % sampwidth
    data = np.frombuffer(buffer, dtype=format).reshape(-1, nchannels)  # read data
    wf.close()
    if len(data.shape) == 1 :
        if trace >= 1 :
            print('number of traces in file is %d' % 1)
            quit()
        return rate, data/2.0**(sampwidth*8-1)
    else :
        tracen = data.shape[1]
        if trace >= tracen :
            print('number of traces in file is %d' % tracen)
            quit()
        return rate, data[:,trace]/2.0**(sampwidth*8-1)


###############################################################################
## filter and envelope:

def highpass_filter(data, rate, cutoff) :
    sos = sig.butter(2, cutoff, 'highpass', fs=rate, output='sos')
    fdata = sig.sosfiltfilt(sos, data)
    return fdata


def bandpass_filter(data, rate, lowf=5500.0, highf=7500.0):
    """
    Bandpass filter the signal.
    """
    sos = sig.butter(2, (lowf, highf), 'bandpass', fs=rate, output='sos')
    fdata = sig.sosfiltfilt(sos, data)
    return fdata


def envelope(data, rate, freq=100.0):
    sos = sig.butter(2, freq, 'lowpass', fs=rate, output='sos')
    envelope = np.sqrt(2)*sig.sosfiltfilt(sos, np.abs(data))
    return envelope


###############################################################################
## configuration file writing and loading:

def dump_config(filename, cfg, sections=None, header=None, maxline=60) :
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

    def write_comment(f, comment, maxline=60, cs='#') :
        # format comment:
        if len(comment) > 0 :
            for line in comment.split('\n') :
                f.write(cs + ' ')
                cc = len(cs) + 1  # character count
                for w in line.strip().split(' ') :
                    # line too long?
                    if cc + len(w) > maxline :
                        f.write('\n' + cs + ' ')
                        cc = len(cs) + 1
                    f.write(w + ' ')
                    cc += len(w) + 1
                f.write('\n')
    
    with open(filename, 'w') as f :
        if header != None :
            write_comment(f, header, maxline, '##')
        maxkey = 0
        for key in cfg.keys() :
            if maxkey < len(key) :
                maxkey = len(key)
        for key, v in cfg.items() :
            # possible section entry:
            if sections != None and key in sections :
                f.write('\n\n')
                write_comment(f, sections[key], maxline, '##')

            # get value, unit, and comment from v:
            val = None
            unit = ''
            comment = ''
            if hasattr(v, '__len__') and (not isinstance(v, str)) :
                val = v[0]
                if len(v) > 1 :
                    unit = ' ' + v[1]
                if len(v) > 2 :
                    comment = v[2]
            else :
                val = v

            # next key-value pair:
            f.write('\n')
            write_comment(f, comment, maxline, '#')
            f.write('{key:<{width}s}: {val}{unit:s}\n'.format(key=key, width=maxkey, val=val, unit=unit))


def load_config(filename, cfg) :
    """
    Set values of dictionary cfg to values from key-value pairs read in from file.
    
    Args:
        filename: The name of the file from which to read in the configuration.
        cfg (dict): Configuration keys, values, units, and comments.
    """
    with open(filename, 'r') as f :
        for line in f :
            # do not process empty lines and comments:
            if len(line.strip()) == 0 or line[0] == '#' or not ':' in line :
                continue
            key, val = line.split(':', 1)
            key = key.strip()
            if not key in cfg :
                continue
            cv = cfg[key]
            vals = val.strip().split(' ')
            if hasattr(cv, '__len__') and (not isinstance(cv, str)) :
                unit = ''
                if len(vals) > 1 :
                    unit = vals[1]
                if unit != cv[1] :
                    print('unit for %s is %s but should be %s' % (key, unit, cv[1]))
                cv[0] = type(cv[0])(vals[0])
            else :
                cfg[key] = type(cv)(vals[0])
            

###############################################################################
## peak detection:

def detect_peaks(time, data, threshold, check_func=None, check_conditions=None):

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
                    r = check_func(time, data, event_inx, index, trough_inx, min_inx, threshold, check_conditions)
                    if len(r) > 0 :
                        # this really is an event:
                        event_list.append(r)
                else:
                    # this really is an event:
                    event_list.append(time[event_inx])

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

    return np.array(event_list)


def threshold_estimate(data, noise_factor) :
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
    hist, bins = np.histogram(data, 100, density=True)
    inx = hist > np.max(hist) / np.sqrt(np.e)
    lower = bins[inx][0]
    upper = bins[inx][-1] # needs to return the next bin
    center = 0.5*(lower+upper)
    noisestd = 0.5*(upper-lower)
    
    # threshold:
    threshold = noise_factor*noisestd

    return threshold, center


def accept_psd_peaks(freqs, data, peak_inx, index, trough_inx, min_inx, threshold, check_conditions) :
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
    for k in range(peak_inx, trough_inx, -1) :
        if data[k] < wthresh :
            width = freqs[peak_inx] - freqs[k]
            break
    for k in range(peak_inx, index) :
        if data[k] < wthresh :
            width += freqs[k] - freqs[peak_inx]
            break
    return [ freqs[peak_inx], data[peak_inx], size, width, 0.0 ]


def psd_peaks(psd_freqs, psd, cfg) :
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
    log_psd = 10.0*np.log10(psd)

    # thresholds:
    threshold = cfg['threshold'][0]
    center = 0.0
    if cfg['threshold'][0] <= 0.0 :
        n = len(log_psd)
        threshold, center = threshold_estimate(log_psd[2*n/3:n*9/10],
                                                cfg['noiseFactor'][0])
        if verbose > 1 :
            print()
            print('threshold=', threshold, center+threshold)
            print('center=', center)
    
    # detect peaks in decibel power spectrum:
    all_freqs = detect_peaks(psd_freqs, log_psd, threshold, accept_psd_peaks)

    # convert peak sizes back to power:
    if len(all_freqs) > 0 :
        all_freqs[:,1] = 10.0**(0.1*all_freqs[:,1])
    
    return all_freqs, threshold, center

    
###############################################################################
## plotting etc.
    
class SignalPlot :
    def __init__(self, samplingrate, data, unit, filename, channel, path) :
        self.filepath = ''
        if platform.system() == 'Windows' :
            self.filepath = path
        self.filename = filename
        self.channel = channel
        self.rate = samplingrate
        self.data = data
        self.unit = unit
        self.envcutofffreq = cfg['envcutofffreq'][0]
        self.envthreshfac = cfg['envthreshfac'][0]
        self.envelope = envelope(self.data, self.rate, self.envcutofffreq)
        self.envpower = None
        self.envfreqs = None
        self.time = np.arange(0.0, len(self.data))/self.rate
        self.toffset = 0.0
        self.twindow = 8.0
        if self.twindow > self.time[-1] :
            self.twindow = np.round(2**(np.floor(np.log(self.time[-1]) / np.log(2.0)) + 1.0))
        self.ymin = -1.0
        self.ymax = +1.0
        self.trace_artist = None
        self.envelope_artist = None
        self.show_envelope = True
        self.spectrogram_artist = None
        self.fmin = 0.0
        self.fmax = 0.0
        self.decibel = True
        self.fresolution = 300.0
        self.power_label = None
        self.all_peaks_artis = None
        self.power_artist = None
        self.power_frequency_label = None
        self.envpower_label = None
        self.envpower_artist = None
        self.legend = True
        self.legendhandle = None
        self.help = cfg['displayHelp'][0]
        self.helptext = []
        self.allpeaks = []
        self.peak_specmarker = []
        self.peak_annotation = []
        self.analysis_file = None

        # audio output:
        if have_audioio :
            self.audio = PlayAudio()
        else :
            self.audio = None

        # set key bindings:
        plt.rcParams['keymap.fullscreen'] = 'ctrl+f'
        plt.rcParams['keymap.pan'] = 'ctrl+m'
        plt.rcParams['keymap.quit'] = 'ctrl+w, alt+q, q'
        plt.rcParams['keymap.yscale'] = ''
        plt.rcParams['keymap.xscale'] = ''
        plt.rcParams['keymap.grid'] = ''
        plt.rcParams['keymap.save'] = ''
        if 'keymap.all_axes' in plt.rcParams:
            plt.rcParams['keymap.all_axes'] = ''
        
        # the figure:
        plt.ioff()
        self.fig = plt.figure(figsize=(15, 9))
        self.fig.canvas.manager.set_window_title('AUDIoANalyser: ' + self.filename + ' channel {0:d}'.format(self.channel))
        self.fig.canvas.mpl_connect('key_press_event', self.keypress)
        self.fig.canvas.mpl_connect('button_press_event', self.buttonpress)
        self.fig.canvas.mpl_connect('pick_event', self.onpick)
        self.fig.canvas.mpl_connect('resize_event', self.resize)
        # trace plot:
        self.axt = self.fig.add_axes([ 0.1, 0.7, 0.87, 0.25 ])
        self.axt.set_ylabel('Amplitude [{:s}]'.format(self.unit))
        self.span = widgets.SpanSelector(self.axt, self.analyse_trace,
                                         direction='horizontal')
        ht = self.axt.text(0.98, 0.05, '(ctrl+) page and arrow up, down, home, end: scroll', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.15, '+, -, X, x: zoom in/out', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.25, 'y,Y,v,V: zoom amplitudes', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.35, 'p,P: play audio (display,all)', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.45, 'ctrl-f: full screen', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.55, 'w, W: plot waveform/spectrum into png file', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.65, 's: save current segment to wav file', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.75, 'q: quit', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        ht = self.axt.text(0.98, 0.85, 'h: toggle this help', ha='right', transform=self.axt.transAxes)
        self.helptext.append(ht)
        #self.axt.set_xticklabels([])
        # spectrogram:
        self.axs = self.fig.add_axes([ 0.1, 0.45, 0.87, 0.25 ])
        self.axs.set_xlabel('Time [seconds]')
        self.axs.set_ylabel('Frequency [Hz]')
        # power spectrum:
        self.axp = self.fig.add_axes([ 0.1, 0.1, 0.4, 0.25 ])
        ht = self.axp.text(0.98, 0.9, 'r, R: frequency resolution', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.8, 'f, F: zoom', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.7, '(ctrl+) left, right: move', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.6, 'l: toggle legend', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.5, 'd: toggle decibel', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.3, 'left mouse: show peak properties', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.2, 'shift/ctrl + left/right mouse: goto previous/next harmonic', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        ht = self.axp.text(0.98, 0.1, 'S: save current spectrum to csv file', ha='right', transform=self.axp.transAxes)
        self.helptext.append(ht)
        # power spectrum of envelope:
        self.axpe = self.fig.add_axes([ 0.6, 0.1, 0.4, 0.25 ])
        ht = self.axpe.text(0.98, 0.9, 'c, C: envelope cutoff frequency', ha='right', transform=self.axpe.transAxes)
        self.helptext.append(ht)
        ht = self.axpe.text(0.98, 0.8, 't, T: threshold for envelope peak detection', ha='right', transform=self.axpe.transAxes)
        self.helptext.append(ht)
        ht = self.axpe.text(0.98, 0.7, 'e: toggle envelope', ha='right', transform=self.axpe.transAxes)
        self.helptext.append(ht)
        ht = self.axpe.text(0.98, 0.6, 'E: save envelope and its spectrum to files', ha='right', transform=self.axpe.transAxes)
        self.helptext.append(ht)
        # plot:
        for ht in self.helptext :
            ht.set_visible(self.help)
        self.update_plots(False)
        plt.show()

    def __del__(self) :
        if self.analysis_file != None :
            self.analysis_file.close()
        if self.audio is not None:
            self.audio.close()

    def compute_psd(self, t0, t1) :
        nfft = int(np.round(2**(np.floor(np.log(self.rate/self.fresolution) / np.log(2.0)) + 1.0)))
        if nfft < 16 :
            self.fresolution *= 0.5
            nfft = 16
        t00 = t0
        t11 = t1
        w = t11-t00
        minw = int(nfft*(cfg['minPSDAverages'][0]+1)//2)
        if t11-t00 < minw :
            w = minw
            t11 = t00 + w
        if t11 >= len(self.data) :
            t11 = len(self.data)
            t00 = t11 - w
        if t00 < 0 :
            t00 = 0
            t11 = w           
        power, freqs = ml.psd(self.data[t00:t11], NFFT=nfft, noverlap=nfft//2, Fs=self.rate, detrend=ml.detrend_mean)
        return power, freqs, nfft, w

    def remove_peak_annotation(self) :
        for fm in self.peak_specmarker :
            fm.remove()
        self.peak_specmarker = []
        for fa in self.peak_annotation :
            fa.remove()
        self.peak_annotation = []

    def annotate_peak(self, peak) :
        # marker:
        m, = self.axs.plot([self.toffset+0.01*self.twindow], [peak[0]], linestyle='None',
                            color='k', marker='o', ms=10.0, mec=None, mew=0.0, zorder=2)
        self.peak_specmarker.append(m)
        # annotation:
        fwidth = self.fmax - self.fmin
        pt = []
        if cfg['labelFrequency'][0] :
            pt.append(r'$f=${:.1f} Hz'.format(peak[0]))
        if cfg['labelPower'][0] :
            pt.append(r'$p=${:g}'.format(peak[1]))
        if cfg['labelWidth'][0] :
            pt.append(r'$\Delta f=${:.2f} Hz'.format(peak[3]))
        self.peak_annotation.append(self.axp.annotate('\n'.join(pt), xy=(peak[0], peak[1]),
                       xytext=(peak[0]+0.03*fwidth, peak[1]),
                       bbox=dict(boxstyle='round',facecolor='white'),
                       arrowprops=dict(arrowstyle='-')))
            
    def update_plots(self, draw=True) :
        self.remove_peak_annotation()
        # trace:
        self.axt.set_xlim(self.toffset, self.toffset+self.twindow)
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        tstep = 1
        if cfg['maxpixel'][0] > 0 :
            tstep = int((t1-t0)//cfg['maxpixel'][0])
            if tstep < 1 :
                tstep = 1
        if self.trace_artist == None :
            self.trace_artist, = self.axt.plot(self.time[t0:t1:tstep], self.data[t0:t1:tstep])
        else :
            self.trace_artist.set_data(self.time[t0:t1:tstep], self.data[t0:t1:tstep])
        if self.envelope_artist == None :
            self.envelope_artist,  = self.axt.plot(self.time[t0:t1:tstep], self.envelope[t0:t1:tstep], '-r')
        else :
            self.envelope_artist.set_data(self.time[t0:t1:tstep], self.envelope[t0:t1:tstep])
        self.axt.set_ylim(self.ymin, self.ymax)

        # compute power spectrum:
        nfft = int(np.round(2**(np.floor(np.log(self.rate/self.fresolution) / np.log(2.0)) + 1.0)))
        if nfft < 16 :
            self.fresolution *= 0.5
            nfft = 16
        t00 = t0
        t11 = t1
        w = t11-t00
        minw = int(nfft*(cfg['minPSDAverages'][0]+1)//2)
        if t11-t00 < minw :
            w = minw
            t11 = t00 + w
        if t11 >= len(self.data) :
            t11 = len(self.data)
            t00 = t11 - w
        if t00 < 0 :
            t00 = 0
            t11 = w           
        self.power, self.freqs = ml.psd(self.data[t00:t11], NFFT=nfft, noverlap=nfft/2, Fs=self.rate, detrend=ml.detrend_mean)
        # detect peaks:
        self.allpeaks, lowth, center = psd_peaks(self.freqs, self.power, cfg)
        lowth = center + 0.5*lowth

        # spectrogram:
        t2 = t1 + nfft
        specpower, freqs, bins = ml.specgram(self.data[t0:t2], NFFT=nfft, Fs=self.rate, noverlap=nfft/2,
                                              detrend=ml.detrend_mean)
        specpower[specpower<=0.0] = np.min(specpower[specpower>0.0]) # remove zeros
        z = 10.*np.log10(specpower)
        z = np.flipud(z)
        sstep = z.shape[1]//2000
        if sstep < 1 :
            sstep = 1
        extent = self.toffset, self.toffset+np.amax(bins), freqs[0], freqs[-1]
        self.axs.set_xlim(self.toffset, self.toffset+self.twindow)
        if self.spectrogram_artist == None :
            self.fmax = np.round((freqs[-1])/1000.0)*1000.0
            min = np.percentile(z, 70.0)
            max = np.percentile(z, 99.9) + 5.0
            cm = plt.get_cmap('jet')
            self.spectrogram_artist = self.axs.imshow(z[:,::sstep], aspect='auto',
                                                         extent=extent, vmin=min, vmax=max,
                                                         cmap=cm, zorder=1)
            #self.spectrogram_artist = self.axs.pcolormesh(bins, freqs, z,
            #                                                vmin=min, vmax=max,
            #                                                cmap=cm, zorder=1)
        else :
            self.spectrogram_artist.set_data(z[:,::sstep])
            self.spectrogram_artist.set_extent(extent)
        self.axs.set_ylim(self.fmin, self.fmax)

        # power spectrum:
        df = self.freqs[1]-self.freqs[0]
        if df >= 1000.0 :
            dfs = '%.3gkHz' % (0.001*df)
        else :
            dfs = '%.3gHz' % df
        tw = float(w)/self.rate
        if tw < 1.0 :
            tws = '%.3gms' % (1000.0*tw)
        else :
            tws = '%.3gs' % (tw)
        a = 2*w/nfft-1 # number of ffts
        if self.power_frequency_label == None :
            self.power_frequency_label = self.axp.set_xlabel(r'Frequency [Hz] (nfft={:d}, $\Delta f$={:s}: T={:s}/{:.0f})'.format(nfft, dfs, tws, a))
        else :
            self.power_frequency_label.set_text(r'Frequency [Hz] (nfft={:d}, $\Delta f$={:s}: T={:s}/{:.0f})'.format(nfft, dfs, tws, a))
        self.axp.set_xlim(self.fmin, self.fmax)
        if self.power_label == None :
            self.power_label = self.axp.set_ylabel('Signal power')
        if self.decibel :
            if len(self.allpeaks) > 0 :
                self.allpeaks[:,1] = 10.0*np.log10(self.allpeaks[:,1])
            self.power = 10.0*np.log10(self.power)
            pmin = np.min(self.power[self.freqs<self.fmax])
            pmin = np.floor(pmin/10.0)*10.0
            pmax = np.max(self.power[self.freqs<self.fmax])
            pmax = np.ceil(pmax/10.0)*10.0
            doty = pmax-5.0
            self.power_label.set_text('Signal power [dB]')
            self.axp.set_ylim(pmin, pmax)
        else :
            pmax = np.max(self.power[self.freqs<self.fmax])
            doty = pmax
            pmax *= 1.1
            self.power_label.set_text('Signal power')
            self.axp.set_ylim(0.0, pmax)
        if self.all_peaks_artis == None :
            if len(self.allpeaks) > 0 :
                self.all_peaks_artis, = self.axp.plot(self.allpeaks[:,0],
                                                       np.zeros(len(self.allpeaks[:,0]))+doty,
                                                       'o', color='#ffffff')
            else :
                self.all_peaks_artis, = self.axp.plot([], [], 'o', color='#ffffff')
        else :
            if len(self.allpeaks) > 0 :
                self.all_peaks_artis.set_data(self.allpeaks[:,0],
                                                np.zeros(len(self.allpeaks[:,0]))+doty)
            else :
                self.all_peaks_artis.set_data([], [])
        if self.power_artist == None :
            self.power_artist, = self.axp.plot(self.freqs, self.power, 'b', zorder=2)
        else :
            self.power_artist.set_data(self.freqs, self.power)

        # power spectrum of envelope:
        self.envfresolution=1.0
        nfft = int(np.round(2**(np.floor(np.log(self.rate/self.envfresolution) / np.log(2.0)) + 1.0)))
        if nfft < 16 :
            self.envfresolution *= 0.5
            nfft = 16
        t00 = t0
        t11 = t1
        w = t11-t00
        minw = int(nfft*(cfg['minPSDAverages'][0]+1)//2)
        if t11-t00 < minw :
            w = minw
            t11 = t00 + w
        if t11 >= len(self.envelope) :
            t11 = len(self.envelope)
            t00 = t11 - w
        if t00 < 0 :
            t00 = 0
            t11 = w
        self.envpower, self.envfreqs = ml.psd(self.envelope[t00:t11], NFFT=nfft, noverlap=nfft//2, Fs=self.rate, detrend=ml.detrend_mean)
        self.axpe.set_xlim(0.0, 100.0)
        self.axpe.set_xlabel('Frequency [Hz]')
        if self.envpower_label == None :
            self.envpower_label = self.axpe.set_ylabel('Envelope power')
        if self.decibel :
            self.envpower = 10.0*np.log10(self.envpower)
            pmin = np.min(self.envpower[self.envfreqs<100.0])
            pmin = np.floor(pmin/10.0)*10.0
            pmax = np.max(self.envpower[self.envfreqs<100.0])
            pmax = np.ceil(pmax/10.0)*10.0
            doty = pmax-5.0
            self.envpower_label.set_text('Envelope power [dB]')
            self.axpe.set_ylim(pmin, pmax)
        else :
            pmax = np.max(self.envpower[self.envfreqs<100.0])
            doty = pmax
            pmax *= 1.1
            self.envpower_label.set_text('Envelope power')
            self.axpe.set_ylim(0.0, pmax)
        if self.envpower_artist == None :
            self.envpower_artist, = self.axpe.plot(self.envfreqs, self.envpower, 'r', zorder=2)
        else :
            self.envpower_artist.set_data(self.envfreqs, self.envpower)
        
        if draw :
            self.fig.canvas.draw()
                 
    def keypress(self, event) :
        # print 'pressed', event.key
        if event.key in '+=X' :
            if self.twindow*self.rate > 20 :
                self.twindow *= 0.5
                self.update_plots()
        elif event.key in '-x' :
            if self.twindow < len(self.data)/self.rate :
                self.twindow *= 2.0
                self.update_plots()
        elif event.key == 'pagedown' :
            if self.toffset + 0.5*self.twindow < len(self.data)/self.rate :
                self.toffset += 0.5*self.twindow
                self.update_plots()
        elif event.key == 'pageup' :
            if self.toffset > 0 :
                self.toffset -= 0.5*self.twindow
                if self.toffset < 0.0 :
                    self.toffset = 0.0
                self.update_plots()
        elif event.key == 'ctrl+pagedown' :
            if self.toffset + 5.0*self.twindow < len(self.data)/self.rate :
                self.toffset += 5.0*self.twindow
                self.update_plots()
        elif event.key == 'ctrl+pageup' :
            if self.toffset > 0 :
                self.toffset -= 5.0*self.twindow
                if self.toffset < 0.0 :
                    self.toffset = 0.0
                self.update_plots()
        elif event.key == 'down' :
            if self.toffset + self.twindow < len(self.data)/self.rate :
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
            toffs = np.floor(len(self.data)/self.rate / self.twindow) * self.twindow
            if self.toffset < toffs :
                self.toffset = toffs
                self.update_plots()
        elif event.key == 'y':
            h = self.ymax - self.ymin
            c = 0.5*(self.ymax + self.ymin)
            self.ymin = c-h
            self.ymax = c+h
            self.axt.set_ylim(self.ymin, self.ymax)
            self.fig.canvas.draw()
        elif event.key == 'Y':
            h = 0.25*(self.ymax - self.ymin)
            c = 0.5*(self.ymax + self.ymin)
            self.ymin = c-h
            self.ymax = c+h
            self.axt.set_ylim(self.ymin, self.ymax)
            self.fig.canvas.draw()
        elif event.key == 'v':
            t0 = int(np.round(self.toffset*self.rate))
            t1 = int(np.round((self.toffset+self.twindow)*self.rate))
            min = np.min(self.data[t0:t1])
            max = np.max(self.data[t0:t1])
            h = 0.5*(max - min)
            c = 0.5*(max + min)
            self.ymin = c-h
            self.ymax = c+h
            self.axt.set_ylim(self.ymin, self.ymax)
            self.fig.canvas.draw()
        elif event.key == 'V':
            self.ymin = -1.0
            self.ymax = +1.0
            self.axt.set_ylim(self.ymin, self.ymax)
            self.fig.canvas.draw()
        elif event.key == 'left' :
            if self.fmin > 0.0 :
                fwidth = self.fmax-self.fmin
                self.fmin -= 0.5*fwidth
                self.fmax -= 0.5*fwidth
                if self.fmin < 0.0 :
                    self.fmin = 0.0
                    self.fmax = fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key == 'right' :
            if self.fmax < 0.5*self.rate :
                fwidth = self.fmax-self.fmin
                self.fmin += 0.5*fwidth
                self.fmax += 0.5*fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key == 'ctrl+left' :
            if self.fmin > 0.0 :
                fwidth = self.fmax-self.fmin
                self.fmin = 0.0
                self.fmax = fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key == 'ctrl+right' :
            if self.fmax < 0.5*self.rate :
                fwidth = self.fmax-self.fmin
                fm = 0.5*self.rate
                self.fmax = np.ceil(fm/fwidth)*fwidth
                self.fmin = self.fmax - fwidth
                if self.fmin < 0.0 :
                    self.fmin = 0.0
                    self.fmax = fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key in 'e' :
            self.show_envelope = not self.show_envelope
            self.envelope_artist.set_visible(self.show_envelope)
            self.fig.canvas.draw()
        elif event.key in 'C' :
            self.envcutofffreq *= 1.2
            self.envelope = envelope(self.data, self.rate, self.envcutofffreq)
            self.update_plots()
        elif event.key in 'c' :
            self.envcutofffreq /= 1.2
            self.envelope = envelope(self.data, self.rate, self.envcutofffreq)
            self.update_plots()
        elif event.key in 'T' :
            self.envthreshfac *= 1.2
        elif event.key in 't' :
            self.envthreshfac /= 1.2
        elif event.key in 'f' :
            if self.fmax < 0.5*self.rate or self.fmin > 0.0 :
                fwidth = self.fmax-self.fmin
                if self.fmax < 0.5*self.rate :
                    self.fmax = self.fmin + 2.0*fwidth
                elif self.fmin > 0.0 :
                    self.fmin = self.fmax - 2.0*fwidth
                    if self.fmin < 0.0 :
                        self.fmin = 0.0
                        self.fmax = 2.0*fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key in 'F' :
            if self.fmax - self.fmin > 1.0 :
                fwidth = self.fmax-self.fmin
                self.fmax = self.fmin + 0.5*fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
        elif event.key in 'r' :
            if self.fresolution < 10000.0 :
                self.fresolution *= 2.0
                self.update_plots()
        elif event.key in 'R' :
            if 1.0/self.fresolution < self.time[-1] :
                self.fresolution *= 0.5
                self.update_plots()
        elif event.key in 'd' :
            self.decibel = not self.decibel
            self.update_plots()
        elif event.key in 'm' :
            if cfg['mainsFreq'][0] == 0.0 :
                cfg['mainsFreq'][0] = self.mains_freq
            else :
                cfg['mainsFreq'][0] = 0.0
            self.update_plots()
        elif event.key == 'escape' :
            self.remove_peak_annotation()
            self.fig.canvas.draw()
        elif event.key in 'h' :
            self.help = not self.help
            for ht in self.helptext :
                ht.set_visible(self.help)
            self.fig.canvas.draw()
        elif event.key in 'l' :
            self.legend = not self.legend
            self.legendhandle.set_visible(self.legend)
            self.fig.canvas.draw()
        elif event.key in 'w' :
            self.plot_waveform()
        elif event.key in 'W' :
            self.plot_powerspec()
        elif event.key in 's' :
            self.save_segment()
        elif event.key in 'S' :
            self.save_powerspec()
        elif event.key in 'E' :
            self.save_envelope()
            self.save_envelope_powerspec()
        elif event.key in 'p' :
            self.play_segment()
        elif event.key in 'P' :
            self.play_all()

    def buttonpress(self, event) :
        # print 'mouse pressed', event.button, event.key, event.step
        if event.inaxes == self.axp :
            if event.key == 'shift' or event.key == 'control' :
                # show next or previous harmonic:
                if event.key == 'shift' :
                    if event.button == 1 :
                        ftarget = event.xdata/2.0
                    elif event.button == 3 :
                        ftarget = event.xdata*2.0
                else :
                    if event.button == 1 :
                        ftarget = event.xdata/1.5
                    elif event.button == 3 :
                        ftarget = event.xdata*1.5
                foffs = event.xdata - self.fmin
                fwidth = self.fmax - self.fmin
                self.fmin = ftarget - foffs
                self.fmax = self.fmin + fwidth
                self.axs.set_ylim(self.fmin, self.fmax)
                self.axp.set_xlim(self.fmin, self.fmax)
                self.fig.canvas.draw()
            else :
                # put label on peak
                self.remove_peak_annotation()
                # find closest peak:
                fwidth = self.fmax - self.fmin
                peakdist = np.abs(self.allpeaks[:,0]-event.xdata)
                inx = np.argmin(peakdist)
                if peakdist[inx] < 0.005*fwidth :
                    peak = self.allpeaks[inx,:]
                    self.annotate_peak(peak)
                    self.fig.canvas.draw()
                else :
                    self.fig.canvas.draw()

    def onpick(self, event) :
        print('pick')

    def analyse_envelopepeaks(self, tmin, tmax) :
        t0 = int(tmin*self.rate)
        t1 = int(tmax*self.rate)
        threshold = self.envthreshfac*np.std(self.envelope[t0:t1])
        peaktimes = detect_peaks(self.time[t0:t1], self.envelope[t0:t1], threshold)
        npeaks = len(peaktimes)
        rate = 0.0
        interval = 0.0
        if npeaks > 1 :
            rate = (npeaks-1.0)/(peaktimes[-1]-peaktimes[0])
            interval = 1.0/rate
        return npeaks, interval, rate

    def analyse_trace(self, tmin, tmax) :
        t0 = int(tmin*self.rate)
        t1 = int(tmax*self.rate)
        npeaks, pinterval, prate = self.analyse_envelopepeaks(tmin, tmax)
        print('\t'.join([ '{:10s}'.format(x) for x in [ "# width [s]", "trace mean", "trace std", "env mean", "env std", "env peaks", "env T [s]", "env rate [Hz]" ] ]))
        print('\t'.join('{:10.4f}'.format(x) for x in [ tmax-tmin, np.mean(self.data[t0:t1]), np.std(self.data[t0:t1]), np.mean(self.envelope[t0:t1]), np.std(self.envelope[t0:t1]), npeaks, pinterval, prate ]))
        if self.analysis_file == None :
            name = os.path.splitext(self.filename)[0]
            if self.channel > 0 :
                datafile = '{name}-{channel:d}-data.txt'.format(
                    name=name, channel=self.channel)
            else :
                datafile = '{name}-data.txt'.format(name=name)
            self.analysis_file = open(os.path.join(self.filepath, datafile), 'w')
            self.analysis_file.write('\t'.join([ '{:10s}'.format(x) for x in [ "# width [s]", "trace mean", "trace std", "env mean", "env std", "env peaks", "env T [s]", "env rate [Hz]" ] ]) + '\n')
            print('saved selected data to: %s' % datafile)
        self.analysis_file.write('\t'.join('{:10.4f}'.format(x) for x in [ tmax-tmin, np.mean(self.data[t0:t1]), np.std(self.data[t0:t1]), np.mean(self.envelope[t0:t1]), np.std(self.envelope[t0:t1]), npeaks, pinterval, prate ]) + '\n')
        self.analysis_file.flush()
            

    def resize(self, event) :
        # print 'resized', event.width, event.height
        leftpixel = 80.0
        rightpixel = 20.0
        midpixel = 80.0
        xaxispixel = 50.0
        toppixel = 20.0
        timeaxis = 0.42
        left = leftpixel/event.width
        width = 1.0 - left - rightpixel/event.width
        halfwidth = 0.5*(width - midpixel/event.width)
        halfleft = left + halfwidth + midpixel/event.width
        xaxis = xaxispixel/event.height
        top = toppixel/event.height
        height = (1.0-timeaxis-top)/2.0
        if left < 0.5 and width < 1.0 and xaxis < 0.3 and top < 0.2 :
            self.axt.set_position([ left, timeaxis+height, width, height ])
            self.axs.set_position([ left, timeaxis, width, height ])
            self.axp.set_position([ left, xaxis, halfwidth, timeaxis-2.0*xaxis ])
            self.axpe.set_position([ halfleft, xaxis, halfwidth, timeaxis-2.0*xaxis ])

    def plot_waveform(self) :
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        name = os.path.splitext(self.filename)[0]
        if self.channel > 0 :
            ax.set_title('{filename} channel={channel:d}'.format(
                filename=self.filename, channel=self.channel))
            figfile = '{name}-{channel:d}-{time:.4g}s-waveform.png'.format(
                name=name, channel=self.channel, time=self.toffset)
        else :
            ax.set_title(self.filename)
            figfile = '{name}-{time:.4g}s-waveform.png'.format(
                name=name, time=self.toffset)
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        if self.twindow < 1.0 :
            ax.set_xlabel('Time [ms]')
            ax.set_xlim(1000.0*self.toffset,
                         1000.0*(self.toffset+self.twindow))
            ax.plot(1000.0*self.time[t0:t1], self.data[t0:t1], 'b')
            if self.show_envelope :
                ax.plot(1000.0*self.time[t0:t1], self.envelope[t0:t1], 'r')
        else :
            ax.set_xlabel('Time [s]')
            ax.set_xlim(self.toffset, self.toffset+self.twindow)
            ax.plot(self.time[t0:t1], self.data[t0:t1], 'b')
            if self.show_envelope :
                ax.plot(self.time[t0:t1], self.envelope[t0:t1], 'r')
        ax.set_ylabel('Amplitude [{:s}]'.format(self.unit))
        fig.tight_layout()
        # on linux the following is not what you want! You want to save this into the current working directory!!!
        fig.savefig(os.path.join(self.filepath, figfile))
        fig.clear()
        plt.close(fig)
        print('saved waveform figure to: %s' % figfile)

    def plot_powerspec(self) :
        fig = plt.figure()
        ax = fig.add_subplot(1, 1, 1)
        name = os.path.splitext(self.filename)[0]
        if self.channel > 0 :
            ax.set_title('{filename} channel={channel:d}'.format(
                filename=self.filename, channel=self.channel))
            figfile = '{name}-{channel:d}-{time:.4g}s-powerspec.png'.format(
                name=name, channel=self.channel, time=self.toffset)
        else :
            ax.set_title(self.filename)
            figfile = '{name}-{time:.4g}s-powerspec.png'.format(
                name=name, time=self.toffset)
        ax.set_xlabel('Frequency [Hz]')
        ax.set_xlim(self.fmin, self.fmax)
        if self.decibel :
            ax.set_ylabel('Signal power [dB]')
        else :
            ax.set_ylabel('Signal power')
        ax.plot(self.freqs, self.power, 'b')
        fig.tight_layout()
        # on linux the following is not what you want! You want to save this into the current working directory!!!
        fig.savefig(os.path.join(self.filepath, figfile))
        fig.clear()
        plt.close(fig)
        print('saved power spectrum figure to: %s' % figfile)

        
    def save_segment(self):
        t0s = int(np.round(self.toffset))
        t1s = int(np.round(self.toffset + self.twindow))
        t0 = int(np.round(self.toffset * self.rate))
        t1 = int(np.round((self.toffset + self.twindow) * self.rate))
        savedata = 1.0 * self.data[t0:t1]
        filename = self.filename.split('.')[0]
        if self.channel > 0:
            segmentfilename = '{name}-{channel:d}-{time0:.4g}s-{time1:.4g}s.wav'.format(
                name=filename, time0=t0s, time1=t1s)
        else:
            segmentfilename = '{name}-{time0:.4g}s-{time1:.4g}s.wav'.format(
                name=filename, time0=t0s, time1=t1s)
        write_audio(segmentfilename, savedata, self.rate)
        print('saved segment to: ' , segmentfilename)
    

    def save_powerspec(self) :
        t0s = int(np.round(self.toffset))
        t1s = int(np.round(self.toffset + self.twindow))
        t0 = int(np.round(self.toffset * self.rate))
        t1 = int(np.round((self.toffset + self.twindow) * self.rate))
        filename = self.filename.split('.')[0]
        if self.channel > 0:
            filename = '{name}-{channel:d}-{time0:.4g}s-{time1:.4g}s-powerspec.csv'.format(
                name=filename, time0=t0s, time1=t1s)
        else:
            filename = '{name}-{time0:.4g}s-{time1:.4g}s-powerspec.csv'.format(
                name=filename, time0=t0s, time1=t1s)
        punit = 'x^2/Hz'
        if self.decibel :
            punit = 'dB'
        with open(filename, 'w') as df:
            df.write('# {:<7s}\t{:s}\n'.format('freq', 'power'))
            df.write('# {:<7s}\t{:s}\n'.format('Hz', punit))
            for f, p in zip(self.freqs, self.power) :
                df.write('{:9.2f}\t{:g}\n'.format(f, p))
        print('saved power spectrum data to: %s' % filename)

        
    def save_envelope(self):
        t0s = int(np.round(self.toffset))
        t1s = int(np.round(self.toffset + self.twindow))
        t0 = int(np.round(self.toffset * self.rate))
        t1 = int(np.round((self.toffset + self.twindow) * self.rate))
        savedata = 1.0 * self.envelope[t0:t1]
        filename = self.filename.split('.')[0]
        if self.channel > 0:
            segmentfilename = '{name}-{channel:d}-{time0:.4g}s-{time1:.4g}s-envelope.wav'.format(
                name=filename, time0=t0s, time1=t1s)
        else:
            segmentfilename = '{name}-{time0:.4g}s-{time1:.4g}s-envelope.wav'.format(
                name=filename, time0=t0s, time1=t1s)
        write_audio(segmentfilename, savedata, self.rate)
        print('saved envelope to: ' , segmentfilename)

    def save_envelope_powerspec(self) :
        t0s = int(np.round(self.toffset))
        t1s = int(np.round(self.toffset + self.twindow))
        t0 = int(np.round(self.toffset * self.rate))
        t1 = int(np.round((self.toffset + self.twindow) * self.rate))
        filename = self.filename.split('.')[0]
        if self.channel > 0:
            filename = '{name}-{channel:d}-{time0:.4g}s-{time1:.4g}s-envelope-powerspec.csv'.format(
                name=filename, time0=t0s, time1=t1s)
        else:
            filename = '{name}-{time0:.4g}s-{time1:.4g}s-envelope-powerspec.csv'.format(
                name=filename, time0=t0s, time1=t1s)
        punit = 'x^2/Hz'
        if self.decibel :
            punit = 'dB'
        with open(filename, 'w') as df:
            df.write('# {:<7s}\t{:s}\n'.format('freq', 'power'))
            df.write('# {:<7s}\t{:s}\n'.format('Hz', punit))
            for f, p in zip(self.envfreqs, self.envpower) :
                df.write('{:9.2f}\t{:g}\n'.format(f, p))
        print('saved power spectrum of envelope to: %s' % filename)
        

    def play_segment(self) :
        if not have_audioio :
            return
        t0 = int(np.round(self.toffset*self.rate))
        t1 = int(np.round((self.toffset+self.twindow)*self.rate))
        playdata = 1.0*self.data[t0:t1]
        fade(playdata, self.rate, 0.1)
        self.audio.play(playdata, self.rate, blocking=False)
        
    def play_all(self) :
        if not have_audioio :
            return
        self.audio.play(self.data, self.rate, blocking=False)
                    

def main(cargs):
    # config file name:
    prog, ext = os.path.splitext(sys.argv[0])
    cfgfile = prog + '.cfg'

    # command line arguments:
    parser = argparse.ArgumentParser(description='Display waveform, spectrogram, power spectrum, envelope, and envelope spectrum of time series data.', epilog=f'version {__version__} by Jan Benda (2015-{__year__})')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('-v', action='count', dest='verbose',
                        help='print debug information')
    parser.add_argument('-c', '--save-config', nargs='?', default='', const=cfgfile, type=str, metavar='cfgfile',
                        help='save configuration to file cfgfile (defaults to {0})'.format(cfgfile))
    parser.add_argument('-f', dest='high_pass', type=float, metavar='FREQ', default=None,
                        help='cutoff frequency of highpass filter in Hz')
    parser.add_argument('-l', dest='low_pass', type=float, metavar='FREQ', default=None,
                        help='cutoff frequency of lowpass filter in Hz')
    parser.add_argument('file', nargs='?', default='', type=str, help='name of the file with the time series data')
    parser.add_argument('channel', nargs='?', default=0, type=int, help='channel to be displayed')
    args = parser.parse_args(cargs)

    # load configuration from the current directory:
    if os.path.isfile(cfgfile) :
        print('load configuration file %s' % cfgfile)
        load_config(cfgfile, cfg)

    # set configuration from command line:
    if args.verbose != None :
        cfg['verboseLevel'][0] = args.verbose
    
    # save configuration:
    if len(args.save_config) > 0 :
        ext = os.path.splitext(args.save_config)[1]
        if ext != '.cfg' :
            print('configuration file name must have .cfg as extension!')
        else :
            print('write configuration to %s ...' % args.save_config)
            dump_config(args.save_config, cfg, cfgsec)
        quit()

    # load data:
    filepath = args.file
    channel = args.channel
    filename = os.path.basename(filepath)
    ext = os.path.splitext(filename)[1]
    if have_audioio :
        rate, data = load_audioio(filepath, channel)
    else :
        rate, data = load_wave(filepath, channel)
    if not args.high_pass is None:
        if not args.low_pass is None:
            data = bandpass_filter(data, rate, args.high_pass, args.low_pass)
        else:
            data = highpass_filter(data, rate, args.high_pass)
    unit = 'a.u.'
    
    # plot:
    sp = SignalPlot(rate, data, unit, filename, channel, os.path.dirname(filepath))


def run():
    main(sys.argv[1:])

if __name__ == '__main__':
    run()

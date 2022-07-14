import os
from audian import SignalPlot, load_wavfile, load_rawfile, have_audioio, load_audioio, highpass_filter

filepath = '210801-000150-Oecanthus.WAV'
#filepath = "210731-125903.WAV"

#filepath = os.getcwd() + '\\' + dataname

# load data:
channel = 0
filename = os.path.basename( filepath )
ext = os.path.splitext( filename )[1]
if ext == '.raw' :
    freq, data, unit = load_rawfile( filepath, channel )
else :
    if have_audioio :
        freq, data, unit = load_audioio( filepath, channel )
    else :
        freq, data, unit = load_wavfile( filepath, channel )
        #freq, data, unit = load_wave( filepath, channel )
        #freq, data, unit = load_audioread( filepath, channel )
highpass_cutoff = 1000.0
data = highpass_filter( freq, data, highpass_cutoff )
#data = bandpass_filter(data, freq)



sp = SignalPlot( freq, data, unit, filename, channel, os.path.dirname( filepath ) )

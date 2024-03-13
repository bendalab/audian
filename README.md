[![PyPI license](https://img.shields.io/pypi/l/audian.svg)](https://pypi.python.org/pypi/audian/)
[![PyPI version](https://badge.fury.io/py/audian.svg)](https://badge.fury.io/py/audian)

# audian - AUDIoANalyzer

Python-based GUI for viewing and analyzing recordings of animal
vocalizations.

Simply run it from a terminal:
``` sh
audian data.wav
```

or call it from a script (see `runfile.py`):

``` py
import audian

filepath = 'data.wav'
high_pass = 500.0
audian.main(['-f', f'{high_pass}', filepath])
```

## audiangui

Still experimental new implementation of `audian` based on
[pyqtgraph](https://pyqtgraph.readthedocs.io):

``` sh
audiangui data.wav
```

I currently explore various possibilities for interactive analysis
of audio signals. Here an incomplete list of ToDos:

- Handle all data in one class
- Implement a proper layout for showing the plot panels, allowing also for
  an optional grid layout.
- FullTracePlot:
  - fix offset problem,
  - indicate time under mouse cursor.
- Interactive high- and low-pass filtering:
  - high- and low-pass filter lines must not cross! Update limits.
  - databrowser should provide the filtered traces to both traceitems and specitems.
  - filter original signal in trace plot and spectrogram plot.
  - play should filter its data on its own.
  - add a toolbar widget for setting filter order.
- Improve downsampling and filtering of traces
- Implement downsampling of spectrograms! Or make it even dependent on window size.
- New plot widget showing power spectrum of visible range
  or slice at current cursor position.
- Improve on the concept of current cursor:
  - play should not stop at visible range but keeps going and scrolls data.
  - make cursor moveable by mouse.
  - some key shortcuts for moving and handling cursor.
- Improve on marking cross hair, cues, regions, events:
  - Cross hair should only be used for measuring! Just a single whitish color.
    Comments only in the table.
    Show points only fom active measurement.
  - Cues and regions have position data with labels. Same for all channels.
    - visualize them by infinite vertical lines/regions, both in plots and
      FullTracePlot (maybe in extra row?).
    - can be set from cursor position/marked region.
    - add key shortcuts to go to next/previous cue.
    - from cue table go to selected cue.
    - how does boris export them?
  - Events are channel specific points.
    - Plotted as dot at data amplitude.
    - Many events per label.
    - Result from some analysis.
    - But should be editable.
  - Event regions are channel specific:
    - Plotted as lines on top of data.
    - Result from some analysis.
    - But should be editable.
- Define interface for analysis on full data, visible range, selected range.
- Have a dockable sidebar for showing metadata, cue tables etc.


### Installation of audiangui in Anaconda3 on windows

Anaconda supports really old versions of PyQt5 and Qt5 only that are
not compatible with a recent pyqtgraph. No fun.

A workaround is to first create a new conda environment. For this open
the windows powershell from the Anaconda navigator. Type in and execute
``` sh
conda create -n Qt python=3.9
```
Then activate the new `Qt` environment:
``` sh
conda activate Qt
```
Then we use `pip` to install PyQt5:
``` sh
pip install PyQt5
```
Change into a directory where you want to put audioio and audian. First, download audioio and install it:
``` sh
git clone https://github.com/janscience/audioio.git
cd audioio
pip install .
cd ..
```
And then do the same with audian:
``` sh
git cone https://github.com/bendalab/audian.git
cd audian
pip install .
```
This installs many other packages (numpy, scipy, etc.).

Then you should be able to run `audiangui` from the power shell

For updating audian do
``` sh
cd audian
git pull origin master
pip install .
```
Same for audioio.


## Run Audian from Spyder IPython console:

In the IPython console do:
``` py
%set_env MPLBACKEND=
! audian -f 1000 -l 15000 data.wav
```

## Installation

Simply run (as superuser):
```
pip install audian
```


## Options

Output of `audian --help`:

``` txt
usage: audian [-h] [--version] [-v] [-c [cfgfile]] [-f FREQ] [-l FREQ] [file] [channel]

Display waveform, spectrogram, power spectrum, envelope, and envelope spectrum of time series data.

positional arguments:
  file                  name of the file with the time series data
  channel               channel to be displayed

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -v                    print debug information
  -c [cfgfile], --save-config [cfgfile]
                        save configuration to file cfgfile (defaults to /usr/local/bin/audian.cfg)
  -f FREQ               cutoff frequency of highpass filter in Hz
  -l FREQ               cutoff frequency of lowpass filter in Hz

version 1.0 by Jan Benda (2015-2022)
```

## Other scientific software for working on timeseries data

- [BioSPPy](https://github.com/scientisst/BioSPPy): The toolbox
  bundles together various signal processing and pattern recognition
  methods geared towards the analysis of biosignals.
  


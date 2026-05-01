# Audian user manual

...

## Full trace overview

In the bottom the full traces are displayed for navigation. Some
computations are needed before they can be displayed. For long
recordings, this processing can last quite a long time. This is
annoying, since this slows down any user interaction.

Two mechanisms help to avoid this:

1. Once the data are processed, the result is stored in the cache
   folder. When you later open the same recording, then no more 
   processing is needed since the processed data is simply loeded from
   the cache.

2. You may generate the processed data in advance via the
   `audian-compress`command line tool. Simply call it with the data
   file(s) as argument(s) and it will generate a file with
   `-fulltrace.wav` added to the file's name inside the same folder
   as the data file. `audian` then uses this file for displaying
   the full traces.

Note, that for short files no processed file will be produced, since
it can be computed quickly enough.

Note, although the `-fulltrace.wav` are wave files, the information
they store are the minima and maxima within data segments. Since they
heavily downsample the data, the sampling rate can drop blow 1Hz - the
smallest rate a wave file can store. Therefore the sampling rate is
multiplied with 1e3 or 1e6.


## Screenshots

With audian you can easily generate screenshots of interesting
snippets of the data and you can use screenshot files to navigate to
these snippets later on.

Pressing `Ctrl + Alt + S` takes a screen shot of the audian window . A
file dialog pops up that allows you to set the name of the resulting
png file. The default file name for the screenshot file is
`screenshot.png`.  You may change the file name to any name you want
to describe the screenshot. But it needs to be a PNG file.

Audian stores the name and position of the displayed data file in the
PNG file's metadata.


### Go to the position shown in a screenshot file

If you drag a screenshot file onto the audian window, then audian
moves the displayed window to the position shown in the
screenshot. The window position is taken from the screenshot's
metadata.
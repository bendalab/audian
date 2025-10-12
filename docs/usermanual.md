# Audian user manual

...

## Screenshots

With audian you can easily generate screenshots of interesting
snippets of the data and you can use screenshot files to navigate to
these snippets later on.

Pressing `Ctrl + Alt + S` takes a screen shot of the audian window . A
file dialog pops up that allows you to set the name and location of
the resulting png file.

The default file name for the screenshot file is
```txt
screenshot-<name>-<time>.png
```
where `<time>` is the position of the time window currently shown in
audian relative to the content of the data file with name `<name>`
(with dashes in the file name removed). For example,
```txt
screenshot-logger1120250911T001627-2m7s014ms.png
```
You may change `screenshot` to any name you want, but we recommend to
keep the dash followed by `<name>` and `<time>`. For example, you may
change the screenshot file name to
```txt
pulse-fish-logger1120250911T001627-2m7s014ms.png
```


### Go to the position shown in a screenshot file

If you drag a screenshot file onto the audian window, then audian
moves the displayed window to the position shown in the
screenshot. The window position is taken from the screenshot's
filename. This only works if the screenshot filename ends with
`-<name>-<time>.png`, where `<name>` and `<time>` are the name of the
file displayed and the window position within this file, as described
above.

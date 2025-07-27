"""Analyze a selected region.

- class `Analyzer`: Base class for analyzing selected regions.
- class `PlainAnalyzer`: Implementation of an Analyzer that stores the analysis window into the table.
"""

from math import floor, log10
import pyqtgraph as pg
from thunderlab.tabledata import TableData


class Analyzer(object):
    """Base class for analyzing selected regions.

    Classes inheriting the `Analyzer` class need to reimplement the
    `analyze()` function. Their constructor takes an instance of the
    DataBrowser as the only argument. See class `PlainAnalyzer` as an
    example.

    The constructor adds columns to the table where analysis results
    are stored (`make_column()` function) and initializes event
    markers to be plotted on top of traces or into specific panels
    (`make_trace_events()` and `make_panel_events()` functions).

    The `analyze()` function then stores analysis results into the
    table (`store()` function) and plots event markers (`set_events()`
    and `add_events()` functions).

    Parameters
    ----------
    browser: DataBrowser
        Instance of the data browser.
    name: str
        Name of the analyzer implementation.
    source_name: str
        Source trace on which the analyzer will work on.

    Attributes
    ----------
    browser: DataBrowser
        Instance of the data browser.
    name: str
        Name of the analyzer implementation.
    source_name: str
        Source trace on which the analyzer will work on.
    source: BufferedData
        Trace on which the analyzer will work on.
        You rarely need to access the full source trace, since
        `analyze()` provides all the traces of the selected region.
    data: thunderlab.TableData
        The table storing the analysis results.
    events: dict of list of pyqtgraph.ScatterPlotItem
        Dictionary of the plot items for plotting event markers.

    Methods
    -------
    - `analyze()`: Analysis function. 
    - `traces()`: Names of all available data traces. 
    - `trace()`: Full data trace of a given name
    - `make_column()`: Make a column for the table collecting the analysis results.
    - `store()`: Store analysis results in table. 
    - `make_trace_events()`: Prepare events for plotting on top of a specific trace.
    - `make_panel_events()`: Prepare events for plotting in a specific panel. 
    - `set_events()`: Plot event markers. 
    - `add_events()`: Plot additional event markers.

    """

    def __init__(self, browser, name, source_name):
        self.browser = browser
        self.name = name
        self.source_name = source_name
        self.source = self.trace(self.source_name)
        self.data = TableData()
        self.events = {}
        self.browser.add_analyzer(self)


    def clear(self):
        """Clear the data table and the markers.
        """
        self.data.clear_data()
        for name in self.events:
            for c in range(len(self.events[name])):
                self.events[name][c].clear()

        
    def analyze(self, t0, t1, channel, traces):
        """Analysis function.

        This function is called whenever a region is selected for
        analysis. Reimplement it for your purposes.

        Parameters
        ----------
        t0: float
            Start time of the selected region.
        t1: float
            End time of the selected region.
        channel: int
            Channel of the selected region.
        traces: dict of arrays
            Dictionary with all data traces cut out between `t0` and `t1`.
            Keys are the names of the data traces.
        """
        pass


    def traces(self):
        """Names of all available data traces.
        
        Returns
        -------
        traces: list of str
            Names of all available data traces.
        """
        return self.browser.data.keys()


    def trace(self, name):
        """Full data trace of a given name.

        Parameters
        ----------
        name: str
            Name of the requested data trace.

        Returns
        -------
        trace: BufferedData or None
            Full data trace or None if name was not found.
        """
        if name in self.browser.data:
            return self.browser.data[name]
        else:
            return None


    def make_column(self, label, unit=None, formats=None):
        """Make a column for the table collecting the analysis results.

        Analysis results are stored in a table. Each Analyzer can add
        columns to this table in its constructor using this function.

        Parameters
        ----------
        label: str
            Label of the column.
        unit: str
            Unit of the values stored in this column.
        formats: str
            Format string for the values stored in this column.
        """
        self.data.append(label, unit, formats)

        
    def store(self, *args):
        """Store analysis results in table.

        Call this function once in `analyze()` with as many arguments
        as columns generated using `make_column()`.

        Parameters
        ----------
        *args: float, int, or str
            Values to be stored in the table.
            As many values as columns generated using `make_column()`.

        """
        self.data.add(args, 0)

        
    def make_trace_events(self, name, trace_name, symbol, color, size):
        """Prepare events for plotting on top of a specific trace.

        Call this function in the constructor if your `analyze()`
        function wants to plot some event markers onto a trace using
        the `set_events()` or àdd_events()` functions.

        Parameters
        ----------
        name: str
            Name identifying the events.
        trace_name: str
            Name of the trace on which the event markers should be plotted.
        symbol: str
            Symbol to be used for plotting event markers.

            See [pyqtgraph.ScatterPlotItem.setSymbol()](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/scatterplotitem.html)
            for options.
        color: pyqtgraph color specifier
            Color of the marker symbol.
        size: int or float
            Size of the event marker.

        """
        self.events[name] = []
        for c in range(self.browser.data.data.channels):
            spi = pg.ScatterPlotItem()
            spi.setSymbol(symbol)
            spi.setBrush(color)
            spi.setSize(size)
            self.events[name].append(spi)
            self.browser.add_to_panel_trace(trace_name, c, spi)

        
    def make_panel_events(self, name, panel_name, symbol, color, size):
        """Prepare events for plotting in a specific panel.

        Call this function in the constructor if your `analyze()`
        function wants to plot some event markers in a specific panel
        using the `set_events()` or àdd_events()` functions.

        Parameters
        ----------
        name: str
            Name identifying the events.
        panel_name: str
            Name of the panel on which the event markers should be plotted.
        symbol: str
            Symbol to be used for plotting event markers.

            See [pyqtgraph.ScatterPlotItem.setSymbol()](https://pyqtgraph.readthedocs.io/en/latest/api_reference/graphicsItems/scatterplotitem.html)
            for options.
        color: pyqtgraph color specifier
            Color of the marker symbol.
        size: int or float
            Size of the event marker.

        """
        self.events[name] = []
        panel = self.browser.panels[panel_name]
        for ax in panel.axs:
            spi = pg.ScatterPlotItem()
            spi.setSymbol(symbol)
            spi.setBrush(color)
            spi.setSize(size)
            self.events[name].append(spi)
            ax.add_item(spi)

        
    def set_events(self, name, channel, x, y):
        """Plot event markers.

        Call this function from the analyze() function
        for plotting event markers.
        Previously plotted event markers are erased.

        Parameters
        ----------
        name: str
            Name identifying the events.
            This is the name that has been used when calling
            `make_trace_events()` or `make_panel_events()`
        channel: int
            Channel where to plot the data.
            If negative, plot them on all channels.
        x: array of float
            x-coordinates of the event marker.
        y: array of float
            y-coordinates of the event marker.

        """
        for c in range(self.browser.data.data.channels):
            if c == channel or channel < 0:
                self.events[name][c].setData(x, y)
            else:
                self.events[name][c].clear()
        
        
    def add_events(self, name, channel, x, y):
        """Plot additional event markers.

        Call this function from the analyze() function
        for plotting event markers.
        Previously plotted event markers are not erased.

        Parameters
        ----------
        name: str
            Name identifying the events.
            This is the name that has been used when calling
            `make_trace_events()` or `make_panel_events()`
        channel: int
            Channel where to plot the data.
            If negative, plot them on all channels.
        x: array of float
            x-coordinates of the event marker.
        y: array of float
            y-coordinates of the event marker.

        """
        for c in range(self.browser.data.data.channels):
            if c == channel or channel < 0:
                self.events[name][c].addPoints(x, y)
        
        
class PlainAnalyzer(Analyzer):
    """Implementation of an Analyzer that stores the analysis window into the table.

    This analyzer is name 'plain' and simply stores start and end time
    of the slected region, the duration of the selected time interval,
    and the channel into the table.

    Parameters
    ----------
    browser: DataBrowser
        Instance of the data browser.

    Methods
    -------
    - `analyze()`: Analysis function.

    """

    def __init__(self, browser):
        super().__init__(browser, 'plain', 'data')
        nd = int(floor(-log10(1/self.source.rate)))
        if nd < 0:
            nd = 0
        self.make_column('tstart', 's', f'%.{nd}f')
        self.make_column('tend', 's', f'%.{nd}f')
        self.make_column('duration', 's', f'%.{nd}f')
        self.make_column('channel', '', '%.0f')

        
    def analyze(self, t0, t1, channel, traces):
        """Analyze the selected region.
        """
        self.store(t0, t1, t1 - t0, channel)

        

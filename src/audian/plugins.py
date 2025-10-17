import os
import sys
import importlib

from pathlib import Path

from .bufferedfilter import BufferedFilter
from .bufferedspectrogram import BufferedSpectrogram


def default_setup_traces(browser):
    browser.add_trace(BufferedFilter())
    browser.add_trace(BufferedSpectrogram())


class Plugins(object):

    def __init__(self):
        self.plugins = {}
        self.trace_factories = []
        self.add_trace_factory(default_setup_traces)
        self.analyzer_factories = []


    def add_plugin(self, name, module):
        self.plugins[name] = module


    def add_trace_factory(self, factory_func):
        self.trace_factories.append(factory_func)


    def clear_trace_factories(self):
        self.trace_factories = []


    def add_analyzer_factory(self, factory_func):
        self.analyzer_factories.append(factory_func)


    def clear_analyzer_factories(self):
        self.analyzer_factories = []

        
    def load_plugins(self):
        cwd = Path.cwd()
        sys.path.append(os.fspath(cwd))
        for module in cwd.glob('audian*.py'):
            x = importlib.import_module(module.stem)
            called = False
            for k in dir(x):
                if k.startswith('audian_') and callable(getattr(x, k)):
                    if k.endswith('traces'):
                        self.add_trace_factory(getattr(x, k))
                        called = True
                    elif k.endswith('analyzer'):
                        self.add_analyzer_factory(getattr(x, k))
                        called = True
            if called:
                self.add_plugin(k, x)
                print(f'loaded audian plugins from {module.stem}')
        sys.path.pop()


    def setup_traces(self, browser):
        for f in self.trace_factories:
            f(browser)

            
    def setup_analyzer(self, browser):
        for f in self.analyzer_factories:
            f(browser)

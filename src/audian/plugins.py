import os
import sys
import glob
import importlib
from .bufferedfilter import BufferedFilter
from .bufferedenvelope import BufferedEnvelope
from .bufferedspectrogram import BufferedSpectrogram


def default_setup_traces(browser):
    browser.add_trace(BufferedFilter())
    browser.add_trace(BufferedEnvelope())
    browser.add_trace(BufferedSpectrogram())


class Plugins(object):

    def __init__(self):
        self.plugins = {}
        self.trace_factories = []
        self.add_trace_factory(default_setup_traces)


    def add_plugin(self, name, module):
        self.plugins[name] = module


    def add_trace_factory(self, factory_func):
        self.trace_factories.append(factory_func)


    def clear_traces(self):
        self.trace_factories = []


    def load_plugins(self):
        sys.path.append(os.getcwd())
        for module in glob.glob('audian*.py'):
            x = importlib.import_module(module[:-3])
            called = False
            for k in dir(x):
                if k.startswith('audian_') and callable(getattr(x, k)):
                    if k.endswith('traces'):
                        self.add_trace_factory(getattr(x, k))
                        called = True
            if called:
                self.add_plugin(k, x)
                print(f'loaded audian plugins from {module}')
        sys.path.pop()


    def setup_traces(self, browser):
        for f in self.trace_factories:
            f(browser)

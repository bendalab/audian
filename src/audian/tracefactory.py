import os
import sys
import glob
import importlib
from .bufferedfilter import BufferedFilter
from .bufferedenvelope import BufferedEnvelope
from .bufferedspectrogram import BufferedSpectrogram


def default_factory(factory):
    factory.clear()
    return [BufferedFilter(),
            BufferedEnvelope(),
            BufferedSpectrogram()]


class TraceFactory(object):

    def __init__(self):
        self.factories = []
        self.add(default_factory)


    def add(self, factory_func):
        self.factories.append(factory_func)


    def clear(self):
        self.factories = []


    def load_plugins(self):
        sys.path.append(os.getcwd())
        for module in glob.glob('audian*.py'):
            x = importlib.import_module(module[:-3])
            called = False
            for k in dir(x):
                if k.startswith('audian_') and callable(getattr(x, k)):
                    self.add(getattr(x, k))
                    called = True
            if called:
                print(f'loaded audian plugins from {module}')
        sys.path.pop()


    def traces(self):
        t = []
        for f in self.factories:
            t.extend(f(self))
        return t

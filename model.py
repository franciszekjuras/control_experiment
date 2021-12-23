import matplotlib.pyplot as plt
from labpy.types import Series, NestedDict

class Model:

    def __init__(self, data, idx='x', verbose=False, bounds={}):
        self._data = data
        self._sett = NestedDict(data['settings'])
        self._idx = idx
        self._v = bool(verbose)
        self.bounds = bounds

    @property
    def params(self):
        return ('r', 'gr', 'f', 'ph', 'c1', 'g1', 'c2', 'g2', 'off')

    def normalize(self, dest=None):
        raise NotImplementedError()

    def fit(self):
        return {
            'oscil': self._oscil_fit(),
            'const': self._const_fit()
        }

    def _oscil_fit(self):
        rot = Series(self._data[self._idx])

    def _const_fit(self):
        rot = Series(self._data[self._idx])

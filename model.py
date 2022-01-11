import matplotlib.pyplot as plt
from labpy.types import Series, NestedDict

class Model:

    def __init__(self, data, idx='x', verbose=False, bounds={}):
        self._data = data
        self._sett = NestedDict(data['settings'])
        self._idx = idx
        self._v = bool(verbose)
        self.bounds = bounds
        self.osc_freq = data.settings['current_source']['sweep'][-1] \
                        * data.settings['current_source'].get('field_coef', 4e6)

    @property
    def params(self):
        return ('r', 'gr', 'f', 'ph', 'c1', 'g1', 'c2', 'g2', 'off')

    def fit(self):
        rot = Series(self._data[self._idx])
        rot_con, rot_osc = self._filter(rot)

        # return self._oscil_fit() + self._const_fit()

    def _filter(self, rot):
        samp_freq = rot.freq
        nyq_freq = samp_freq/2.

    def _oscil_fit(self):
        rot = Series(self._data[self._idx])

    def _const_fit(self):
        rot = Series(self._data[self._idx])

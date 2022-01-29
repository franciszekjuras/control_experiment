import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from labpy.types import Series, NestedDict, DataList
from labpy import dsp
from labpy import utils

class Model:

    def __init__(self, data: DataList, idx='x', bounds={}, verbose=False):
        self._data = data
        self._meta = data.meta
        self._settings = NestedDict(data.settings)
        self._idx = idx
        self.bounds = bounds
        '''dict: Bounds for fit parameters. Estimated from data if not specified,
        except decay parameters `gr`, `g1` and `g2`'''
        self._v = verbose
        self.hyper_params = {'osc_freq_window': 0.1, 'filter_atten_dB': 52.}
        self.result = []
        '''Model fit results'''
        # self.osc_freq = data.settings['current_source']['sweep'][-1] \
        #                 * data.settings['current_source'].get('field_coef', 4e6)

    @property
    def params(self):
        return ('r', 'gr', 'f', 'ph', 'c1', 'g1', 'c2', 'g2', 'off')

    def process(self):
        '''Process measruements (e.g. normalize) and fit model.
        Result is stored in `result` attribute
        '''
        self.result = [self._process_shot(shot) for shot in self._data]

    def _process_shot(self, shot: dict):
        settings = self._settings
        settings.shadow = shot['settings']
        idx = self._idx
        rot: Series = shot[idx]
        samp_freq = rot.freq
        osc_freq = self._freq_estimate(rot)
        print(f'osc_freq: {osc_freq:.3f} Hz')
        kerlp, kerbp = self._calc_filter_kernels(samp_freq, osc_freq)
        dead_time = len(kerlp) / samp_freq / 2
        if self._v: print(f'dead_time: {dead_time*1e3:.3f} ms')
        rotlp = dsp.filter(rot, kerlp).cut(dead_time, -dead_time)
        rotbp = dsp.filter(rot, kerbp).cut(dead_time, -dead_time)
        if idx + '_norm' in shot:
            # Filter normalization data and normalize rotlp and rotbp
            print("Normalization not implemented. Normalization data ignored.")
        else:
            if self._v: print('No normalization data. Fitting to raw signal.')
        fit_bp_res = self._fit_bp(rotbp, osc_freq)

    def _fit_bp(self, rot, osc_freq):
        bounds = self._bounds_bp(rot, osc_freq)
        pass

    def _bounds_bp(self, rot, osc_freq):
        bounds = self.bounds.copy()
        if 'r' not in bounds:
            ptp = np.max(rot.y) - np.min(rot.y)
            bounds['r'] = [0, ptp]
        if 'f' not in bounds:
            bounds['f'] = [osc_freq * (1 + s * self.hyper_params['osc_freq_window']) for s in [-1, 1]]
        if 'ph' not in bounds:
            bounds['ph'] = [-2 * np.pi, 2 * np.pi]
        return [bounds[idx] for idx in self.params[0:4]]

    def _bounds_lp(self, rot):
        bounds = self.bounds.copy()
        maxv, minv =  np.max(rot.y), np.min(rot.y)
        ptp = maxv - minv
        if 'c1' not in bounds:
            bounds['c1'] = [-4* ptp, 4* ptp]
        if 'c2' not in bounds:
            bounds['c2'] = [-4* ptp, 4* ptp]
        if 'off' not in bounds:
            bounds['off'] = [rot.y[-1] - ptp, rot.y[-1] + ptp]
        return [bounds[idx] for idx in self.params[4:9]]


    def _calc_filter_kernels(self, samp_freq, osc_freq):
        nyq_freq = samp_freq/2.
        lpcutoff = 0.5*0.98*osc_freq/2.
        atten = self.hyper_params['filter_atten_dB']
        taps, beta = signal.kaiserord(atten, 2*lpcutoff/nyq_freq)
        kerlp = signal.firwin(taps, lpcutoff, window=('kaiser', beta), fs=samp_freq)
        kerbp = signal.firwin(taps, (osc_freq - lpcutoff, osc_freq + lpcutoff),
                              window=('kaiser', beta), fs=samp_freq, pass_zero=False)
        return kerlp, kerbp

    def _freq_estimate(self, rot: Series):
        settings = self._settings
        osc_freq = settings[('current_source','sweep')][-1] \
                   * settings.get(('current_source','field_coef'), 4e6)
        osc_freq_wind = self.hyper_params['osc_freq_window']
        fft_range = [osc_freq * (1 + s * osc_freq_wind) for s in [-1, 1]]
        rot_fft = dsp.fft(rot.cut(5e-3, 45e-3), pad=8).slice(*fft_range)
        freq = rot_fft.x[np.argmax(rot_fft.abs().y)]
        #TODO: better thresholding
        if utils.in_bounds(freq, fft_range, rel=0.05):
            osc_freq = freq
        else:
            if self._v: print("No frequency peak found")
        return osc_freq

def chi_squared_gen(model):
    return lambda params, x, y: np.sum(np.square(model(x, *params) - y))

def model_bp(x, r, gr, f, ph):
    return r * np.sin(2*np.pi*f * x + ph) * np.exp(-gr * x)

class model_lp_gen:
    def __init__(self, slow_decay: bool = True, fast_decay: bool = True, offset: float = None):
        self._fast_decay = bool(fast_decay)
        self._slow_decay = bool(slow_decay)
        self._offset = offset

    def strip_params(self, params):
        p = list(params)
        i = 0
        for decay in [self._slow_decay, self._fast_decay]:
            if not decay:
                del p[i:i+2]
            else:
                i += 2
        if self._offset is not None:
            del p[-1:]
        return p

    def full_params(self, params):
        p = []
        for decay in [self._slow_decay, self._fast_decay]:
            if decay:
                c, g, *params = params
                p += [c, g]
            else:
                p += [0., 0.]
        if self._offset is None:
            c, = params
            p += [c]
        else:
            p += [self._offset]
        return p

    def __call__(self, *args):
        x, *params = args
        c1, g1, c2, g2, off = self.full_params(params)
        res = np.full_like(x, off, dtype=np.float64)
        if c1 != 0.:
            res += c1 * np.exp(-g1 * x)
        if c2 != 0.:
            res += c2 * np.exp(-g2 * x)
        return res

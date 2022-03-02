import matplotlib.pyplot as plt
import numpy as np
from scipy import signal
from scipy.optimize import differential_evolution, curve_fit
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
        self.hyper_params = {'osc_freq_window': 0.1, 'osc_fft_rel_density': 1000,
                             'filter_atten_dB': 52., 'lp_est_dec_freq': 1e3}
        self.result = []
        '''list[dict]: Model fit results'''
        # self.osc_freq = data.settings['current_source']['sweep'][-1] \
        #                 * data.settings['current_source'].get('field_coef', 4e6)

    @property
    def params(self):
        return ('r', 'gr', 'f', 'ph', 'c1', 'g1', 'c2', 'g2', 'off')

    def apply(self, x, params=None):
        x = np.asarray(x)
        if params is None:
            return [self.apply(x, r['best fit']) for r in self.result]
        if isinstance(params, dict):
            params = [params[i] for i in self.params]
        bp_params, lp_params = params[0:4], params[4:]
        y = model_bp(x, *bp_params) + model_lp_gen()(x, *lp_params)
        return Series(y, x)

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
        bp_best_fit, bp_sd = self._fit_bp(rotbp, osc_freq)
        lp_best_fit, lp_sd = self._fit_lp(rotlp)
        # best_fit_l = list(bp_best_fit) + list(lp_best_fit)
        # fit_sd_l = list(np.sqrt(np.diag(bp_cov_matrix))) + list(np.sqrt(np.diag(lp_cov_matrix)))
        best_fit = dict(zip(self.params, bp_best_fit + lp_best_fit))
        fit_sd = dict(zip(self.params, bp_sd + lp_sd))
        return {'best fit': best_fit, 'fit sd': fit_sd}

    def _fit_lp(self, rot):        
        bounds = self._bounds_lp(rot)
        estimates = self._estimates_lp(rot, bounds)
        if self._v: print('lp est:', estimates)
        model = model_lp_gen()
        res = curve_fit(model, *rot.xy, estimates, bounds=list(zip(*bounds)))
        bounds_d = dict(zip(self.params[-5:], bounds))
        fit = dict(zip(self.params[-5:], res[0]))
        slow_decay = True
        if not utils.in_bounds(fit['g1'], bounds_d['g1'], rel=0.05):
            slow_decay = False
            model = model_lp_gen(slow_decay=slow_decay)
            sp = model.strip_params
            res = curve_fit(model, *rot.xy, sp(estimates), bounds=list(zip(*sp(bounds))))
            fit = dict(zip(self.params[-5:], model.full_params(res[0])))
        if not utils.in_bounds(fit['g2'], bounds_d['g2'], rel=0.05):
            model = model_lp_gen(slow_decay=slow_decay, fast_decay=False)
            sp = model.strip_params
            res = curve_fit(model, *rot.xy, sp(estimates), bounds=list(zip(*sp(bounds))))
            # fit = dict(zip(self.params[-5:], model.full_params(res[0])))
        res = [res[0], np.sqrt(np.diag(res[1]))]
        res = [model.full_params(p) for p in res]
        return res

    def _fit_bp(self, rot, osc_freq):
        bounds = self._bounds_bp(rot, osc_freq)
        estimates = self._estimates_bp(rot, osc_freq, bounds)
        if self._v: print('bp est:', estimates)
        res = curve_fit(model_bp, *rot.xy, estimates, bounds=list(zip(*bounds)))        
        res = [list(res[0]), list(np.sqrt(np.diag(res[1])))]
        return res

    def _estimates_lp(self, rot: Series, bounds):
        rot = rot.decimate(freq=self.hyper_params['lp_est_dec_freq'])
        est = differential_evolution(chi_squared, bounds, args=(rot.x, rot.y, model_lp_gen()))
        # Multiprocessing resulted in slower computation :(
        # est = differential_evolution(chi_squared, bounds, args=(rot.x, rot.y, model_lp_gen()), workers=1, updating='deferred')
        return list(est.x)

    def _estimates_bp(self, rot, osc_freq, bounds):
        est = {}
        pad = self.hyper_params['osc_fft_rel_density'] / osc_freq / rot.span
        if self._v: print(f'pad: {pad:.1f}')
        if pad < 1.:
            pad = 1.
        fft = dsp.fft(rot, pad = pad)
        freq_bound = [osc_freq * (1 + s * self.hyper_params['osc_freq_window']) for s in [-1, 1]]
        fft = fft.slice(*freq_bound)
        maxi = np.argmax(fft.abs().y)
        ph = fft.angle().y[maxi] + (np.pi/2)
        if ph > np.pi: ph -= 2 * np.pi
        est['ph'] = ph
        est['f'] = fft.x[maxi]
        est['r'] = np.max(rot.cut(r=2./osc_freq).abs().y)
        est['gr'] = dsp.fwhm(fft.abs(), est['f']) * 2
        for idx, bound in zip(self.params[0:4], bounds):
            if not utils.in_bounds(est[idx], bound):
                if self._v: print(f"Parmater {idx} estimation ({est[idx]}) is out of bounds {bound}. Changing to bounds average.")
                est[idx] = np.average(bound)
        return [est[idx] for idx in self.params[0:4]]

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

def chi_squared(params, x, y, model):
    return np.sum(np.square(model(x, *params) - y))

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

    def __call__(self, x, *params):
        c1, g1, c2, g2, off = self.full_params(params)
        res = np.full_like(x, off, dtype=np.float64)
        if c1 != 0.:
            res += c1 * np.exp(-g1 * x)
        if c2 != 0.:
            res += c2 * np.exp(-g2 * x)
        return res

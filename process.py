import localpkgs
import numpy as np
import pickle
import argparse
import matplotlib.pyplot as plt
import scipy.signal as dsp
from labpy.series import Series
import labpy.utils as utils
from statsmodels.tsa.ar_model import AutoReg

def main(args):
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    sers = data["data"]
    if args.params: print(data["params"])
    if args.settings: print(data["settings"])
    sens = utils.str_to_value(data['settings']['lockin']['sensitivity'])
    
    tau = 5e-3
    dmx: Series = (sers['x'] * sens).slice(-tau)
    cut = 5e-3
    # dmx.project(cut, 5e-4)
    # sers['back_proj'] = dmx.copy_y()

    ker = dsp.firwin(int(2 * tau // dmx.dx), 100, fs=dmx.freq, scale=True)
    kerbp = dsp.firwin(int(2 * tau // dmx.dx), (300, 500), fs=dmx.freq, pass_zero=False)
    kerbp2 = dsp.firwin(int(2 * tau // dmx.dx), (200, 600), fs=dmx.freq, pass_zero=False)
    sers['filter'] = Series(*dsp.freqz(kerbp, worN=int(1e4), fs=dmx.freq)[::-1]).slice(0, 1e3)

    mon = sers["mon1"] + sers["mon2"]
    mon = mon.slice(0) - np.mean(mon.slice(r=0).y)
    mon.y = dsp.convolve(mon.y, ker, mode='same')
    mon = mon.slice(tau, -tau, rel=True)
    mon_poly = np.polynomial.Polynomial.fit(*mon.xy, deg=2)
    monfit = Series(mon_poly(dmx.x), dmx.x)
    dmx /= monfit
    sers['monfit'] = monfit

    x_sta = dmx.filter(ker)
    # x_sta.project(cut)
    # x_sta_poly = np.polynomial.Polynomial.fit(*x_sta.slice(tau, 3*tau).xy, deg=2)
    # x_sta_beg = x_sta.slice(0, tau)
    # x_sta_beg.y[:] = x_sta_poly(x_sta_beg.x)
    
    sers['x_static'] = x_sta
    # sers['x1'] = dmx - x_sta
    sers['x'] = dmx.filter(kerbp)
    # sers['x2'] = dmx.filter(kerbp2)
    sers['mon'] = mon

    fig, _ = plt.subplots(3)
    axs = fig.axes
    fig.set_tight_layout(True)
    for k, i in (('x', 0),('x_static', 0),('mon', 1),('monfit', 1)):
        axs[i].plot(*sers[k].xy)
    axs[2].plot(*sers['filter'].abs().xy)
    # axs[2].loglog(*sers['x'].slice(0, 0.1).fft().abs().xy)
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for processing measurement results")
    parser.add_argument("file", help="File with data to process")
    parser.add_argument("-p", "--params", action="store_true", help="Show measurement parameters")
    parser.add_argument("-e", "--settings", action="store_true", help="Show measurement settings")
    args = parser.parse_args()
    main(args)

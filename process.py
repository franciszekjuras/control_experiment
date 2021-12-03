import localpkgs
import numpy as np
import pickle
import argparse
import matplotlib.pyplot as plt
import scipy.signal as dsp
from labpy.series import Series

def main(args):
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    sers = data["data"]
    if args.params: print(data["params"])
    if args.settings: print(data["settings"])

    mon = sers["mon1"] + sers["mon2"].y
    mon = mon.slice(0) - np.mean(mon.slice(r=0).y)
    mon_org = mon.copy_y()
    sers['mon_org'] = mon_org
    tau = 10e-3
    ker = dsp.firwin(int(2 * tau // mon.dx), 200, fs=mon.freq, scale=True)
    sers['ker'] = Series(*dsp.freqz(ker, worN=int(1e4), fs=mon.freq)[::-1]).slice(0, 1e3)
    mon.y = dsp.convolve(mon.y, ker, mode='same')
    mon = mon.slice(tau, -tau, rel=True)
    mon_poly = np.polynomial.Polynomial.fit(*mon.xy, deg=2)
    monfit = Series(mon_poly(mon_org.x), mon_org.x)
    sers['monfit'] = monfit

    sers['mon'] = mon

    fig, _ = plt.subplots(3)
    axs = fig.axes
    fig.set_tight_layout(True)
    for k, i in (('x', 0),('mon', 1),('monfit', 1)):
        axs[i].plot(*sers[k].xy)
    axs[2].plot(*sers['ker'].abs().xy)
    # axs[2].loglog(*sers['x'].slice(0, 0.1).fft().abs().xy)
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for processing measurement results")
    parser.add_argument("file", help="File with data to process")
    parser.add_argument("-p", "--params", action="store_true", help="Show measurement parameters")
    parser.add_argument("-e", "--settings", action="store_true", help="Show measurement settings")
    args = parser.parse_args()
    main(args)

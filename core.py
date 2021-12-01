import localpkgs
import pyvisa
import PyDAQmx as dmx
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import pickle
import argparse
from datetime import datetime
import constants
from labpy.arduinopulsegen import ArduinoPulseGen
from labpy.daqmx import Measurement
from labpy import series
from labpy.series import Series, Average, from2darray
from labpy.srs import Srs
from labpy.wavemeter import Wavemeter
from labpy.keithley_cs import KeithleyCS

rm = pyvisa.ResourceManager()

def main():
    parser = argparse.ArgumentParser(description="Program for tweaking experimental sequence")
    parser.add_argument("--list", "-l", action="store_true")
    parser.add_argument("--aom", "-a", action="store_true")
    parser.add_argument("--save", "-s", nargs='?', const="data/tests/", default=None)
    args = parser.parse_args()
    exec_aux_commands(args)
    params = {}
    s = {}

    s["daq"] = {"chs_n": 7, "freq":40e3, "time": 300e-3, "t0": -50e-3}
    cs = s["daq"]
    daq = Measurement("Dev1", channels="ai0:"+str(cs["chs_n"]-1)
        , freq=cs["freq"], time=cs["time"]-cs["t0"], trig="PFI2", t0=cs["t0"])

    pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
    pulsegen.time_unit = "ms"
    pulsegen.xon(("pumpEn")) # Reversed polarity
    constZt = [-210, 0]
    constZt = sum([[v, v + 0.01] for v in constZt],[])
    s["timing"] = {
        "pumpEn": (-200, -5), "probeEn": (0, 300),
        "daqTrig": (0, 0.01), "constZTrig": constZt
    }
    for k, v in s["timing"]:
        pulsegen.add(k, v)

    lockin = Srs(rm, "Lock-in", auxout_map=constants.lockin.auxout)
    s["lockin"] = {
        'source': 'internal', 'reserve': 'low noise',
        'frequency': 5e4, 'phase': -21., 'sensitivity': '2 mV',
        'time_constant': '300 us', 'filter_slope': '24 dB/oct'
    }
    s["auxout"] = {"aom1": 6., "aom2": 6, "pulseAmp": 0.5}
    lockin.setup(s["lockin"])
    for k, v in s["auxout"]:
        lockin.auxout(k, v)

    pulse_current = 100e-6
    s["current source"] = {"pulse current": pulse_current}
    curr_src = KeithleyCS(rm, "KEITHLEY")
    curr_src.set_remote_only()
    curr_src.current = 0.
    curr_src.set_sweep((0, pulse_current))

    wavemeter = Wavemeter(rm, "Wavemeter")
    params["laser freq THz"] = wavemeter.frequency(1)
    print(f"Laser frequency: {1e3*params['laser freq THz']:.3f} GHz")

    plt.ion()
    fig, axs = plt.subplots(3)
    axs = fig.axes
    avgs = [Average() for _ in range(daq.chs_n)]
    time.sleep(0.1)

    t = np.linspace(daq.t0, daq.time + daq.t0, daq.samples, endpoint=False)

    for i in range(3):
        curr_src.init()
        daq.start()
        time.sleep(-daq.t0)
        pulsegen.run()
        data = daq.read(10)
        series = from2darray(data, t)
        for avg, ser in zip(avgs, series):
            avg.add(ser.y)
        for ax in axs:
            ax.clear()
        for i, ser in zip((0,0,1,1,1,2), series):
            axs[i].plot(*ser.xy)
        axs[1].set_xbound([-0.1e-3, 0.2e-3])
        axs[2].set_xbound([-0.1e-3, 0.2e-3])
        fig.canvas.draw()
        fig.canvas.flush_events()

    avgs = {k:avg.value for (k, avg) in zip(constants.daq.labels, avgs)}
    avgser = {key:Series(avg, t) for (key, avg) in avgs.items()}
    fig, axs = plt.subplots(3)
    for i, ser in zip((0,0,1,1,1,2), avgser.values()):
        axs[i].plot(*ser.xy)
    fig.canvas.draw()
    fig.canvas.flush_events()

    if args.save is not None:
        with open(args.save + datetime.now().strftime("SINGLE%y%m%d%H%M%S.pickle")) as f:
            pickle.dump({"data": avgser, "params": params, "settings": s}, f)

    input("Press enter to exit...")

def exec_aux_commands(args):
    exit = False
    if args.list:
        exit = True
        res = [(str(inst.alias), str(inst.resource_name)) for inst in rm.list_resources_info().values()]
        res.insert(0, ("Alias", "Resource name"))
        for el in res:
            print(f"{el[0]:>15}  {el[1]}")
    if args.aom:
        exit = True
        pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
        pulsegen.xon(("probeEn"))
    if exit:
        sys.exit(0)

if(__name__ == "__main__"):
    main()
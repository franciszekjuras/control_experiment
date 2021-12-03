import localpkgs
import pyvisa
import PyDAQmx as dmx
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import pickle
import argparse
from pathlib import Path
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

def main(args):
    exec_aux_commands(args)
    params = {}
    s = {}

    s["daq"] = {"chs_n": 6, "freq":40e3, "time": 300e-3, "t0": -100e-3}
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
    for k, v in s["timing"].items():
        pulsegen.add(k, v)

    lockin = Srs(rm, "Lock-in", auxout_map=constants.lockin.auxout)
    s["lockin"] = {
        'source': 'internal', 'reserve': 'low noise',
        'frequency': 5e4, 'phase': -21., 'sensitivity': '100 uV',
        'time_constant': '300 us', 'filter_slope': '24 dB/oct'
    }
    s["auxout"] = {"aom1": 6., "aom2": 6, "pulseAmp": 0.5}
    lockin.setup(s["lockin"])
    for k, v in s["auxout"].items():
        lockin.auxout(k, v)

    pulse_current = 100e-6
    s["current source"] = {"pulse current": pulse_current}
    curr_src = KeithleyCS(rm, "KEITHLEY")
    curr_src.set_remote_only()
    curr_src.current = 0.
    curr_src.set_sweep((0, pulse_current))

    wavemeter = Wavemeter(rm, "Wavemeter")
    params["moglabs freq"], params["dl100 freq"] = wavemeter.frequency((1,2))
    print(f"Moglabs (probe/pump) frequency: {params['moglabs freq']:.6f} THz\n"
        f"DL100 (pump/repump) frequency: {params['dl100 freq']:.6f} THz")

    plt.ion()
    fig, axs = plt.subplots(2)
    fig.set_tight_layout(True)
    axs = fig.axes
    avgs = [Average() for _ in range(daq.chs_n)]
    time.sleep(0.1)

    t = np.linspace(daq.t0, daq.time + daq.t0, daq.samples, endpoint=False)

    s["avarages"] = args.repeat
    for i in range(s["avarages"]):
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
        for i, ser in zip((0,0,1,1,1), series):
            axs[i].plot(*ser.xy)
        # axs[1].set_xbound([-0.1e-3, 0.2e-3])
        fig.canvas.draw()
        fig.canvas.flush_events()

    avgs = {k:avg.value for (k, avg) in zip(constants.daq.labels, avgs)}
    avgser = {key:Series(avg, t) for (key, avg) in avgs.items()}
    if s["avarages"] != 1:
        fig, axs = plt.subplots(2)
        fig.set_tight_layout(True)
        for i, ser in zip((0,0,1,1,1), avgser.values()):
            axs[i].plot(*ser.xy)
        fig.canvas.draw()
        fig.canvas.flush_events()

    if args.save is not None:
        savepath = Path("data/" + args.save.strip("/\\") + '/' + "SINGLE"
            + datetime.now().strftime("%y%m%d%H%M%S") + args.comment + ".pickle")
        print(savepath.parent)
        savepath.parent.mkdir(exist_ok=True, parents=True)
        with savepath.open("wb") as f:
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
    parser = argparse.ArgumentParser(description="Program for tweaking experimental sequence"
        , formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-s", "--save", nargs='?', const="tests", default=None
        , help="Save data to a file in 'data/tests' or in 'data/DIR' if DIR is specified", metavar="DIR(opt)")
    parser.add_argument("-c", "--comment", default="", help="Append COMMENT to saved file name")
    parser.add_argument("-r", "--repeat", type=int, default=3
        , help="Repeat mesurement (average) N times", metavar='N')
    parser.add_argument("-l", "--list", action="store_true", help="List available devices and exit")
    parser.add_argument("-a", "--aom", action="store_true", help="Test AOMs operation and exit")
    args = parser.parse_args()
    main(args)
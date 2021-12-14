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
import settings
from labpy.devices import daqmx, arduinopulsegen, keithley_cs, srs, tb3000_aom_driver, wavemeter
from labpy.types import Series, Average, NestedDict

class Core:
    def __init__(self, settings):
        self.rm = pyvisa.ResourceManager()
        self.s = NestedDict(settings)
        self.base_settings = self.s.copy()
        self.params = {}
        self.init_devices()
        time.sleep(0.1)

    def init_devices(self):
        self.daq = daqmx.DAQmx(**self.s['daq'])

        timing = self.s['timing']
        self.pulsegen = arduinopulsegen.ArduinoPulseGen(
            self.rm, portmap=constants.arduino.portmap,  **timing)
        self.pulsegen.xon(constants.arduino.reversed_polarity)
        pulses = timing['pulses']
        for k, seq in timing['triggers']:
            pulses[k] = self._trigger_to_pulse(seq)
        for k, v in pulses.items():
            self.pulsegen.xadd(k, v)

        self.lockin = srs.Srs(self.rm, auxout_map=constants.lockin.auxout, **self.s['lockin'])
        for k, v in self.s['lockin'].get('auxout', {}).items():
            self.lockin.auxout(k, v)

        self.curr_src = keithley_cs.KeithleyCS(self.rm, self.s['current_source']['dev'])
        self.curr_src.set_remote_only()
        self.curr_src.current = 0.
        self.curr_src.set_sweep(self.s['current_source']['sweep'])

        self._dev_set = {'daq': self._daq_set, 'timing': self._pulsegen_set,
                         'lockin': self._lockin_set, 'current_source': self._curr_src_set}

        self.wavemeter = wavemeter.Wavemeter(self.rm, constants.wavemeter.dev)

    def set(self, dic):
        for path, v in dic:
            dev, path = path[0], path[1:]
            self._dev_set[dev](path, v)

    def _daq_set(self, path, v):
        raise ValueError(f"Can't set property {path} on daq")

    def _timing_set(self, path, v):
        k, prop = path[0], path[1:]
        if k == 'triggers':
            ch, = prop
            self.pulsegen.xadd(ch, self._trigger_to_pulse(v))
        elif k == 'pulses':
            ch, = prop
            self.pulsegen.xadd(ch, v)
        else:
            raise ValueError(f"Can't set property {path} on timing")

    def _lockin_set(self, path, v):
        k, prop = path[0], path[1:]
        if k == 'settings':
            setting, = prop
            setattr(self.lockin, setting, v)
        elif k == 'auxout':
            ch, = prop
            self.lockin.auxout(ch, v)
        else:
            raise ValueError(f"Can't set property {path} on lockin")

    def _curr_src_set(self, path, v):
        k, prop = path[0], path[1:]
        if k == 'sweep' and len(prop) == 0:
            self.curr_src.set_sweep(v)
        else:
            raise ValueError(f"Can't set property {path} on curr_src")

    def _trigger_to_pulse(self, trigs):
        return sum([[v, v + self.s['timing']['trigger_width']] for v in trigs],[])

    def snap_params(self):
        p = {}
        chs = constants.wavemeter.channels
        freqs = self.wavemeter.frequency(chs)
        p['lasers'] = {ch + ' freq': v for ch, v in zip(chs, freqs)}
        return p


def main(args):
    exec_aux_commands(args)
    setts = settings.load()
    core = Core(settings=settings.load())

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
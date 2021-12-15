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
from labpy.types import Series, Average, NestedDict, DataList

class Core:
    def __init__(self, settings, rm = None):
        self.rm = rm if rm is not None else pyvisa.ResourceManager()
        self._s = NestedDict(settings)
        # self.base_settings = self._s.copy()
        self.params = {}
        self._init_devices()
        time.sleep(0.1)

    def _init_devices(self):
        self.daq = daqmx.DAQmx(**self._s['daq'])

        timing = self._s['timing']
        self.pulsegen = arduinopulsegen.ArduinoPulseGen(
            self.rm, portmap=constants.arduino.portmap,  **timing)
        self.pulsegen.xon(constants.arduino.reversed_polarity)
        pulses = timing['pulses']
        for k, seq in timing['triggers']:
            pulses[k] = self._trigger_to_pulse(seq)
        for k, v in pulses.items():
            self.pulsegen.xadd(k, v)

        self.lockin = srs.Srs(self.rm, auxout_map=constants.lockin.auxout, **self._s['lockin'])
        for k, v in self._s['lockin'].get('auxout', {}).items():
            self.lockin.auxout(k, v)

        self.curr_src = keithley_cs.KeithleyCS(self.rm, self._s['current_source']['dev'])
        self.curr_src.set_remote_only()
        self.curr_src.current = 0.
        self.curr_src.set_sweep(self._s['current_source']['sweep'])

        self._dev_set = {'daq': self._daq_set, 'timing': self._pulsegen_set,
                         'lockin': self._lockin_set, 'current_source': self._curr_src_set}

        self.wavemeter = wavemeter.Wavemeter(self.rm, constants.wavemeter.dev)

    def set(self, dic):
        for path, v in dic:
            dev, path = path[0], path[1:]
            self._dev_set[dev](path, v)
            self._s[path] = v

    @property
    def settings(self):
        return self._s.copy()

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
        return sum([[v, v + self._s['timing']['trigger_width']] for v in trigs],[])

    def snap_params(self):
        p = {}
        chs = constants.wavemeter.channels
        freqs = self.wavemeter.frequency(chs)
        p['lasers'] = {ch + ' freq': v for ch, v in zip(chs, freqs)}
        return p

    @staticmethod
    def _create_figures(specs:dict={}, grid_specs:dict={}):
        figs = {}
        for fig in specs:
            if fig in grid_specs:
                grid_spec = grid_specs[fig]
            else:
                grid_spec = [max([el[1] for el in specs]) - 1]
            f, _ = plt.subplots(*grid_spec)
            f.set_tight_layout(True)
            figs[fig] = {'fig': f, 'spec': specs[fig]}
        return figs

    @staticmethod
    def _zip_scan(scan:dict[list]):
        scan_list = [{k: v for k, v in zip(scan.keys(), lst)}
                               for lst in zip(*scan.values())]
        if len(scan_list) != max([len(el) for el in scan.values()]):
            raise ValueError("All lists in scan should be of same length")
        return scan_list

    @staticmethod
    def _plot(data, fig=None, spec=None):
        if fig is None or spec is None:
            return
        axs = fig.axes
        for ax in axs:
            ax.clear()
        for id, pos, *opt in spec:
            opt = opt[0] if len(opt) else {}
            print(opt)
            axs[pos].plot(*data[id].xy)
        # axs[1].set_xbound([-0.1e-3, 0.2e-3])
        fig.canvas.draw()
        fig.canvas.flush_events()

    def run(self, scan:dict[list]=None, plots:dict={}, grid_specs:dict={}):
        self.result = DataList()
        if scan is not None:
            scan_list = Core._zip_scan(scan)
            self.result.scan = scan
        else:
            scan_list = [{}]
        self.result.settings = self._s.copy()
        self.result.params = self.snap_params()
        plt.ion()
        figs = Core._create_figures(plots, grid_specs).values()
        t = self.daq.space()
        avgs = {k: Average() for k, _
            in zip(constants.daq.labels, range(self.daq.chs_n))}

        for shot_sett in scan_list:
            entry = {}
            self.set(shot_sett)
            entry['settings'] = shot_sett.copy()
            entry['params'] = self.snap_params()
            for _ in range(self._s["averages"]):
                self.curr_src.init()
                self.daq.start()
                time.sleep(-self.daq.t0)
                self.pulsegen.run()
                data = self.daq.read()
                series = dict(zip(constants.daq.labels, Series.from2darray(data, t)))
                for k, ser in series.items():
                    avgs[k].add(ser)
                if self._s['averages'] != 1:
                    Core._plot(series, **figs.get('single', {}))
            series_avg = {k: v.value() for k, v in avgs.items()}
            entry.update(series_avg)
            self.result.append(entry)
            Core._plot(entry, **figs.get('avg', {}))

def main(args):
    rm = pyvisa.ResourceManager()
    exec_aux_commands(args, rm)
    setts = settings.load()
    setts['averages'] = args.repeat
    core = Core(settings=setts, rm=rm)
    core.run()

    input("d - discard, enter to confirm\n:")
    if args.save is not None and c != 'd':
        savepath = Path("data/" + args.save.strip("/\\") + '/' + "SINGLE"
            + datetime.now().strftime("%y%m%d%H%M%S") + args.comment + ".pickle")
        print(savepath.parent)
        savepath.parent.mkdir(exist_ok=True, parents=True)
        with savepath.open("wb") as f:
            pickle.dump(core.result, f)

def exec_aux_commands(args, rm):
    exit = False
    if args.list:
        exit = True
        res = [(str(inst.alias), str(inst.resource_name)) for inst in rm.list_resources_info().values()]
        res.insert(0, ("Alias", "Resource name"))
        for el in res:
            print(f"{el[0]:>15}  {el[1]}")
    if args.aom:
        exit = True
        pulsegen = arduinopulsegen.ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
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
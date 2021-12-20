from __future__ import annotations
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
import settings as stngs
from labpy.devices import daqmx, arduinopulsegen, keithley_cs, srs, tb3000_aom_driver, wavemeter
from labpy.types import Series, Average, NestedDict, DataList
from labpy import utils

class Core:
    def __init__(self, settings='settings', rm = None, args=None):
        self.rm = rm if rm else pyvisa.ResourceManager()
        if not isinstance(settings, dict):
            sett_path = 'settings/' + settings + '.json' if settings else None
            settings = stngs.load(sett_path)
        self._s = NestedDict(settings)
        self._args = args if args else parser.parse_args()
        self._apply_args()
        self.params = {}

    def _apply_args(self, args):
        self._s['averages'] = self._args.repeat
        if self._args.probe:
            self._s['probe_aom']['amplitude'] = self._args.probe

    def _init_devices(self):
        if self._args.list:
            utils.list_visa_devices(self.rm)
            sys.exit()
        if self._args.aom:
            pulsegen = arduinopulsegen.ArduinoPulseGen(self.rm, "Arduino", portmap=constants.arduino.portmap)
            pulsegen.xon(constants.arduino.aom_enable)
            sys.exit()

        self.daq = daqmx.DAQmx(**self._s['daq'])

        timing = self._s['timing']
        self.pulsegen = arduinopulsegen.ArduinoPulseGen(
            self.rm, portmap=constants.arduino.portmap,  **timing)
        self.pulsegen.xon(constants.arduino.reversed_polarity)
        pulses = timing['pulses'].copy()
        for k, seq in timing['triggers'].items():
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

        self.timebase = tb3000_aom_driver.TB3000AomDriver(self.rm, "TB3000")
        for k, v in self._s["probe_aom"].items():
            setattr(self.timebase, k, v)

        self._dev_set = {
            'daq': self._daq_set, 'timing': self._timing_set,
            'lockin': self._lockin_set, 'current_source': self._curr_src_set,
            'probe_aom': self._probe_set,
        }

        self.wavemeter = wavemeter.Wavemeter(self.rm, constants.wavemeter.dev)

        time.sleep(0.1)

    def set(self, dic):
        for path, v in dic.items():
            dev, path = path[0], path[1:]
            if dev:
                self._dev_set[dev](path, v)
                self._s[path] = v

    @property
    def settings(self):
        return self._s

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
        k, = path
        if k == 'sweep':
            self.curr_src.set_sweep(v)
        else:
            raise ValueError(f"Can't set property {path} on curr_src")

    def _probe_set(self, path, v):
        k, = path
        setattr(self.timebase, k, v)

    def _trigger_to_pulse(self, trigs):
        return sum([[v, v + self._s['timing']['trigger_width']] for v in trigs],[])

    def snap_params(self):
        p = {}
        chs = constants.wavemeter.channels
        freqs = self.wavemeter.frequency(chs.values())
        p['lasers'] = {ch + ' freq': v for ch, v in zip(chs, freqs)}
        return p

    @staticmethod
    def _create_figures(specs:dict={}, grid_specs:dict={}):
        figs = {}
        for fig, spec in specs.items():
            if fig in grid_specs:
                grid_spec = grid_specs[fig]
            else:
                grid_spec = [max([el[1] for el in spec]) + 1]
            f, _ = plt.subplots(*grid_spec)
            f.set_tight_layout(True)
            figs[fig] = {'fig': f, 'spec': spec}
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
            kwargs = opt[0] if len(opt) > 0 else {}
            fun = opt[1] if len(opt) > 1 else None
            if fun is None:
                axs[pos].plot(*data[id].xy, **kwargs)
            else:
                fun(axs[pos], data[id], kwargs)
        # axs[1].set_xbound([-0.1e-3, 0.2e-3])
        for ax in axs:
            ax.legend(loc='best')
        fig.canvas.draw()
        fig.canvas.flush_events()

    def save(self, dir=None, comment=None):
        dir = dir if dir is not None else self._args.save
        comment = comment if comment is not None else self._args.comment
        if dir:
            savepath = Path("data/" + dir.strip("/\\") + '/' + "M"
                + datetime.now().strftime("%y%m%d_%H%M%S") + comment + ".pickle")
            savepath.parent.mkdir(exist_ok=True, parents=True)
            with savepath.open("wb") as f:
                pickle.dump(self.result, f)

    def export_settings(self, filename='exported'):
        stngs.save(self.result.settings, "settings/" + filename + '.json')

    def run(self, scan:dict[list]=None, plots:dict={}, grid_specs:dict={}):
        self._init_devices()

        self.result = DataList()
        if scan is not None:
            scan_list = Core._zip_scan(scan)
            self.result.scan = scan
        else:
            scan_list = [{}]
        self.result.settings = self._s.copy()
        self.result.params = self.snap_params()
        plt.ion()
        figs = Core._create_figures(plots, grid_specs)
        t = self.daq.space()

        for shot_sett in scan_list:
            entry = {}
            avgs = {k: Average() for k, _
                in zip(constants.daq.labels, range(self.daq.chs_n))}
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
            series_avg = {k: v.value for k, v in avgs.items()}
            entry.update(series_avg)
            self.result.append(entry)
            Core._plot(entry, **figs.get('avg', {}))

def scan_dict(paths: list[str|tuple]):
    scan = {}
    for path in paths:
        if isinstance(path, str):
            path = path.split('/')
        path = tuple(path)
        scan[path] = []
    return scan

parser = argparse.ArgumentParser(description="Program for tweaking experimental sequence"
    , formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("-s", "--save", nargs='?', const="tests", default=None
    , help="Save data to a file in 'data/tests' or in 'data/DIR' if DIR is specified", metavar="DIR(opt)")
parser.add_argument("-c", "--comment", default="", help="Append COMMENT to saved file name")
parser.add_argument("-r", "--repeat", type=int, default=3
    , help="Repeat mesurement (average) N times", metavar='N')
parser.add_argument("-se", "--sensitivity", default=None
    , help="Lock-in sensitivity, formatted as string with unit, e.g '200 uV'", metavar='STR')
parser.add_argument("-p", "--probe", type=float, default=None
    , help="Probe AOM amplitude (in percents)", metavar='AMPLITUDE')
parser.add_argument("-l", "--list", action="store_true", help="List available devices and exit")
parser.add_argument("-a", "--aom", action="store_true", help="Enable AOMs operation and exit")

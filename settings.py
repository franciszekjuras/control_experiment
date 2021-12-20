from labpy import utils
import json
from pathlib import Path

def load(path=None):
    if path:
        with open(path, 'r') as f:
            return json.load(f)
    else:
        return default

def save(settings, path):
        savepath = Path(path)
        savepath.parent.mkdir(exist_ok=True, parents=True)
        with savepath.open("w") as f:
            f.write(utils.json_dumps_compact(settings))

default = {
    'daq': {
        'dev': 'Dev1',
        'channels': 'ai0:5', 'freq':40e3,
        'time': 300e-3, 't0': -100e-3, 'trig': 'PFI2'
    },
    'timing':{
        'dev': 'Arduino',
        'time_unit': 'ms', 'trigger_width': 0.1,
        'triggers': {
            'constZTrig': [-210, 0],
            'daqTrig': [0]
        },
        'pulses': {
            'pumpEn': [-200, 0],
            'probeEn': [0, 300],
        }
    },
    'lockin': {
        'dev': 'Lock-in',
        'settings': {
            'source': 'internal', 'reserve': 'normal',
            'frequency': 5e4, 'phase': -21., 'sensitivity': '1 mV',
            'time_constant': '300 us', 'filter_slope': '24 dB/oct'
        },
        'auxout': {"aom1": 6., "aom2": 6, "pulseAmp": 0.5}
    },
    'current_source': {
        'dev': 'KEITHLEY',
        'sweep': [0, 100e-6]
    },
    'probe_aom': {
        'dev': 'TB3000',
        'amplitude': 30
    }
}
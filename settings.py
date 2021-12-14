def load(file=None):
    return default

default = {
    'daq': {'dev': 'Dev1', 'channels': 'ai0:5', 'freq':40e3, 'time': 300e-3, 't0': -100e-3},
    'timing':{
        'dev': 'Arduino', 'time_unit': 'ms', 'trigger_width': 0.1,
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
            'source': 'internal', 'reserve': 'low noise',
            'frequency': 5e4, 'phase': -21., 'sensitivity': '100 uV',
            'time_constant': '300 us', 'filter_slope': '24 dB/oct'
        },
        'auxout': {"aom1": 6., "aom2": 6, "pulseAmp": 0.5}
    },
    'current_source': {
        'dev': 'KEITHLEY',
        'sweep': [0, 100e-6]
    }
}
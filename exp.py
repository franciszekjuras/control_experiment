import core
import settings
import pyvisa
import numpy as np

args = core.parser.parse_args()
rm = pyvisa.ResourceManager()
core.exec_aux_commands(args, rm)
setts = settings.load('settings')
core.apply_args(setts, args)
meas = core.Core(settings=setts, rm=rm)

scan = None
# scan = core.scan_dict(['probe_aom/amplitude'])
# probe_amp, = scan.values()
# for i in np.linspace(10, 20, 6):
#     probe_amp.append(i)

scan = core.scan_dict(['timing/pulses/pulseZ'])
pulseZ, = scan.values()
for i in np.linspace(0., 0.5, 11):
    pulseZ.append([-1., -0.9 + i])

plots = {
    'avg': [
        ('x', 0, {'label': 'Polarization rotation'}),
        ('probe', 1, {'label': 'Probe amplitude'}), 
        ('mon1', 1, {'label': 'Monitor'})
    ]
}
meas.run(scan=scan, plots=plots)
print(meas.result.params)

c = input("(d)iscard, (s)ave, e(x)port settings, enter to confirm\n:")
if 's' in c or args.save and 'd' not in c:
    meas.save(args.save, args.comment)
if 'x' in c:
    settings.save(meas.result.settings)
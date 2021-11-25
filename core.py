import localpkgs
import pyvisa
import PyDAQmx as dmx
import numpy as np
import matplotlib.pyplot as plt
import time
import sys
import constants
from labpy.arduinopulsegen import ArduinoPulseGen
from labpy.daqmx import Measurement
from labpy.series import Series, from2darray, Average
from labpy.srs import Srs
from labpy.wavemeter import Wavemeter

rm = pyvisa.ResourceManager()

if (len(sys.argv) > 1 and sys.argv[1] in ["--list", "-l"]):
    res = [(str(inst.alias), str(inst.resource_name)) for inst in rm.list_resources_info().values()]
    res.insert(0, ("Alias", "Resource name"))
    for el in res:        
        print(f"{el[0]:>15}  {el[1]}")
    sys.exit()

prepulse_t = 0.
meas_t = 500
daq = Measurement("Dev1", channels="ai0:5", freq=7e3, time=(meas_t/1e3), trig="PFI2", t0=-0/1e3)
pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
pulsegen.time_unit = "ms"
# pulsegen.reset()
pulsegen.xon("pumpEn")
pulsegen.add("pumpEn", (-200, -5))
pulsegen.add("probeEn", (-200, 300))
pulsegen.add("daqTrig", (0, 0.01))
# pulsegen.add("constZ", (0, 20))

lockin = Srs(rm, "Lock-in")
wavemeter = Wavemeter(rm, "Wavemeter")

print(f"Laser frequency: {1e3 * wavemeter.frequency(1):.3f} GHz")

lockin_settings = {
    'source': 'internal', 'reserve': 'low noise',
    'frequency': 5e4, 'phase': -21., 'sensitivity': '2 mV',
    'time_constant': '300 us', 'filter_slope': '24 dB/oct'
}
lockin.setup(lockin_settings)
lockin.auxout(1, 6.)
lockin.auxout(2, 6.)
lockin.auxout(3, 0.5)

plt.ion()
fig, axs = plt.subplots(2, squeeze=False)
axs = fig.axes
avgs = [Average() for _ in range(5)]

for i in range(5):
    daq.start()
    time.sleep(-daq.t0)
    pulsegen.run()
    data = daq.read()
    series = from2darray(data, (daq.t0, daq.time))
    for ax in axs:
        ax.clear()
    axs[0].plot(*series[0].xy)
    axs[0].plot(*series[1].xy)
    axs[1].plot(*series[2].xy)
    axs[1].plot(*series[3].xy)
    axs[1].plot(*series[4].xy)
    for avg, ser in zip(avgs, series):
        avg.add(ser.y)
    fig.canvas.draw()
    fig.canvas.flush_events()

series_avg = [Series(avg.value, series[0].x) for avg in avgs]
fig, axs = plt.subplots(2)
axs[0].plot(*series_avg[0].xy)
axs[0].plot(*series_avg[1].xy)
axs[1].plot(*series_avg[2].xy)
axs[1].plot(*series_avg[3].xy)
axs[1].plot(*series_avg[4].xy)
fig.canvas.draw()
fig.canvas.flush_events()

input("Press enter to exit...")

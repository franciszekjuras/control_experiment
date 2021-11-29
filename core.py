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
from labpy.keithley_cs import KeithleyCS

rm = pyvisa.ResourceManager()

def main():
    if len(sys.argv) > 1:
        list_resources()

    prepulse_t = 0.
    meas_t = 500
    daq = Measurement("Dev1", channels="ai0:6", freq=7e3, time=(meas_t/1e3), trig="PFI2", t0=-0/1e3)

    pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
    pulsegen.time_unit = "ms"
    # pulsegen.reset()
    pulsegen.xon(("pumpDis", "constZ"))
    pulsegen.add("pumpDis", (-200, -5))
    pulsegen.add("probeEn", (0, 300))
    pulsegen.add("daqTrig", (0, 0.01))
    pulsegen.add("constZ", (10, 15, 50, 60, 70, 80))

    lockin = Srs(rm, "Lock-in")
    lockin_settings = {
        'source': 'internal', 'reserve': 'low noise',
        'frequency': 5e4, 'phase': -21., 'sensitivity': '2 mV',
        'time_constant': '300 us', 'filter_slope': '24 dB/oct'
    }
    lockin.setup(lockin_settings)
    lockin.auxout(1, 6.)
    lockin.auxout(2, 6.)
    lockin.auxout(3, 0.5)

    curr_src = KeithleyCS(rm, "KEITHLEY")
    curr_src.set_remote_only()
    curr_src.current = 0.
    curr_src.set_sweep(np.array([0, 50, 100]) * 1e-6)

    wavemeter = Wavemeter(rm, "Wavemeter")
    print(f"Laser frequency: {1e3 * wavemeter.frequency(1):.3f} GHz")

    plt.ion()
    fig, axs = plt.subplots(3)
    axs = fig.axes
    avgs = [Average() for _ in range(daq.chs_n)]
    time.sleep(0.1)

    for i in range(5):
        curr_src.init()
        daq.start()
        time.sleep(-daq.t0)
        pulsegen.run()
        data = daq.read()
        series = from2darray(data, (daq.t0, daq.time))
        for avg, ser in zip(avgs, series):
            avg.add(ser.y)
        for ax in axs:
            ax.clear()
        for i, j in zip((0,0,1,1,1,2), range(daq.chs_n)):
            axs[i].plot(*series[j].xy)
        fig.canvas.draw()
        fig.canvas.flush_events()

    series_avg = [Series(avg.value, series[0].x) for avg in avgs]
    fig, axs = plt.subplots(3)
    for i, j in zip((0,0,1,1,1,2), range(6)):
        axs[i].plot(*series_avg[j].xy)
    fig.canvas.draw()
    fig.canvas.flush_events()

    input("Press enter to exit...")

def list_resources():
    if sys.argv[1] in ["--list", "-l"]:
        res = [(str(inst.alias), str(inst.resource_name)) for inst in rm.list_resources_info().values()]
        res.insert(0, ("Alias", "Resource name"))
        for el in res:
            print(f"{el[0]:>15}  {el[1]}")
    elif sys.argv[1] in ["--aom", "-a"]:
        pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
        pulsegen.xon(("probeEn"))
    sys.exit()

if(__name__ == "__main__"):
    main()
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
from labpy.series import Series, from2darray
from labpy.srs import Srs
from labpy.wavemeter import Wavemeter

rm = pyvisa.ResourceManager()

if (len(sys.argv) > 1 and sys.argv[1] in ["--list", "-l"]):
    res = [(str(inst.alias), str(inst.resource_name)) for inst in rm.list_resources_info().values()]
    res.insert(0, ("Alias", "Resource name"))
    for el in res:        
        print(f"{el[0]:>15}  {el[1]}")
    sys.exit()

pulsegen = ArduinoPulseGen(rm, "Arduino", portmap=constants.arduino.portmap)
pulsegen.time_unit = "ms"
lockin = Srs(rm, "Lock-in")
wavemeter = Wavemeter(rm, "DESKTOP-HPSND6H")

prepulse_t = 2.
meas_t = 300.
pulsegen.xadd("pumpEn", -200, 0)
pulsegen.xadd(("probeEn", "daqTrig", "constZ"), prepulse_t, meas_t + prepulse_t)

lockin_settings = {
    'source': 'internal', 'reserve': 'normal',
    'frequency': 4e4, 'phase': 0, 'sensitivity': '5 mV',
    'time_constant': '1 ms', 'filter_slope': '24 db/oct'
}
lockin.setup(lockin_settings)

daq = Measurement("Dev1", channels="ai0:5", freq=7e4, time=(meas_t/1e3), trig="PFI2")
daq.start()
time.sleep(daq.t0)
pulsegen.run()

data = daq.read()
series = from2darray(data, (daq.t0, daq.time))

fig, axs = plt.subplots(2)
axs[0].plot(*series[0])
axs[0].plot(*series[1])
axs[1].plot(*series[2])
axs[1].plot(*series[3])
axs[1].plot(*series[4])

fig.show()

#inst = rm.open_resource('Arduino', baud_rate=115200, write_termination='\n')
# arduino = rm.open_resource('Arduino', access_mode=4, write_termination='\n', read_termination='\n')
# print("Arduino identification:",arduino.query('*IDN?'))
# print("Arduino time unit:", arduino.query("syst:unit?"))
# arduino.write("outp:off")
# times = range(0,1000,100)
# arduino.write("pulse:reset")
# # arduino.write("pulse:add 6," + ','.join(map(str,times)))
# arduino.write("pulse:add 9," + ','.join(map(str,[0,1])))

# a_in = dmx.Task()
# read = dmx.int32()
# data = numpy.zeros((50,), dtype=numpy.float64)
# a_in.CreateAIVoltageChan("/Dev1/ai0", "", dmx.DAQmx_Val_Cfg_Default, -10., 10., dmx.DAQmx_Val_Volts, None)
# # a_in.SetSampClkRate(1000.13431)
# a_in.CfgSampClkTiming("", 1000.13431, dmx.DAQmx_Val_Rising, dmx.DAQmx_Val_FiniteSamps, 100)
# af = dmx.float64()
# a_in.GetSampClkRate(dmx.byref(af))
# print("Actual sampling rate:", af.value)

# # CreateAIVoltageChan(physicalChannel=str, nameToAssignToChannel=str, terminalConfig=enum, minVal=float, maxVal=float, units=enum, None);
# a_in.CreateAIVoltageChan("/Dev1/ai0", "", dmx.DAQmx_Val_Cfg_Default, -10., 10., dmx.DAQmx_Val_Volts, None)
# # CfgSampClkTiming(source=str, rate=float, activeEdge=enum, sampleMode=enum, sampsPerChan=int);
# a_in.CfgSampClkTiming("", 1000., dmx.DAQmx_Val_Rising, dmx.DAQmx_Val_FiniteSamps, 50)
# a_in.CfgDigEdgeRefTrig("/Dev1/PFI2", dmx.DAQmx_Val_Rising, 2)
# n = dmx.uInt32()
# a_in.GetTaskNumChans(dmx.byref(n))
# # ni = int(n)
# print("Channels in task:", n.value, "type:", type(n.value))
# a_in.StartTask()
# time.sleep(0.1)
# arduino.write("puls:run")
# # ReadAnalogF64(numSampsPerChan=int, timeout=float[sec], fillMode=enum, readArray=numpy.array, arraySizeInSamps=int, sampsPerChanRead=int_p, None);
# a_in.ReadAnalogF64(50,5.0,dmx.DAQmx_Val_GroupByChannel,data,50,dmx.byref(read),None)
# a_in.StopTask()
# print(data)

# data = numpy.zeros((100,), dtype=numpy.float64)
# a_in.CfgSampClkTiming("", 1000.13431, dmx.DAQmx_Val_Rising, dmx.DAQmx_Val_FiniteSamps, 100)
# af = dmx.float64()
# a_in.GetSampClkRate(dmx.byref(af))
# print("Actual sampling rate:", af.value)
# a_in.StartTask()
# time.sleep(0.2)
# arduino.write("puls:run")
# # ReadAnalogF64(numSampsPerChan=int, timeout=float[sec], fillMode=enum, readArray=numpy.array, arraySizeInSamps=int, sampsPerChanRead=int_p, None);
# a_in.ReadAnalogF64(1000,5.0,dmx.DAQmx_Val_GroupByChannel,data,1000,dmx.byref(read),None)
# print(data)

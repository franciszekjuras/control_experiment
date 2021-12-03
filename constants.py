class Struct:
    pass

arduino = Struct()
arduino.portmap = {
    "pulseX": 2,
    "pulseY": 3,
    "pulseZ": 4,
    "constZTrig": 5,
    "daqTrig": 9,
    "pumpEn": 7,
    "probeEn": 8,  
    "extra": 6  
}

lockin = Struct()
lockin.auxout = {
    "aom1": 1,
    "aom2": 2,
    "pulseAmp": 3
}

daq = Struct()
daq.labels = ("x", "y", "mon1", "mon2", "probe")
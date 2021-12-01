class Struct:
    pass

arduino = Struct()
arduino.portmap = {
    "pulseX": 2,
    "pulseY": 3,
    "pulseZ": 4,
    "constZ": 5,
    "daqTrig": 9,
    "pumpDis": 7,
    "probeEn": 8,  
    "extra": 6  
}

daq = Struct()
daq.labels = ("x", "y", "mon1", "mon2", "probe", "sync")
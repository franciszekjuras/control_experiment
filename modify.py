import argparse
import pickle
from model import Model
from labpy.types import DataList

def main(args):    
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    pulses = [x[1] - x[0] for x in data.meta['scan'][('timing','pulses','pulseZ')]]
    data.meta['calibration'] = {}
    data.meta['calibration']['axis'] = 'z'
    data.meta['calibration']['pulses'] = pulses
    data.meta['calibration']['pulseAmp'] = data.meta['settings']['lockin']['auxout']['pulseAmp']
    fn: str = args.file
    fn = fn.removesuffix('.pickle')
    fn += '_mod.pickle'
    with open(fn, "wb") as f:
        pickle.dump(data, f)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for displaying DataList measurement")
    parser.add_argument("file", help="File with data to show")
    args = parser.parse_args()
    main(args)

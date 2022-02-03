import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import argparse
import pickle
from model import Model
from pprint import pprint

def main(args):    
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    data[:] = data[0:1]
    bounds = {'gr': [15., 50.], 'g1': [2., 10.], 'g2': [15., 50.]}
    model = Model(data, verbose=True, bounds=bounds)
    model.process()
    pprint(model.result, sort_dicts=False)
    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for processing measurement results")
    parser.add_argument("file", help="File with data to process")
    args = parser.parse_args()
    main(args)

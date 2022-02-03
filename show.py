import argparse
import pickle
from model import Model
from labpy.types import DataList

def main(args):    
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    print(data)    

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for displaying DataList measurement")
    parser.add_argument("file", help="File with data to show")
    args = parser.parse_args()
    main(args)

import localpkgs
import numpy as np
import pickle
import argparse
import matplotlib.pyplot as plt
from labpy.series import Series

def main(args):
    with open(args.file, "rb") as f:
        data = pickle.load(f)
    print(*data)
    sers = data["data"]
    print(data["params"])
    fig, axs = plt.subplots(2)
    fig.set_tight_layout(True)
    for i, ser in zip((0,0,1,1,1),sers.values()):
        axs[i].plot(*ser.xy)
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Program for processing measurement results")
    parser.add_argument("file")
    args = parser.parse_args()
    main(args)

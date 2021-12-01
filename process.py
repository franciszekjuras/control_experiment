import localpkgs
import numpy as np
import matplotlib.pyplot as plt
from labpy.series import Series, from_npz, from_pickle
import pickle

def main():
    with open("data/test_pickle", "rb") as f:
        data = pickle.load(f)
    print(*data)
    sers = data["data"]
    print(data["params"])
    fig, axs = plt.subplots(3)
    for i, ser in zip((0,0,1,1,1,2),sers.values()):
        axs[i].plot(*ser.xy)
    plt.show()

if __name__ == "__main__":
    main()

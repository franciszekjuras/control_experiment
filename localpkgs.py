from os.path import dirname, join, realpath
from os import walk
import sys
parent_dir =dirname(dirname(realpath(__file__)))
prll_dir_names = next(walk(parent_dir))[1]
prll_dirs = [join(parent_dir, name) for name in prll_dir_names]
# print(prll_dirs)
for dir in prll_dirs:
    sys.path.insert(1, dir)
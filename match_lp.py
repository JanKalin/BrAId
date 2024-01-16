##############################################################################
# Imports
##############################################################################

import argparse
from datetime import timedelta
import platform

import numpy as np
import pandas as pd

from swm.filesys import FS
from swm.vehicle import Vehicle

##############################################################################
#%% Read arguments
##############################################################################

parser = argparse.ArgumentParser(description="Match vehicles from XMLs based on the <lp></lp> tag and write them to a file", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--data_root", help="Data root directory", default=r'D:\siwim\sites' if platform.system() == 'Windows' else '/mnt/siwim/sites/cestel')
parser.add_argument("--left", help="Site directory 1", default='Moerdijk_PK')
parser.add_argument("--right", help="Site directory 2", default='Klaverpolder_NL')
parser.add_argument("--extdir", help="Extended data directory", default='ext')
parser.add_argument("--glob", help="Glob for files", default='????-??-??.xml')
parser.add_argument("--savehdf5", help="Save DataFrame of matches to a hdf5 file")
parser.add_argument("--savexml", help="Save left and right XMLs of matched vehicles", nargs=2)
parser.add_argument("--maxDt", help="Maximum time difference in seconds", type=int, default=15)
parser.add_argument("--maxDv", help="Maximum speed difference in km/h", type=float, default=10)
parser.add_argument("--groups", help="Use only these groups", type=int, nargs='+')

try:
    __IPYTHON__
    args = parser.parse_args("--savexml left_all.xml right_all.xml".split())
except:
    args = parser.parse_args()
    
#%% Load data

fs = FS(data_root=args.data_root, site=args.left, module=args.extdir)
left_files = fs.multiglob(args.glob)
left = Vehicle.from_txt_files(left_files)

fs.site = args.right
right_files = fs.multiglob(args.glob)
right = Vehicle.from_txt_files(right_files)

#%% Rearrange data and match non-duplicated vehicles

anpr_left = {x.anpr_lp: x for x in left if x.anpr_lp}
anpr_right = {x.anpr_lp: x for x in right if x.anpr_lp}

count_left = {}
for vehicle in left:
    try:
        count_left[vehicle.id()] += 1
    except:
        count_left[vehicle.id()] = 1

count_right = {}
for vehicle in right:
    try:
        count_right[vehicle.id()] += 1
    except:
        count_right[vehicle.id()] = 1


matched = []
for (lp, l) in anpr_left.items():
    try:
        r = anpr_right[lp]
        if count_left[l.id()] == 1 and count_right[r.id()] == 1:
            if r.timestamp < l.timestamp or r.timestamp > l.timestamp + timedelta(seconds=args.maxDt): continue
            if np.abs(r.v() - l.v())*3.6 > args.maxDv: continue
            matched.append([lp, l, r])
    except:
        pass

#%% Save data

if args.savehdf5:
    df = pd.DataFrame([[x[0], x[1].timestamp, x[1].lane, x[2].timestamp, x[2].lane] for x in matched],
                      columns=['lp', 'tsl', 'll', 'tsr', 'lr'])
    df.to_hdf(args.save, 'matches')
    
if args.savexml:
    with open(args.savexml[0], 'w') as f:
        f.writelines("\n".join(Vehicle.xml_lines([x[1] for x in matched])))
    with open(args.savexml[1], 'w') as f:
        f.writelines("\n".join(Vehicle.xml_lines([x[2] for x in matched])))

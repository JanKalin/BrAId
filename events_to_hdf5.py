##############################################################################
#%% Imports
##############################################################################

import os
import sys
try:
    __IPYTHON__
except:
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    addpath = os.path.join(os.path.split(os.path.dirname(SCRIPT_DIR))[0], "siwim-pi")
    sys.path.append(addpath)

import argparse
import platform

import numpy as np
import pandas as pd

from swm.filesys import FS
from swm.factory import read_file
from swm.utils import Progress

##############################################################################
#%% Read arguments
##############################################################################

parser = argparse.ArgumentParser(description="Compare SiWIM and HBM sensors", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)

parser.add_argument("--data_root", help="Data root directory", default=r'D:\siwim\sites' if platform.system() == 'Windows' else '/mnt/siwim/sites/cestel')
parser.add_argument("--site", help="Site directory", default='Crnuce')
parser.add_argument("--rpindex", help="Replay index", type=int, default=11)
parser.add_argument("--module", help="Output module", default='cf')
parser.add_argument("--glob", help="Glob for files", default='*.event')
parser.add_argument("--head", help="Average this many seconds at the beginning", type=float, default=0.5)
parser.add_argument("--tail", help="Average this many seconds at the end", type=float, default=0.5)
parser.add_argument("--mingvw", help="Minimal GVW in tons to include", type=float, default=5)

try:
    __IPYTHON__
    args = parser.parse_args("--glob 2022-07-01*.event".split())
except:
    args = parser.parse_args()

#%% Get a list of files

fs = FS(args.data_root, args.site, args.rpindex, args.module)
filenames = fs.multiglob(args.glob, recurse=True)

#%% Process files

chs = [('W_SIWIM_N1', 'S1'), ('W_HBM_N1', 'H1'), ('W_HBM_N2', 'H2'), ('W_SIWIM_DEW', 'SD'), ('W_SIWIM_N2', 'S2')]
lines = []
MP = 0
light = 0

try:
    __IPYTHON__
except:
    progress = Progress("Processing {} events... {{}}% ".format(len(filenames)), len(filenames))
    
for filename in filenames:
    event = read_file(fs.fullname(filename))
    try:
        __IPYTHON__
    except:
        progress.step()
    
    # Eliminate MPs, low weights and possibly wrong configurations
    if len(event.weighed_vehicles) != 1:
        MP += 1
        continue
    vehicle = event.weighed_vehicles[0]
    if vehicle.gvw() < args.mingvw*9.81:
        light += 1
        continue
    
    # Process
    line = [event.acqdata.sample_timestamp(), vehicle.flags, vehicle.lane,
            vehicle.v(), len(vehicle.axle), vehicle.subclass, vehicle.groups,
            vehicle.gvw()/9.81, vehicle.axconfig]
    error = False
    for ch in range(len(event.acqdata.a)):
        if event.acqdata.a[ch].shortdescription not in [x for x,_ in chs]:
            continue
        else:
            data = event.acqdata.a[ch]
        if data.all_ok(need_offset=True):
            offset = data.offset(0)
            line += [np.max(data.data) - offset,
                     data.calc_offset(samples=args.tail*event.acqdata.sampling_rate, tail=True)
                     - data.calc_offset(samples=args.head*event.acqdata.sampling_rate)]
            line.append(100*line[-1]/line[-2])
        else:
            error = True
    if not error:
        lines.append(line)

df = pd.DataFrame(lines)
columns = ['ts', 'flags', 'lane', 'v', 'naxles', 'cls', 'axgrps', 'gvw', 'axconfig']
for _, ch in chs:
    columns += [f"{ch}_{x}" for x in ['max', 'diff', 'perc']]
chs = [x for _, x in chs]
df.columns = columns
df.set_index('ts', inplace=True)

df.to_hdf(f"{os.path.splitext(fs.fullname(args.glob.replace('*', 'X')))[0]}.hdf5", 'data')

print(f"Skipped {MP} MP events and {light} events with light vehicles")

### Import stuff

import argparse
import datetime
import getpass
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm import vehicle

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Compare axle distances from two NSWDs", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--siwim_site", help="SiWIM site", default=r"E:\sites\original\AC_Sentvid_2012_2")
parser.add_argument("--nswd", help="NSWD name", default="2014-03-05.nswd")

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

#%% Load vehicle to event map

with open(os.path.join(args.data_dir, 'vehicle2event.json'), 'r') as f:
    vehicle2event = json.load(f)
vehicle2event = {datetime.datetime.fromtimestamp(float(x)): datetime.datetime.fromtimestamp(y) for (x,y) in vehicle2event.items()}

#%% Find first and last timestamps

vehicles = {}
allrps = ['rp41', 'rp42']

for rp in allrps:
    print("Reading", rp)
    all_vehicles = vehicle.Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', args.nswd))
    vehicles[rp] = {x.timestamp: x for x in all_vehicles if not x.lane}
    del(all_vehicles)
    
#%% Get intersection of timestamps

rps = allrps

for rp in rps:
    tss = {x for x in vehicles[rp]}
    try:
        all_tss &= tss # noqa
    except:
        all_tss = tss

all_tss = sorted(list(all_tss))

#%% Now compare the data

def compare(a, b):
    return (a > b) - (a < b)

count = {True: 0, False: 0}
timestamps = []

for ts in all_tss:

    cmp = compare(len(vehicles[rps[0]][ts].axle_distance), len(vehicles[rps[1]][ts].axle_distance))
    if not cmp:
        try:
            eq = (vehicles[rps[0]][ts].axle_distance == vehicles[rps[1]][ts].axle_distance).all()
        except AttributeError:
            eq = vehicles[rps[0]][ts].axle_distance == vehicles[rps[1]][ts].axle_distance
    else:
        eq = False
    count[eq] += 1
    if not eq:
        print(f"{vehicles[rps[0]][ts].timestamp}\t{vehicles[rps[0]][ts].v()}\t{vehicles[rps[1]][ts].timestamp}\t{vehicles[rps[1]][ts].v()}")

print(count)
print(timestamps)
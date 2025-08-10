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

from swm import vehicle, utils
from locallib import load_metadata

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Generate a list of vehicles and some info for training ML to detect axles from signals", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--siwim_site", help="SiWIM site", default=r"S:\sites\original\AC_Sentvid_2012_2")

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data --photo e:\yolo_photos --noseen".split())
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data --photo b:\yolo_photos --noseen --findmany data/missed_ids.txt data/missed_batch_idx.txt".split())
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data".split())
        args = parser.parse_args(r"".split())
    else:
        raise Exception
except:
    args = parser.parse_args()


#%% Load data first and make datetime from timestamps
print(f"Loading {os.path.join(args.data_dir, 'recognized_vehicles.json')}, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "recognized_vehicles.json")) as f:
    rvs_loaded = json.load(f)
print("done.")

ts2rv = {}
for rv in rvs_loaded:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    ts2rv[rv['vehicle_timestamp']] = rv
    
#%% Load vehicle to event map

with open(os.path.join(args.data_dir, 'vehicle2event.json'), 'r') as f:
    vehicle2event = json.load(f)
vehicle2event = {datetime.datetime.fromtimestamp(float(x)): datetime.datetime.fromtimestamp(y) for (x,y) in vehicle2event.items()}

#%% Find first and last timestamps

ts_min = min(x['vehicle_timestamp'] for x in rvs_loaded)
ts_max = max(x['vehicle_timestamp'] for x in rvs_loaded)

#%% Load NSWDs for all stages

vehicles = {}
rps = ['rp01', 'rp03']
for rp in rps:
    print("Reading", rp)
    all_vehicles = vehicle.Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', 'braid.nswd'))
    vehicles[rp] = {x.timestamp: {'axle_groups': x.groups2str(), 'flags': f"0x{x.flags:08X}", 'axle_distance': list(x.axle_distance)} for x in all_vehicles if x.timestamp >= ts_min and x.timestamp <= ts_max}
    del(all_vehicles)
    
#%% Get intersection of timestamps

for rp in rps:
    tss = {x for x in vehicles[rp]}
    try:
        all_tss &= tss # noqa
    except:
        all_tss = tss

all_tss = sorted(list(all_tss))

#%% Find just the vehicles that have been seen and have the correct axle groups

metadatafile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")

tss = []
counter = [0, 0, 0]
for ts in all_tss:
    try:
        md = load_metadata(ts2rv[ts], metadatafile)
        counter[0] += 1
    except:
        pass
    if md['seen_by'] is not None:
        counter[1] += 1
        try:
            md['axle_groups']
        except:
            tss.append(ts)
            counter[2] += 1
        
#%% Now collect and save the data

def compare(a, b):
    return (a > b) - (a < b)

itemss = {'nop': [], 'mov': [], 'add': [], 'del': []}

for ts in tss:
    item = {'ts': ts.timestamp(), 'ts_str': utils.datetime2ts(ts),
            'ets': vehicle2event[ts].timestamp(), 'ets_str': utils.datetime2ts(vehicle2event[ts])}
    cmp = compare(len(vehicles['rp01'][ts]['axle_distance']), len(vehicles['rp03'][ts]['axle_distance']))
    if not cmp:
        try:
            eq = (vehicles['rp01'][ts]['axle_distance'] == vehicles['rp03'][ts]['axle_distance']).all()
        except AttributeError:
            eq = vehicles['rp01'][ts]['axle_distance'] == vehicles['rp03'][ts]['axle_distance']
        key = 'nop' if eq else 'mov'
    else:
        key = 'add' if cmp < 0 else 'del'
    item['v1'] = vehicles['rp01'][ts]
    item['v2'] = vehicles['rp03'][ts]
    itemss[key].append(item)

for key, items in itemss.items():
    with open(os.path.join(SCRIPT_DIR, 'data', f"vehicles_for_axles-{key}.json"), 'w') as f:
        json.dump(items, f, indent=2)
    print(f"{key}: {len(items)}")

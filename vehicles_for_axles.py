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
    
ts_min = min(x['vehicle_timestamp'] for x in rvs_loaded)
ts_max = max(x['vehicle_timestamp'] for x in rvs_loaded)

#%% Load vehicle to event map

with open(os.path.join(args.data_dir, 'vehicle2event.json'), 'r') as f:
    vehicle2event = json.load(f)
vehicle2event = {datetime.datetime.fromtimestamp(float(x)): datetime.datetime.fromtimestamp(y) for (x,y) in vehicle2event.items()}

#%% Find first and last timestamps

vehicles = {}
allrps = ['rp01', 'rp03']

for rp in allrps:
    print("Reading", rp)
    all_vehicles = vehicle.Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', 'braid.nswd'))
    vehicles[rp] = {x.timestamp: x for x in all_vehicles if x.timestamp >= ts_min and x.timestamp <= ts_max and not x.lane}
    del(all_vehicles)
    
#%% Get intersection of timestamps

rps = ('rp01', 'rp03')

for rp in rps:
    tss = {x for x in vehicles[rp]}
    try:
        all_tss &= tss # noqa
    except:
        all_tss = tss

all_tss = sorted(list(all_tss))

#%% Collect metadata

metadatafile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")

metadata = {}
counter = {'total': len(all_tss), 'has_metadata': 0, 'unseen': 0, 'seen': 0, 'match': 0, 'nonmatch': 0, 'raised': 0, 'nonraised': 0}
for ts in all_tss:
    try:
        data = load_metadata(ts2rv[ts], metadatafile)
        counter['has_metadata'] += 1
    except KeyError:
        continue
    if data['seen_by'] is None:
        counter['unseen'] += 1
    else:
        metadata[ts] = {}
        counter['seen'] += 1
        try:
            data['axle_groups']
            metadata[ts].update({'match': False, 'axle_groups': data['axle_groups']})
            counter['nonmatch'] += 1
            try:
                metadata[ts]['raised_axles'] = data['raised_axles']
                counter['raised'] += 1
            except:
                counter['nonraised'] += 1
        except:
            metadata[ts]['match'] = True
            counter['match'] += 1

print(counter)
        
#%% Now collect the data

def compare(a, b):
    return (a > b) - (a < b)

statuses = ['nop', 'mov', 'add', 'del']
count = {x: 0 for x in statuses}
items = []
etss = {}

for ts, data in sorted(metadata.items()):
    item = {'ts': ts.timestamp(), 'ts_str': utils.datetime2ts(ts),
            'ets': vehicle2event[ts].timestamp(), 'ets_str': utils.datetime2ts(vehicle2event[ts])}
    item.update(data)
    item['vehicle'] = {x: {'axle_groups': vehicles[rp][ts].groups2str(),
                            'axle_distance': list(vehicles[rp][ts].axle_distance),
                            'axle_weight': [x.cw for x in vehicles[rp][ts].axle],
                            'rcn': vehicles[rp][ts].vehiclereconstructedflag(),
                            'fix': vehicles[rp][ts].qafixedflag(),
                            'man': vehicles[rp][ts].manuallychangedflags()}
                        for (x, rp) in zip(['weighed', 'manual'], rps)}

    cmp = compare(len(vehicles[rps[0]][ts].axle_distance), len(vehicles[rps[1]][ts].axle_distance))
    if not cmp:
        try:
            eq = (vehicles[rps[0]][ts].axle_distance == vehicles[rps[1]][ts].axle_distance).all()
        except AttributeError:
            eq = vehicles[rps[0]][ts].axle_distance == vehicles[rps[1]][ts].axle_distance
        distance_op = 'nop' if eq else 'mov'
    else:
        distance_op = 'add' if cmp < 0 else 'del'
    item['vehicle']['manual']['distance_op'] = distance_op
    if distance_op in ['nop', 'mov']:
        item['vehicle']['manual']['weight_op'] = 'nop' if [x.cw for x in vehicles[rps[0]][ts].axle] == [x.cw for x in vehicles[rps[1]][ts].axle] else 'chg'
    else:
        item['vehicle']['manual']['weight_op'] = 'undef'
    items.append(item)
    count[distance_op] += 1

    try:
        etss[vehicle2event[ts].timestamp()] += 1
    except:
        etss[vehicle2event[ts].timestamp()] = 1

multiple = sum([x > 1 for x in etss.values()])
print(f"total: {sum([x for x in count.values()])}, {count}, multiple: {multiple}")

#%% Remove multiple vehicles in event and save

with open(os.path.join(SCRIPT_DIR, 'data', "vehicles_for_axles.json"), 'w') as f:
    json.dump([x for x in items if etss[x['ets']] == 1], f, indent=2)

### Import stuff

import argparse
import datetime
import getpass
import gc
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm.vehicle import Vehicle
from swm.utils import datetime2ts, Progress
from locallib import load_metadata

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Generate a list of vehicles and some info for training ML to detect axles from signals", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--siwim_site", help="SiWIM site", default=r"E:\sites\original\AC_Sentvid_2012_2")
parser.add_argument("--src", help="Input file", default="braid.nswd")
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--dst", help="Output file", default="nn_vehicles.json")
parser.add_argument("--rps", help="Replays", nargs=2, default=['rp01', 'rp03'])

try:
    __IPYTHON__ # noqa
    if True and getpass.getuser() == 'jank':
        args = parser.parse_args(r"--src four.nswd --dst nn_vehicles-test.json".split())
        args = parser.parse_args()
    else:
        raise Exception
except:
    args = parser.parse_args()


#%% Load recognized_vehicles and determine min and max timestamps

print("Loading recognized_vehicles.json")
sys.stdout.flush()
with open(os.path.join(args.data_dir, "recognized_vehicles.json")) as f:
    rvs_loaded = json.load(f)

ts2rv = {}
for rv in rvs_loaded:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    ts2rv[rv['vehicle_timestamp']] = rv
    
ts_min = min(x['vehicle_timestamp'] for x in rvs_loaded)
ts_max = max(x['vehicle_timestamp'] for x in rvs_loaded)

#%% Load NSWDs and construct vehicle2event

nswds = {}
vehicle2event = {}

for rp in args.rps:
    print("Loading", rp)
    nswd = Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', args.src))
    nswds[rp] = {x.timestamp: x for x in nswd if x.timestamp >= ts_min and x.timestamp <= ts_max and not x.lane}
    vehicle2event.update({x.timestamp: x.event_timestamp for x in nswds[rp].values()})
    del nswd
gc.collect()
    
#%% Get intersection of timestamps and remove multiple vehicles

for rp in args.rps:
    tss = {x for x in nswds[rp]}
    etss = {}
    for ts in tss:
        try:
            etss[vehicle2event[ts]] += 1
        except:
            etss[vehicle2event[ts]] = 1
    tss = {x for x in sorted(tss) if etss[vehicle2event[x]] == 1}
    try:
        all_tss &= tss # noqa
    except NameError:
        all_tss = tss

tss = list(sorted(all_tss))

#%% Collect metadata

print("Loading metadata.hdf5")
metadatafile = os.path.join(SCRIPT_DIR, "data", "metadata.hdf5")

metadata = {}
counter = {'total': len(tss), 'has_metadata': 0, 'unseen': 0, 'seen': 0, 'photo_match': 0, 'photo_non_match': 0, 'raised': 0, 'nonraised': 0}

progress = Progress("Processing {} items from metadata... {{}}% ".format(len(tss)), len(tss))
for ts in tss:
    progress.step()
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
            metadata[ts].update({'photo_match': False, 'axle_groups': data['axle_groups']})
            counter['photo_non_match'] += 1
            try:
                metadata[ts]['raised_axles'] = data['raised_axles']
                counter['raised'] += 1
            except:
                metadata[ts]['raised_axles'] = ""
                counter['nonraised'] += 1
        except:
            metadata[ts]['photo_match'] = True
            counter['photo_match'] += 1

print("Metadata stats:", counter)
        
#%% Now collect the data

def compare(a, b):
    return (a > b) - (a < b)

opcount = {x: 0 for x in ['nop', 'mov', 'add', 'del']}
items = []

progress = Progress("Processing {} items in memory... {{}}% ".format(len(metadata)), len(metadata))
for ts, data in sorted(metadata.items()):
    progress.step()
    
    # Create and copy basic data
    item = {'ts': ts.timestamp(), 'ts_str': datetime2ts(ts),
            'ets': vehicle2event[ts].timestamp(), 'ets_str': datetime2ts(vehicle2event[ts])}
    item.update(data)
    item['vehicle'] = {x: {'axle_groups': nswds[rp][ts].groups2str(),
                           'axle_distance': list(nswds[rp][ts].axle_distance),
                           'axle_weight': [x.cw for x in nswds[rp][ts].axle],
                           'rcn': nswds[rp][ts].vehiclereconstructedflag(),
                           'fix': nswds[rp][ts].qafixedflag(),
                           'man': nswds[rp][ts].manuallychangedflags()}
                       for (x, rp) in zip(['weighed', 'final'], args.rps)}

    # Get distance op
    cmp = compare(len(nswds[args.rps[0]][ts].axle_distance), len(nswds[args.rps[1]][ts].axle_distance))
    if not cmp:
        try:
            eq = (nswds[args.rps[0]][ts].axle_distance == nswds[args.rps[1]][ts].axle_distance).all()
        except AttributeError:
            eq = nswds[args.rps[0]][ts].axle_distance == nswds[args.rps[1]][ts].axle_distance
        distance_op = 'nop' if eq else 'mov'
    else:
        distance_op = 'add' if cmp < 0 else 'del'
    item['vehicle']['final']['distance_op'] = distance_op
    opcount[distance_op] += 1

    # Perhaps get weight op
    if distance_op in ['nop', 'mov']:
        item['vehicle']['final']['weight_op'] = 'nop' if [x.cw for x in nswds[args.rps[0]][ts].axle] == [x.cw for x in nswds[args.rps[1]][ts].axle] else 'chg'
    else:
        item['vehicle']['final']['weight_op'] = 'undef'
    
    # Done        
    items.append(item)
    
print(f"total: {sum([x for x in opcount.values()])}, {opcount}")

#%% Save data

with open(os.path.join(SCRIPT_DIR, 'data', args.dst), 'w') as f:
    json.dump(items, f, indent=2)

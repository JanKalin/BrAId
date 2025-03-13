### Import stuff

import argparse
import datetime
import getpass
import json
import os
import sys

import pandas as pd

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), 'siwim-pi'))
sys.path.append(os.path.join(os.path.dirname(SCRIPT_DIR), '..', 'siwim-pi'))

from swm import vehicle

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

#%% Parse args and do simple initialisations

parser = argparse.ArgumentParser(description="Summarise SiWIM changes", fromfile_prefix_chars='@', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
parser.add_argument("--data_dir", help="Data directory", default=os.path.join(SCRIPT_DIR, 'data'))
parser.add_argument("--siwim_site", help="SiWIM site", default=r"S:\sites\original\AC_Sentvid_2012_2")

try:
    __IPYTHON__
    if True and getpass.getuser() == 'jank':
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data --photo e:\yolo_photos --noseen".split())
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data --photo b:\yolo_photos --noseen --findmany data/missed_ids.txt data/missed_batch_idx.txt".split())
        # args = parser.parse_args(r"--metadata n:\disk_600_konstrukcije\JanK\braid_photo\data".split())
        args = parser.parse_args(r"".split())
    else:
        raise Exception
except:
    args = parser.parse_args()

# Force no threads
#args.threaded = False

#%% Load data first and make datetime from timestamps
print(f"Loading {os.path.join(args.data_dir, 'recognized_vehicles.json')}, ", end='')
sys.stdout.flush()
with open(os.path.join(args.data_dir, "recognized_vehicles.json")) as f:
    rvs_loaded = json.load(f)
print("done.")

ts2id = {}    
for rv in rvs_loaded:
    rv['vehicle_timestamp'] = datetime.datetime.fromtimestamp(rv['vehicle_timestamp'])
    rv['photo_timestamp'] = datetime.datetime.fromtimestamp(rv['photo_timestamp'])
    ts2id[rv['vehicle_timestamp']] = rv['photo_id']

#%% Find first and last timestamps

ts_min = min(x['vehicle_timestamp'] for x in rvs_loaded)
ts_max = max(x['vehicle_timestamp'] for x in rvs_loaded)

#%% Load NSWDs for all 3 stages

vehicles = {}
for rp in ['rp01', 'rp02', 'rp03']:
    print("Reading", rp)
    all_vehicles = vehicle.Vehicle.from_txt_files(os.path.join(args.siwim_site, rp, 'cf', 'braid.nswd'))
    vehicles[rp] = [(x.timestamp, x.groups2str(), x.flags) for x in all_vehicles if x.timestamp >= ts_min and x.timestamp <= ts_max]
    
#%% Map timestamp to vehicle

ts2vehicle = {}
for rp in ['rp01', 'rp02', 'rp03']:
    ts2vehicle[rp] = {x[0]: x for x in vehicles[rp]}

#%% Get all timestamps and construct a PD datafame

all_tss = set()
for rp in ['rp01', 'rp02', 'rp03']:
    tss = {x[0] for x in vehicles[rp]}
    all_tss = all_tss | tss

all_tss = sorted(list(all_tss))

df = pd.DataFrame(index=all_tss, columns=['id', 'rp01_grp', 'rp02_grp', 'rp03_grp', 'rp02_fixed', 'rp03_fixed'])
df[['id', 'rp01_grp', 'rp02_grp', 'rp03_grp']] = df[['id', 'rp01_grp', 'rp02_grp', 'rp03_grp']].astype('str')
df[['rp02_fixed', 'rp03_fixed']] = df[['rp02_fixed', 'rp03_fixed']].astype('bool')
df[['rp02_fixed', 'rp03_fixed']] = False

#%% Now fill the dataframe

for ts in all_tss:
    try:
        df.loc[ts, 'id'] = ts2id[ts]
    except:
        pass
    try:
        df.loc[ts, 'rp01_grp'] = ts2vehicle['rp01'][ts][1]
    except:
        pass
    try:
        df.loc[ts, 'rp02_grp'] = ts2vehicle['rp02'][ts][1]
    except:
        pass
    try:
        df.loc[ts, 'rp03_grp'] = ts2vehicle['rp03'][ts][1]
    except:
        pass
    try:
        df.loc[ts, 'rp02_fixed'] = (ts2vehicle['rp02'][ts][2] & vehicle.Flag_QA_Fixed) == vehicle.Flag_QA_Fixed
    except:
        pass
    try:
        df.loc[ts, 'rp03_fixed'] = (ts2vehicle['rp03'][ts][2] & vehicle.Flag_QA_Fixed) == vehicle.Flag_QA_Fixed
    except:
        pass
    
#%% And save dataframe to HDF5

df.to_hdf("grp_and_fixed.hdf5", "data")
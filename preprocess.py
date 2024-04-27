# -*- coding: utf-8 -*-
"""
Created on Wed Feb 14 16:00:50 2024

@author: jank

Removes all non-lane 1 vehicles and changes 'bus' to 'truck' for all "busses"
with groups other than 11, 12, 111 and 121.
"""

#%% Import stuff

import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(SCRIPT_DIR)), 'siwim-pi'))

from swm.vehicle import Vehicle
from swm.utils import Progress

from locallib import save_metadata

#%% Load all files

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles-ORIGINAL.json")) as f:
    rvs = json.load(f)

vehicles = Vehicle.from_txt_files(os.path.join(SCRIPT_DIR, "data", "*.nswd"), glob=True)

#%%

lane1 = set([x.timestamp.timestamp() for x in vehicles if not x.lane])
v2e = {x.timestamp.timestamp(): x.event_timestamp.timestamp() for x in vehicles if not x.lane}


#%% Now change busses for trucks

datafile = os.path.join(SCRIPT_DIR, 'data', 'metadata.hdf5')

count = 0
noprogress = False
rvs_lane1 = []

if not noprogress: progress = Progress("Processing {} photos... {{}}% ".format(len(rvs)), len(rvs))
for rv in rvs:
    if not noprogress: progress.step()
    if not rv['vehicle_timestamp'] in lane1:
        continue
    rvs_lane1.append(rv)
    if rv['axle_groups'] in ['11', '12', '111', '121']:
        continue
    metadata = {'seen_by': None, 'changed_by': None}
    changed = 0
    for segment in rv['segments']:
        if segment['type'] == 'bus':
            try:
                metadata['type'][segment['box']['color']] = 'truck'
            except:
                metadata['type'] = {segment['box']['color']: 'truck'}
            changed += 1
    if changed:
        count += changed
        save_metadata(rv, metadata, datafile)

print("Found", count, "vehicles bus->truck")

#%% Save only lane 1 vehicles and v2e

with open(os.path.join(SCRIPT_DIR, 'data', "recognized_vehicles.json"), 'w') as f:
    json.dump(rvs_lane1, f, indent=2)

with open(os.path.join(SCRIPT_DIR, 'data', "vehicle2event.json"), 'w') as f:
    json.dump(v2e, f, indent=2)
